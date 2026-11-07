"""H6-WINb parte 2: padrões no WIN real (velas de 1 min montadas dos negócios da B3)."""
import json
import statistics as st
import time

from . import padroes as P
from .b3_win import PASTA

PONTO_RS = 0.20
CUSTO_PONTOS = 15


def carregar():
    dias = sorted(a for a in PASTA.glob("2026-*.json"))
    lidos = [(a.stem, json.loads(a.read_text())) for a in dias]
    return [(d, x) for d, x in lidos if len(x["velas"]) >= 500]  # a B3 às vezes publica o dia incompleto


def rodar():
    dias = carregar()
    v = [tuple(x) for _, d in dias for x in d["velas"]]
    P.HORIZONTES = {"1min": 1, "5min": 5, "15min": 15}
    P.CUSTO_PCT = CUSTO_PONTOS / st.fmean(x[4] for x in v) * 100
    a = P.detectar(v)
    corte = _ms_dia(dias[len(dias) // 2][0])
    tr, te = P.medir(v, a, fim_ms=corte, passo_ms=60_000), P.medir(v, a, inicio_ms=corte, passo_ms=60_000)
    return dias, v, tr, te


def _ms_dia(dia):
    import calendar
    return (calendar.timegm(time.strptime(dia, "%Y-%m-%d")) + 3 * 3600) * 1000


if __name__ == "__main__":
    dias, v, tr, te = rodar()
    print(f"{len(dias)} pregões ({dias[0][0]} a {dias[-1][0]}), {len(v)} velas de 1 min, contratos {sorted({d['contrato'] for _, d in dias})}")
    print(f"custo assumido {CUSTO_PONTOS} pontos = {P.CUSTO_PCT:.4f}%")
    f = lambda s: f"{s.get('casos', 0):>5} {s.get('chance_alta', 0):5.1%} {s.get('retorno_medio_pct', 0):+7.4f}% t={s.get('t', 0):+5.2f}"
    for _, k in sorted(((abs(te[k].get("t", 0)), k) for k in tr), reverse=True)[:15]:
        print(f"{k[0] + '|' + k[1]:24} {f(tr[k])} | {f(te[k])} | {'PASSOU' if P.passou(tr[k], te[k]) else '-'}")
    print("passaram", sum(P.passou(tr[k], te[k]) for k in tr), "de", len(tr))
