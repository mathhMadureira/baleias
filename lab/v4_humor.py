"""H42 — o humor do mercado como filtro de lado para o v4 (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar).

Humor = média entre as 33 moedas, a cada vela, do retorno normalizado de 4 velas (r4) ou de 16 velas (r16), as mesmas medidas do v4.
Braços no teste fora da amostra da H30, com o modelo ANTIGO (lab/modelos/lgbm_v4_anterior.txt — o v4.1 treinou dentro desse período):
  A) só apostas alinhadas com o sinal do humor r4; B) idem com r16; C) = A só quando |humor r4| ≥ 0,3. Referência: todas as apostas.
Juiz: líquido no perpétuo (0,12% ida e volta) > 0, t ≥ 2 agrupado por instante, > 0 em 2 dos 3 blocos, ≥ 20.000 apostas.

Uso: .venv-ml/bin/python -m lab.v4_humor
"""
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M
from lab.v4_estudo import achatar

MODELO = Path(__file__).resolve().parent / "modelos" / "lgbm_v4_anterior.txt"
SAIDA = config.RAIZ / "lab" / "v4_humor.json"
CUSTO, LIMIAR = 0.0012, 0.03


def agrupado(valor, tt):
    ordem = np.argsort(tt, kind="stable")
    tv, vv = tt[ordem], valor[ordem]
    grupos = np.split(vv, np.flatnonzero(np.diff(tv)) + 1)
    medias = np.array([g.mean() for g in grupos])
    return float(valor.mean()), float(medias.mean() / (medias.std(ddof=1) / np.sqrt(len(medias)))) if len(medias) > 1 and medias.std(ddof=1) > 0 else 0.0


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    nt = len(t)
    teste = slice(nt * 3 // 4, nt - 1)
    humor4_t = np.nanmean(X[:, :, M.NOMES.index("r4")], axis=0)        # humor por vela (média entre moedas)
    humor16_t = np.nanmean(X[:, :, M.NOMES.index("r16")], axis=0)
    A, yy, rr, moeda, tempo = achatar(X, hora, y, ret, t, teste)
    idx = np.searchsorted(np.asarray(t), tempo)                          # índice da vela de cada amostra
    h4, h16 = humor4_t[idx], humor16_t[idx]
    p = lgb.Booster(model_file=str(MODELO)).predict(A)
    aposta = np.abs(p - 0.5) >= LIMIAR
    lado = np.where(p > 0.5, 1.0, -1.0)
    liq = lado * rr - CUSTO
    certo = ((p > 0.5) == (yy > 0.5)).astype(float)
    n_t = len(tempo)
    ordem = np.argsort(tempo, kind="stable")
    bloco = np.empty(n_t, dtype=int)
    bloco[ordem] = np.arange(n_t) * 3 // n_t
    res = {"quando": time.strftime("%Y-%m-%d %H:%M"), "bracos": {}}

    def julgar(nome, masc, referencia=False):
        m, tt_ = agrupado(liq[masc], tempo[masc])
        blocos = [float(liq[masc & (bloco == b)].mean() * 100) if (masc & (bloco == b)).any() else None for b in range(3)]
        r = {"n": int(masc.sum()), "perp_pct": m * 100, "t": tt_, "blocos_pct": blocos, "acerto": float(certo[masc].mean()),
             "passa": bool(not referencia and m > 0 and tt_ >= 2 and sum(1 for b in blocos if b is not None and b > 0) >= 2 and masc.sum() >= 20000)}
        res["bracos"][nome] = r
        print(f"{nome:34s} n={r['n']:6d} acerto {r['acerto'] * 100:.2f}% perp {r['perp_pct']:+.4f}%/op (t {tt_:+.1f}) blocos {[round(b, 4) if b is not None else None for b in blocos]}"
              + ("" if referencia else f" → {'PASSA' if r['passa'] else 'não passa'}"))

    julgar("referência: todas as apostas", aposta, referencia=True)
    alinhado4 = aposta & (np.sign(h4) == lado)
    julgar("A: alinhado com o humor r4", alinhado4)
    julgar("B: alinhado com o humor r16", aposta & (np.sign(h16) == lado))
    julgar("C: A e |humor r4| ≥ 0,3", alinhado4 & (np.abs(h4) >= 0.3))
    julgar("leitura: CONTRA o humor r4", aposta & (np.sign(h4) == -lado), referencia=True)
    res["segundos"] = round(time.time() - t0)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
