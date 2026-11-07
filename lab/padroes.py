"""Hipótese 6: padrões de vela e de mercado no BTC, com probabilidade medida no treino e conferida no teste (lab/PROTOCOLO_LAB.md)."""
import json
import math
import statistics as st
import time
import urllib.error
import urllib.request

from baleias import config

CACHE = config.RAIZ / "lab" / "btc_15m.json"
INICIO_MS = 1_577_836_800_000          # 2020-01-01
FIM_TREINO = "2024-01-01"
HORIZONTES = {"15min": 1, "1h": 4, "4h": 16}
CUSTO_PCT = 0.2
T_TREINO, T_TESTE, MIN_CASOS = 3.2, 2.0, 30


def baixar():
    if CACHE.exists():
        return [tuple(x) for x in json.loads(CACHE.read_text())]
    saida, t, fim = [], INICIO_MS, int(time.time() * 1000)
    while t < fim:
        for tentativa in range(6):
            try:
                url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime={t}&limit=1000"
                with urllib.request.urlopen(url, timeout=40) as r:
                    lote = json.load(r)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(10 * (tentativa + 1))
        else:
            raise RuntimeError("Binance indisponível")
        if not lote:
            break
        saida += [(v[0], float(v[1]), float(v[2]), float(v[3]), float(v[4]), float(v[5])) for v in lote]
        t = lote[-1][0] + 900_000
        time.sleep(0.2)
    saida = saida[:-1]  # a última vela ainda está aberta
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(saida))
    return saida


def _ema(xs, n):
    a, saida, m = 2 / (n + 1), [], xs[0]
    for x in xs:
        m = a * x + (1 - a) * m
        saida.append(m)
    return saida


def _rsi(c, n=14):
    saida, g, p = [50.0] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        p = (p * (n - 1) + max(-d, 0)) / n
        saida[i] = 100 if p == 0 else 100 - 100 / (1 + g / p)
    return saida


def detectar(v):
    """Lista, por vela, os padrões ativos no fechamento dela (só usa velas até i)."""
    o, h, l, c, vol = ([x[k] for x in v] for k in (1, 2, 3, 4, 5))
    e20, e50, rsi = _ema(c, 20), _ema(c, 50), _rsi(c)
    rets = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    ativos = [[] for _ in v]
    for i in range(100, len(v)):
        corpo, faixa = abs(c[i] - o[i]), h[i] - l[i]
        if faixa <= 0:
            continue
        sup, inf = h[i] - max(o[i], c[i]), min(o[i], c[i]) - l[i]
        alta, baixa = c[i] > o[i], c[i] < o[i]
        alta_ant, baixa_ant = c[i - 1] > o[i - 1], c[i - 1] < o[i - 1]
        p = ativos[i]
        if alta and baixa_ant and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
            p.append("engolfo_alta")
        if baixa and alta_ant and c[i] <= o[i - 1] and o[i] >= c[i - 1]:
            p.append("engolfo_baixa")
        if inf >= 2 * corpo and sup <= 0.3 * faixa and corpo > 0:
            p.append("martelo")
        if sup >= 2 * corpo and inf <= 0.3 * faixa and corpo > 0:
            p.append("estrela_cadente")
        if corpo <= 0.1 * faixa:
            p.append("doji")
        if all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2]:
            p.append("tres_soldados")
        if all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2]:
            p.append("tres_corvos")
        if h[i] < h[i - 1] and l[i] > l[i - 1]:
            p.append("inside_bar")
        if corpo >= 0.9 * faixa:
            p.append("marubozu_alta" if alta else "marubozu_baixa")
        if e20[i] > e50[i] and c[i] > e20[i]:
            p.append("tendencia_alta")
        if e20[i] < e50[i] and c[i] < e20[i]:
            p.append("tendencia_baixa")
        if c[i] > max(h[i - 20:i]):
            p.append("rompe_maxima_20")
        if c[i] < min(l[i - 20:i]):
            p.append("rompe_minima_20")
        if rsi[i] < 30:
            p.append("rsi_abaixo_30")
        if rsi[i] > 70:
            p.append("rsi_acima_70")
        if vol[i] > 3 * st.fmean(vol[i - 96:i]):
            p.append("volume_3x")
        dp = st.pstdev(rets[i - 96:i])
        if dp > 0 and rets[i] > 3 * dp:
            p.append("alta_forte")
        if dp > 0 and rets[i] < -3 * dp:
            p.append("queda_forte")
    return ativos


def _stats(xs):
    if len(xs) < 2:
        return {"casos": len(xs)}
    m, dp = st.fmean(xs), st.stdev(xs)
    return {"casos": len(xs), "chance_alta": round(sum(x > 0 for x in xs) / len(xs), 3), "retorno_medio_pct": round(m, 4),
            "t": round(m / (dp / math.sqrt(len(xs))), 2) if dp > 0 else 0.0}


def medir(v, ativos, inicio_ms=None, fim_ms=None, passo_ms=None):
    """Retornos sem sobreposição: um caso novo do mesmo padrão só depois de passado o horizonte do anterior.
    Com passo_ms, ignora casos cujo horizonte atravessa um buraco (ex.: a noite entre dois pregões)."""
    c = [x[4] for x in v]
    nomes = sorted({p for a in ativos for p in a})
    saida = {}
    for nome in nomes:
        for hz, n in HORIZONTES.items():
            xs, livre = [], -1
            for i, a in enumerate(ativos):
                if i + n >= len(v) or nome not in a or i < livre:
                    continue
                if passo_ms and v[i + n][0] - v[i][0] != n * passo_ms:
                    continue
                if (inicio_ms and v[i][0] < inicio_ms) or (fim_ms and v[i][0] >= fim_ms):
                    continue
                xs.append((c[i + n] / c[i] - 1) * 100)
                livre = i + n
            saida[(nome, hz)] = _stats(xs)
    return saida


def passou(treino, teste):
    if treino.get("casos", 0) < MIN_CASOS or teste.get("casos", 0) < MIN_CASOS:
        return False
    a, b = treino["retorno_medio_pct"], teste["retorno_medio_pct"]
    return (abs(a) > CUSTO_PCT and abs(treino["t"]) > T_TREINO and a * b > 0
            and abs(b) > CUSTO_PCT and abs(teste["t"]) > T_TESTE)


def _ms(dia):
    import calendar
    return calendar.timegm(time.strptime(dia, "%Y-%m-%d")) * 1000


def tabela():
    v = baixar()
    ativos = detectar(v)
    corte = _ms(FIM_TREINO)
    tr, te = medir(v, ativos, fim_ms=corte), medir(v, ativos, inicio_ms=corte)
    return {f"{k[0]}|{k[1]}": {"treino": tr[k], "teste": te.get(k, {"casos": 0}), "passou": passou(tr[k], te.get(k, {"casos": 0}))} for k in tr}


if __name__ == "__main__":
    t = tabela()
    (config.RAIZ / "lab" / "padroes_tabela.json").write_text(json.dumps(t, ensure_ascii=False, indent=1))
    print("padrão | prazo | treino: casos, chance de alta, retorno médio, t | teste: idem | passou")
    for k, x in sorted(t.items()):
        a, b = x["treino"], x["teste"]
        f = lambda s: f"{s.get('casos', 0):>6} {s.get('chance_alta', 0):5.1%} {s.get('retorno_medio_pct', 0):+7.3f}% t={s.get('t', 0):+6.2f}"
        print(f"{k:28} {f(a)} | {f(b)} | {'PASSOU' if x['passou'] else '-'}")
    print(f"\npassaram {sum(x['passou'] for x in t.values())} de {len(t)}")
