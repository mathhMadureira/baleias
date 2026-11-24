"""H77 e H78 (PROTOCOLO_LAB.md, 24/11): estratégias do livro 151 Trading Strategies em velas diárias dos perpétuos da Binance.

H77: carteira neutra em dólar de máximo Sharpe (3.18) na cesta de 10 moedas, E = reversão ou momento de d dias.
H78: tendência com filtro HP (8.1) em BTC e ETH, filtro só no passado.
Uso: .venv-ml/bin/python -m lab.livro151   (baixa e guarda o cache em dados/lab/livro151_cache.json)
"""
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "dados" / "lab" / "livro151_cache.json"
SAIDA = RAIZ / "dados" / "lab" / "livro151_resultado.json"
CESTA = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"]
INICIO, FIM = "2021-01-01", "2026-11-23"
CUSTO = 0.0006                 # por lado, sobre o giro
FAPI = "https://fapi.binance.com/fapi/v1"


def _get(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except OSError:
            time.sleep(2 + 3 * i)
    raise RuntimeError("falhou: " + url)


def baixar():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    t0 = int(pd.Timestamp(INICIO, tz="UTC").timestamp() * 1000)
    t1 = int(pd.Timestamp(FIM, tz="UTC").timestamp() * 1000)
    out = {}
    for m in CESTA:
        s, velas, fund = m + "USDT", [], []
        t = t0
        while t < t1:
            k = _get(f"{FAPI}/klines?symbol={s}&interval=1d&startTime={t}&endTime={t1}&limit=1500")
            if not k:
                break
            velas += [[int(x[0]), float(x[4])] for x in k]
            t = int(k[-1][0]) + 86_400_000
            if len(k) < 1500:
                break
        t = t0
        while t < t1:
            f = _get(f"{FAPI}/fundingRate?symbol={s}&startTime={t}&endTime={t1}&limit=1000")
            if not f:
                break
            fund += [[int(x["fundingTime"]), float(x["fundingRate"])] for x in f]
            t = int(f[-1]["fundingTime"]) + 1
            if len(f) < 1000:
                break
        out[m] = {"velas": velas, "funding": fund}
        print(m, len(velas), "velas", len(fund), "fundings", flush=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out))
    return out


def tabelas(bruto):
    px, fd = {}, {}
    for m, d in bruto.items():
        v = pd.Series({pd.Timestamp(t, unit="ms", tz="UTC").normalize(): c for t, c in d["velas"]})
        f = pd.Series([r for _, r in d["funding"]], index=[pd.Timestamp(t, unit="ms", tz="UTC").normalize() for t, _ in d["funding"]])
        px[m] = v
        fd[m] = f.groupby(level=0).sum()
    P = pd.DataFrame(px).sort_index()
    F = pd.DataFrame(fd).reindex(P.index).fillna(0.0)
    return P, F


def carteira(W, R, F):
    """W[t] = pesos decididos no fechamento de t; ganham R[t+1] e pagam o funding de t+1. Devolve a série diária líquida."""
    Wp = W.shift(1).fillna(0.0)
    bruto = (Wp * R).sum(axis=1)
    funding = -(Wp * F).sum(axis=1)                    # comprado paga, vendido recebe
    giro = W.diff().abs().sum(axis=1).shift(1).fillna(0.0)
    return bruto + funding - CUSTO * giro


def sharpe(x):
    x = x.dropna()
    return float(x.mean() / x.std() * math.sqrt(365)) if len(x) > 2 and x.std() > 0 else float("nan")


def t_nw(x, lags=5):
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    n = len(x)
    if n < 10:
        return float("nan")
    e = x - x.mean()
    v = e @ e / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / n
    return float(x.mean() / math.sqrt(v / n)) if v > 0 else float("nan")


def queda(x):
    c = (1 + x.fillna(0)).cumprod()
    return float((c / c.cummax() - 1).min())


# ---------------- H77 ----------------
def pesos_h77(R, modo, d, jan, ridge=1e-4, E_embaralhado=None, rng=None):
    W = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    arr = R.to_numpy()
    for i in range(jan + d, len(R)):
        bloco = arr[i - jan + 1:i + 1]
        ok = ~np.isnan(bloco).any(axis=0)
        if ok.sum() < 4:
            continue
        rd = np.nansum(arr[i - d + 1:i + 1][:, ok], axis=0)
        E = (rd - rd.mean()) * (-1 if modo == "reversao" else 1)
        if rng is not None:
            E = rng.permutation(E)
        C = np.cov(bloco[:, ok].T) + ridge * np.eye(ok.sum())
        Ci = np.linalg.inv(C)
        a, b = Ci @ E, Ci @ np.ones(ok.sum())
        w = a - b * (a.sum() / b.sum())
        s = np.abs(w).sum()
        if s > 0:
            W.iloc[i, np.where(ok)[0]] = w / s
    return W


# ---------------- H78 ----------------
def hp_ultimo(y, lam):
    n = len(y)
    D = sparse.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n))
    A = sparse.eye(n) + lam * (D.T @ D)
    return spsolve(A.tocsc(), y)[-1]


def tendencia_hp(p, W, lam):
    y = np.log(p.to_numpy())
    out = np.full(len(y), np.nan)
    for t in range(W, len(y) + 1):
        out[t - 1] = hp_ultimo(y[t - W:t], lam)
    return pd.Series(out, index=p.index)


def sinal_ma(s, t1, t2):
    a, b = s.rolling(t1).mean(), s.rolling(t2).mean()
    z = np.where(a > b, 1.0, np.where(a < b, -1.0, 0.0))
    return pd.Series(z, index=s.index).where(b.notna(), 0.0)


def main():
    P, F = tabelas(baixar())
    R = P.pct_change()
    n = len(P)
    corte = P.index[int(n * 0.6)]
    aj, te = (P.index < corte), (P.index >= corte)
    res = {"dias": n, "corte": str(corte.date()), "inicio": str(P.index[0].date()), "fim": str(P.index[-1].date())}

    # H77
    grade = []
    cache_w = {}
    for modo in ("reversao", "momento"):
        for d in (1, 3, 7):
            for jan in (60, 120, 250):
                W = pesos_h77(R, modo, d, jan)
                x = carteira(W, R, F)
                cache_w[(modo, d, jan)] = (W, x)
                grade.append({"modo": modo, "d": d, "jan": jan, "sharpe_ajuste": sharpe(x[aj]), "sharpe_teste_info": None})
    melhor = max(grade, key=lambda g: g["sharpe_ajuste"] if not math.isnan(g["sharpe_ajuste"]) else -9)
    W, x = cache_w[(melhor["modo"], melhor["d"], melhor["jan"])]
    xt = x[te]
    meio = xt.index[len(xt) // 2]
    rng = np.random.default_rng(77)
    ctrl = []
    for _ in range(500):
        Wc = pesos_h77(R, melhor["modo"], melhor["d"], melhor["jan"], rng=rng)
        ctrl.append(sharpe(carteira(Wc, R, F)[te]))
    pct = float(np.mean([sharpe(xt) > c for c in ctrl if not math.isnan(c)]))
    btc = R["BTC"][te]
    beta = float(np.cov(xt.fillna(0), btc.fillna(0))[0, 1] / btc.var())
    j77 = {"a": bool(xt.mean() > 0 and t_nw(xt) >= 2.24), "b": bool(xt[xt.index < meio].mean() > 0 and xt[xt.index >= meio].mean() > 0), "c": pct > 0.975}
    res["H77"] = {"escolhida": melhor, "teste": {"media_dia_%": float(xt.mean() * 100), "t_nw": t_nw(xt), "sharpe": sharpe(xt), "queda_max": queda(xt),
                  "metades_%": [float(xt[xt.index < meio].mean() * 100), float(xt[xt.index >= meio].mean() * 100)], "percentil_controle": pct,
                  "beta_btc": beta, "giro_dia": float(W[te].diff().abs().sum(axis=1).mean())},
                  "grade_ajuste": sorted(grade, key=lambda g: -g["sharpe_ajuste"])[:6], "juiz": j77, "passou": all(j77.values())}
    print("H77", json.dumps(res["H77"]["teste"], ensure_ascii=False), j77, flush=True)

    # H78
    Rb = R[["BTC", "ETH"]]
    Fb = F[["BTC", "ETH"]]
    hp = {}
    g78 = []
    for Wn in (180, 365, 730):
        for lam in (14400.0, 100 * 365.0 ** 2):
            for m in ("BTC", "ETH"):
                hp[(m, Wn, lam)] = tendencia_hp(P[m], Wn, lam)
            for t1 in (5, 10, 20):
                for t2 in (20, 30, 60):
                    if t1 >= t2:
                        continue
                    Wt = pd.DataFrame({m: 0.5 * sinal_ma(hp[(m, Wn, lam)], t1, t2) for m in ("BTC", "ETH")})
                    x = carteira(Wt, Rb, Fb)
                    g78.append({"W": Wn, "lam": lam, "t1": t1, "t2": t2, "sharpe_ajuste": sharpe(x[aj])})
    m78 = max(g78, key=lambda g: g["sharpe_ajuste"] if not math.isnan(g["sharpe_ajuste"]) else -9)
    Wt = pd.DataFrame({m: 0.5 * sinal_ma(hp[(m, m78["W"], m78["lam"])], m78["t1"], m78["t2"]) for m in ("BTC", "ETH")})
    x = carteira(Wt, Rb, Fb)[te]
    cru = carteira(pd.DataFrame({m: 0.5 * sinal_ma(np.log(P[m]), m78["t1"], m78["t2"]) for m in ("BTC", "ETH")}), Rb, Fb)[te]
    bh = carteira(pd.DataFrame(0.5, index=P.index, columns=["BTC", "ETH"]), Rb, Fb)[te]
    meio = x.index[len(x) // 2]
    j78 = {"a": bool(x.mean() > 0 and t_nw(x) >= 2.24), "b": bool(x[x.index < meio].mean() > 0 and x[x.index >= meio].mean() > 0),
           "c": bool(sharpe(x) > sharpe(bh) and sharpe(x) > sharpe(cru))}
    res["H78"] = {"escolhida": m78, "teste": {"media_dia_%": float(x.mean() * 100), "t_nw": t_nw(x), "sharpe": sharpe(x), "queda_max": queda(x),
                  "metades_%": [float(x[x.index < meio].mean() * 100), float(x[x.index >= meio].mean() * 100)],
                  "sharpe_comprar_segurar": sharpe(bh), "sharpe_ma_preco_cru": sharpe(cru), "trocas": int((Wt[te].diff().abs() > 0).sum().sum())},
                  "grade_ajuste": sorted(g78, key=lambda g: -g["sharpe_ajuste"])[:6], "juiz": j78, "passou": all(j78.values())}
    print("H78", json.dumps(res["H78"]["teste"], ensure_ascii=False), j78, flush=True)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
