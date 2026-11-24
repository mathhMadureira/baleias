"""H79 (PROTOCOLO_LAB.md): MA 5 × 60 dias no preço, BTC + ETH 50/50, no papel, de 2026-11-25 em diante. Sem estado: recalcula tudo das velas.

Uso: .venv-ml/bin/python -m lab.h79_papel   → dados/lab/h79_papel.json e o resumo na tela.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab import livro151 as L

INICIO = pd.Timestamp("2026-11-25", tz="UTC")
SAIDA = Path(__file__).resolve().parent.parent / "dados" / "lab" / "h79_papel.json"


def velas(sym, desde_ms):
    k = L._get(f"{L.FAPI}/klines?symbol={sym}&interval=1d&startTime={desde_ms}&limit=1500")
    s = pd.Series({pd.Timestamp(int(x[0]), unit="ms", tz="UTC"): float(x[4]) for x in k if int(x[6]) < pd.Timestamp.now(tz="UTC").value // 10**6})
    f = L._get(f"{L.FAPI}/fundingRate?symbol={sym}&startTime={desde_ms}&limit=1000")
    fu = pd.Series([float(x["fundingRate"]) for x in f], index=[pd.Timestamp(int(x["fundingTime"]), unit="ms", tz="UTC").normalize() for x in f])
    return s, fu.groupby(level=0).sum()


def main():
    desde = int((INICIO - pd.Timedelta(days=80)).value // 10**6)
    P, F = {}, {}
    for m in ("BTC", "ETH"):
        P[m], F[m] = velas(m + "USDT", desde)
    P = pd.DataFrame(P).sort_index()
    F = pd.DataFrame(F).reindex(P.index).fillna(0.0)
    R = P.pct_change()
    W = pd.DataFrame({m: 0.5 * L.sinal_ma(np.log(P[m]), 5, 60) for m in ("BTC", "ETH")})
    x = L.carteira(W, R, F)
    bh = L.carteira(pd.DataFrame(0.5, index=P.index, columns=["BTC", "ETH"]), R, F)
    x, bh = x[x.index >= INICIO], bh[bh.index >= INICIO]
    meio = x.index[len(x) // 2] if len(x) else None
    out = {"dias": len(x), "de": str(x.index[0].date()) if len(x) else None, "ate": str(x.index[-1].date()) if len(x) else None,
           "media_dia_%": float(x.mean() * 100) if len(x) else None, "acumulado_%": float(((1 + x).prod() - 1) * 100) if len(x) else None,
           "sharpe": L.sharpe(x), "sharpe_comprar_segurar": L.sharpe(bh), "queda_max": L.queda(x) if len(x) else None,
           "metades_%": [float(x[x.index < meio].mean() * 100), float(x[x.index >= meio].mean() * 100)] if len(x) > 3 else None,
           "posicao_agora": W.iloc[-1].to_dict() if len(W) else None}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
