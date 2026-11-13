"""H39 — pegar a tendência de horas e segurar (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar).

Pedido do dono (13/11): "BMT subiu de 01:00 até 13:00, por que nenhum robô entrou e ficou comprado segurando a subida?" Nenhum robô
atual segura além de uma vela de 15 min. Regra, como escrita no protocolo:
  a cada vela de 15 min fechada: z = retorno de 4 h (16 velas) ÷ desvio-padrão dos retornos de 4 h dos últimos 20 dias;
  vol = volume das últimas 4 h ÷ média do volume de 4 h dos últimos 20 dias.
  COMPRA se z ≥ 2 e vol ≥ 1,5; VENDA se z ≤ −2 e vol ≥ 1,5; ao fechamento da vela, uma posição por moeda.
  Sai no stop móvel (extremo desde a entrada ∓ k × ATR20 de 15 min, conferido na mínima/máxima da vela seguinte com o extremo até a
  vela anterior), no stop fixo de 2% ou no tempo máximo. Custo 0,12% ida e volta.
Três tentativas (contadas): A) k = 2, máx. 48 velas, compra e venda; B) k = 3, máx. 96 velas, compra e venda; C) = A só compra.
Juiz: média líquida/op > 0, t ≥ 2 agrupado por dia de entrada, média > 0 em 2 dos 3 blocos, ≥ 300 operações.

Uso: .venv-ml/bin/python -m lab.tendencia_horas   (lê dados/lab/minerador_15m.npz pelo lab.minerador)
"""
import json
import math
import time

import numpy as np

from baleias import config
from lab import minerador as M

CUSTO = 0.0012
STOP_FIXO = 0.02
JANELA_20D = 96 * 20
SAIDA = config.RAIZ / "lab" / "tendencia_horas_resultado.json"


def simular(ohlcv, t, k_atr, max_velas, lados, z_min=2.0, vol_min=1.5):
    ops = []
    nm, nt = ohlcv.shape[:2]
    for i in range(nm):
        o, h, l, c, v = (ohlcv[i, :, k] for k in range(5))
        if np.isfinite(c).sum() < JANELA_20D + 100:
            continue
        lc = np.log(c)
        r16 = lc - M._desloca(lc, 16)
        sig16 = M._janela(r16, JANELA_20D, np.nanstd)
        vol4 = M._janela(v, 16, np.nansum)
        vol4m = M._janela(vol4, JANELA_20D, np.nanmean)
        tr = np.maximum(h - l, np.maximum(np.abs(h - M._desloca(c, 1)), np.abs(l - M._desloca(c, 1))))
        atr = M._janela(tr, 20, np.nanmean)
        pos, j = 0, JANELA_20D + 20
        while j < nt - 1:
            if pos == 0:
                z = r16[j] / sig16[j] if sig16[j] > 0 else np.nan
                vr = vol4[j] / vol4m[j] if vol4m[j] > 0 else np.nan
                if np.isfinite(z) and np.isfinite(vr) and abs(z) >= z_min and vr >= vol_min and np.isfinite(c[j]) and atr[j] > 0:
                    lado = 1 if z > 0 else -1
                    if lado in lados:
                        pos, entrada, extremo, j0, t0 = lado, c[j], c[j], j, t[j]
            else:
                if not (np.isfinite(h[j]) and np.isfinite(l[j]) and np.isfinite(c[j])):
                    j += 1
                    continue
                stop = extremo - k_atr * atr[j - 1] if pos == 1 else extremo + k_atr * atr[j - 1]
                fixo = entrada * (1 - STOP_FIXO) if pos == 1 else entrada * (1 + STOP_FIXO)
                gatilho = max(stop, fixo) if pos == 1 else min(stop, fixo)
                saida, motivo = None, None
                if (l[j] <= gatilho) if pos == 1 else (h[j] >= gatilho):
                    saida = (min(o[j], gatilho) if pos == 1 else max(o[j], gatilho)) if np.isfinite(o[j]) else gatilho
                    motivo = "stop móvel" if (gatilho == stop) else "stop fixo 2%"
                elif j - j0 >= max_velas:
                    saida, motivo = c[j], "tempo máximo"
                if saida is not None:
                    ret = pos * (saida / entrada - 1) - CUSTO
                    ops.append({"moeda": i, "lado": pos, "t": int(t0), "velas": j - j0, "ret": float(ret), "motivo": motivo})
                    pos = 0
                else:
                    extremo = max(extremo, h[j]) if pos == 1 else min(extremo, l[j])
            j += 1
    return ops


def juiz(ops, t_ini, t_fim):
    if not ops:
        return {"n": 0}
    por_dia = {}
    for op in ops:
        por_dia.setdefault(op["t"] // 86_400_000, []).append(op["ret"])
    medias = np.array([np.mean(x) for x in por_dia.values()])
    tt = medias.mean() / (medias.std(ddof=1) / math.sqrt(len(medias))) if len(medias) > 1 and medias.std(ddof=1) > 0 else 0.0
    rets = np.array([op["ret"] for op in ops])
    n = len(ops)
    cortes = [t_ini + (t_fim - t_ini) * k // 3 for k in range(4)]
    blocos = [float(np.mean([op["ret"] for op in ops if cortes[k] <= op["t"] < cortes[k + 1]]) * 100) if any(cortes[k] <= op["t"] < cortes[k + 1] for op in ops) else None for k in range(3)]
    return {"n": n, "dias": len(medias), "media_pct": float(rets.mean() * 100), "t": float(tt), "acerto": float((rets > 0).mean()),
            "blocos_pct": blocos, "velas_medio": float(np.mean([op["velas"] for op in ops])),
            "motivos": {m: int(sum(1 for op in ops if op["motivo"] == m)) for m in ("stop móvel", "stop fixo 2%", "tempo máximo")},
            "passa": bool(rets.mean() > 0 and tt >= 2 and sum(1 for b in blocos if b is not None and b > 0) >= 2 and n >= 300)}


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    t = np.asarray(t)
    saida = {"quando": time.strftime("%Y-%m-%d %H:%M"), "moedas": len(moedas), "bracos": {}}
    for nome, k, mx, lados in (("A: k=2, 12 h, compra e venda", 2.0, 48, (1, -1)), ("B: k=3, 24 h, compra e venda", 3.0, 96, (1, -1)),
                               ("C: k=2, 12 h, só compra", 2.0, 48, (1,))):
        ops = simular(ohlcv, t, k, mx, lados)
        j = juiz(ops, int(t[0]), int(t[-1]) + 1)
        saida["bracos"][nome] = j
        if j["n"]:
            print(f"[{nome}] {j['n']} op. em {j['dias']} dias, acerto {j['acerto']:.1%}, média {j['media_pct']:+.3f}%/op (t {j['t']:+.1f}), "
                  f"blocos {[round(b, 3) if b is not None else None for b in j['blocos_pct']]}, segura {j['velas_medio']:.0f} velas, saídas {j['motivos']} → {'PASSA' if j['passa'] else 'não passa'}")
        else:
            print(f"[{nome}] nenhuma operação")
    saida["segundos"] = round(time.time() - t0)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
