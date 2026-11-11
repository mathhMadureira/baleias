"""H30 — LightGBM como os "olhos" do robô, com juiz duro (pré-registrado em PROTOCOLO_LAB.md).

Mesmos dados e medidas do minerador (H26). Treina na 1ª metade, para cedo pela validação (25%) e julga no teste (25% finais),
dividido em 3 blocos: passa só se vencer no total E em 2 dos 3 blocos, depois dos custos.

Uso: .venv-ml/bin/python -m lab.lgbm
"""
import json
import time

import lightgbm as lgb
import numpy as np

from baleias import config

from . import minerador as M

PARAMS = {"objective": "binary", "num_leaves": 63, "learning_rate": 0.03, "min_data_in_leaf": 2000, "bagging_fraction": 0.8,
          "bagging_freq": 1, "feature_fraction": 0.8, "verbose": -1, "seed": 7}
LIMIAR_BIN, LIMIAR_PERP, CUSTO = 0.03, 0.04, 0.0012
ARQ = config.RAIZ / "lab" / "lgbm_resultado.json"


def matriz(X, hora, y, ret, fatia):
    nm = X.shape[0]
    xs = X[:, fatia, :]
    hs = np.broadcast_to(hora[fatia], (nm, xs.shape[1]))
    tempo = np.broadcast_to(np.arange(fatia.start, fatia.stop), (nm, xs.shape[1]))
    A = np.concatenate([xs.reshape(-1, xs.shape[2]), hs.reshape(-1, 1)], axis=1)
    yy, rr, tt = y[:, fatia].reshape(-1), ret[:, fatia].reshape(-1), tempo.reshape(-1)
    ok = np.isfinite(yy) & np.isfinite(rr)
    return A[ok], yy[ok], rr[ok], tt[ok]


def julgar(p, yy, rr, tt):
    """Binário: acerto agrupado por instante; perpétuo: retorno líquido agrupado por instante."""
    def agrupado(valor, usa):
        if usa.sum() < 50:
            return {"n": int(usa.sum()), "media": None, "t": 0.0}
        tv, vv = tt[usa], valor[usa]
        ordem = np.argsort(tv)
        tv, vv = tv[ordem], vv[ordem]
        cortes = np.flatnonzero(np.diff(tv)) + 1
        medias = np.array([g.mean() for g in np.split(vv, cortes)])
        t = float(medias.mean() / (medias.std(ddof=1) / np.sqrt(len(medias)))) if len(medias) > 2 and medias.std(ddof=1) > 0 else 0.0
        return {"n": int(usa.sum()), "instantes": len(medias), "media": float(vv.mean()), "t": t}
    aposta = np.abs(p - 0.5) >= LIMIAR_BIN
    sobe = p >= 0.5
    acerto = (sobe == (yy == 1)).astype(float)
    b = agrupado(acerto - 0.5, aposta)
    if b["media"] is not None:
        b["acerto"] = b["media"] + 0.5
    opera = np.abs(p - 0.5) >= LIMIAR_PERP
    liquido = np.where(sobe, rr, -rr) - CUSTO
    q = agrupado(liquido, opera)
    return {"binario": b, "perpetuo": q}


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    nt = len(t)
    treino, valid = slice(200, nt // 2), slice(nt // 2, nt * 3 // 4)
    teste = slice(nt * 3 // 4, nt - 1)
    At, yt, _, _ = matriz(X, hora, y, ret, treino)
    Av, yv, _, _ = matriz(X, hora, y, ret, valid)
    nomes = M.NOMES + ["hora"]
    modelo = lgb.train(PARAMS, lgb.Dataset(At, yt, feature_name=nomes, categorical_feature=["hora"]), num_boost_round=600,
                       valid_sets=[lgb.Dataset(Av, yv, feature_name=nomes, categorical_feature=["hora"])],
                       callbacks=[lgb.early_stopping(50, verbose=False)])
    resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "arvores": modelo.best_iteration,
                 "importancia": dict(sorted(zip(nomes, modelo.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])), "blocos": []}
    n_teste = teste.stop - teste.start
    fatias = [slice(teste.start + i * n_teste // 3, teste.start + (i + 1) * n_teste // 3) for i in range(3)]
    for nome, f in [("teste inteiro", teste)] + [(f"bloco {i + 1}", f) for i, f in enumerate(fatias)]:
        A, yy, rr, tt = matriz(X, hora, y, ret, f)
        j = julgar(modelo.predict(A, num_iteration=modelo.best_iteration), yy, rr, tt)
        j["nome"] = nome
        resultado["blocos"].append(j)
    tot, blocos = resultado["blocos"][0], resultado["blocos"][1:]
    bin_ok = (tot["binario"].get("acerto") or 0) > 0.51 and tot["binario"]["t"] >= 2 and \
        sum(1 for b in blocos if (b["binario"].get("acerto") or 0) > 0.51) >= 2
    perp_ok = (tot["perpetuo"]["media"] or -1) > 0 and tot["perpetuo"]["t"] >= 2 and \
        sum(1 for b in blocos if (b["perpetuo"]["media"] or -1) > 0) >= 2
    resultado.update(binario_passa=bin_ok, perpetuo_passa=perp_ok, segundos=round(time.time() - t0))
    ARQ.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    modelo.save_model(str(config.RAIZ / "lab" / "lgbm_modelo.txt"), num_iteration=modelo.best_iteration)
    print(f"árvores: {modelo.best_iteration} · medidas mais usadas: {list(resultado['importancia'])[:6]}")
    for b in resultado["blocos"]:
        bi, pe = b["binario"], b["perpetuo"]
        print(f"  {b['nome']:14} binário: {bi['n']:7d} apostas, acerto {(bi.get('acerto') or 0):.1%} t={bi['t']:.1f} | "
              f"perpétuo: {pe['n']:7d} op., líquido {((pe['media'] or 0) * 100):+.3f}%/op t={pe['t']:.1f}")
    print(f"JUIZ → binário {'PASSA' if bin_ok else 'reprova'} · perpétuo {'PASSA' if perp_ok else 'reprova'}")


if __name__ == "__main__":
    main()
