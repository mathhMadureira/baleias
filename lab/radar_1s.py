"""H56 — Radar de oportunidades a partir de 1 s, em todos os tempos gráficos (regra e critério em lab/PROTOCOLO_LAB.md, registrados antes).

Uso: .venv-ml/bin/python -m lab.radar_1s <pasta com os .zip diários de velas de 1 s da Binance>
"""
import csv
import io
import sys
import zipfile
from pathlib import Path

import numpy as np

MOEDAS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "PEPE", "SUI", "LINK", "AVAX", "TRX"]
AQUECE, DIAS = "2026-11-12", ["2026-11-13", "2026-11-14", "2026-11-15"]
JANELAS = [5, 15, 60, 300, 900, 3600, 14400]
Z, NOC, CUSTO, STOP, ALVO, ARMA, GUARDA, MAX_S, ESPERA = 4.0, 25.0, 0.0006, 0.01, 0.02, 0.005, 0.70, 3600, 60


def ler(pasta, moeda, dia):
    with zipfile.ZipFile(Path(pasta) / f"{moeda}USDT-1s-{dia}.zip") as z:
        linhas = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]))))
    a = np.array([[float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in linhas])   # máxima, mínima, fechamento, volume em US$
    return a


def _soma_movel(x, n):
    c = np.concatenate(([0.0], np.cumsum(x)))
    s = np.full(len(x), np.nan)
    s[n - 1:] = c[n:] - c[:-n]
    return s


def leitura(c, v):
    """z máximo (com sinal) entre as janelas, a janela dele e o volume relativo dela, em cada segundo."""
    lc = np.log(c)
    r1 = np.concatenate(([0.0], np.diff(lc)))
    var = _soma_movel(r1 ** 2, 3600) / 3600 - (_soma_movel(r1, 3600) / 3600) ** 2
    sig = np.sqrt(np.clip(var, 1e-18, None))
    vh = _soma_movel(v, 3600) / 3600                                  # volume médio por segundo na última hora
    zs, vols = [], []
    for w in JANELAS:
        rw = np.full(len(c), np.nan)
        rw[w:] = lc[w:] - lc[:-w]
        zs.append(rw / (sig * np.sqrt(w)))
        vols.append(_soma_movel(v, w) / (vh * w))
    zs, vols = np.array(zs), np.array(vols)
    zs = np.where(np.isfinite(zs), zs, 0.0)
    j = np.abs(zs).argmax(axis=0)
    idx = np.arange(len(c))
    return zs[j, idx], j, vols[j, idx]


def sair(h, l, c, t, lado):
    """(índice, preço) de saída da posição aberta no fechamento do segundo t. Na dúvida dentro do segundo, o pior primeiro (stop)."""
    e = c[t]
    fim = min(len(c) - 1, t + MAX_S)
    pico = 0.0
    for k in range(t + 1, fim + 1):
        contra = (l[k] / e - 1) if lado > 0 else (1 - h[k] / e)        # pior excursão no segundo
        favor = (h[k] / e - 1) if lado > 0 else (1 - l[k] / e)
        if contra <= -STOP:
            return k, e * (1 - lado * STOP)
        if pico >= ARMA and contra <= GUARDA * pico:
            return k, e * (1 + lado * GUARDA * pico)
        if favor >= ALVO:
            return k, e * (1 + lado * ALVO)
        pico = max(pico, favor)
    return fim, c[fim]


def simular(dados, regra):
    """dados: [(h, l, c, z, j, vol, inicio_pontuado)] por moeda. Devolve {dia: [resultados em US$]}."""
    out = {d: [] for d in DIAS}
    for h, l, c, z, j, vol, ini, dias_idx in dados:
        sinal = np.abs(z) >= Z
        if regra == "R3":
            sinal &= vol <= 1.0
        t, livre = ini, ini
        cand = np.flatnonzero(sinal[ini:]) + ini
        for t in cand:
            if t < livre:
                continue
            lado = -np.sign(z[t]) if regra in ("R1", "R3") else np.sign(z[t])
            k, px = sair(h, l, c, t, lado)
            res = NOC * lado * (px / c[t] - 1) - 2 * CUSTO * NOC
            out[DIAS[min(2, (t - ini) // 86400)]].append(res)
            livre = k + ESPERA
    return out


def main(pasta):
    dados = []
    for m in MOEDAS:
        a = np.concatenate([ler(pasta, m, d) for d in [AQUECE] + DIAS])
        h, l, c, v = a.T
        z, j, vol = leitura(c, v)
        dados.append((h, l, c, z, j, vol, 86400, None))
        print(f"{m}: {len(c)} segundos, oportunidades |z|≥{Z}: {int((np.abs(z[86400:]) >= Z).sum())}", flush=True)
    for regra in ("R1", "R2", "R3"):
        r = simular(dados, regra)
        tudo = sum(r.values(), [])
        print(f"\n{regra}: {len(tudo)} operações, média {np.mean(tudo):+.4f} US$/op, soma {sum(tudo):+.2f}, acerto {np.mean(np.array(tudo) > 0):.0%}")
        for d in DIAS:
            x = r[d]
            print(f"   {d}: n {len(x)}, média {np.mean(x) if x else 0:+.4f}, soma {sum(x):+.2f}")
        ok = all(len(r[d]) >= 30 and np.mean(r[d]) > 0 for d in DIAS)
        print("   →", "APROVADA" if ok else "REPROVADA")


if __name__ == "__main__":
    main(sys.argv[1])
