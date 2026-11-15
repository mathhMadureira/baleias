"""Mesa proprietária: cada robô em teste recebe uma conta de US$ 10 e é avaliado pelas mesmas regras (ideia das empresas que
financiam traders). Robôs que operam em % do próprio capital têm a curva convertida para a escala de US$ 10.

Regras da fase 1 (avaliação):
- perda máxima no dia: 10% da conta (US$ 1) → violação registrada;
- conta abaixo de 50% (US$ 5) → eliminado;
- aprovado para a fase 2 (conta de US$ 50, ainda simulada) com ≥ 30 operações, conta ≥ +10%, nenhuma violação e queda máxima < 30%.
Dinheiro real só por decisão do dono, para quem passar das duas fases.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from . import config

CONTA = 10.0
PERDA_DIA = 0.10
PISO = 0.50
APROVA_OPS = 30
APROVA_GANHO = 0.10
APROVA_QUEDA = 0.30
REPO = Path(__file__).resolve().parent.parent
DESAFIO_INICIO = 1794414944      # regra do dono (2026-11-11): cada robô, carteira própria de US$ 10, tem 24 h para dobrar (US$ 20)
DESAFIO_HORAS = 24


def avaliar(nome, eventos, operacoes_n, inicio=None, nota=""):
    """eventos: [(t_seg, variação relativa do patrimônio)] em ordem. Devolve a ficha do robô na mesa."""
    conta, pico, queda, dias, violacoes, minimo = CONTA, CONTA, 0.0, {}, [], CONTA
    for t, r in eventos:
        antes = conta
        conta *= 1 + r
        minimo = min(minimo, conta)
        pico = max(pico, conta)
        queda = min(queda, conta / pico - 1)
        d = time.strftime("%Y-%m-%d", time.gmtime(t))
        dias[d] = dias.get(d, 0.0) + (conta - antes)
    for d, v in dias.items():
        if v <= -CONTA * PERDA_DIA:
            violacoes.append(d)
    pior_dia = min(dias.values()) if dias else 0.0
    if minimo < CONTA * PISO:                     # passou abaixo do piso em algum momento: eliminado, mesmo que tenha voltado
        status = "❌ eliminado (conta abaixo de US$ 5)"
    elif operacoes_n >= APROVA_OPS and conta >= CONTA * (1 + APROVA_GANHO) and not violacoes and queda > -APROVA_QUEDA:
        status = "🏆 aprovado para a fase 2 (conta de US$ 50)"
    elif violacoes:
        status = f"⚠️ em teste, com {len(violacoes)} violação(ões) de perda diária"
    else:
        status = "🧪 fase 1 em teste"
    fim = DESAFIO_INICIO + DESAFIO_HORAS * 3600
    no_inicio, ate_agora, nas_24h = CONTA, CONTA, CONTA
    for t, r in eventos:                          # a carteira de US$ 10 de cada robô começa no início do desafio e SEGUE depois das 24 h
        if t < DESAFIO_INICIO:                    # (uma régua só: o placar e os lucros realizados mostram o mesmo número)
            no_inicio *= 1 + r
        else:
            ate_agora *= 1 + r
            if t < fim:
                nas_24h *= 1 + r
    if time.time() < fim:
        situacao = "🎯 DOBROU" if ate_agora >= 2 * CONTA else "⏱ em andamento"
    else:
        situacao = (f"🎯 dobrou nas 24 h (US$ {nas_24h:.2f})" if nas_24h >= 2 * CONTA else f"✗ não dobrou nas 24 h (fechou em US$ {nas_24h:.2f})") + \
                   (" · dobrou depois" if ate_agora >= 2 * CONTA and nas_24h < 2 * CONTA else " · a carteira segue")
    desafio = {"carteira": ate_agora, "nas_24h": nas_24h, "meta": 2 * CONTA, "progresso": (ate_agora - CONTA) / CONTA, "fim": fim, "situacao": situacao}
    return {"robo": nome, "conta": conta, "resultado": conta - CONTA, "desafio": desafio, "queda_max": queda, "pior_dia": pior_dia, "operacoes": operacoes_n,
            "violacoes": violacoes, "status": status, "inicio": inicio, "nota": nota,
            "falta": {"operacoes": max(0, APROVA_OPS - operacoes_n), "ganho_us": max(0.0, CONTA * (1 + APROVA_GANHO) - conta)}}


import threading

_git = {"trava": threading.Lock(), "t": 0.0}


def _buscar_estado():
    """git fetch do ramo `estado` no máximo a cada 30 s e nunca dois ao mesmo tempo (vários pedidos disputavam a trava do git)."""
    with _git["trava"]:
        if time.time() - _git["t"] < 30:
            return
        try:
            subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "estado"], capture_output=True, timeout=60)
        except subprocess.SubprocessError:
            pass
        _git["t"] = time.time()


def _git_json(caminho):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"origin/estado:{caminho}"], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None


def _git_texto(caminho):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"origin/estado:{caminho}"], capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else ""


_licoes = {"t": 0.0, "texto": ""}


def licoes():
    """Diário de lições dos robôs (dados/LICOES.md, escrito a cada rodada da nuvem por executor.licoes); em cache por 60 s."""
    if time.time() - _licoes["t"] > 60:
        _buscar_estado()
        _licoes.update(t=time.time(), texto=_git_texto("dados/LICOES.md") or "O diário ainda não foi escrito pela nuvem (sai a cada 15 min).")
    return _licoes["texto"]


def _curva_para_eventos(curva):
    return [(curva[i][0], curva[i][1] / curva[i - 1][1] - 1) for i in range(1, len(curva)) if curva[i - 1][1]]


EXPOSICAO_VELA = 0.06   # todas as moedas na mesma conta: no máximo 6% da conta apostados por vela (3 apostas cheias de 2%)


def _cerebro(estado, nome, outras=None, versao="v1"):
    if not estado:
        return avaliar(nome, [], 0, nota="sem estado ainda")
    ini = estado.get("inicio_ao_vivo")
    ops = [(o["t"], o["liquido"], o["aposta"]) for o in estado.get("operacoes", []) if ini and o["t"] >= ini]
    for x in (outras or {}).values():
        ops += [tuple(o) for o in x.get(versao, {}).get("ops", [])]
    por_vela = {}
    for t, liq, aposta in ops:
        por_vela.setdefault(t, []).append((liq, aposta))
    eventos = []
    for t in sorted(por_vela):
        total = len(por_vela[t]) * 0.02                                 # cada aposta é 2% da conta (aposta = ±1 é só o lado)
        escala = min(1.0, EXPOSICAO_VELA / total) if total else 1.0      # moedas andam juntas: não apostar 33 vezes 2% na mesma vela
        eventos.append((t / 1000 + 900, sum(liq for liq, _ in por_vela[t]) * escala))   # hora em que a aposta é feita (fim da vela do sinal)
    moedas = 1 + len(outras or {})
    return avaliar(nome, eventos, len(ops), ini and time.strftime("%Y-%m-%d", time.gmtime(ini / 1000)),
                   f"contrato binário de 15 min em {moedas} moedas, 2% por aposta e no máximo 6% da conta por vela; só apostas ao vivo")


def _tartaruga(estado, nome):
    if not estado:
        return avaliar(nome, [], 0, nota="sem estado ainda")
    curva = estado.get("curva", [])
    return avaliar(nome, _curva_para_eventos(curva), len(estado.get("fechadas", [])), estado.get("inicio"), "Tartaruga diária, 33 moedas")


INTERVALO_RAPIDO = os.environ.get("ROBO_RAPIDO", "1m")


def _rapido(nome_arq=f"robo_rapido_{INTERVALO_RAPIDO}.json", nome=f"Rápido {INTERVALO_RAPIDO.replace('m', ' min')}",
            nota="conta nativa de US$ 10, perpétuo simulado (compra/venda), no máximo 12 velas", nuvem=False):
    if nuvem:                                       # robô que roda na nuvem do GitHub: estado no ramo `estado`
        e = _git_json(f"dados/{nome_arq}")
        if not e:
            return avaliar(nome, [], 0, nota="esperando a 1ª rodada na nuvem")
    else:
        arq = config.RAIZ / nome_arq
        if not arq.exists():
            return avaliar(nome, [], 0, nota="sem estado ainda")
        e = json.loads(arq.read_text())
    eventos, conta = [], float(e.get("capital_inicial", CONTA))
    for f in sorted(e.get("fechadas", []), key=lambda x: x["saida_t"]):
        eventos.append((f["saida_t"], f["resultado_usd"] / conta))
        conta += f["resultado_usd"]
    return avaliar(nome, eventos, len(e.get("fechadas", [])), e.get("inicio"), nota)


def _funding():
    import sqlite3
    try:
        c = sqlite3.connect(f"file:{config.BANCO}?mode=ro", uri=True, timeout=10)
        linha = c.execute("SELECT estado FROM lab_funding").fetchone()
        c.close()
        e = json.loads(linha[0])
    except (sqlite3.Error, TypeError, ValueError):
        return avaliar("Funding (carry)", [], 0, nota="sem dados")
    eventos = [(time.mktime(time.strptime(d, "%Y-%m-%d")), v) for d, v in sorted(e.get("por_dia", {}).items())]
    return avaliar("Funding (carry)", eventos, len(eventos), "2026-11-07", "operação contínua: conta 1 'operação' por dia fechado")


def _h19():
    arq = config.RAIZ / "h19_vortice.jsonl"
    if not arq.exists():
        return avaliar("Previsor H19", [], 0, nota="sem dados")
    regs = [json.loads(x) for x in arq.read_text().splitlines() if x.strip()]
    apostas = [r for r in regs if r.get("aposta") and r.get("resolvida") and r.get("acertou") is not None]
    eventos = [(r["t"] / 1000, 0.02 * ((1 / 0.51 - 1) if r["acertou"] else -1)) for r in apostas]
    return avaliar("Previsor H19", eventos, len(apostas), None, "aposta binária simulada, 2% por aposta a 0,51")


_cm = {"t": 0, "dados": None}


def cerebros_por_moeda():
    """Placar ao vivo de cada cérebro v1, v2 e v3, moeda por moeda (BTC + as outras 32), para a aba Robô (guardado por 60 s)."""
    if time.time() - _cm["t"] < 60 and _cm["dados"]:
        return _cm["dados"]
    _cm.update(t=time.time(), dados=_cerebros_por_moeda())
    return _cm["dados"]


def _cerebros_por_moeda():
    _buscar_estado()
    linhas = []
    for nome_arq, versao in (("dados/cerebro.json", "v1"), ("dados/cerebro_v2.json", "v2"), ("dados/cerebro_v3.json", "v3")):
        e = _git_json(nome_arq) or {}
        ini = e.get("inicio_ao_vivo")
        ops = [[o["t"], o["liquido"], o["aposta"]] for o in e.get("operacoes", []) if ini and o["t"] >= ini]
        linhas.append(("BTCUSDT", versao, ops))
    for par, x in sorted((_git_json("dados/cerebros_moedas.json") or {}).items()):
        for versao in ("v1", "v2", "v3"):
            linhas.append((par, versao, x.get(versao, {}).get("ops", [])))
    saida, ultimas_v3 = {}, []
    for par, versao, ops in linhas:
        if versao == "v3":
            ultimas_v3.extend({"moeda": par[:-4], "t": o[0], "lado": "sobe" if o[2] > 0 else "desce", "liquido": o[1]} for o in ops[-30:])
        ultima = ops[-1] if ops else None
        saida.setdefault(par, {"moeda": par[:-4]})[versao] = {
            "apostas": len(ops), "acertos": sum(1 for o in ops if o[1] > 0), "resultado": sum(o[1] for o in ops),
            "ultima": ultima and {"t": ultima[0], "lado": "sobe" if ultima[2] > 0 else "desce", "ganhou": ultima[1] > 0}}
    ultimas_v3.sort(key=lambda x: -x["t"])
    return {"t": time.time(), "ultimas_v3": ultimas_v3[:40], "moedas": sorted(saida.values(), key=lambda m: -sum(m.get(v, {}).get("apostas", 0) for v in ("v1", "v2", "v3")))}


_sinais = {"t": 0, "dados": []}


def sinais_v3():
    """Apostas em aberto do Cérebro v3 em cada moeda (vela de 15 min que acabou de fechar), para o scalper seguir.
    [{par, t (abertura da vela fechada, ms), px, prob, lado}] — só as que apostam (prob ≥ 52% para um lado)."""
    if time.time() - _sinais["t"] < 60:
        return _sinais["dados"]
    _buscar_estado()
    saida = []
    btc = _git_json("dados/cerebro_v3.json") or {}
    fontes = [("BTCUSDT", btc.get("pendente"))] + [(par, x.get("v3", {}).get("pendente")) for par, x in (_git_json("dados/cerebros_moedas.json") or {}).items()]
    for par, p in fontes:
        if p and p.get("aposta"):
            saida.append({"par": par, "t": p["t"], "px": p["px"], "prob": p["prob"], "lado": "compra" if p["aposta"] > 0 else "venda"})
    _sinais.update(t=time.time(), dados=saida)
    return saida


_sinais_v4 = {"t": 0, "dados": []}


def sinais_v4(limiar=0.03):
    """Apostas em aberto do Cérebro v4 (LightGBM, nuvem) na vela de 15 min que acabou de fechar: [{par, t, px, prob, lado}].
    Decisão do dono (2026-11-13): todos os robôs seguem o cérebro de mais lucro. `limiar` = |p − 0,5| mínimo (0,03 = todas as apostas do v4)."""
    if time.time() - _sinais_v4["t"] < 60:
        return _sinais_v4["dados"]
    _buscar_estado()
    saida = []
    for par, p in ((_git_json("dados/cerebro_v4.json") or {}).get("pendentes") or {}).items():
        if abs(p["prob"] - 0.5) >= limiar:
            saida.append({"par": par, "t": p["t"], "px": p["px"], "prob": p["prob"], "lado": "compra" if p["aposta"] > 0 else "venda"})
    _sinais_v4.update(t=time.time(), dados=saida)
    return saida


_v3_ops = {"t": 0, "ops": []}


def realizados():
    """Todas as operações FECHADAS dos robôs que operam no dia (Rápido, Scalper e as apostas do Cérebro v3), numa lista só,
    com o total realizado hoje (dia UTC) de cada um — o que o dono quer ver: lucro realizado, não só o saldo."""
    saida = []
    for arq, robo in (("robo_minerador.json", "⛏ Minerador"),
                      ("robo_v4_perp.json", "🌲 Rápido nuvem"), ("robo_v4_cacador.json", "🎯 Caçador"), ("robo_v4_testnet.json", "🧪 v4 Testnet"), ("robo_scalper_nuvem.json", "✂ Scalper nuvem"),
                      ("robo_claude.json", "🤖 Robô Claude")):
        try:
            e = _git_json(f"dados/{arq}") if arq.startswith(("robo_minerador", "robo_v4_", "robo_claude", "robo_scalper_nuvem")) else json.loads((config.RAIZ / arq).read_text())
        except (OSError, ValueError):
            continue
        if not e:
            continue
        for f in e.get("fechadas", [])[-80:]:
            saida.append({"robo": robo, "t": f["saida_t"], "moeda": f["moeda"].replace("USDT", ""), "lado": f.get("lado", "compra"),
                          "resultado": f["resultado_usd"], "motivo": f.get("motivo", "")})
    # (2026-11-13) as apostas de contrato binário dos cérebros v3/v4 saíram desta lista, junto com as contas deles no placar (decisão do dono)
    saida = [x for x in saida if x.get("t_entrada", x["t"]) >= DESAFIO_INICIO]   # a mesma régua da mesa: o que cada carteira fez desde o início do desafio
    saida.sort(key=lambda x: -x["t"])
    hoje = time.strftime("%Y-%m-%d", time.gmtime())
    totais = {}
    for x in saida:
        tt = totais.setdefault(x["robo"], {"lucro": 0.0, "ganhos": 0, "perdas": 0, "soma_lista": 0.0})
        tt["soma_lista"] += x["resultado"]
        tt["ganhos" if x["resultado"] > 0 else "perdas"] += 1
    try:                                                                  # UMA régua só: o lucro de cada robô é a carteira do placar − US$ 10
        regua = {f["robo"]: f["desafio"]["carteira"] - CONTA for f in mesa()["fichas"] if f.get("desafio")}
    except Exception:
        regua = {}
    for robo, tt in totais.items():
        nome = robo.split(" ", 1)[-1]                                      # "🌲 Cérebro v4" → "Cérebro v4"
        tt["lucro"] = next((v for k, v in regua.items() if k.startswith(nome)), tt["soma_lista"])
    return {"t": time.time(), "hoje": hoje, "desde": DESAFIO_INICIO, "totais": totais, "operacoes": saida[:120]}


_cache = {"t": 0, "dados": None}


def mesa():
    if time.time() - _cache["t"] < 60 and _cache["dados"]:
        return _cache["dados"]
    _buscar_estado()
    outras = _git_json("dados/cerebros_moedas.json") or {}
    fichas = [
        _rapido("robo_minerador.json", "Minerador (H28)", "☁ na nuvem 24 h: movimento forte com volume baixo reverte; 15 min, 33 moedas, compra e venda", nuvem=True),
        _rapido("robo_v4_perp.json", "Rápido nuvem (cérebro v4)", "☁ na nuvem 24 h: TODAS as apostas do Cérebro v4 no perpétuo simulado; US$ 25 a 10×, stop 1%, lucro realizado +US$ 0,50, sai no fim da vela (H37, agressivo)", nuvem=True),
        _rapido("robo_claude.json", "Robô Claude (decide de hora em hora)", "☁ o Claude lê o retrato do mercado (tendência de 24 h e 4 h, amplitude, líderes, v4) e a cartilha, decide compras e vendas de horas e escreve uma lição por decisão; executor com stop 1,5%, até 4 posições, US$ 25 a 10× (H43)", nuvem=True),
        _rapido("robo_v4_cacador.json", "Caçador (v4: 2 compras e 2 vendas por vela)", "☁ na nuvem 24 h: a cada vela caça entre todas as moedas as 2 com maior chance de subir (compra) e as 2 com maior chance de cair (venda), pelo cérebro v4; sempre posicionado; mesmas regras do Rápido nuvem (H37)", nuvem=True),
        _rapido("robo_v4_testnet.json", "v4 Testnet (Binance)", "☁ na nuvem 24 h: TESTNET de futuros da Binance, todas as apostas do v4, ordens reais na conta de teste (US$ 10 a 10×, stop 1%); resultado em US$ de preenchimento real", nuvem=True),
        _rapido("robo_scalper_nuvem.json", "Scalper nuvem (alvo +0,5%)", "☁ na nuvem 24 h: apostas do v4 com a regra de tendência do dono; lucro realizado em +0,5%, stop −1,5%, segura enquanto a tendência e o v4 concordam (15/11: saiu da máquina local)", nuvem=True),
    ]
    # (15/11) Funding (carry) saiu do placar: fica parado em US$ 10 sem operar (dono: "tire os robôs que não operam")
    # Decisão do dono (2026-11-13): as contas de contrato binário (cérebros v1–v4) saem do placar — o produto é bloqueado no Brasil.
    # Os cérebros continuam rodando na nuvem como fonte de sinal (o v4 é o cérebro de todos os robôs); a tabela de acerto fica na aba de pesquisa.
    ordem = {"🏆": 0, "🧪": 1, "⚠️": 2, "❌": 3}
    fichas.sort(key=lambda f: (ordem.get(f["status"][:2].strip(), ordem.get(f["status"][0], 9)), -f["conta"]))
    dados = {"t": time.time(), "fichas": fichas,
             "regras": {"conta": CONTA, "perda_dia": CONTA * PERDA_DIA, "piso": CONTA * PISO, "aprova_ops": APROVA_OPS,
                        "aprova_conta": CONTA * (1 + APROVA_GANHO), "aprova_queda": APROVA_QUEDA}}
    _cache.update(t=time.time(), dados=dados)
    return dados


_nuvem = {"t": 0.0, "dados": None}
_precos = {"t": 0.0, "px": {}}
ROBOS_NUVEM = (("robo_claude.json", "🤖 Robô Claude (decide de hora em hora)"), ("robo_livre.json", "🦅 Robô Livre (sem regras, 20×)"), ("robo_v4_cacador.json", "🎯 Caçador"), ("robo_v4_perp.json", "🌲 Rápido nuvem"),
               ("robo_scalper_nuvem.json", "✂ Scalper nuvem"), ("robo_scalper_b.json", "✂ Scalper B (sem alvo)"), ("robo_scalper_c.json", "✂ Scalper C (só confiantes)"), ("robo_minerador.json", "⛏ Minerador"), ("robo_v4_testnet.json", "🧪 v4 Testnet (Binance)"))


def _precos_agora():
    if time.time() - _precos["t"] > 10:
        try:
            import urllib.request
            with urllib.request.urlopen("https://data-api.binance.vision/api/v3/ticker/price", timeout=20) as r:
                _precos.update(t=time.time(), px={x["symbol"]: float(x["price"]) for x in json.load(r)})
        except (OSError, ValueError):
            pass
    return _precos["px"]


def nuvem():
    """Robôs da nuvem para o painel: posições abertas com o preço de agora, últimas operações e eventos, e o retrato do mercado."""
    if time.time() - _nuvem["t"] < 10 and _nuvem["dados"]:
        return _nuvem["dados"]
    _buscar_estado()
    px = _precos_agora()
    robos = []
    for arq, nome in ROBOS_NUVEM:
        e = _git_json(f"dados/{arq}")
        if not e:
            continue
        abertas = []
        for par, p in (e.get("abertas") or {}).items():
            lado = "venda" if p.get("lado") in ("venda", "SELL") else "compra"
            ent = float(p.get("entrada") or 0)
            agora = px.get(par if par.endswith("USDT") else par + "USDT")
            noc = p.get("nocional") or (p.get("qtd", 0) * ent if p.get("qtd") else 25.0)
            if p.get("stop_pct") is None and "margem" in p:            # Robô Livre: sem stop; a linha vermelha é a liquidação
                p = {**p, "stop_pct": 0.045}
            res = (1 if lado == "compra" else -1) * noc * (agora / ent - 1) if agora and ent else None
            t0 = p.get("entrada_t") or p.get("t")
            abertas.append({"moeda": par.replace("USDT", ""), "lado": lado, "entrada": ent, "agora": agora, "resultado_usd": res,
                            "resultado_pct": (res / noc * 100) if res is not None and noc else None, "desde": t0,
                            "stop": ent * (1 + (p.get("stop_pct") or 0.01)) if lado == "venda" else ent * (1 - (p.get("stop_pct") or 0.01)) if ent else None,
                            "motivo": (p.get("motivo") or "")[:140]})
        fech = sorted(e.get("fechadas", []), key=lambda f: f.get("saida_t", 0))[-6:][::-1]
        carteira = e.get("patrimonio", e.get("carteira"))
        robos.append({"alerta": e.get("alerta_rotina"), "nome": nome, "carteira": carteira, "sem_custo": e.get("patrimonio_sem_custo"), "regime": (e.get("regime") or {}).get("lado") if isinstance(e.get("regime"), dict) else e.get("regime"),
                      "abertas": abertas, "n_fechadas": len(e.get("fechadas", [])),
                      "fechadas": [{"moeda": f["moeda"].replace("USDT", ""), "lado": f.get("lado"), "resultado_usd": f.get("resultado_usd"), "t": f.get("saida_t"),
                                    "motivo": (f.get("motivo_saida") or f.get("motivo") or "")[:60]} for f in fech],
                      "eventos": [x for x in (e.get("eventos") or [])[:4]]})
    retrato = _git_json("dados/mercado_agora.json") or {}
    dados = {"t": time.time(), "robos": robos, "retrato": {k: retrato.get(k) for k in ("hora_utc", "mercado_24h", "mercado_4h", "btc", "contexto")}}
    _nuvem.update(t=time.time(), dados=dados)
    return dados


# ---------------- Sala de operações (fusão com o OpenBot: baleias.equipe) ----------------

_enviadas = []          # mensagens do dono já enviadas e ainda não vistas na sala da nuvem (mostra "enviada, aguardando a rodada")


def sala_painel(forcar=False):
    """Sala da mesa para o painel: equipe (carteira, posições, ordem vigente), linha do tempo das conversas e eventos."""
    from . import equipe
    if forcar:
        _git["t"] = 0.0
    _buscar_estado()
    sala = _git_json("dados/sala.json") or []
    ordens = _git_json("dados/ordens.json") or {}
    estados = {a["arquivo"]: _git_json(f"dados/{a['arquivo']}") for a in equipe.EQUIPE}
    agora = time.time()
    time_ = []
    for a in equipe.EQUIPE:
        e = estados.get(a["arquivo"])
        if not e:
            continue
        o = ordens.get(a["id"])
        o = o if o and o.get("acao") != "liberar" and o.get("ate", 0) > agora else None
        time_.append({"id": a["id"], "nome": a["nome"], "avatar": a["avatar"], "motor": a["motor"], "missao": a["missao"],
                      "carteira": e.get("patrimonio", e.get("carteira")), "sem_custo": e.get("patrimonio_sem_custo"), "abertas": len(e.get("abertas") or {}),
                      "fechadas": len(e.get("fechadas") or []), "alerta": e.get("alerta_rotina"),
                      "ordem": {"acao": equipe.ACOES.get(o["acao"], o["acao"]), "motivo": o.get("motivo", ""), "ate": o.get("ate")} if o else None})
    ids = {x["id"] for x in sala}
    _enviadas[:] = [m for m in _enviadas if m["id"] not in ids and agora - m["t"] < 6 * 3600]
    return {"t": agora, "equipe": time_, "sala": sala[-300:], "aguardando": list(_enviadas)}


def enviar_ao_chefe(texto, para="claude"):
    """O dono escreve no painel → um arquivo novo em dados/caixa/ no ramo estado, pela API do GitHub (um arquivo por mensagem: nunca
    conflita com a gravação da nuvem). A rodada seguinte da nuvem põe a mensagem na sala; a rotina do Claude responde na hora seguinte."""
    import base64
    from . import equipe
    texto = str(texto or "").strip()
    if not texto:
        return {"erro": "mensagem vazia"}
    caminho, m = equipe.nova_mensagem_dono(texto, para=para)
    url = subprocess.run(["git", "-C", str(REPO), "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    repo = url.removesuffix(".git").split("github.com/")[-1].replace(":", "/")
    corpo = json.dumps({"message": "dono escreveu na sala", "branch": "estado",
                        "content": base64.b64encode(json.dumps(m, ensure_ascii=False).encode()).decode()})
    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{caminho}", "--input", "-"], input=corpo,
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {"erro": (r.stderr or r.stdout or "falha no gh")[:300]}
    _enviadas.append(m)
    return {"ok": True, "mensagem": m}
