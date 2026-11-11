"""Cérebro v4 (H30 aprovada no binário): LightGBM treinado em 18 meses de velas de 15 min das 33 moedas, rodando na nuvem.

A cada vela de 15 min fechada: confere as apostas da vela anterior e aposta de novo onde o modelo vê p ≥ 0,53 (sobe) ou p ≤ 0,47
(desce) — as mesmas regras do teste que passou no juiz. Contrato binário simulado a 0,51, 2% da conta por aposta.
O modelo é fixo (lab/modelos/lgbm_v4.txt): não aprende ao vivo, para o placar ao vivo julgar exatamente o que foi testado.

Uso: BALEIAS_DADOS=... BINANCE_DADOS=https://data-api.binance.vision python -m executor.cerebro_v4_nuvem   (precisa de numpy e lightgbm)
"""
import json
import os
import time
import urllib.request
from pathlib import Path

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M
from lab import tartaruga as T

MODELO = Path(__file__).resolve().parent.parent / "lab" / "modelos" / "lgbm_v4.txt"
LIMIAR, PRECO, APOSTA = 0.03, 0.51, 0.02
VELAS = 2200                    # 20 dias do mesmo horário + média de 200 velas
PASSO = 900_000


def baixar(par, cache=None):
    """Velas fechadas de 15 min (as últimas VELAS). Com cache, baixa só as novas (a 1ª vez é a única pesada)."""
    if cache and len(cache) >= VELAS - 5:
        with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={par}&interval=15m&startTime={cache[-1][0]}&limit=1000", timeout=30) as r:
            novas = json.load(r)
        junto = {x[0]: x for x in cache + novas}
        return [junto[t] for t in sorted(junto) if junto[t][6] < time.time() * 1000][-VELAS:]
    fim, saida = None, []
    while len(saida) < VELAS:
        url = f"{T.DADOS}/api/v3/klines?symbol={par}&interval=15m&limit=1000" + (f"&endTime={fim}" if fim else "")
        with urllib.request.urlopen(url, timeout=30) as r:
            k = json.load(r)
        if not k:
            break
        saida = k + saida
        fim = k[0][0] - 1
        time.sleep(0.05)
    return [x for x in saida if x[6] < time.time() * 1000][-VELAS:]


def prever(todas):
    """{par: velas} → {par: (t_ultima_vela, fechamento, prob_de_subir)} usando as mesmas medidas do treino (lab.minerador)."""
    pares = [p for p in T.MOEDAS_ROBO if todas.get(p)]
    fim = max(k[-1][0] for k in todas.values() if k)
    grade = np.arange(fim - (VELAS - 1) * PASSO, fim + 1, PASSO)
    ohlcv = np.full((len(pares), len(grade), 5), np.nan)
    for i, p in enumerate(pares):
        for x in todas[p]:
            j = (x[0] - grade[0]) // PASSO
            if 0 <= j < len(grade):
                ohlcv[i, j] = [float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])]
    X, hora, _, _ = M.medidas(grade, pares, ohlcv)
    modelo = lgb.Booster(model_file=str(MODELO))
    A = np.concatenate([X[:, -1, :], np.full((len(pares), 1), hora[-1])], axis=1)
    p_sobe = modelo.predict(A)
    return {p: (int(grade[-1]), float(ohlcv[i, -1, 3]), float(p_sobe[i])) for i, p in enumerate(pares) if np.isfinite(ohlcv[i, -1, 3])}


def passo(e, previsoes):
    """Confere as apostas pendentes com o fechamento da vela seguinte e registra as novas."""
    for par, pend in list(e["pendentes"].items()):
        nova = previsoes.get(par)
        if not nova or nova[0] != pend["t"] + PASSO:
            if nova and nova[0] > pend["t"] + PASSO:          # pulou vela (rodada atrasada): a aposta não tem como ser conferida
                del e["pendentes"][par]
            continue
        subiu = nova[1] > pend["px"]
        if nova[1] != pend["px"]:
            ganhou = subiu == (pend["aposta"] > 0)
            liquido = APOSTA * ((1 / PRECO - 1) if ganhou else -1)
            e["ops"].setdefault(par, []).append([pend["t"], round(liquido, 6), pend["aposta"]])
            e["ops"][par] = e["ops"][par][-3000:]
        del e["pendentes"][par]
    for par, (t, px, p) in previsoes.items():
        if abs(p - 0.5) >= LIMIAR:
            e["pendentes"][par] = {"t": t, "px": px, "prob": p, "aposta": 1 if p > 0.5 else -1}
    e["ultima"] = {par: {"t": t, "prob": round(p, 4)} for par, (t, px, p) in previsoes.items()}


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / "cerebro_v4.json"
    e = json.loads(arq.read_text()) if arq.exists() else {"ops": {}, "pendentes": {}, "inicio_ao_vivo": int(time.time() * 1000)}
    arq_cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    cache = json.loads(arq_cache.read_text()) if arq_cache.exists() else {}
    todas = {}
    for par in T.MOEDAS_ROBO:
        try:
            todas[par] = baixar(par, cache.get(par))
        except (OSError, ValueError):
            todas[par] = cache.get(par, [])
    arq_cache.parent.mkdir(parents=True, exist_ok=True)
    arq_cache.write_text(json.dumps(todas))
    previsoes = prever(todas)
    passo(e, previsoes)
    arq.write_text(json.dumps(e))
    ops = [o for x in e["ops"].values() for o in x]
    print(f"🌲 Cérebro v4 (LightGBM): {len(ops)} apostas conferidas, acerto {sum(o[1] > 0 for o in ops) / len(ops) * 100 if ops else 0:.1f}%, "
          f"{len(e['pendentes'])} apostas novas nesta vela")


if __name__ == "__main__":
    main()
