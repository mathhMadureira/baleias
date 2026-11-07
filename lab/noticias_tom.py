"""Hipótese 9: o tom das notícias sobre bitcoin (PLN do GDELT) antecipa o BTC? (lab/PROTOCOLO_LAB.md)"""
import datetime as dt
import json
import math
import statistics as st
import time
import urllib.error
import urllib.parse
import urllib.request

from baleias import config

from . import padroes as P

CACHE = config.RAIZ / "lab" / "gdelt_tom_bitcoin.json"
API = "https://api.gdeltproject.org/api/v2/doc/doc"
HORIZONTES = {"15min": 1, "1h": 4, "4h": 16}
CUSTO = 0.2


def _pedir(inicio, fim):
    q = urllib.parse.urlencode({"query": "bitcoin", "mode": "timelinetone", "format": "json",
                                "startdatetime": inicio.strftime("%Y%m%d%H%M%S"), "enddatetime": fim.strftime("%Y%m%d%H%M%S")})
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
                corpo = r.read()
            if not corpo.strip():
                raise ValueError("resposta vazia")
            return json.loads(corpo)["timeline"][0]["data"]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError):
            time.sleep(15 * (tentativa + 1))   # o GDELT pede ≥ 5 s entre pedidos e às vezes responde vazio
    return []


def baixar(dias=88):
    if CACHE.exists():
        return {int(k): v for k, v in json.loads(CACHE.read_text()).items()}
    fim = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    ini = fim - dt.timedelta(days=dias)
    tom = {}
    while ini < fim:
        prox = min(ini + dt.timedelta(days=2), fim)
        for p in _pedir(ini, prox):
            t = int(dt.datetime.strptime(p["date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            tom[t] = float(p["value"])
        ini = prox
        time.sleep(6)
    CACHE.write_text(json.dumps(tom))
    return tom


def serie_btc(inicio_ms):
    """Velas de 15 min do BTC desde inicio_ms (Binance)."""
    saida, t = [], inicio_ms
    while True:
        with urllib.request.urlopen(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime={t}&limit=1000", timeout=30) as r:
            lote = json.load(r)
        if not lote:
            break
        saida += [(x[0], float(x[4])) for x in lote]
        if len(lote) < 1000:
            break
        t = lote[-1][0] + 900_000
        time.sleep(0.2)
    return dict(saida[:-1])


def _corr_t(xs, ys):
    n = len(xs)
    if n < 30:
        return None, None
    mx, my = st.fmean(xs), st.fmean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx, syy = sum((a - mx) ** 2 for a in xs), sum((b - my) ** 2 for b in ys)
    if sxx == 0 or syy == 0:
        return 0.0, 0.0
    r = sxy / math.sqrt(sxx * syy)
    return r, r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))


def avaliar(tom, preco):
    tempos = sorted(t for t in tom if t in preco)
    corte = tempos[len(tempos) // 2]
    saida = {}
    for medida in ("tom", "variacao_1h"):
        for nome, n in HORIZONTES.items():
            linhas = []
            for k, t in enumerate(tempos):
                alvo = t + n * 900_000
                if alvo not in preco:
                    continue
                if medida == "tom":
                    x = tom[t]
                else:
                    antes = t - 3_600_000
                    if antes not in tom:
                        continue
                    x = tom[t] - tom[antes]
                linhas.append((t, x, (preco[alvo] / preco[t] - 1) * 100))
            tr = [(x, y) for t, x, y in linhas if t < corte]
            te = [(x, y) for t, x, y in linhas if t >= corte]
            r1, t1 = _corr_t(*zip(*tr)) if len(tr) >= 30 else (None, None)
            r2, t2 = _corr_t(*zip(*te)) if len(te) >= 30 else (None, None)
            # regra: segue o sinal da variação do tom (ou do tom acima/abaixo da mediana do treino), sem sobreposição
            ref = st.median(x for x, _ in tr) if medida == "tom" and tr else 0.0
            ops, livre = [], -1
            for i, (t, x, y) in enumerate(linhas):
                if t < corte or i < livre or x == ref:
                    continue
                ops.append(math.copysign(1, x - ref) * y - CUSTO)
                livre = i + n
            passou = (None not in (t1, t2) and t1 * t2 > 0 and abs(t1) > 3.2 and abs(t2) > 2 and ops and st.fmean(ops) > 0)
            saida[f"{medida}|{nome}"] = {"casos_treino": len(tr), "casos_teste": len(te), "r_treino": r1, "t_treino": t1, "r_teste": r2,
                                         "t_teste": t2, "operacoes": len(ops), "media_op_pct": st.fmean(ops) if ops else None, "passou": bool(passou)}
    return saida, corte


if __name__ == "__main__":
    tom = baixar()
    print(f"tom: {len(tom)} pontos de 15 min, {time.strftime('%F', time.gmtime(min(tom) / 1000))} a {time.strftime('%F', time.gmtime(max(tom) / 1000))}", flush=True)
    preco = serie_btc(min(tom))
    r, corte = avaliar(tom, preco)
    print(f"corte treino/teste: {time.strftime('%F %H:%M', time.gmtime(corte / 1000))}")
    f = lambda a: "—" if a is None else f"{a:+.3f}"
    for k, x in r.items():
        print(f"{k:20} treino n={x['casos_treino']} r={f(x['r_treino'])} t={f(x['t_treino'])} | teste n={x['casos_teste']} r={f(x['r_teste'])} t={f(x['t_teste'])} | "
              f"regra {x['operacoes']} op. média {f(x['media_op_pct'])}% | {'PASSOU' if x['passou'] else 'não passou'}")
    (config.RAIZ / "lab" / "noticias_tom_resultado.json").write_text(json.dumps(r, indent=1))
