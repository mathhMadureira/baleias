"""H36, parte 1 (descritiva, pré-registrada em lab/PROTOCOLO_LAB.md): onde o Cérebro v4 acerta e onde erra, no TESTE fora da
amostra da H30 (25% finais dos dados), com o modelo salvo em lab/modelos/lgbm_v4.txt — SEM retreinar e sem mudar nada no modelo.

Cortes fixados antes de rodar: faixa de hora UTC (0–5, 6–11, 12–17, 18–23), dia da semana, faixa de confiança |p − 0,5|
(0,03–0,05, 0,05–0,08, 0,08–0,12, ≥0,12), lado (compra/venda) e moeda. Para cada corte: nº de apostas, acerto no binário e
resultado líquido no perpétuo (0,12% ida e volta), no teste inteiro e nos 3 blocos.

Uso: .venv-ml/bin/python -m lab.v4_estudo   (precisa de numpy e lightgbm; lê o cache dados/lab/minerador_15m.npz)
"""
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

from baleias import config
from lab import minerador as M

MODELO = Path(__file__).resolve().parent / "modelos" / "lgbm_v4.txt"
SAIDA = config.RAIZ / "lab" / "v4_estudo.json"
CUSTO = 0.0012
LIMIAR = 0.03


def achatar(X, hora, y, ret, t, fatia):
    nm = X.shape[0]
    xs = X[:, fatia, :]
    n = xs.shape[1]
    A = np.concatenate([xs.reshape(-1, xs.shape[2]), np.broadcast_to(hora[fatia], (nm, n)).reshape(-1, 1)], axis=1)
    yy, rr = y[:, fatia].reshape(-1), ret[:, fatia].reshape(-1)
    moeda = np.broadcast_to(np.arange(nm)[:, None], (nm, n)).reshape(-1)
    tempo = np.broadcast_to(np.asarray(t)[fatia], (nm, n)).reshape(-1)
    ok = np.isfinite(yy) & np.isfinite(rr) & np.isfinite(A[:, :-1]).all(axis=1)
    return A[ok], yy[ok], rr[ok], moeda[ok], tempo[ok]


def resumo(certo, liq, mascara):
    n = int(mascara.sum())
    if n == 0:
        return {"n": 0}
    return {"n": n, "acerto": round(float(certo[mascara].mean()), 4), "perp_liq_pct": round(float(liq[mascara].mean()) * 100, 4)}


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    X, hora, y, ret = M.medidas(t, moedas, ohlcv)
    nt = len(t)
    teste = slice(nt * 3 // 4, nt - 1)
    A, yy, rr, moeda, tempo = achatar(X, hora, y, ret, t, teste)
    p = lgb.Booster(model_file=str(MODELO)).predict(A)
    aposta = np.abs(p - 0.5) >= LIMIAR
    lado = np.where(p > 0.5, 1.0, -1.0)
    certo = ((p > 0.5) == (yy > 0.5)).astype(float)
    liq = lado * rr - CUSTO
    n_teste = len(tempo)
    ordem = np.argsort(tempo, kind="stable")
    bloco = np.empty(n_teste, dtype=int)
    bloco[ordem] = np.arange(n_teste) * 3 // n_teste
    saida = {"quando": time.strftime("%Y-%m-%d %H:%M"), "apostas_teste": int(aposta.sum()), "cortes": {}}
    hora_utc = A[:, -1]
    dia_semana = np.array([time.gmtime(x / 1000).tm_wday for x in tempo])
    conf = np.abs(p - 0.5)
    cortes = {
        "total": {"todas": aposta},
        "hora_utc": {f"{h:02d}-{h + 5:02d}": aposta & (hora_utc >= h) & (hora_utc < h + 6) for h in (0, 6, 12, 18)},
        "dia_semana": {n: aposta & (dia_semana == i) for i, n in enumerate(["seg", "ter", "qua", "qui", "sex", "sáb", "dom"])},
        "confianca": {"0,03–0,05": aposta & (conf < 0.05), "0,05–0,08": aposta & (conf >= 0.05) & (conf < 0.08),
                      "0,08–0,12": aposta & (conf >= 0.08) & (conf < 0.12), "≥0,12": aposta & (conf >= 0.12)},
        "lado": {"compra": aposta & (lado > 0), "venda": aposta & (lado < 0)},
        "moeda": {m[:-4]: aposta & (moeda == i) for i, m in enumerate(moedas)},
    }
    for nome, grupos in cortes.items():
        saida["cortes"][nome] = {}
        for g, masc in grupos.items():
            saida["cortes"][nome][g] = {"teste": resumo(certo, liq, masc), "blocos": [resumo(certo, liq, masc & (bloco == b)) for b in range(3)]}
    saida["segundos"] = round(time.time() - t0)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1))
    print(f"teste fora da amostra: {saida['apostas_teste']} apostas ({saida['segundos']} s)")
    for nome in ("total", "hora_utc", "dia_semana", "confianca", "lado"):
        for g, r in saida["cortes"][nome].items():
            tt = r["teste"]
            bl = " ".join(f"{b['acerto'] * 100:.1f}" if b.get("n") else "—" for b in r["blocos"])
            print(f"  {nome:11s} {g:10s} n={tt['n']:7d} acerto {tt['acerto'] * 100:5.1f}% [blocos {bl}] perp {tt['perp_liq_pct']:+.3f}%/op")
    rk = sorted(((g, r["teste"]) for g, r in saida["cortes"]["moeda"].items() if r["teste"]["n"]), key=lambda x: -x[1]["acerto"])
    print("  moedas melhores:", [(g, f"{r['acerto'] * 100:.1f}%") for g, r in rk[:5]])
    print("  moedas piores:  ", [(g, f"{r['acerto'] * 100:.1f}%") for g, r in rk[-5:]])


if __name__ == "__main__":
    main()
