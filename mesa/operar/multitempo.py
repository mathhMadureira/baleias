"""Varredura em todos os tempos gráficos, de 1 s a 1 dia (pedido do dono, 18/11) — usada por operar.py (agentes) e pelo universo.py do chefe.

Por moeda (dados públicos da Binance à vista, só leitura):
  - janelas de 1 s, 5 s, 15 s, 1 min, 5 min e 15 min: variação até agora, das velas de 1 s dos últimos ~16 min;
    z = variação ÷ (desvio dos retornos de 1 s × √segundos) — z ≥ 2 em módulo = movimento fora do normal naquela janela;
  - 1 h (velas de 1 min), 4 h e 1 dia (velas de 1 h): variação até agora;
  - tendência: preço acima ou abaixo da média de 20 velas em 1 min, 5 min, 15 min, 1 h, 4 h e 1 dia;
  - volume da última vela de 1 min ÷ média das 20 anteriores.
Lembrete do laboratório (H56, 16/11): entrar só pela leitura de 1 s perdeu para o custo nas 3 regras testadas; isto é informação, não gatilho.
"""
import json
import math
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/home/servidor-de-producao/baleias")
from lab import padroes_graficos as PG  # noqa: E402  (mesmas definições objetivas da H45)

DADOS = "https://data-api.binance.vision/api/v3/klines"
JANELAS_1S = (("1s", 1), ("5s", 5), ("15s", 15), ("1m", 60), ("5m", 300), ("15m", 900))
TEMPOS_MM = ("1m", "5m", "15m", "1h", "4h", "1d")
TEMPOS_PADRAO = ("15m", "1h", "4h")          # padrões gráficos clássicos (topo/fundo duplo, OCO, triângulo, bandeira, virada de estrutura)
CURTO = {"topo duplo": "TD", "fundo duplo": "FD", "ombro-cabeça-ombro": "OCO", "OCO invertido": "OCOi", "triângulo simétrico": "TRI",
         "triângulo ascendente": "TRIa", "triângulo descendente": "TRId", "bandeira": "BAND", "virada de estrutura": "VIR"}


def _k(par, iv, limite):
    with urllib.request.urlopen(urllib.request.Request(f"{DADOS}?symbol={par}&interval={iv}&limit={limite}", headers={"User-Agent": "baleias/1.0"}),
                                timeout=25) as r:
        return json.load(r)


def ler(par):
    """Leitura de uma moeda; None se faltar dado (a moeda fica fora da tabela, nada é inventado)."""
    try:
        s = _k(par, "1s", 1000)
        velas = {iv: _k(par, iv, 61 if iv == "1m" else 100 if iv in TEMPOS_PADRAO else 25) for iv in TEMPOS_MM}
    except (OSError, ValueError):
        return None
    if len(s) < 120 or any(len(v) < 21 for v in velas.values()):
        return None
    t = [x[0] // 1000 for x in s]
    c = [float(x[4]) for x in s]
    agora_px, agora_t = c[-1], t[-1]
    rets = [math.log(c[i] / c[i - 1]) / math.sqrt(max(1, t[i] - t[i - 1])) for i in range(1, len(c)) if c[i - 1] > 0]
    sig = (sum(r * r for r in rets) / len(rets)) ** 0.5 if rets else 0.0
    out = {"par": par, "preco": agora_px, "var": {}, "z": {}, "acima_mm20": {}}
    for nome, w in JANELAS_1S:
        ref = next((c[i] for i in range(len(t) - 1, -1, -1) if t[i] <= agora_t - w), None)
        if ref:
            v = agora_px / ref - 1
            out["var"][nome] = round(v * 100, 3)
            out["z"][nome] = round(v / (sig * math.sqrt(w)), 1) if sig else None
    m1, h1 = velas["1m"], velas["1h"]
    for nome, k, n in (("1h", m1, 60), ("4h", h1, 4), ("1d", h1, 24)):
        if len(k) > n:
            out["var"][nome] = round((agora_px / float(k[-1 - n][4]) - 1) * 100, 3)
    for iv in TEMPOS_MM:
        fech = [float(x[4]) for x in velas[iv][-21:-1]]             # 20 velas fechadas antes da atual
        out["acima_mm20"][iv] = agora_px > sum(fech) / len(fech)
    vol = [float(x[7]) for x in m1[-22:-1]]
    out["vol_1m_rel"] = round(vol[-1] / (sum(vol[:-1]) / 20), 2) if sum(vol[:-1]) else None
    out["padroes"] = []
    for iv in TEMPOS_PADRAO:                                         # só velas fechadas: a última da lista ainda está aberta
        k = velas[iv][:-1]
        try:
            achados = PG.detectar([float(x[1]) for x in k], [float(x[2]) for x in k], [float(x[3]) for x in k], [float(x[4]) for x in k])
        except Exception:
            achados = []
        for a in achados:
            out["padroes"].append({"tempo": iv, "padrao": a.get("padrao"), "sentido": a.get("sentido"), "confirmado": bool(a.get("confirmado"))})
    h1 = velas["1h"][-25:-1]
    mx, mn = max(float(x[2]) for x in h1), min(float(x[3]) for x in h1)
    out["dist_max24h"], out["dist_min24h"] = round((agora_px / mx - 1) * 100, 2), round((agora_px / mn - 1) * 100, 2)
    out["t"] = int(time.time())
    return out


def varrer(pares, max_moedas=12):
    pares = list(dict.fromkeys(pares))[:max_moedas]
    with ThreadPoolExecutor(6) as ex:
        return [x for x in ex.map(ler, pares) if x]


def curto(nome):
    nome = str(nome or "")
    for k, v in (("bandeira", "BAND"), ("triângulo", "TRI"), ("estrutura", "EST"), ("virada", "EST")):
        if nome.startswith(k):
            return v
    return CURTO.get(nome, nome)


def tabela(leituras):
    """Texto (markdown) para o agente e para o recibo."""
    cols = [n for n, _ in JANELAS_1S] + ["1h", "4h", "1d"]
    linhas = ["| moeda | " + " | ".join(cols) + " | acima da MM20 (1m 5m 15m 1h 4h 1d) | vol 1 min | até máx/mín 24 h | padrões (tempo:código↑↓, * = confirmado) |",
              "|" + "---|" * (len(cols) + 5)]
    for x in leituras:
        cel = []
        for n in cols:
            v, z = x["var"].get(n), x["z"].get(n)
            cel.append("—" if v is None else f"{v:+.2f}%" + ("!" if z is not None and abs(z) >= 2 else ""))
        mm = " ".join("↑" if x["acima_mm20"][iv] else "↓" for iv in TEMPOS_MM)
        pad = " ".join(f"{q['tempo']}:{curto(q['padrao'])}{'↑' if q['sentido'] == 'alta' else '↓'}{'*' if q['confirmado'] else ''}"
                       for q in x.get("padroes", [])) or "—"
        linhas.append(f"| {x['par'][:-4]} | " + " | ".join(cel) + f" | {mm} | {x.get('vol_1m_rel')}× | {x.get('dist_max24h')}% / +{x.get('dist_min24h')}% | {pad} |")
    legenda = ("(! = movimento fora do normal naquela janela, |z| ≥ 2 pela volatilidade de 1 s; ↑/↓ = preço acima/abaixo da média de 20 velas; padrões: "
               "TD topo duplo, FD fundo duplo, OCO/OCOi ombro-cabeça-ombro (invertido), TRI triângulo, BAND bandeira, EST estrutura de topos e fundos; "
               "↑ alta ↓ baixa; * confirmado. H45: nenhuma família passou como regra sozinha em 1 h — use como contexto, não como gatilho)")
    return "\n".join(linhas) + "\n" + legenda
