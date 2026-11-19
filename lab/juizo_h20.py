"""Juízo da H20 (Cérebro v1 no binário simulado de 15 min), pelo critério pré-registrado.

Critério (ajuste 2 da H20, 10/11/2026): >= 500 apostas ao vivo (t >= inicio_ao_vivo) e
limite inferior de Wilson (95%, z = 1,96) do acerto > 51%. Os 3 blocos de tempo são só informação.

Uso: git fetch -q origin estado && python3 -m lab.juizo_h20
"""
import json
import math
import subprocess
from datetime import datetime, timezone


def wilson(a, n, z=1.96):
    p = a / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / den, (c + r) / den


def hora(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%d/%m %H:%M UTC")


def main():
    rev = subprocess.check_output(["git", "rev-parse", "--short", "origin/estado"], text=True).strip()
    d = json.loads(subprocess.check_output(["git", "show", "origin/estado:dados/cerebro.json"]))
    t0 = d["inicio_ao_vivo"]
    todas = d["operacoes"]
    ops = [o for o in todas if o["t"] >= t0]
    n = len(ops)
    acertos = sum(1 for o in ops if o["liquido"] > 0)
    lo, hi = wilson(acertos, n)
    i0 = todas.index(ops[0])
    cap_antes = todas[i0 - 1]["capital"] if i0 else None
    print(f"origin/estado {rev}; ao vivo desde {hora(t0)}; apostas {hora(ops[0]['t'])} a {hora(ops[-1]['t'])}")
    print(f"apostas ao vivo {n}; acertos {acertos} ({acertos / n:.1%}); Wilson 95% [{lo:.1%}; {hi:.1%}]")
    print(f"capital simulado {cap_antes:.2f} -> {ops[-1]['capital']:.2f}")
    a, b = ops[0]["t"], ops[-1]["t"] + 1
    passo = (b - a) / 3
    for k in range(3):
        s = [o for o in ops if a + k * passo <= o["t"] < a + (k + 1) * passo]
        w = sum(1 for o in s if o["liquido"] > 0)
        print(f"bloco {k + 1} (desde {hora(a + k * passo)}): {len(s)} apostas, acerto {w / len(s):.1%}, "
              f"soma {sum(o['liquido'] for o in s):+.4f} (fração do capital)")
    passa = n >= 500 and lo > 0.51
    print("VEREDITO:", "PASSA" if passa else "REPROVADA")


if __name__ == "__main__":
    main()
