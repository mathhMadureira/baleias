"""H38 — LightGBM com alvo de LUCRO no perpétuo (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar).

Pedido do dono: operações com lucro, não só direção. O v4 acerta a direção (53,9%) mas o movimento de 15 min é pequeno demais para
pagar o custo. Aqui o alvo muda: em vez de "sobe ou desce", dois modelos aprendem "o fechamento da PRÓXIMA vela fica ≥ +0,15% acima"
(classe alta) e "fica ≤ −0,15% abaixo" (classe baixa) — movimentos que pagam o custo de 0,12% e sobram. Mesmos dados e as mesmas
16 medidas da H30 (lab/minerador.py), mesmos cortes (treino 50%, validação 25%, teste 25% em 3 blocos), mesmos parâmetros.

Regra de operação no teste: compra quando P(alta) − P(baixa) ≥ d, vende quando P(baixa) − P(alta) ≥ d, para d em {0,05, 0,10, 0,15}
(três tentativas, contadas). Resultado líquido por operação = retorno da vela no sentido da aposta − 0,12%.
Juiz (igual ao da H30 no perpétuo): média líquida > 0, t ≥ 2 agrupado por instante, média > 0 em 2 dos 3 blocos, ≥ 1.000 operações.

Uso: .venv-ml/bin/python -m lab.lgbm_alvo
"""
import json
import time

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M
from lab.lgbm import PARAMS, matriz

ALVO = 0.0015
CUSTO = 0.0012
DELTAS = (0.05, 0.10, 0.15)
ARQ = config.RAIZ / "lab" / "lgbm_alvo_resultado.json"
MODELOS = config.RAIZ.parent / "lab" / "modelos"


def agrupado(valor, tt):
    """Média e t do retorno líquido agrupando por instante (as moedas andam juntas: cada vela conta como uma observação)."""
    if len(valor) < 50:
        return {"n": int(len(valor)), "media": None, "t": 0.0}
    ordem = np.argsort(tt, kind="stable")
    tv, vv = tt[ordem], valor[ordem]
    cortes = np.flatnonzero(np.diff(tv)) + 1
    grupos = np.split(vv, cortes)
    medias = np.array([g.mean() for g in grupos])
    t = medias.mean() / (medias.std(ddof=1) / np.sqrt(len(medias))) if len(medias) > 1 and medias.std(ddof=1) > 0 else 0.0
    return {"n": int(len(valor)), "instantes": int(len(medias)), "media": float(valor.mean()), "t": float(t)}


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    nt = len(t)
    treino, valid, teste = slice(200, nt // 2), slice(nt // 2, nt * 3 // 4), slice(nt * 3 // 4, nt - 1)
    nomes = M.NOMES + ["hora"]
    At, _, rt, _ = matriz(X, hora, y, ret, treino)
    Av, _, rv, _ = matriz(X, hora, y, ret, valid)
    modelos = {}
    for classe, rotulo_t, rotulo_v in (("alta", (rt >= ALVO).astype(float), (rv >= ALVO).astype(float)),
                                       ("baixa", (rt <= -ALVO).astype(float), (rv <= -ALVO).astype(float))):
        m = lgb.train(PARAMS, lgb.Dataset(At, rotulo_t, feature_name=nomes, categorical_feature=["hora"]), num_boost_round=600,
                      valid_sets=[lgb.Dataset(Av, rotulo_v, feature_name=nomes, categorical_feature=["hora"])],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
        modelos[classe] = m
        print(f"modelo {classe}: {m.best_iteration} árvores, base {rotulo_t.mean():.1%} das velas; medidas mais usadas: "
              f"{[n for n, _ in sorted(zip(nomes, m.feature_importance('gain')), key=lambda x: -x[1])[:5]]}")
    n_teste = teste.stop - teste.start
    fatias = [("teste inteiro", teste)] + [(f"bloco {i + 1}", slice(teste.start + i * n_teste // 3, teste.start + (i + 1) * n_teste // 3)) for i in range(3)]
    resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "alvo": ALVO, "custo": CUSTO, "arvores": {k: m.best_iteration for k, m in modelos.items()}, "deltas": {}}
    for d in DELTAS:
        linhas = []
        for nome, f in fatias:
            A, _, rr, tt = matriz(X, hora, y, ret, f)
            pa = modelos["alta"].predict(A, num_iteration=modelos["alta"].best_iteration)
            pb = modelos["baixa"].predict(A, num_iteration=modelos["baixa"].best_iteration)
            lado = np.where(pa - pb >= d, 1.0, np.where(pb - pa >= d, -1.0, 0.0))
            usa = lado != 0
            liq = lado[usa] * rr[usa] - CUSTO
            j = agrupado(liq, tt[usa])
            j.update(nome=nome, acerto=float((lado[usa] * rr[usa] > 0).mean()) if usa.any() else None)
            linhas.append(j)
        tot, blocos = linhas[0], linhas[1:]
        passa = (tot["media"] or -1) > 0 and tot["t"] >= 2 and sum(1 for b in blocos if (b["media"] or -1) > 0) >= 2 and tot["n"] >= 1000
        resultado["deltas"][str(d)] = {"linhas": linhas, "passa": passa}
        print(f"d = {d:.2f}: " + " | ".join(f"{l['nome']}: {l['n']} op, líquido {((l['media'] or 0) * 100):+.3f}%/op, acerto {(l['acerto'] or 0):.1%}, t {l['t']:.1f}" for l in linhas)
              + f" → {'PASSA' if passa else 'reprova'}")
    resultado["segundos"] = round(time.time() - t0)
    ARQ.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    MODELOS.mkdir(parents=True, exist_ok=True)
    for k, m in modelos.items():
        m.save_model(str(MODELOS / f"lgbm_alvo_{k}.txt"), num_iteration=m.best_iteration)


if __name__ == "__main__":
    main()
