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
    no_inicio, ate_agora = CONTA, CONTA
    for t, r in eventos:                          # desafio de 24 h: a carteira de US$ 10 começa no início do desafio
        if t < DESAFIO_INICIO:
            no_inicio *= 1 + r
        elif t < DESAFIO_INICIO + DESAFIO_HORAS * 3600:
            ate_agora *= 1 + r
    fim = DESAFIO_INICIO + DESAFIO_HORAS * 3600
    desafio = {"carteira": ate_agora, "meta": 2 * CONTA, "progresso": (ate_agora - CONTA) / CONTA, "fim": fim,
               "situacao": "🎯 DOBROU" if ate_agora >= 2 * CONTA else ("⏱ em andamento" if time.time() < fim else "✗ não dobrou")}
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
        eventos.append((t / 1000, sum(liq for liq, _ in por_vela[t]) * escala))
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


_v3_ops = {"t": 0, "ops": []}


def realizados():
    """Todas as operações FECHADAS dos robôs que operam no dia (Rápido, Scalper e as apostas do Cérebro v3), numa lista só,
    com o total realizado hoje (dia UTC) de cada um — o que o dono quer ver: lucro realizado, não só o saldo."""
    saida = []
    for arq, robo in ((f"robo_rapido_{INTERVALO_RAPIDO}.json", "⚡ Rápido"), ("robo_scalper.json", "✂ Scalper"), ("robo_minerador.json", "⛏ Minerador")):
        try:
            e = _git_json(f"dados/{arq}") if arq == "robo_minerador.json" else json.loads((config.RAIZ / arq).read_text())
        except (OSError, ValueError):
            continue
        if not e:
            continue
        for f in e.get("fechadas", [])[-80:]:
            saida.append({"robo": robo, "t": f["saida_t"], "moeda": f["moeda"].replace("USDT", ""), "lado": f.get("lado", "compra"),
                          "resultado": f["resultado_usd"], "motivo": f.get("motivo", "")})
    if time.time() - _v3_ops["t"] > 60:
        _buscar_estado()
        ops = [("BTC", o["t"], o["liquido"], o["aposta"]) for o in (_git_json("dados/cerebro_v3.json") or {}).get("operacoes", [])[-40:]]
        for par, x in (_git_json("dados/cerebros_moedas.json") or {}).items():
            ops += [(par.replace("USDT", ""), o[0], o[1], o[2]) for o in x.get("v3", {}).get("ops", [])[-40:]]
        _v3_ops.update(t=time.time(), ops=ops)
    por_vela = {}
    for o in _v3_ops["ops"]:
        por_vela[o[1]] = por_vela.get(o[1], 0) + 1
    for moeda, t, liquido, aposta in _v3_ops["ops"]:
        escala = min(1.0, EXPOSICAO_VELA / (por_vela[t] * 0.02))           # o mesmo limite da mesa: no máximo 6% da conta por vela
        saida.append({"robo": "🧠 Cérebro v3", "t": t / 1000 + 1800, "moeda": moeda, "lado": "compra" if aposta > 0 else "venda",
                      "resultado": liquido * CONTA * escala, "motivo": "aposta de 15 min " + ("ganha" if liquido > 0 else "perdida")})
    saida.sort(key=lambda x: -x["t"])
    hoje = time.strftime("%Y-%m-%d", time.gmtime())
    totais = {}
    for x in saida:
        if time.strftime("%Y-%m-%d", time.gmtime(x["t"])) == hoje:
            tt = totais.setdefault(x["robo"], {"lucro": 0.0, "ganhos": 0, "perdas": 0})
            tt["lucro"] += x["resultado"]
            tt["ganhos" if x["resultado"] > 0 else "perdas"] += 1
    return {"t": time.time(), "hoje": hoje, "totais": totais, "operacoes": saida[:120]}


_cache = {"t": 0, "dados": None}


def mesa():
    if time.time() - _cache["t"] < 60 and _cache["dados"]:
        return _cache["dados"]
    _buscar_estado()
    outras = _git_json("dados/cerebros_moedas.json") or {}
    fichas = [
        _tartaruga(_git_json("dados/robo_tartaruga.json"), "Diário (Tartaruga)"),
        _tartaruga(_git_json("dados/teto6/robo_tartaruga.json"), "Sombra (teto de 6)"),
        _rapido(),
        _rapido("robo_minerador.json", "Minerador (H28)", "☁ na nuvem 24 h: movimento forte com volume baixo reverte; 15 min, 33 moedas, compra e venda", nuvem=True),
        _rapido("robo_scalper.json", "Scalper", "segue as apostas do Cérebro v3 (15 min); alvo +0,5%, stop −0,5%, sai no fim da vela apostada"),
        _cerebro(_git_json("dados/cerebro.json"), "Cérebro v1", outras, "v1"),
        _cerebro(_git_json("dados/cerebro_v2.json"), "Cérebro v2", outras, "v2"),
        _cerebro(_git_json("dados/cerebro_v3.json"), "Cérebro v3 (humor do mercado)", outras, "v3"),
        _funding(),
        _h19(),
    ]
    ordem = {"🏆": 0, "🧪": 1, "⚠️": 2, "❌": 3}
    fichas.sort(key=lambda f: (ordem.get(f["status"][:2].strip(), ordem.get(f["status"][0], 9)), -f["conta"]))
    dados = {"t": time.time(), "fichas": fichas,
             "regras": {"conta": CONTA, "perda_dia": CONTA * PERDA_DIA, "piso": CONTA * PISO, "aprova_ops": APROVA_OPS,
                        "aprova_conta": CONTA * (1 + APROVA_GANHO), "aprova_queda": APROVA_QUEDA}}
    _cache.update(t=time.time(), dados=dados)
    return dados
