"""Juízo da H76 ("hora_22utc", proposta do Caçador), pelo critério pré-registrado (b54babde).

Compra na abertura da vela de 1 h das 22:00 UTC, venda na abertura da vela das 00:00 UTC; BTCUSDT à vista da Binance, 01/01/2022 a 23/11/2026; custo 0,12%.
Controle: no mesmo dia, 2 h a partir de uma hora sorteada entre 00 e 21 UTC (−0,12% ± 3 EP, senão inválida).
Juiz: n ≥ 300, média > 0, t ≥ 2,69 e > 0 em cada um de 3 blocos iguais. ETHUSDT só relatado.

Uso: python3 -m lab.juizo_h76
"""
import json
import math
import random
import time
import urllib.request
from datetime import datetime, timezone

U = timezone.utc
DE = int(datetime(2022, 1, 1, tzinfo=U).timestamp() * 1000)
ATE = int(datetime(2026, 11, 24, tzinfo=U).timestamp() * 1000)
CUSTO, T_MIN = 0.0012, 2.69
URL = "https://data-api.binance.vision/api/v3/klines"


def velas(par):
    out, t = {}, DE
    while t < ATE:
        for tent in range(5):
            try:
                with urllib.request.urlopen(f"{URL}?symbol={par}&interval=1h&startTime={t}&endTime={ATE - 1}&limit=1000", timeout=20) as r:
                    k = json.load(r)
                break
            except (OSError, ValueError):
                time.sleep(2)
        else:
            raise RuntimeError("rede")
        if not k:
            break
        for x in k:
            out[int(x[0])] = float(x[1])                     # abertura
        t = int(k[-1][0]) + 3_600_000
        time.sleep(0.1)
    return out


def stats(v):
    n = len(v)
    m = sum(v) / n
    ep = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1) / n)
    return n, m, ep


def medir(par, rnd):
    ab = velas(par)
    real, ctl = [], []
    dia = DE
    while dia + 26 * 3_600_000 <= ATE:
        e, s = ab.get(dia + 22 * 3_600_000), ab.get(dia + 24 * 3_600_000)
        h = rnd.randrange(0, 22)
        ce, cs = ab.get(dia + h * 3_600_000), ab.get(dia + (h + 2) * 3_600_000)
        if e and s:
            real.append((dia, s / e - 1 - CUSTO))
        if ce and cs:
            ctl.append((dia, cs / ce - 1 - CUSTO))
        dia += 86_400_000
    return real, ctl


def relatar(nome, L):
    v = [r for _, r in L]
    n, m, ep = stats(v)
    k = n // 3
    blocos = [sum(v[:k]) / k, sum(v[k:2 * k]) / k, sum(v[2 * k:]) / (n - 2 * k)]
    print(f"{nome}: n {n}, média {m:+.4%}, EP {ep:.4%}, t {m / ep:+.2f}, acerto {sum(x > 0 for x in v) / n:.1%}; blocos "
          + " / ".join(f"{b:+.4%}" for b in blocos))
    return n, m, ep, blocos


def main():
    rnd = random.Random(76)
    for par in ("BTCUSDT", "ETHUSDT"):
        real, ctl = medir(par, rnd)
        print(f"\n{par}")
        _, mc, epc, _ = relatar("  controle (hora sorteada)", ctl)
        valido = abs(mc + CUSTO) <= 3 * epc
        print(f"  controle dentro de −0,12% ± 3 EP: {'sim' if valido else 'NÃO (rodada inválida)'}")
        n, m, ep, bl = relatar("  22:00→00:00 UTC", real)
        bruto = m + CUSTO
        print(f"  sem custo: {bruto:+.4%} por dia")
        if par == "BTCUSDT":
            passa = valido and n >= 300 and m > 0 and m / ep >= T_MIN and all(b > 0 for b in bl)
            print("  Veredito H76:", "APROVADA" if passa else "REPROVADA" if valido else "INVÁLIDA")


if __name__ == "__main__":
    main()
