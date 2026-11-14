"""H40 — alvo dinâmico por ATR nas apostas do v4 (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar).

Apostas do v4 (|p − 0,5| ≥ 0,03) no teste fora da amostra da H30, entrada no fechamento da vela do sinal, saída DENTRO da vela seguinte:
  stop fixo de 1% (mínima/máxima; se stop e alvo caberiam na mesma vela, conta o stop), alvo = entrada ± k × ATR14, senão o fechamento.
Braços (três tentativas): k = 1,0 / 1,5 / 2,0. Referências: R1 = sair no fechamento; R2 = fechamento com stop de 1% (Rápido nuvem de hoje).
Custo 0,06% por lado. Juiz: média líquida > 0, t ≥ 2 agrupado por instante, média > 0 em 2 dos 3 blocos, e acima de R2.

Uso: .venv-ml/bin/python -m lab.v4_alvo_atr
"""
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M

MODELO = Path(__file__).resolve().parent / "modelos" / "lgbm_v4.txt"
SAIDA = config.RAIZ / "lab" / "v4_alvo_atr.json"
CUSTO_LADO, STOP, LIMIAR = 0.0006, 0.01, 0.03


def agrupado(valor, tt):
    ordem = np.argsort(tt, kind="stable")
    tv, vv = tt[ordem], valor[ordem]
    grupos = np.split(vv, np.flatnonzero(np.diff(tv)) + 1)
    medias = np.array([g.mean() for g in grupos])
    t = medias.mean() / (medias.std(ddof=1) / np.sqrt(len(medias))) if len(medias) > 1 and medias.std(ddof=1) > 0 else 0.0
    return float(valor.mean()), float(t), int(len(medias))


def saida_na_vela(lado, entrada, o, h, l, c, alvo, stop):
    """Preço de saída dentro da vela seguinte: stop primeiro (conservador), depois alvo, senão fechamento. Vetorizado."""
    px_stop = np.where(lado > 0, entrada * (1 - stop), entrada * (1 + stop))
    toca_stop = np.where(lado > 0, l <= px_stop, h >= px_stop)
    px_stop_exec = np.where(lado > 0, np.minimum(o, px_stop), np.maximum(o, px_stop))      # abriu além do stop: sai na abertura
    saida = c.copy()
    if alvo is not None:
        toca_alvo = np.where(lado > 0, h >= alvo, l <= alvo)
        saida = np.where(toca_alvo, alvo, saida)
    saida = np.where(toca_stop, px_stop_exec, saida)
    motivo = np.where(toca_stop, 0, np.where((alvo is not None) & (np.where(lado > 0, h >= alvo, l <= alvo) if alvo is not None else False), 1, 2))
    return saida, motivo


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    t = np.asarray(t)
    nm, nt = ohlcv.shape[:2]
    teste = slice(nt * 3 // 4, nt - 1)
    o, h, l, c = (ohlcv[:, :, k] for k in range(4))
    pc = np.concatenate([np.full((nm, 1), np.nan), c[:, :-1]], axis=1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = np.stack([M._janela(tr[i], 14, np.nanmean) for i in range(nm)])
    js = np.arange(teste.start, teste.stop)
    ii = np.repeat(np.arange(nm), len(js))
    jj = np.tile(js, nm)
    A = np.concatenate([X[ii, jj, :], hora[jj][:, None]], axis=1)
    entrada, atr_j = c[ii, jj], atr[ii, jj - 1]
    o1, h1, l1, c1 = o[ii, jj + 1], h[ii, jj + 1], l[ii, jj + 1], c[ii, jj + 1]
    ok = np.isfinite(A).all(axis=1) & np.isfinite(entrada) & np.isfinite(atr_j) & (atr_j > 0) & np.isfinite(o1) & np.isfinite(h1) & np.isfinite(l1) & np.isfinite(c1)
    A, entrada, atr_j, o1, h1, l1, c1, tt = A[ok], entrada[ok], atr_j[ok], o1[ok], h1[ok], l1[ok], c1[ok], t[jj[ok]]
    p = lgb.Booster(model_file=str(MODELO)).predict(A)
    aposta = np.abs(p - 0.5) >= LIMIAR
    lado = np.where(p > 0.5, 1.0, -1.0)
    conf = np.abs(p - 0.5)
    n = int(aposta.sum())
    ordem = np.argsort(tt[aposta], kind="stable")
    bloco = np.empty(n, dtype=int)
    bloco[ordem] = np.arange(n) * 3 // n
    resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "apostas": n, "bracos": {}}

    def julgar(nome, saida, motivo, referencia=False):
        liq = (lado * (saida / entrada - 1) - 2 * CUSTO_LADO)[aposta]
        media, tstat, inst = agrupado(liq, tt[aposta])
        blocos = [float(liq[bloco == b].mean() * 100) for b in range(3)]
        alta = conf[aposta] >= 0.12
        m_alta = float(liq[alta].mean() * 100) if alta.any() else None
        mot = motivo[aposta]
        r = {"media_pct": media * 100, "t": tstat, "instantes": inst, "blocos_pct": blocos, "acerto": float((liq > 0).mean()),
             "stops": int((mot == 0).sum()), "alvos": int((mot == 1).sum()), "fechamentos": int((mot == 2).sum()), "conf_alta_pct": m_alta, "referencia": referencia}
        resultado["bracos"][nome] = r
        print(f"{nome:28s} média {media * 100:+.4f}%/op (t {tstat:+.1f}) blocos {[round(b, 4) for b in blocos]} acerto {r['acerto']:.1%} "
              f"stops {r['stops']} alvos {r['alvos']} fech {r['fechamentos']} | conf ≥0,12: {m_alta:+.4f}%/op")
        return r

    s, m = saida_na_vela(lado, entrada, o1, h1, l1, c1, None, 99.0)          # R1: fechamento, sem stop (stop impossível)
    r1 = julgar("R1 fechamento", s, m, referencia=True)
    s, m = saida_na_vela(lado, entrada, o1, h1, l1, c1, None, STOP)
    r2 = julgar("R2 fechamento + stop 1%", s, m, referencia=True)
    for k in (1.0, 1.5, 2.0):
        alvo = entrada + lado * k * atr_j
        s, m = saida_na_vela(lado, entrada, o1, h1, l1, c1, alvo, STOP)
        r = julgar(f"alvo {k:.1f}×ATR14 + stop 1%", s, m)
        r["passa"] = bool(r["media_pct"] > 0 and r["t"] >= 2 and sum(1 for b in r["blocos_pct"] if b > 0) >= 2 and r["media_pct"] > r2["media_pct"])
        print(f"   → {'PASSA' if r['passa'] else 'não passa'}")
    resultado["segundos"] = round(time.time() - t0)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
