"""H26 — minerador de oportunidades (pré-registrado em PROTOCOLO_LAB.md).

Como na mineração do Bitcoin: gera muitas regras candidatas (compra E venda) e só aceita as que passam num "alvo de dificuldade"
que sobe com o número de tentativas (Bonferroni), depois numa validação e numa reserva olhada uma vez só.
Alvo: direção da próxima vela de 15 min (o mesmo do Cérebro v3; aposta binária a 0,51 → empate em 51%).

Uso: .venv-ml/bin/python -m lab.minerador
"""
import json
import os
import time
import urllib.request
from itertools import combinations
from statistics import NormalDist

import numpy as np

from baleias import config

from . import tartaruga as T

INTERVALO = os.environ.get("MINERADOR_INTERVALO", "15m")          # H26: 15m · H32: 1m
PASSO_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000}[INTERVALO]
DIA = 86_400_000 // PASSO_MS                                      # velas por dia (para o "mesmo horário")
HORIZONTE = int(os.environ.get("MINERADOR_HORIZONTE", "1"))       # velas à frente do alvo (H26: 1 · H32: 12)
FIM_MS = 1_794_355_200_000           # 2026-11-11 00:00 UTC (fixo: o teste é reproduzível)
INICIO_MS = FIM_MS - int(os.environ["MINERADOR_DIAS"]) * 86_400_000 if os.environ.get("MINERADOR_DIAS") else 1_746_057_600_000   # 2025-05-01
_sufixo = "" if INTERVALO == "15m" else f"_{INTERVALO}"
ARQ_DADOS = config.RAIZ / "lab" / f"minerador_{INTERVALO}.npz"
ARQ_RESULTADO = config.RAIZ / "lab" / f"minerador_resultado{_sufixo}.json"
QUANTIS = (5, 10, 20, 80, 90, 95)
CUSTO_PERP = float(os.environ.get("MINERADOR_CUSTO", "0.001"))


# ---------------- dados ----------------

def baixar():
    if ARQ_DADOS.exists():
        z = np.load(ARQ_DADOS)
        return z["t"], list(z["moedas"]), z["ohlcv"]
    from concurrent.futures import ThreadPoolExecutor
    grade = np.arange(INICIO_MS, FIM_MS, PASSO_MS)
    ohlcv = np.full((len(T.MOEDAS_ROBO), len(grade), 5), np.nan)

    def moeda(i_m):
        i, m = i_m
        t = INICIO_MS
        while t < FIM_MS:
            for tentativa in range(6):
                try:
                    url = f"{T.DADOS}/api/v3/klines?symbol={m}&interval={INTERVALO}&startTime={t}&endTime={FIM_MS - 1}&limit=1000"
                    with urllib.request.urlopen(url, timeout=30) as r:
                        lote = json.load(r)
                    break
                except OSError:
                    time.sleep(5 * (tentativa + 1))
            else:
                raise RuntimeError(f"Binance não respondeu ({m})")
            if not lote:
                break
            for x in lote:
                j = (x[0] - INICIO_MS) // PASSO_MS
                if 0 <= j < len(grade):
                    ohlcv[i, j] = [float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])]
            t = lote[-1][0] + PASSO_MS
        print(f"  {m}: {int(np.isfinite(ohlcv[i, :, 3]).sum())} velas", flush=True)
    with ThreadPoolExecutor(6) as fios:
        list(fios.map(moeda, enumerate(T.MOEDAS_ROBO)))
    np.savez_compressed(ARQ_DADOS, t=grade, moedas=np.array(T.MOEDAS_ROBO), ohlcv=ohlcv)
    return grade, list(T.MOEDAS_ROBO), ohlcv


# ---------------- medidas (só o passado) ----------------

def _media(x, n):
    """Média móvel simples terminando em t (NaN se faltar histórico)."""
    s = np.nancumsum(np.nan_to_num(x), dtype=float)
    out = np.full_like(x, np.nan)
    out[n - 1:] = (s[n - 1:] - np.concatenate(([0.0], s[:-n]))) / n
    return out


def _janela(x, n, f):
    out = np.full_like(x, np.nan)
    v = np.lib.stride_tricks.sliding_window_view(x, n)
    out[n - 1:] = f(v, axis=1)
    return out


def _desloca(x, k):
    out = np.full_like(x, np.nan)
    out[k:] = x[:-k]
    return out


NOMES = ["r1", "r4", "r16", "r96", "z20", "z200", "amplitude", "corpo", "vol96", "vol_hora", "rsi14", "d_max96", "d_min96", "btc_r4", "forca_btc"]


def medidas(t, moedas, ohlcv):
    """Devolve X (moedas × tempo × medidas), hora (tempo,) e y (moedas × tempo: 1 sobe, 0 desce, NaN empate/sem dado), ret (próx. retorno)."""
    nm, nt = ohlcv.shape[:2]
    X = np.full((nm, nt, len(NOMES)), np.nan)
    y = np.full((nm, nt), np.nan)
    ret = np.full((nm, nt), np.nan)
    r4s = {}
    for i in range(nm):
        o, h, l, c, v = (ohlcv[i, :, k] for k in range(5))
        lc = np.log(c)
        lr = np.concatenate(([np.nan], np.diff(lc)))
        sig = _janela(lr, 96, np.nanstd)
        sig[sig <= 0] = np.nan
        f = {}
        for k in (1, 4, 16, 96):
            f[f"r{k}"] = (lc - _desloca(lc, k)) / (sig * np.sqrt(k))
        f["z20"] = (lc - np.log(_media(c, 20))) / (sig * np.sqrt(20))
        f["z200"] = (lc - np.log(_media(c, 200))) / (sig * np.sqrt(200))
        f["amplitude"] = (h - l) / _media(h - l, 20)
        amp = h - l
        f["corpo"] = np.where(amp > 0, (c - o) / np.where(amp > 0, amp, 1), 0.0)
        f["vol96"] = v / _media(v, 96)
        mesmo_horario = np.nanmean(np.stack([_desloca(v, DIA * k) for k in range(1, 21)]), axis=0)
        f["vol_hora"] = v / mesmo_horario
        ganho, perda = np.clip(lr, 0, None), np.clip(-lr, 0, None)
        mg, mp = _media(ganho, 14), _media(perda, 14)
        f["rsi14"] = 100 * mg / (mg + mp)
        f["d_max96"] = (lc - np.log(_janela(h, 96, np.nanmax))) / sig
        f["d_min96"] = (lc - np.log(_janela(l, 96, np.nanmin))) / sig
        r4s[moedas[i]] = f["r4"]
        for k, nome in enumerate(NOMES[:13]):
            X[i, :, k] = f[nome]
        prox = np.full_like(lc, np.nan)                            # retorno HORIZONTE velas à frente
        prox[:-HORIZONTE] = lc[HORIZONTE:] - lc[:-HORIZONTE]
        ret[i] = prox
        y[i] = np.where(prox > 0, 1.0, np.where(prox < 0, 0.0, np.nan))
    btc = r4s["BTCUSDT"]
    for i in range(nm):
        X[i, :, 13] = btc
        X[i, :, 14] = X[i, :, 1] - btc
    X[moedas.index("BTCUSDT"), :, 13:] = np.nan          # contra si mesmo não faz sentido
    hora = (t // 3_600_000) % 24
    return X, hora, y, ret


# ---------------- avaliação ----------------

def avaliar(mascara, y, ret, sobe, fatia):
    """Estatística agrupada por instante: média, entre as moedas, de (acertou − 0,5) em cada instante em que a regra dispara."""
    m = mascara[:, fatia] & np.isfinite(y[:, fatia])
    if not m.any():
        return None
    acerto = (y[:, fatia] == (1.0 if sobe else 0.0)) & m
    n_t = m.sum(axis=0)
    usa = n_t > 0
    d = acerto.sum(axis=0)[usa] / n_t[usa] - 0.5
    n = int(usa.sum())
    if n < 30:
        return {"instantes": n, "acerto": None, "t": 0.0}
    tt = float(d.mean() / (d.std(ddof=1) / np.sqrt(n))) if d.std(ddof=1) > 0 else 0.0
    r = ret[:, fatia][m] * (1 if sobe else -1)
    return {"instantes": n, "sinais": int(m.sum()), "acerto": float(acerto.sum() / m.sum()), "t": tt,
            "perp_liquido_pct": float((np.nanmean(r) - CUSTO_PERP) * 100)}


def candidatas(X, hora, treino):
    """Lista de (nome, máscara moedas×tempo) com limiares tirados SÓ do treino."""
    lim = {}
    for k, nome in enumerate(NOMES):
        v = X[:, treino, k]
        v = v[np.isfinite(v)]
        lim[nome] = {q: float(np.percentile(v, q)) for q in QUANTIS}
    def cond(k, q):
        nome = NOMES[k]
        return (X[:, :, k] <= lim[nome][q]) if q < 50 else (X[:, :, k] >= lim[nome][q])
    for k, nome in enumerate(NOMES):
        for q in QUANTIS:
            yield (f"{nome} {'≤' if q < 50 else '≥'} q{q}", cond(k, q), {"tipo": "regra", "medida": nome, "quantil": q, "limiar": lim[nome][q]})
    for a, b in combinations(range(len(NOMES)), 2):
        for qa in (10, 90):
            for qb in (10, 90):
                yield (f"{NOMES[a]} {'≤' if qa < 50 else '≥'} q{qa} E {NOMES[b]} {'≤' if qb < 50 else '≥'} q{qb}", cond(a, qa) & cond(b, qb),
                       {"tipo": "par", "medidas": [[NOMES[a], qa, lim[NOMES[a]][qa]], [NOMES[b], qb, lim[NOMES[b]][qb]]]})
    nm = X.shape[0]
    for hh in range(24):
        yield (f"hora {hh:02d} UTC", np.broadcast_to(hora == hh, (nm, len(hora))).copy(), {"tipo": "hora", "hora": hh})


def n_candidatas():
    from math import comb
    return len(NOMES) * len(QUANTIS) + comb(len(NOMES), 2) * 4 + 24


def main():
    t0 = time.time()
    print("baixando/lendo velas de 15 min…", flush=True)
    t, moedas, ohlcv = baixar()
    X, hora, y, ret = medidas(t, moedas, ohlcv)
    nt = len(t)
    treino, valid, reserva = slice(0, nt // 2), slice(nt // 2, nt * 3 // 4), slice(nt * 3 // 4, nt)
    tentativas = 2 * n_candidatas()                              # cada condição vale nos dois sentidos
    z_alvo = NormalDist().inv_cdf(1 - 0.05 / tentativas)
    print(f"{n_candidatas()} condições × 2 sentidos = {tentativas} tentativas; alvo de dificuldade t ≥ {z_alvo:.2f}", flush=True)
    passaram_treino, aprovadas, todas = [], [], []
    for nome, mascara, definicao in candidatas(X, hora, treino):
        for sobe in (True, False):
            tr = avaliar(mascara, y, ret, sobe, treino)
            if not tr or tr["acerto"] is None:
                continue
            todas.append((tr["t"], nome, sobe))
            if tr["t"] >= z_alvo and tr["acerto"] >= 0.52 and tr["instantes"] >= 300:
                va = avaliar(mascara, y, ret, sobe, valid)
                item = {"regra": nome, "lado": "sobe" if sobe else "desce", "definicao": definicao, "treino": tr, "validacao": va}
                passaram_treino.append(item)
                if va and va["acerto"] is not None and va["acerto"] >= 0.515 and va["t"] >= 2:
                    re = avaliar(mascara, y, ret, sobe, reserva)              # a reserva é olhada uma única vez, só para quem chegou aqui
                    item["reserva"] = re
                    if re and re["acerto"] is not None and re["acerto"] > 0.51 and re["t"] >= 1.65:
                        aprovadas.append(item)
    todas.sort(reverse=True)
    resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "tentativas": tentativas, "z_alvo": z_alvo,
                 "periodo": {"treino": [int(t[0]), int(t[nt // 2 - 1])], "validacao": [int(t[nt // 2]), int(t[nt * 3 // 4 - 1])],
                             "reserva": [int(t[nt * 3 // 4]), int(t[-1])]},
                 "melhores_treino": [{"t": round(a, 2), "regra": b, "lado": "sobe" if c else "desce"} for a, b, c in todas[:25]],
                 "passaram_treino": passaram_treino, "aprovadas": aprovadas, "segundos": round(time.time() - t0)}
    ARQ_RESULTADO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    print(f"passaram no alvo do treino: {len(passaram_treino)} · aprovadas nas 3 etapas: {len(aprovadas)}")
    for a in passaram_treino:
        tr, va, re = a["treino"], a.get("validacao") or {}, a.get("reserva") or {}
        print(f"  {'✅' if a in aprovadas else '✗'} {a['lado']:5} {a['regra']}: treino {tr['acerto']:.1%} t={tr['t']:.1f} | "
              f"validação {va.get('acerto') or 0:.1%} t={va.get('t', 0):.1f} | reserva {(re.get('acerto') or 0):.1%} t={re.get('t', 0):.1f} | "
              f"perp {tr['perp_liquido_pct']:+.3f}%/op")
    print("melhores do treino (antes do alvo):")
    for x in resultado["melhores_treino"][:10]:
        print(f"  t={x['t']:.2f} {x['lado']:5} {x['regra']}")


if __name__ == "__main__":
    main()
