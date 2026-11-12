"""Robô v4 no testnet de futuros da Binance: segue as apostas do Cérebro v4 (LightGBM, nuvem) com confiança ≥ LIMIAR, entrando com
ordem limitada SÓ MAKER (taxa 0,02% em vez de 0,05% do tomador) no melhor preço do livro, e ACOMPANHANDO o livro: a cada REPEG s,
se o melhor preço se afastou da nossa ordem, cancela e reposiciona (continua maker). A ordem fica no livro até 2 min antes do fim
da vela apostada. Sai começando 60 s antes do fim da vela, também maker acompanhando o livro; se ESPERA_SAIDA s depois do fim da
vela ainda não executou, vai a mercado. Stop de segurança de 1% a mercado. Registra quantas ordens executam, em quanto tempo e
com quantas reposições — o número que decide se a taxa de tomador pode ser evitada na carteira do dono.
Dinheiro de teste. Serviço: baleias-v4testnet. Estado: dados/robo_v4_testnet.json.
"""
import json
import math
import os
import time

from baleias import config, mesa
from executor.binance_futuros import ErroFuturos, Futuros

LIMIAR = float(os.environ.get("V4_LIMIAR", "0.10"))         # |p − 0,5| mínimo (H31: só as apostas mais confiantes chegam perto de pagar)
NOCIONAL = float(os.environ.get("V4_NOCIONAL", "25"))       # US$ por posição (sobe ao mínimo da moeda: BTC 50, ETH 20)
MAX_POS = 6
CAPITAL, ALAV, PISO = float(os.environ.get("V4_CAPITAL", "10")), 10, 5.0   # carteira de US$ 10 a 10× (regra do dono), como no real
PERDA_DIA = float(os.environ.get("V4_PERDA_DIA", "0"))      # 0 = sem trava de perda do dia (decisão do dono 12/11: "tirar"); só o piso elimina
STOP_SEG = float(os.environ.get("V4_STOP", "0.01"))         # stop de segurança de 1% (a mercado): o 4N de 1 min do Rápido saía no ruído
VELA = 900
MARGEM_ENTRADA = 120     # a ordem de entrada fica no livro até 2 min antes do fim da vela apostada
ANTECIPAR_SAIDA = 60     # começa a sair (maker) 60 s antes do fim da vela
ESPERA_SAIDA = 45        # depois do fim da vela, mais 45 s maker; aí vai a mercado
REPEG = 20               # a cada 20 s, se o melhor preço se afastou, reposiciona a ordem (continua maker)
TAXA_MAKER, TAXA_TAKER = 0.0002, 0.0005
ARQ = config.RAIZ / "robo_v4_testnet.json"


def carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text())
    return {"inicio": time.strftime("%Y-%m-%d"), "capital_inicial": 10.0, "abertas": {}, "ordens": {}, "fechadas": [], "tentadas": [],
            "nao_executadas": 0, "eventos": []}


def salvar(e):
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text(json.dumps(e))
    tmp.replace(ARQ)


def anotar(e, texto):
    e["eventos"] = ([{"t": time.time(), "texto": "🧪 " + texto}] + e["eventos"])[:100]
    print(time.strftime("%H:%M:%S"), texto, flush=True)


def cancelar_conferindo(f, par, oid):
    """Cancela a ordem e devolve (quantidade já executada, preço médio): a ordem pode executar entre a consulta e o cancelamento."""
    try:
        d = f.cancelar(par, oid)
        return float(d.get("executedQty") or 0), float(d.get("avgPrice") or 0)
    except ErroFuturos:
        st = f.consultar(par, oid)
        return st["executada"], st["preco_medio"]


def arredondar_qtd(f, par, qtd):
    r = f.regras(par)
    casas = max(0, -int(math.floor(math.log10(r["step"]))))
    return round(math.floor(qtd / r["step"] + 1e-9) * r["step"], casas)


def abrir(e, par, lado, qtd, px, o, agora, parcial=False):
    t0, repegs = o.get("t0", o["t"]), o.get("repegs", 0)
    e["abertas"][par] = {"lado": lado, "qtd": qtd, "entrada": px, "t": agora, "fim": o["fim"], "prob": o["prob"],
                         "espera_s": round(agora - t0, 1), "repegs": repegs, "ex_maker": [0.0, 0.0], "ex_taker": [0.0, 0.0]}
    anotar(e, f"{'◐' if parcial else '✅'} {par} EXECUTOU {lado} {qtd} a {px} (maker, {agora - t0:.0f} s, {repegs} reposições)"
              + (" — o resto foi cancelado" if parcial else ""))


def registrar_saida(e, par, p, qtd, px, maker):
    """Acumula uma execução (total ou parcial) da saída; fecha a posição quando tudo saiu."""
    if qtd <= 0:
        return False
    acum = p["ex_maker" if maker else "ex_taker"]
    acum[0], acum[1] = acum[0] + qtd, acum[1] + qtd * px
    if p["ex_maker"][0] + p["ex_taker"][0] < p["qtd"] - 1e-9:
        return False
    fechar(e, par, p)
    return True


def fechar(e, par, p):
    qm, vm = p["ex_maker"]
    qt, vt = p["ex_taker"]
    px_saida = (vm + vt) / (qm + qt)
    sinal = 1 if p["lado"] == "BUY" else -1
    bruto = sinal * (px_saida - p["entrada"]) * p["qtd"]
    taxas = p["qtd"] * p["entrada"] * TAXA_MAKER + vm * TAXA_MAKER + vt * TAXA_TAKER
    res = bruto - taxas
    maker = qt <= 1e-12
    motivo = p.get("motivo") or "fim da vela do v4"
    e["fechadas"].append({"moeda": par, "lado": "venda" if p["lado"] == "SELL" else "compra", "entrada": p["entrada"], "saida": px_saida,
                          "entrada_t": p["t"], "saida_t": time.time(), "qtd": p["qtd"], "resultado_usd": res, "saida_maker": maker, "prob": p["prob"],
                          "espera_s": p.get("espera_s"), "repegs": p.get("repegs", 0), "repegs_saida": p.get("repegs_saida", 0),
                          "motivo": motivo + ("" if maker else " (saída a mercado)")})
    del e["abertas"][par]
    anotar(e, f"{'✅' if res > 0 else '❌'} {par} fechou {'maker' if maker else 'a mercado'} a {px_saida:.6g} ({motivo}): {res:+.3f} USDT")


def resumo(e):
    f = e["fechadas"]
    esperas = [x["espera_s"] for x in f if x.get("espera_s") is not None] + [p["espera_s"] for p in e["abertas"].values()]
    return {"fechadas": len(f), "ganhos": sum(1 for x in f if x["resultado_usd"] > 0), "resultado": sum(x["resultado_usd"] for x in f),
            "nao_executadas": e["nao_executadas"], "executadas": len(f) + len(e["abertas"]),
            "saidas_maker": sum(1 for x in f if x["saida_maker"]), "stops": sum(1 for x in f if "stop" in x["motivo"]),
            "espera_media_s": round(sum(esperas) / len(esperas), 1) if esperas else None,
            "repegs": sum(x.get("repegs", 0) for x in f) + sum(p.get("repegs", 0) for p in e["abertas"].values())
                      + sum(o.get("repegs", 0) for o in e["ordens"].values())}


def main():
    f = Futuros.do_env()
    e = carregar()
    e.setdefault("ordens", {})
    livre, total = f.saldo_usdt()
    anotar(e, f"ligado no testnet (saldo de teste {total:.0f}), carteira de US$ {CAPITAL:.0f} a {ALAV}× · confiança ≥ {LIMIAR:.0%} · US$ {NOCIONAL:.0f} por posição · "
              f"ordens maker acompanhando o livro a cada {REPEG} s · stop de segurança {STOP_SEG:.0%}"
              + (f" · perda do dia −{PERDA_DIA:.2f}" if PERDA_DIA else " · sem trava do dia (só o piso de US$ 5)"))
    while True:
        agora = time.time()
        try:
            mesa._buscar_estado()
            v4 = mesa._git_json("dados/cerebro_v4.json") or {}
        except Exception:
            v4 = {}
        carteira = CAPITAL + sum(x["resultado_usd"] for x in e["fechadas"])
        hoje = time.strftime("%Y-%m-%d", time.gmtime(agora))
        dia = sum(x["resultado_usd"] for x in e["fechadas"] if time.strftime("%Y-%m-%d", time.gmtime(x["saida_t"])) == hoje)
        margem_usada = (sum(p["qtd"] * p["entrada"] for p in e["abertas"].values()) + sum(o["qtd"] * o["px"] for o in e["ordens"].values())) / ALAV
        trava = ("conta abaixo de US$ 5" if carteira < PISO else
                 f"perda do dia {dia:+.2f} (limite −{PERDA_DIA:.2f})" if PERDA_DIA and dia <= -PERDA_DIA else None)
        if trava and e.get("trava") != f"{hoje} {trava}":
            anotar(e, f"🛑 sem novas entradas: {trava}; as saídas continuam")
        e["trava"] = f"{hoje} {trava}" if trava else None
        e["carteira"] = carteira
        # ---- novas apostas do v4: ordem maker no melhor preço ----
        for par, p in v4.get("pendentes", {}).items():
            inicio, fim = p["t"] / 1000 + VELA, p["t"] / 1000 + 2 * VELA
            chave = f"{par}@{p['t']}"
            if trava or abs(p["prob"] - 0.5) < LIMIAR or chave in e["tentadas"] or not (inicio <= agora <= fim - MARGEM_ENTRADA):
                continue
            if par in e["abertas"] or par in e["ordens"] or len(e["abertas"]) + len(e["ordens"]) >= MAX_POS:
                continue
            lado = "BUY" if p["aposta"] > 0 else "SELL"
            e["tentadas"] = (e["tentadas"] + [chave])[-500:]
            try:
                bid, ask = f.livro(par)
                px = f.preco_redondo(par, bid if lado == "BUY" else ask, lado)
                qtd = f.quantidade(par, NOCIONAL, px)
                if margem_usada + qtd * px / ALAV > carteira:              # não cabe na carteira de US$ 10 a 10×
                    anotar(e, f"· {par}: não cabe (margem usada {margem_usada:.2f} + {qtd * px / ALAV:.2f} > carteira {carteira:.2f})")
                    continue
                if par not in e.setdefault("alav_ok", []):
                    f.alavancagem(par, ALAV)
                    e["alav_ok"].append(par)
                o = f.ordem_limit(par, lado, qtd, px, so_maker=True)
                margem_usada += qtd * px / ALAV
            except ErroFuturos as ex:
                e["nao_executadas"] += 1
                anotar(e, f"✗ {par} ordem maker recusada ({str(ex)[:80]})")
                continue
            e["ordens"][par] = {"id": o["orderId"], "lado": lado, "qtd": qtd, "px": px, "t0": agora, "t": agora, "fim": fim, "prob": p["prob"], "repegs": 0}
            anotar(e, f"📝 {par} ordem maker {lado} {qtd} a {px} (v4 {max(p['prob'], 1 - p['prob']):.0%}, nocional {qtd * px:.0f})")
        # ---- ordens de entrada no livro: executou? acabou o tempo? o livro se afastou (reposicionar)? ----
        for par, o in list(e["ordens"].items()):
            try:
                st = f.consultar(par, o["id"])
            except ErroFuturos:
                continue
            if st["status"] == "FILLED":
                abrir(e, par, o["lado"], st["executada"], st["preco_medio"], o, agora)
                del e["ordens"][par]
                continue
            acabou = st["status"] in ("CANCELED", "EXPIRED", "REJECTED") or agora > o["fim"] - MARGEM_ENTRADA
            try:
                if acabou:
                    qx, pxx = (st["executada"], st["preco_medio"]) if st["status"] not in ("NEW", "PARTIALLY_FILLED") else cancelar_conferindo(f, par, o["id"])
                    if qx > 0:
                        abrir(e, par, o["lado"], qx, pxx, o, agora, parcial=qx < o["qtd"] - 1e-9)
                    else:
                        e["nao_executadas"] += 1
                        anotar(e, f"⌛ {par} não executou em {agora - o.get('t0', o['t']):.0f} s ({o.get('repegs', 0)} reposições, {st['status']}): cancelada")
                    del e["ordens"][par]
                elif agora - o["t"] >= REPEG and st["status"] == "NEW":
                    bid, ask = f.livro(par)
                    novo = f.preco_redondo(par, bid if o["lado"] == "BUY" else ask, o["lado"])
                    if (novo > o["px"]) if o["lado"] == "BUY" else (novo < o["px"]):   # o melhor preço se afastou: ficamos fundo no livro
                        qx, pxx = cancelar_conferindo(f, par, o["id"])
                        if qx > 0:                                                     # executou no meio do caminho
                            abrir(e, par, o["lado"], qx, pxx, o, agora, parcial=qx < o["qtd"] - 1e-9)
                            del e["ordens"][par]
                            continue
                        qtd = f.quantidade(par, NOCIONAL, novo)
                        n = f.ordem_limit(par, o["lado"], qtd, novo, so_maker=True)
                        o.update(id=n["orderId"], px=novo, qtd=qtd, t=agora, repegs=o.get("repegs", 0) + 1)
                    else:
                        o["t"] = agora
            except ErroFuturos as ex:
                anotar(e, f"✗ {par} entrada: {str(ex)[:80]}")
                o["t"] = agora
        # ---- posições abertas: stop de segurança, saída maker perto do fim da vela, a mercado se não executar ----
        for par, p in list(e["abertas"].items()):
            p.setdefault("ex_maker", [0.0, 0.0])
            p.setdefault("ex_taker", [0.0, 0.0])
            lado_saida = "SELL" if p["lado"] == "BUY" else "BUY"
            restante = p["qtd"] - p["ex_maker"][0] - p["ex_taker"][0]
            try:
                bid, ask = f.livro(par)
                meio = (bid + ask) / 2
                ganho = (meio / p["entrada"] - 1) * (1 if p["lado"] == "BUY" else -1)
                stop = ganho <= -STOP_SEG
                if not stop and agora < p["fim"] - ANTECIPAR_SAIDA and not p.get("saida_id"):
                    continue
                if p.get("saida_mercado"):                                   # já mandou a mercado: só confere
                    st = f.consultar(par, p["saida_id"])
                    if st["status"] == "FILLED":
                        registrar_saida(e, par, p, st["executada"], st["preco_medio"], maker=False)
                    continue
                if stop and p.get("motivo") is None:
                    p["motivo"] = f"stop de segurança −{STOP_SEG:.0%}"
                    if p.get("saida_id"):
                        qx, pxx = cancelar_conferindo(f, par, p["saida_id"])
                        if registrar_saida(e, par, p, qx, pxx, maker=True):
                            continue
                        restante = p["qtd"] - p["ex_maker"][0] - p["ex_taker"][0]
                    o = f.ordem_mercado(par, lado_saida, arredondar_qtd(f, par, restante), reduce_only=True)
                    p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=True)
                    anotar(e, f"🛑 {par} {ganho:+.2%}: stop de segurança a mercado")
                    continue
                if not p.get("saida_id"):
                    px = f.preco_redondo(par, ask if lado_saida == "SELL" else bid, lado_saida)
                    try:
                        o = f.ordem_limit(par, lado_saida, arredondar_qtd(f, par, restante), px, so_maker=True, reduce_only=True)
                        p.update(saida_id=o["orderId"], saida_px=px, saida_t=agora, saida_t0=agora, saida_mercado=False, repegs_saida=0)
                    except ErroFuturos:
                        o = f.ordem_mercado(par, lado_saida, arredondar_qtd(f, par, restante), reduce_only=True)
                        p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=True)
                    continue
                st = f.consultar(par, p["saida_id"])
                if st["status"] == "FILLED":
                    registrar_saida(e, par, p, st["executada"], st["preco_medio"], maker=True)
                elif agora > p["fim"] + ESPERA_SAIDA or st["status"] in ("CANCELED", "EXPIRED", "REJECTED"):
                    qx, pxx = (st["executada"], st["preco_medio"]) if st["status"] not in ("NEW", "PARTIALLY_FILLED") else cancelar_conferindo(f, par, p["saida_id"])
                    if registrar_saida(e, par, p, qx, pxx, maker=True):
                        continue
                    restante = p["qtd"] - p["ex_maker"][0] - p["ex_taker"][0]
                    o = f.ordem_mercado(par, lado_saida, arredondar_qtd(f, par, restante), reduce_only=True)
                    p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=True)
                elif agora - p["saida_t"] >= REPEG and st["status"] == "NEW":
                    novo = f.preco_redondo(par, ask if lado_saida == "SELL" else bid, lado_saida)
                    if (novo < p["saida_px"]) if lado_saida == "SELL" else (novo > p["saida_px"]):   # o melhor preço se afastou
                        qx, pxx = cancelar_conferindo(f, par, p["saida_id"])
                        if registrar_saida(e, par, p, qx, pxx, maker=True):
                            continue
                        restante = p["qtd"] - p["ex_maker"][0] - p["ex_taker"][0]
                        o = f.ordem_limit(par, lado_saida, arredondar_qtd(f, par, restante), novo, so_maker=True, reduce_only=True)
                        p.update(saida_id=o["orderId"], saida_px=novo, saida_t=agora, repegs_saida=p.get("repegs_saida", 0) + 1)
                    else:
                        p["saida_t"] = agora
            except ErroFuturos as ex:
                anotar(e, f"✗ {par} saída falhou ({str(ex)[:80]})")
        e["resumo"] = resumo(e)
        salvar(e)
        time.sleep(10)


if __name__ == "__main__":
    main()
