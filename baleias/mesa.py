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


def avaliar(nome, eventos, operacoes_n, inicio=None, nota=""):
    """eventos: [(t_seg, variação relativa do patrimônio)] em ordem. Devolve a ficha do robô na mesa."""
    conta, pico, queda, dias, violacoes = CONTA, CONTA, 0.0, {}, []
    for t, r in eventos:
        antes = conta
        conta *= 1 + r
        pico = max(pico, conta)
        queda = min(queda, conta / pico - 1)
        d = time.strftime("%Y-%m-%d", time.gmtime(t))
        dias[d] = dias.get(d, 0.0) + (conta - antes)
    for d, v in dias.items():
        if v <= -CONTA * PERDA_DIA:
            violacoes.append(d)
    pior_dia = min(dias.values()) if dias else 0.0
    if conta < CONTA * PISO:
        status = "❌ eliminado (conta abaixo de US$ 5)"
    elif operacoes_n >= APROVA_OPS and conta >= CONTA * (1 + APROVA_GANHO) and not violacoes and queda > -APROVA_QUEDA:
        status = "🏆 aprovado para a fase 2 (conta de US$ 50)"
    elif violacoes:
        status = f"⚠️ em teste, com {len(violacoes)} violação(ões) de perda diária"
    else:
        status = "🧪 fase 1 em teste"
    return {"robo": nome, "conta": conta, "resultado": conta - CONTA, "queda_max": queda, "pior_dia": pior_dia, "operacoes": operacoes_n,
            "violacoes": violacoes, "status": status, "inicio": inicio, "nota": nota,
            "falta": {"operacoes": max(0, APROVA_OPS - operacoes_n), "ganho_us": max(0.0, CONTA * (1 + APROVA_GANHO) - conta)}}


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
            nota="conta nativa de US$ 10, perpétuo simulado (compra/venda), no máximo 12 velas"):
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


_cache = {"t": 0, "dados": None}


def mesa():
    if time.time() - _cache["t"] < 60 and _cache["dados"]:
        return _cache["dados"]
    subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "estado"], capture_output=True, timeout=60)
    outras = _git_json("dados/cerebros_moedas.json") or {}
    fichas = [
        _tartaruga(_git_json("dados/robo_tartaruga.json"), "Diário (Tartaruga)"),
        _tartaruga(_git_json("dados/teto6/robo_tartaruga.json"), "Sombra (teto de 6)"),
        _rapido(),
        _rapido("robo_scalper.json", "Scalper", "H24: mesmas entradas do cérebro; alvo +1,0%, stop −0,5%, 30 min"),
        _cerebro(_git_json("dados/cerebro.json"), "Cérebro v1", outras, "v1"),
        _cerebro(_git_json("dados/cerebro_v2.json"), "Cérebro v2", outras, "v2"),
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
