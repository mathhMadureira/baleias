"""Hipótese 4: Chronos-Bolt prevendo o retorno de 15 min do BTC (lab/PROTOCOLO_LAB.md). Roda no ambiente .venv-ml."""
import json
import math
import statistics as st
import sys
import time
import urllib.request

CONTEXTO, H, PASSO, CUSTO = 512, 15, 15, 0.2


def velas(dias=7):
    fim = int(time.time() * 1000)
    t, saida = fim - dias * 86_400_000 - CONTEXTO * 60_000, []
    while t < fim:
        with urllib.request.urlopen(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={t}&limit=1000", timeout=30) as r:
            lote = json.load(r)
        if not lote:
            break
        saida += [float(k[4]) for k in lote]
        t = lote[-1][0] + 60_000
        time.sleep(0.2)
    return saida


def avaliar(precos, prever):
    """prever(lista de contextos) -> lista de preços previstos H passos à frente. Só passado em cada contexto."""
    pontos = list(range(CONTEXTO, len(precos) - H, PASSO))
    ctx = [precos[i - CONTEXTO:i] for i in pontos]
    previstos = []
    for k in range(0, len(ctx), 32):
        previstos += prever(ctx[k:k + 32])
    pred = [(p / precos[i - 1] - 1) * 100 for p, i in zip(previstos, pontos)]
    real = [(precos[i - 1 + H] / precos[i - 1] - 1) * 100 for i in pontos]
    r2 = 1 - sum((y - p) ** 2 for y, p in zip(real, pred)) / sum(y * y for y in real)
    pares = [(p > 0) == (y > 0) for p, y in zip(pred, real) if p != 0 and y != 0]
    acerto = st.fmean(pares) if pares else None
    ops = [(y if p > 0 else -y) - CUSTO for p, y in zip(pred, real) if abs(p) > CUSTO]
    return {"previsoes": len(pred), "r2": r2, "acerto_direcao": acerto, "operacoes": len(ops),
            "resultado_medio_op": st.fmean(ops) if ops else None, "soma_ops": sum(ops)}


def chronos_bolt(nome="amazon/chronos-bolt-small"):
    import torch
    from chronos import BaseChronosPipeline
    pipe = BaseChronosPipeline.from_pretrained(nome, device_map="cpu", torch_dtype=torch.float32)
    def prever(contextos):
        q, _ = pipe.predict_quantiles([torch.tensor(c) for c in contextos], prediction_length=H, quantile_levels=[0.5])
        return [float(x[-1, 0]) for x in q]
    return prever


if __name__ == "__main__":
    p = velas(7)
    print(f"velas: {len(p)}", flush=True)
    r = avaliar(p, chronos_bolt())
    print(json.dumps(r, indent=1))
    passou = r["r2"] > 0 and r["operacoes"] > 0 and r["soma_ops"] > 0
    print("RESULTADO:", "PASSA" if passou else "NÃO PASSA")
