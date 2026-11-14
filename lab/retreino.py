"""H41 — ensinar o v4 com os dados novos: retreino com a mesma receita e juiz no holdout (pré-registrada em lab/PROTOCOLO_LAB.md).

Baixa as velas de 15 min das 33 moedas de 2025-05-01 até agora (cache próprio, dados/lab/retreino_15m.npz), separa os ÚLTIMOS 30 DIAS
como holdout (3 blocos de 10 dias), treina o v4.1 com a receita da H30 no período anterior (2/3 treino, 1/3 validação) e compara, no
holdout, o v4 velho (lab/modelos/lgbm_v4.txt) com o v4.1: acerto binário e líquido no perpétuo (0,12%) nas faixas |p − 0,5| ≥ 0,03 e ≥ 0,12.
Passa (v4.1 substitui o v4) se o acerto binário (≥ 0,03) do novo for maior no holdout inteiro E em ≥ 2 dos 3 blocos, com ≥ 20.000 apostas.

Uso: .venv-ml/bin/python -m lab.retreino
"""
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M
from lab.lgbm import PARAMS

MODELO_VELHO = Path(__file__).resolve().parent / "modelos" / "lgbm_v4.txt"
MODELO_NOVO = Path(__file__).resolve().parent / "modelos" / "lgbm_v4_1.txt"
SAIDA = config.RAIZ / "lab" / "retreino_resultado.json"
HOLDOUT_DIAS = 30
CUSTO = 0.0012


def achatar(X, hora, y, ret, fatia):
    nm = X.shape[0]
    xs = X[:, fatia, :]
    n = xs.shape[1]
    A = np.concatenate([xs.reshape(-1, xs.shape[2]), np.broadcast_to(hora[fatia], (nm, n)).reshape(-1, 1)], axis=1)
    yy, rr = y[:, fatia].reshape(-1), ret[:, fatia].reshape(-1)
    tt = np.broadcast_to(np.arange(fatia.start, fatia.stop), (nm, n)).reshape(-1)
    ok = np.isfinite(yy) & np.isfinite(rr) & np.isfinite(A[:, :-1]).all(axis=1)
    return A[ok], yy[ok], rr[ok], tt[ok]


def medir(p, yy, rr, tt, bloco, limiar):
    aposta = np.abs(p - 0.5) >= limiar
    certo = ((p > 0.5) == (yy > 0.5))[aposta]
    liq = (np.where(p > 0.5, 1.0, -1.0) * rr - CUSTO)[aposta]
    bl = bloco[aposta]
    return {"n": int(aposta.sum()), "acerto": float(certo.mean()) if aposta.any() else None, "perp_pct": float(liq.mean() * 100) if aposta.any() else None,
            "blocos_acerto": [float(certo[bl == b].mean()) if (bl == b).any() else None for b in range(3)],
            "blocos_perp_pct": [float(liq[bl == b].mean() * 100) if (bl == b).any() else None for b in range(3)]}


def main():
    t0 = time.time()
    agora_ms = int(time.time() * 1000) // M.PASSO_MS * M.PASSO_MS
    M.FIM_MS = agora_ms                                   # dados até agora (o módulo fixa 2026-11-11 para os testes antigos serem reproduzíveis)
    M.ARQ_DADOS = config.RAIZ / "lab" / "retreino_15m.npz"
    t, moedas, ohlcv = M.baixar()
    print(f"dados: {len(moedas)} moedas, {len(t)} velas de 15 min, de {time.strftime('%Y-%m-%d', time.gmtime(t[0] / 1000))} a "
          f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(t[-1] / 1000))} UTC ({time.time() - t0:.0f} s)")
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    nt = len(t)
    corte = nt - HOLDOUT_DIAS * M.DIA
    treino, valid, hold = slice(200, 200 + (corte - 200) * 2 // 3), slice(200 + (corte - 200) * 2 // 3, corte), slice(corte, nt - 1)
    nomes = M.NOMES + ["hora"]
    At, yt, _, _ = achatar(X, hora, y, ret, treino)
    Av, yv, _, _ = achatar(X, hora, y, ret, valid)
    novo = lgb.train(PARAMS, lgb.Dataset(At, yt, feature_name=nomes, categorical_feature=["hora"]), num_boost_round=600,
                     valid_sets=[lgb.Dataset(Av, yv, feature_name=nomes, categorical_feature=["hora"])], callbacks=[lgb.early_stopping(50, verbose=False)])
    velho = lgb.Booster(model_file=str(MODELO_VELHO))
    Ah, yh, rh, th = achatar(X, hora, y, ret, hold)
    n_h = hold.stop - hold.start
    bloco = (th - hold.start) * 3 // n_h
    pv, pn = velho.predict(Ah), novo.predict(Ah, num_iteration=novo.best_iteration)
    res = {"quando": time.strftime("%Y-%m-%d %H:%M"), "holdout": [time.strftime("%Y-%m-%d", time.gmtime(t[hold.start] / 1000)), time.strftime("%Y-%m-%d", time.gmtime(t[hold.stop - 1] / 1000))],
           "arvores_novo": novo.best_iteration, "treino": [time.strftime("%Y-%m-%d", time.gmtime(t[treino.start] / 1000)), time.strftime("%Y-%m-%d", time.gmtime(t[valid.stop - 1] / 1000))], "faixas": {}}
    for lim in (0.03, 0.12):
        res["faixas"][str(lim)] = {"velho": medir(pv, yh, rh, th, bloco, lim), "novo": medir(pn, yh, rh, th, bloco, lim)}
    v, n = res["faixas"]["0.03"]["velho"], res["faixas"]["0.03"]["novo"]
    ganha_blocos = sum(1 for a, b in zip(n["blocos_acerto"], v["blocos_acerto"]) if a is not None and b is not None and a > b)
    res["passa"] = bool(n["n"] >= 20000 and n["acerto"] > v["acerto"] and ganha_blocos >= 2)
    res["segundos"] = round(time.time() - t0)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    novo.save_model(str(MODELO_NOVO), num_iteration=novo.best_iteration)
    print(f"holdout {res['holdout'][0]} → {res['holdout'][1]} · treino do novo {res['treino'][0]} → {res['treino'][1]} ({novo.best_iteration} árvores)")
    for lim, f in res["faixas"].items():
        for k in ("velho", "novo"):
            m = f[k]
            print(f"  |p−0,5| ≥ {lim} {k:5s}: {m['n']:6d} apostas, acerto {m['acerto'] * 100:.2f}% [blocos {' '.join(f'{b * 100:.1f}' for b in m['blocos_acerto'])}], "
                  f"perp {m['perp_pct']:+.3f}%/op [blocos {' '.join(f'{b:+.3f}' for b in m['blocos_perp_pct'])}]")
    print("JUIZ (acerto ≥0,03, total e 2 de 3 blocos):", "PASSA — v4.1 substitui o v4" if res["passa"] else "não passa — o v4 fica")


if __name__ == "__main__":
    main()
