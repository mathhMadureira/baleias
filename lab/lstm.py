"""Hipótese 8: LSTM nas velas de 15 min do BTC (lab/PROTOCOLO_LAB.md). Roda no .venv-ml (precisa de torch).

Uso: .venv-ml/bin/python -m lab.lstm
"""
import json
import math
import random
import statistics as st
import time

import numpy as np
import torch
from torch import nn

from . import padroes as P

SEQ = 64
HORIZONTES = (1, 4, 16)
CUSTO = 0.2           # % ida e volta
LIMIAR = 0.2          # % de previsão para operar
FIM_TREINO, FIM_VALIDACAO = "2023-01-01", "2024-01-01"
NOMES = ["engolfo_alta", "engolfo_baixa", "martelo", "estrela_cadente", "doji", "tres_soldados", "tres_corvos", "inside_bar",
         "marubozu_alta", "marubozu_baixa", "tendencia_alta", "tendencia_baixa", "rompe_maxima_20", "rompe_minima_20",
         "rsi_abaixo_30", "rsi_acima_70", "volume_3x", "alta_forte", "queda_forte"]


def montar(v):
    """Matriz de entradas por vela (sem olhar à frente) e alvos em % por horizonte."""
    c = np.array([x[4] for x in v])
    o, h, lo, vol = (np.array([x[k] for x in v]) for k in (1, 2, 3, 5))
    ret = np.zeros(len(v))
    ret[1:] = (c[1:] / c[:-1] - 1) * 100
    media_vol = np.convolve(vol, np.ones(96) / 96, mode="full")[:len(v)]
    media_vol = np.concatenate([[vol[0]], media_vol[:-1]])          # média das 96 anteriores
    hora = np.array([(x[0] // 900_000) % 96 for x in v]) / 96 * 2 * math.pi
    ativos = P.detectar(v)
    pad = np.array([[1.0 if n in a else 0.0 for n in NOMES] for a in ativos])
    X = np.column_stack([ret, (h - lo) / c * 100, (c - o) / c * 100, np.log((vol + 1) / (media_vol + 1)),
                         np.sin(hora), np.cos(hora), pad]).astype(np.float32)
    Y = np.full((len(v), len(HORIZONTES)), np.nan, dtype=np.float32)
    for j, n in enumerate(HORIZONTES):
        Y[:-n, j] = (c[n:] / c[:-n] - 1) * 100
    return X, Y


class Rede(nn.Module):
    def __init__(self, entradas):
        super().__init__()
        self.lstm = nn.LSTM(entradas, 32, num_layers=2, batch_first=True, dropout=0.2)
        self.saida = nn.Linear(32, len(HORIZONTES))

    def forward(self, x):
        y, _ = self.lstm(x)
        return self.saida(y[:, -1])


def lotes(X, Y, indices, tamanho, embaralhar):
    idx = list(indices)
    if embaralhar:
        random.shuffle(idx)
    for k in range(0, len(idx), tamanho):
        b = idx[k:k + tamanho]
        xs = np.stack([X[i - SEQ + 1:i + 1] for i in b])
        yield torch.from_numpy(xs), torch.from_numpy(Y[b])


def prever(rede, X, Y, indices):
    rede.eval()
    saida = []
    with torch.no_grad():
        for xb, _ in lotes(X, Y, indices, 2048, False):
            saida.append(rede(xb).numpy())
    return np.concatenate(saida)


def r2_bloco(y, p, blocos=200, reamostras=500, semente=7):
    """R² contra prever zero, com intervalo bootstrap por blocos contíguos (respeita a dependência no tempo)."""
    r2 = 1 - np.sum((y - p) ** 2) / np.sum(y ** 2)
    rng = np.random.default_rng(semente)
    n = len(y)
    tam = max(1, n // blocos)
    inicios = np.arange(0, n - tam + 1, tam)
    amostras = []
    for _ in range(reamostras):
        sel = np.concatenate([np.arange(s, s + tam) for s in rng.choice(inicios, size=len(inicios))])
        amostras.append(1 - np.sum((y[sel] - p[sel]) ** 2) / np.sum(y[sel] ** 2))
    return float(r2), float(np.percentile(amostras, 2.5)), float(np.percentile(amostras, 97.5))


def wilson(acertos, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    f = acertos / n
    centro = (f + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(f * (1 - f) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centro - meia, centro + meia


def regra(y, p, n):
    """Opera só quando |previsão| > LIMIAR, sem sobreposição (um caso a cada n velas)."""
    res, livre = [], -1
    for i in range(len(y)):
        if i < livre or abs(p[i]) <= LIMIAR:
            continue
        res.append(math.copysign(1, p[i]) * y[i] - CUSTO)
        livre = i + n
    return res


def _ms(dia):
    import calendar
    return calendar.timegm(time.strptime(dia, "%Y-%m-%d")) * 1000


def main(epocas=12, semente=7):
    random.seed(semente)
    np.random.seed(semente)
    torch.manual_seed(semente)
    torch.set_num_threads(3)
    v = P.baixar()
    X, Y = montar(v)
    t = np.array([x[0] for x in v])
    validos = [i for i in range(SEQ + 100, len(v)) if not np.isnan(Y[i]).any()]
    tr = [i for i in validos if t[i] < _ms(FIM_TREINO)]
    va = [i for i in validos if _ms(FIM_TREINO) <= t[i] < _ms(FIM_VALIDACAO)]
    te = [i for i in validos if t[i] >= _ms(FIM_VALIDACAO)]
    # normalização só com o treino
    mu, dp = X[tr].mean(0), X[tr].std(0) + 1e-6
    mu[6:], dp[6:] = 0, 1                    # padrões 0/1 e hora ficam como estão
    mu[4:6], dp[4:6] = 0, 1
    X = (X - mu) / dp
    escala = Y[tr].std(0)
    Ys = Y / escala
    rede = Rede(X.shape[1])
    opt = torch.optim.Adam(rede.parameters(), lr=1e-3)
    melhor, parada, melhor_estado = float("inf"), 0, None
    print(f"velas {len(v)} | treino {len(tr)} validação {len(va)} teste {len(te)}", flush=True)
    for ep in range(epocas):
        rede.train()
        inicio = time.time()
        for xb, yb in lotes(X, Ys, tr, 256, True):
            opt.zero_grad()
            perda = nn.functional.mse_loss(rede(xb), yb)
            perda.backward()
            nn.utils.clip_grad_norm_(rede.parameters(), 1.0)
            opt.step()
        pv = prever(rede, X, Ys, va)
        perda_va = float(np.mean((pv - Ys[va]) ** 2))
        print(f"época {ep + 1}: validação {perda_va:.5f} (prever zero = {float(np.mean(Ys[va] ** 2)):.5f}) {time.time() - inicio:.0f}s", flush=True)
        if perda_va < melhor - 1e-5:
            melhor, parada, melhor_estado = perda_va, 0, {k: x.clone() for k, x in rede.state_dict().items()}
        else:
            parada += 1
            if parada >= 3:
                break
    rede.load_state_dict(melhor_estado)
    pt = prever(rede, X, Ys, te) * escala
    yt = Y[te]
    # comparação: regressão linear com as entradas da última vela (mínimos quadrados no treino)
    A = np.column_stack([X[tr], np.ones(len(tr))])
    coef, *_ = np.linalg.lstsq(A, Y[tr], rcond=None)
    pl = np.column_stack([X[te], np.ones(len(te))]) @ coef
    resultado = {}
    for j, n in enumerate(HORIZONTES):
        r2, lo, hi = r2_bloco(yt[:, j], pt[:, j])
        r2l = 1 - np.sum((yt[:, j] - pl[:, j]) ** 2) / np.sum(yt[:, j] ** 2)
        mask = pt[:, j] != 0
        acertos = int(np.sum(np.sign(pt[mask, j]) == np.sign(yt[mask, j])))
        w = wilson(acertos, int(mask.sum()))
        ops = regra(yt[:, j], pt[:, j], n)
        passou = lo > 0 and w[0] > 0.5 and len(ops) >= 100 and st.fmean(ops) > 0
        resultado[f"{n * 15}min"] = {"r2": r2, "r2_ic": [lo, hi], "r2_linear": float(r2l), "acerto": acertos / max(1, mask.sum()),
                                     "acerto_ic": list(w), "operacoes": len(ops), "media_op_pct": st.fmean(ops) if ops else None,
                                     "dp_previsao": float(pt[:, j].std()), "passou": bool(passou)}
    return resultado


if __name__ == "__main__":
    r = main()
    from baleias import config
    (config.RAIZ / "lab" / "lstm_resultado.json").write_text(json.dumps(r, indent=1))
    for k, x in r.items():
        print(f"{k}: R² {x['r2']:+.4f} [{x['r2_ic'][0]:+.4f}, {x['r2_ic'][1]:+.4f}] (linear {x['r2_linear']:+.4f}) | acerto {x['acerto']:.1%} "
              f"[{x['acerto_ic'][0]:.1%}, {x['acerto_ic'][1]:.1%}] | regra: {x['operacoes']} op., média {x['media_op_pct'] if x['media_op_pct'] is None else round(x['media_op_pct'], 3)}% | "
              f"{'PASSOU' if x['passou'] else 'não passou'}")
