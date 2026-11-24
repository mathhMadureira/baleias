"""Chefe OpenBot no testnet (H59, lab/PROTOCOLO_LAB.md): executa na conta de TESTE de futuros da Binance as posições que o chefe decidiu.

Uso:  python3 -I testnet.py            → uma rodada: conferir a corretora, mover stops, guarda do dia, seguir a decisão, gravar o estado
      python3 -I testnet.py --conta    → só mostra saldo, posições e ordens da conta de teste (não muda nada)
Regras (H59): toda entrada sai com STOP_MARKET reduce-only guardado na corretora; stop inicial = o do Robô Claude (2 × amplitude de 1 h,
1,5–4%); stop móvel sobe a cada rodada (pico ≥ +0,5% → entrada ± 70% do pico); posição fora da lista da decisão fecha; 24 h; guarda do dia
(H54) e meta de US$ 12 (H57); carteira de US$ 10, nocional = 2,5 × carteira realizada, 10×. Resultado = realizedPnl − commission da corretora.
Segurança: só o testnet. Para se BINANCE_REAL=1 ou se o endereço não for o do testnet. A chave vem do ~/baleias/.env e nunca é impressa.
Grava SÓ dados/robo_openbot_testnet.json no ramo `estado`.
"""
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/home/servidor-de-producao/baleias")
sys.path.insert(0, str(REPO))
from executor.binance_futuros import ALIAS, TESTNET, ErroFuturos, Futuros  # noqa: E402
from executor import guarda_dia as GD  # noqa: E402
from executor.robo_claude_nuvem import parametros, stop_da_moeda, tamanho  # noqa: E402
from executor import stop_movel as SM  # noqa: E402

AQUI = Path(__file__).resolve().parent
EST = AQUI / "estado"
LOCAL = AQUI / "robo_openbot_testnet.json"          # fonte da verdade do estado (a máquina pode dormir; o ramo recebe uma cópia)
ARQ = "dados/robo_openbot_testnet.json"
CAPITAL, PISO, ALAV, FATOR, MAX_POS, MAX_NOC = 10.0, 5.0, 10, 2.5, 8, 1.5   # R2: 8 posições
ARMA, GUARDA, VALIDADE_S, MAX_HORAS = 0.005, 0.70, 75 * 60, 24
AUTOR = ["-c", "user.name=chefe-openbot", "-c", "user.email=chefe-openbot@users.noreply.github.com"]
TRAILER = "Co-authored-by: OpenBot <335604065+openbotgit[bot]@users.noreply.github.com>"


# ---------------- segurança e conexão ----------------
def conectar():
    env_real = any(l.strip().replace(" ", "") == "BINANCE_REAL=1" for l in (REPO / ".env").read_text().splitlines())
    if os.environ.get("BINANCE_REAL") == "1" or env_real:
        raise SystemExit("PARE: BINANCE_REAL=1 está ligado. Este robô só opera a conta de TESTE. Nada foi feito.")
    if os.environ.get("BINANCE_FUT_BASE"):
        raise SystemExit("PARE: BINANCE_FUT_BASE está definido; o endereço tem de ser o do testnet. Nada foi feito.")
    f = Futuros.do_env()
    if f.base != TESTNET:
        raise SystemExit(f"PARE: endereço {f.base} não é o do testnet. Nada foi feito.")
    return f


def sym(par):
    return ALIAS.get(par, par)


def anotar(e, texto):
    e["eventos"] = ([{"t": time.time(), "texto": "⚓ " + texto}] + e.get("eventos", []))[:100]
    print(time.strftime("%H:%M:%S", time.gmtime()), "UTC", texto, flush=True)


def carregar():
    if LOCAL.exists():
        try:
            return json.loads(LOCAL.read_text())
        except ValueError:                           # auditoria 19/11: arquivo vazio/cortado por desligamento → cópia do ramo estado
            copia = subprocess.run(["git", "-C", str(EST), "show", f"origin/estado:{ARQ}"], capture_output=True, text=True, timeout=60).stdout
            os.replace(LOCAL, LOCAL.with_name(f"{LOCAL.name}.corrompido-{int(time.time())}"))
            e = json.loads(copia)                    # sem cópia válida: para aqui (não opera sem saber o que tem na conta)
            anotar(e, "⚠️ estado local estava corrompido (desligamento?); recuperei a cópia do ramo estado e confiro a corretora")
            return e
    return {"inicio": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "conta": "testnet.binancefuture.com (dinheiro de teste)",
            "capital_inicial": CAPITAL, "caixa": CAPITAL, "patrimonio": CAPITAL, "abertas": {}, "fechadas": [], "eventos": []}


def salvar(e):
    tmp = LOCAL.with_suffix(".tmp")
    with open(tmp, "w") as f:                        # auditoria 19/11: fsync antes da troca (desligamento não deixa arquivo vazio)
        f.write(json.dumps(e, ensure_ascii=False))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, LOCAL)


# ---------------- corretora ----------------
def velas(f, par, intervalo, limite=200, inicio_ms=None):
    p = {"symbol": sym(par), "interval": intervalo, "limit": limite}
    if inicio_ms:
        p["startTime"] = int(inicio_ms)
    agora = time.time() * 1000 + f.desvio_ms                # o relógio do testnet não é o daqui (18/11: 17 h à frente)
    return [x for x in f._pedir("GET", "/fapi/v1/klines", p) if x[6] < agora]


def riscos(f):
    """{symbol: (quantidade com sinal, preço de marca, resultado aberto)} das posições abertas na conta."""
    return {p["symbol"]: (float(p["positionAmt"]), float(p["markPrice"]), float(p["unRealizedProfit"]))
            for p in f._pedir("GET", "/fapi/v2/positionRisk", assinado=True) if float(p["positionAmt"]) != 0}


def colocar_stop(f, par, lado_pos, qtd, preco, tipo="STOP_MARKET"):
    """STOP_MARKET reduce-only guardado na corretora. Tenta o endereço de ordens; se a corretora mandar para o de ordens condicionais
    (algoOrder), usa esse. Devolve {"via", "id", "preco"}; erro nos dois = ErroFuturos (quem chamou fecha a posição)."""
    side = "SELL" if lado_pos == "compra" else "BUY"
    px = f.preco_redondo(par, preco, ("BUY" if side == "SELL" else "SELL") if tipo == "STOP_MARKET" else side)
    try:
        d = f._pedir("POST", "/fapi/v1/order", {"symbol": par, "side": side, "type": tipo, "stopPrice": px, "quantity": qtd,
                                                "reduceOnly": "true", "workingType": "CONTRACT_PRICE"}, assinado=True)
        return {"via": "order", "id": str(d["orderId"]), "preco": px}
    except ErroFuturos as ex1:
        try:
            d = f._pedir("POST", "/fapi/v1/algoOrder", {"algoType": "CONDITIONAL", "symbol": par, "side": side, "type": tipo,
                                                        "triggerPrice": px, "quantity": qtd, "reduceOnly": "true",
                                                        "workingType": "CONTRACT_PRICE"}, assinado=True)
            return {"via": "algo", "id": str(d["algoId"]), "preco": px}
        except ErroFuturos as ex2:
            raise ErroFuturos(f"stop recusado: ordem [{str(ex1)[:120]}] / condicional [{str(ex2)[:120]}]") from None


def cancelar_stop(f, par, st):
    if not st:
        return
    try:
        if st["via"] == "order":
            f.cancelar(par, st["id"])
        else:
            f._pedir("DELETE", "/fapi/v1/algoOrder", {"algoId": st["id"]}, assinado=True)
    except ErroFuturos:
        pass                                           # já executou ou já foi cancelado: a conciliação confere


def stops_abertos(f):
    """Ids dos stops vivos na corretora: {"order": {id: symbol}, "algo": {id: symbol}}."""
    out = {"order": {str(o["orderId"]): o["symbol"] for o in f._pedir("GET", "/fapi/v1/openOrders", assinado=True)}, "algo": {}}
    try:
        for o in f._pedir("GET", "/fapi/v1/openAlgoOrders", assinado=True) or []:
            out["algo"][str(o.get("algoId"))] = o.get("symbol")
    except ErroFuturos:
        pass
    return out


# ---------------- contabilidade ----------------
def realizado(e):
    return float(e["caixa"]) + sum(float(p["gasto"]) for p in e["abertas"].values())


def registrar_fechada(f, e, par, motivo):
    """Fecha no estado com o resultado da corretora: realizedPnl − commission de todas as execuções desde a entrada."""
    p = e["abertas"][par]
    trades = [t for t in f._pedir("GET", "/fapi/v1/userTrades", {"symbol": sym(par), "startTime": int(p["entrada_t"] * 1000) + f.desvio_ms - 2000,
                                                                  "limit": 1000}, assinado=True)]
    lado_saida = "SELL" if p["lado"] == "compra" else "BUY"
    saidas = [t for t in trades if t["side"] == lado_saida]
    if not saidas:
        raise ErroFuturos(f"{par}: a corretora ainda não mostra a execução da saída")
    res = sum(float(t["realizedPnl"]) for t in trades) - sum(float(t["commission"]) for t in trades)
    q = sum(float(t["qty"]) for t in saidas)
    saida = sum(float(t["qty"]) * float(t["price"]) for t in saidas) / q
    e["caixa"] = float(e["caixa"]) + p["gasto"] + res
    cancelar_stop(f, par, p.get("stop"))
    cancelar_stop(f, par, p.get("alvo"))
    if motivo is None:                                    # saiu na corretora: alvo (H62) ou stop
        no_alvo = p.get("alvo") and ((saida >= p["alvo"]["preco"] * 0.999) if p["lado"] == "compra" else (saida <= p["alvo"]["preco"] * 1.001))
        motivo = (f"alvo +{p.get('alvo_pct', 0):.2%} na corretora" if no_alvo else
                  f"stop móvel na corretora (pico +{p.get('pico', 0):.2%})" if p.get("stop_tipo") == "móvel" else
                  f"stop de segurança −{p.get('stop_pct', 0):.2%} na corretora")
    e["fechadas"].append({**{k: v for k, v in p.items() if k not in ("stop",)}, "saida": saida, "saida_t": (max(t["time"] for t in saidas) - f.desvio_ms) / 1000,
                          "motivo": motivo, "resultado_usd": res, "taxas": sum(float(t["commission"]) for t in trades),
                          "stop_final": (p.get("stop") or {}).get("preco")})
    del e["abertas"][par]
    anotar(e, f"{'✅' if res > 0 else '❌'} SAIU da {'COMPRA' if p['lado'] == 'compra' else 'VENDA'} em {par[:-4]} a {saida:.6g} ({motivo}): {res:+.4f} USDT")


def fechar(f, e, par, motivo):
    p = e["abertas"][par]
    cancelar_stop(f, par, p.get("stop"))
    cancelar_stop(f, par, p.get("alvo"))
    q = riscos(f).get(sym(par), (0, 0, 0))[0]
    if q:
        f.ordem_mercado(par, "SELL" if q > 0 else "BUY", abs(q), reduce_only=True)
    for _ in range(5):
        time.sleep(1.5)
        try:
            return registrar_fechada(f, e, par, motivo)
        except ErroFuturos:
            continue
    anotar(e, f"⚠️ {par}: fechei a mercado mas a corretora ainda não mostra a execução; confiro na próxima rodada")


def faltam(pos):
    """REGRAS §5 (R2): entrada nova só com stop_pct escrito na decisão (nada de stop padrão); alvo e prazo são opcionais."""
    return [k for k in ("stop_pct",) if not isinstance((pos or {}).get(k), (int, float))]


def saidas_desde(e, d):
    """20/11: moedas que saíram (stop, alvo, prazo) depois da LEITURA em que a decisão se baseou não reentram até uma decisão nova.
    (1ª versão comparava com a hora da publicação: o stop de NEAR executou às 14:21:26, entre a leitura das 14:20 e a decisão das 14:23:35, e a moeda
    reabriu.) Sem leitura_t na decisão, vale a decisão − 15 min. A inversão de lado pedida pela decisão não bloqueia."""
    d = d if isinstance(d, dict) else {"t": d}
    corte = float(d.get("leitura_t") or float(d.get("t") or 0) - 900)
    return {f.get("moeda") for f in e.get("fechadas") or [] if float(f.get("saida_t") or 0) >= corte
            and "inverteu o lado" not in str(f.get("motivo_saida") or f.get("motivo") or "")}


def _foco_pode(corretora):
    """Chave central da equipe (mesa/foco.py → Shared/baleias/FOCO.json). Sem a chave ou com erro: NÃO abre (seguro)."""
    import importlib.util
    for arq in (Path(__file__).resolve().parent.parent / "foco.py", Path("/home/servidor-de-producao/OpenBot/Shared/baleias/foco.py")):
        if arq.exists():
            try:
                spec = importlib.util.spec_from_file_location("foco_equipe", arq)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                return m.pode_operar(corretora)
            except Exception as ex:                                    # chave quebrada: não abre
                return False, f"chave de foco com erro ({type(ex).__name__})"
    return False, "chave de foco (foco.py) não encontrada"


def abrir(f, e, par, lado, motivo, decisao_t, prm=None):
    pode, porque = _foco_pode("binance")
    if not pode:
        return anotar(e, f"{par[:-4]}: {porque}; não entra")
    if not prm or faltam(prm):
        return anotar(e, f"{par[:-4]}: a decisão não traz stop_pct; não entra (REGRAS §5)")
    noc, alav = tamanho(realizado(e))                         # H64: a fatia cresce com o ganho e encolhe na perda (10× até 2,5×, 20× acima)
    noc *= 4 / MAX_POS                                         # R2: até 8 posições, cada uma com metade (exposição total igual)
    try:
        f.regras(par)
    except ErroFuturos:
        return anotar(e, f"{par[:-4]}: não existe nos futuros do testnet; não entra (H59)")
    usada = None
    for a in [x for x in (alav, 10, 5, 3, 2, 1) if x <= alav]:   # a corretora limita a alavancagem de algumas moedas (KITE recusou 10×)
        try:
            f.alavancagem(par, a)
            usada = a
            break
        except ErroFuturos:
            continue
    if usada is None:
        return anotar(e, f"{par[:-4]}: a corretora recusou todas as alavancagens; não entra")
    if usada < alav:
        noc = min(noc, realizado(e) * usada / MAX_POS)          # alavancagem menor: posição menor; cada margem fica em ¼ da carteira
        anotar(e, f"{par[:-4]}: a corretora aceitou só {usada}× (pedi {alav}×); posição de US$ {noc:.2f}")
    alav = usada
    if 0.95 * noc / alav <= float(e["caixa"]) < noc / alav:   # a 4ª posição: o arredondamento das outras deixou centavos de menos
        noc = float(e["caixa"]) * alav * 0.995
    if float(e["caixa"]) < noc / alav - 1e-9 or noc <= 0:
        return anotar(e, f"{par[:-4]}: sem caixa para a margem (caixa {e['caixa']:.2f}, precisa {noc / alav:.2f})")
    bid, ask = f.livro(par)
    px = ask if lado == "compra" else bid
    qtd = f.quantidade(par, noc, px)
    if qtd * px > MAX_NOC * noc:
        return anotar(e, f"{par[:-4]}: nocional mínimo da corretora ({qtd * px:.2f}) passa de {MAX_NOC} × a posição ({noc:.2f}); não entra (H59)")
    sp = prm["stop_pct"]                                                        # REGRAS §5: o stop da decisão (sem stop padrão)
    d = f.ordem_mercado(par, "BUY" if lado == "compra" else "SELL", qtd)
    st = {"executada": 0.0}
    for _ in range(6):
        time.sleep(1)
        try:                                              # auditoria 20/11: a ordem já foi; erro de rede na consulta não pode largar a posição sem stop
            st = f.consultar(par, d["orderId"])
        except ErroFuturos as ex:
            st = {"executada": 0.0, "status": f"consulta falhou: {str(ex)[:80]}"}
            continue
        if st["status"] == "FILLED":
            break
    if st.get("executada", 0) <= 0 and str(st.get("status", "")).startswith("consulta falhou"):
        return anotar(e, f"🚨 {par[:-4]}: ordem a mercado {d['orderId']} enviada e não confirmada ({st['status']}); "
                         "a conciliação da próxima rodada fecha a posição que aparecer sem estado")
    q, ent = st["executada"], st["preco_medio"]
    if q <= 0:
        return anotar(e, f"{par[:-4]}: ordem a mercado {d['orderId']} não executou ({st.get('status')})")
    gasto = q * ent / alav
    e["caixa"] = float(e["caixa"]) - gasto
    e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": ent, "entrada_t": time.time(), "qtd": q, "nocional": q * ent, "gasto": gasto, "alav": alav,
                         "stop_pct": sp, "motivo": str(motivo)[:300], "decisao_t": decisao_t, "entrada_id": str(d["orderId"]), "pico": 0.0,
                         "movel_ate": int(time.time() * 1000) + f.desvio_ms, "relogio": "corretora", "stop_tipo": "segurança", "preco_testnet": ent, "resultado_aberto": 0.0,
                         **{k: v for k, v in prm.items() if k in ("alvo_pct", "max_min", "movel")}}
    alvo = ent * (1 - sp) if lado == "compra" else ent * (1 + sp)
    try:
        e["abertas"][par]["stop"] = colocar_stop(f, par, lado, q, alvo)
    except ErroFuturos as ex:
        anotar(e, f"🚨 {par[:-4]}: a corretora recusou o stop ({str(ex)[:200]}); fecho a posição agora (H59: nunca sem stop)")
        return fechar(f, e, par, "stop recusado pela corretora: fechada na hora")
    if prm.get("alvo_pct"):                               # H62: alvo (realiza o lucro) também guardado na corretora
        a = prm["alvo_pct"]
        try:
            e["abertas"][par]["alvo"] = colocar_stop(f, par, lado, q, ent * (1 + a) if lado == "compra" else ent * (1 - a), tipo="TAKE_PROFIT_MARKET")
        except ErroFuturos as ex:
            anotar(e, f"⚠️ {par[:-4]}: a corretora recusou o alvo ({str(ex)[:150]}); fica só o stop")
    s = e["abertas"][par]["stop"]
    al = e["abertas"][par].get("alvo")
    anotar(e, f"ENTROU {'COMPRADO' if lado == 'compra' else 'VENDIDO'} em {par[:-4]}: {q} a {ent:.6g} (US$ {q * ent:.2f}, ordem {d['orderId']}); "
              f"stop {s['preco']} (−{sp:.2%}) guardado na corretora ({s['via']} {s['id']})"
              + (f"; alvo {al['preco']} (+{prm['alvo_pct']:.2%}) guardado ({al['via']} {al['id']})" if al else "")
              + (f"; prazo {prm['max_min']:.0f} min" if prm.get("max_min") else ""))


# ---------------- uma rodada ----------------
def conciliar(f, e):
    """Ao voltar (inclusive de uma pausa da máquina): o que a corretora fez enquanto ninguém olhava."""
    pos = riscos(f)
    for par in list(e["abertas"]):
        if sym(par) not in pos:
            p = e["abertas"][par]
            try:
                registrar_fechada(f, e, par, None)          # o motivo (alvo, stop móvel ou stop) sai do preço executado
            except ErroFuturos as ex:
                anotar(e, f"⚠️ {par}: posição sumiu da conta e não achei a execução ({str(ex)[:80]})")
    vivos = stops_abertos(f)
    meus = {(p[k]["via"], p[k]["id"]) for p in e["abertas"].values() for k in ("stop", "alvo") if p.get(k)}
    for via in ("order", "algo"):
        for oid, s in vivos[via].items():
            if (via, oid) not in meus:
                cancelar_stop(f, s, {"via": via, "id": oid})
                anotar(e, f"🧹 ordem desconhecida cancelada na conta: {s} ({via} {oid})")
    minhas = {sym(par) for par in e["abertas"]}
    for s, (q, _, _) in pos.items():
        if s not in minhas:
            f.ordem_mercado(s, "SELL" if q > 0 else "BUY", abs(q), reduce_only=True)
            anotar(e, f"🧹 posição desconhecida fechada a mercado: {s} {q:+g}")
    for par, p in e["abertas"].items():                  # stop sumiu sem a posição sumir: guarda outro na hora
        st = p.get("stop")
        if not st or st["id"] not in vivos[st["via"]]:
            alvo = st["preco"] if st else (p["entrada"] * (1 - p["stop_pct"]) if p["lado"] == "compra" else p["entrada"] * (1 + p["stop_pct"]))
            try:
                p["stop"] = colocar_stop(f, par, p["lado"], p["qtd"], alvo)
                anotar(e, f"🛡 {par[:-4]}: stop não estava na corretora; guardei de novo a {p['stop']['preco']}")
            except ErroFuturos as ex:
                anotar(e, f"🚨 {par[:-4]}: sem stop e a corretora recusou ({str(ex)[:120]}); fecho")
                fechar(f, e, par, "stop recusado pela corretora: fechada na hora")
    e["conciliado_t"] = time.time()


def mover_stops(f, e):
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        k = velas(f, par, "1m", 1000, max(int(p["entrada_t"] * 1000) + f.desvio_ms, int(p.get("movel_ate", 0))))
        compra = p["lado"] == "compra"
        for x in k:
            fav = (float(x[2]) / p["entrada"] - 1) if compra else (1 - float(x[3]) / p["entrada"])
            p["pico"] = max(p.get("pico", 0.0), fav)
            p["movel_ate"] = int(x[0]) + 60_000
        if p["pico"] < SM.armar_em(p.get("alvo_pct"), p.get("movel", True)):      # dono (19/11): com alvo, o móvel arma na metade do caminho até ele
            continue
        g = GUARDA * p["pico"]
        novo = p["entrada"] * (1 + g) if compra else p["entrada"] * (1 - g)
        atual = (p.get("stop") or {}).get("preco")
        if atual is not None and ((novo <= atual) if compra else (novo >= atual)):
            continue
        bid, ask = f.livro(par)
        if (bid <= novo) if compra else (ask >= novo):    # o preço já devolveu além do nível: realiza agora
            fechar(f, e, par, f"stop móvel (pico +{p['pico']:.2%}, guardou +{g:.2%}; preço já no nível)")
            continue
        velho = p.get("stop")
        try:
            p["stop"] = colocar_stop(f, par, p["lado"], p["qtd"], novo)
        except ErroFuturos as ex:
            anotar(e, f"⚠️ {par[:-4]}: não consegui subir o stop ({str(ex)[:100]}); o anterior continua")
            continue
        cancelar_stop(f, par, velho)
        p["stop_tipo"] = "móvel"
        anotar(e, f"⤴ {par[:-4]}: stop móvel {velho and velho['preco']} → {p['stop']['preco']} (pico +{p['pico']:.2%}, guarda +{g:.2%})")


def decisao_do_chefe():
    """A decisão mais nova que o próprio chefe gravou com sucesso (recibos.jsonl status ok), com as posições dela."""
    t_ok = None
    rec = AQUI / "recibos.jsonl"
    if rec.exists():
        for l in rec.read_text().splitlines():
            try:
                r = json.loads(l) if l.strip() else {}
            except ValueError:                           # auditoria 19/11: linha cortada por desligamento não derruba a rodada
                continue
            if isinstance(r, dict) and r.get("status") == "ok" and r.get("decisao_t"):
                t_ok = r["decisao_t"]
    if not t_ok:
        return None
    for arq in sorted(glob.glob(str(AQUI / "rodadas" / "*-decisao.json")), reverse=True):
        try:
            d = json.loads(Path(arq).read_text())
        except (OSError, ValueError):                    # auditoria 19/11: 20261118-231404-decisao.json ficou com 0 byte e quebrava
            continue                                     # a rodada inteira (sem conciliação, sem stop móvel)
        if isinstance(d, dict) and d.get("t") == t_ok:
            return d
    return None


def patrimonio(f, e):
    pos = riscos(f)
    total = float(e["caixa"])
    for par, p in e["abertas"].items():
        q, marca, aberto = pos.get(sym(par), (0, p["entrada"], 0.0))
        p["preco_testnet"], p["resultado_aberto"] = marca, aberto
        total += p["gasto"] + aberto
    e["patrimonio"] = total
    return total


def publicar():
    ultimo = ""
    for k in range(1, 6):
        try:
            run = lambda *a: subprocess.run(["git", "-C", str(EST), *a], capture_output=True, text=True, timeout=120, check=True)
            run("fetch", "-q", "--depth", "20", "origin", "estado")
            run("reset", "-q", "--hard", "origin/estado")
            run("clean", "-qfd")
            (EST / ARQ).write_text(LOCAL.read_text())
            run("add", ARQ)
            mudou = run("diff", "--cached", "--name-only").stdout.split()
            if not mudou:
                return "nada novo"
            if mudou != [ARQ]:
                raise RuntimeError(f"o commit mexeria em outros arquivos: {mudou}")
            run(*AUTOR, "commit", "-q", "-m", f"chefe testnet {time.strftime('%H:%M', time.gmtime())}", "-m", TRAILER)
            r = subprocess.run(["git", "-C", str(EST), "push", "-q", "origin", "HEAD:estado"], capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                return run("rev-parse", "--short", "HEAD").stdout.strip()
            ultimo = (r.stderr or r.stdout)[:200]
        except (subprocess.SubprocessError, RuntimeError, OSError) as ex:
            ultimo = str(ex)[:200]
        time.sleep(3 * k)
    raise RuntimeError(f"push do estado falhou 5 vezes: {ultimo}")


def rodada():
    f = conectar()
    e = carregar()
    guarda = "?"
    try:                                                 # auditoria 20/11: erro no meio da rodada não perde o que já foi feito na corretora
        agora = time.time()
        conciliar(f, e)                                      # 1) o que a corretora fez enquanto a máquina dormia
        mover_stops(f, e)                                    # 2) stop móvel (H49), guardado na corretora
        patrimonio(f, e)
        guarda = GD.checar(e, agora)                         # 3) guarda do dia (H54) e meta de US$ 12 (H57)
        if guarda == "fechar":
            for par in list(e["abertas"]):
                fechar(f, e, par, GD.motivo(e))
            anotar(e, GD.texto("Chefe OpenBot (testnet)", e))
        for par in list(e["abertas"]):                       # 4) tempo máximo
            mm = e["abertas"][par].get("max_min")
            if agora - e["abertas"][par]["entrada_t"] > (mm or MAX_HORAS * 60) * 60:
                fechar(f, e, par, f"prazo da operação ({mm:.0f} min)" if mm else f"tempo máximo ({MAX_HORAS} h)")
        d = decisao_do_chefe()                               # 5) a decisão do chefe, se ainda vale
        fresca = d and agora - d["t"] <= VALIDADE_S
        if fresca:
            nova = d["t"] != e.get("decisao_seguida_t")
            e["decisao_seguida_t"] = d["t"]
            if nova:                                         # cada moeda entra no máximo uma vez por decisão (a que saiu no stop não reentra)
                e["decisao_entradas"] = {"t": d["t"], "pares": list(e["abertas"])}
            querer = {}
            for x in d.get("posicoes") or []:
                par = str(x.get("moeda", "")).upper()
                prm = parametros(x) if not faltam(x) else None   # REGRAS §5: sem stop, alvo e prazo na decisão = não entra (abrir anota)
                querer[par if par.endswith("USDT") else par + "USDT"] = (x.get("lado"), x.get("motivo", ""), prm)
            for par in (list(e["abertas"]) if nova else []):
                if par not in querer:
                    fechar(f, e, par, "fora da lista de posições do chefe")
                elif querer[par][0] != e["abertas"][par]["lado"]:
                    fechar(f, e, par, "o chefe inverteu o lado")
            ja = set(e.get("decisao_entradas", {}).get("pares", [])) | saidas_desde(e, d)   # 20/11: saiu pelo stop/alvo/prazo = não reentra
            if guarda == "normal" and patrimonio(f, e) >= PISO:
                for par, (lado, motivo, prm) in querer.items():
                    if par not in e["abertas"] and par not in ja and len(e["abertas"]) < MAX_POS and lado in ("compra", "venda"):
                        try:
                            abrir(f, e, par, lado, motivo, d["t"], prm)
                            if par in e["abertas"]:
                                e.setdefault("decisao_entradas", {"t": d["t"], "pares": []})["pares"].append(par)
                        except ErroFuturos as ex:
                            anotar(e, f"⚠️ {par[:-4]}: entrada falhou ({str(ex)[:150]})")
            elif guarda != "normal":
                anotar(e, "travado pela guarda do dia: a decisão não abre posição até 00:00 UTC")
        patrimonio(f, e)
    finally:
        e["atualizado"] = time.time()
        salvar(e)
    commit = publicar()
    print(f"⚓ Chefe OpenBot (testnet): patrimônio US$ {e['patrimonio']:.4f} · caixa {e['caixa']:.4f} · {len(e['abertas'])} abertas · "
          f"{len(e['fechadas'])} fechadas · guarda {guarda} · estado {commit}")
    for par, p in e["abertas"].items():
        print(f"   {par} {p['lado']} {p['qtd']} a {p['entrada']:.6g} · agora {p['preco_testnet']:.6g} ({p['resultado_aberto']:+.4f}) · "
              f"stop {p['stop']['preco']} ({p['stop_tipo']}, {p['stop']['via']} {p['stop']['id']})")


def mostrar_conta():
    f = conectar()
    print("endereço:", f.base)
    print("saldo de teste (disponível, total):", f.saldo_usdt())
    print("posições:", riscos(f))
    print("stops/ordens vivos:", stops_abertos(f))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--conta"]:
        mostrar_conta()
    else:
        import fcntl                                     # duas rodadas ao mesmo tempo mandariam ordens em dobro: a segunda espera
        with open(AQUI / ".testnet.lock", "w") as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)
            rodada()
