"""H80 (PROTOCOLO_LAB.md, 24/11): comprado à vista + vendido no perpétuo, recebendo o funding, cesta de 10 moedas da Binance.

Uso: .venv-ml/bin/python -m lab.h80_funding  → dados/lab/h80_resultado.json
Reaproveita o cache do perpétuo e do funding da H77/H78 (lab/livro151.py) e baixa as velas à vista.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab import livro151 as L

SPOT = "https://data-api.binance.vision/api/v3/klines"
CACHE_SPOT = L.RAIZ / "dados" / "lab" / "h80_spot_cache.json"
SAIDA = L.RAIZ / "dados" / "lab" / "h80_resultado.json"
CUSTO_PERNA = 0.0010 + 0.0005          # à vista 0,10% + perpétuo 0,05% por lado


def spot():
    if CACHE_SPOT.exists():
        return json.loads(CACHE_SPOT.read_text())
    t0 = int(pd.Timestamp(L.INICIO, tz="UTC").timestamp() * 1000)
    t1 = int(pd.Timestamp(L.FIM, tz="UTC").timestamp() * 1000)
    out = {}
    for m in L.CESTA:
        v, t = [], t0
        while t < t1:
            k = L._get(f"{SPOT}?symbol={m}USDT&interval=1d&startTime={t}&endTime={t1}&limit=1000")
            if not k:
                break
            v += [[int(x[0]), float(x[4])] for x in k]
            t = int(k[-1][0]) + 86_400_000
            if len(k) < 1000:
                break
        out[m] = v
        print(m, len(v), "velas à vista", flush=True)
    CACHE_SPOT.write_text(json.dumps(out))
    return out


def pesos(F, L_, k):
    """Peso igual entre as moedas cujo funding médio de L_ dias, anualizado, passa de k; sai abaixo de k/2."""
    anual = F.rolling(L_).mean() * 365
    W = pd.DataFrame(0.0, index=F.index, columns=F.columns)
    dentro = set()
    for i, d in enumerate(F.index):
        a = anual.iloc[i]
        for m in F.columns:
            if pd.isna(a[m]):
                continue
            if m in dentro and a[m] < k / 2:
                dentro.discard(m)
            elif m not in dentro and a[m] > k:
                dentro.add(m)
        if dentro:
            W.loc[d, list(dentro)] = 1.0 / len(dentro)
    return W


def serie(W, Rs, Rp, F):
    Wp = W.shift(1).fillna(0.0)
    bruto = (Wp * (Rs.fillna(0) - Rp.fillna(0) + F)).sum(axis=1)
    giro = W.diff().abs().sum(axis=1).shift(1).fillna(0.0)
    return bruto - CUSTO_PERNA * giro


def main():
    bruto = L.baixar()
    P, F = L.tabelas(bruto)
    S = pd.DataFrame({m: pd.Series({pd.Timestamp(t, unit="ms", tz="UTC").normalize(): c for t, c in v}) for m, v in spot().items()}).reindex(P.index)
    Rp, Rs = P.pct_change(), S.pct_change()
    ok = Rp.notna() & Rs.notna()
    Rp, Rs, F = Rp.where(ok), Rs.where(ok), F.where(ok, 0.0)
    n = len(P)
    corte = P.index[int(n * 0.6)]
    aj, te = P.index < corte, P.index >= corte
    grade, guard = [], {}
    for L_ in (3, 7, 14):
        for k in (0.05, 0.10, 0.20):
            W = pesos(F, L_, k)
            x = serie(W, Rs, Rp, F)
            guard[(L_, k)] = (W, x)
            grade.append({"L": L_, "k": k, "sharpe_ajuste": L.sharpe(x[aj]), "media_ajuste_%": float(x[aj].mean() * 100)})
    m = max(grade, key=lambda g: g["sharpe_ajuste"] if not math.isnan(g["sharpe_ajuste"]) else -9)
    W, x = guard[(m["L"], m["k"])]
    xt = x[te]
    meio = xt.index[len(xt) // 2]
    base = (S / P - 1)
    juiz = {"a": bool(xt.mean() > 0 and L.t_nw(xt) >= 2), "b": bool(xt[xt.index < meio].mean() > 0 and xt[xt.index >= meio].mean() > 0),
            "c": L.queda(xt) > -0.05}
    res = {"dias": n, "corte": str(corte.date()), "escolhida": m, "grade": grade,
           "teste": {"media_dia_%": float(xt.mean() * 100), "anual_%": float(xt.mean() * 365 * 100), "t_nw": L.t_nw(xt), "sharpe": L.sharpe(xt),
                     "queda_max": L.queda(xt), "pior_dia_%": float(xt.min() * 100),
                     "metades_%": [float(xt[xt.index < meio].mean() * 100), float(xt[xt.index >= meio].mean() * 100)],
                     "tempo_investido": float((W[te].sum(axis=1) > 0).mean()),
                     "funding_anual_medio_cesta_%": float(F[te].mean().mean() * 365 * 100),
                     "base_max_abs_%": float(base[te].abs().max().max() * 100)},
           "periodo_todo": {"media_dia_%": float(x.mean() * 100), "anual_%": float(x.mean() * 365 * 100), "queda_max": L.queda(x)},
           "juiz": juiz, "passou": all(juiz.values())}
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("escolhida", "teste", "periodo_todo", "juiz", "passou")}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
