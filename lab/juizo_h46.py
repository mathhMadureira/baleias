"""Juízo da H46 (o v4 piora das 18 às 24 h UTC?), pelo critério pré-registrado em 15/11/2026.

Apostas conferidas do v4 (estado:dados/cerebro_v4.json, ops [t_vela, líquido, aposta, prob]) com t de 16/11 00:00 a 22/11 24:00 UTC.
Acerto = líquido > 0 (a mesma conta do vigia do v4). Erro-padrão por vela, como no vigia: média de acerto de cada vela de 15 min,
desvio entre velas / raiz do número de velas.
Juiz (1 tentativa): faixa 18–24 h UTC com acerto < 50% e z ≤ −2 contra 50%, e as outras faixas juntas com acerto ≥ 52%.

Uso: git fetch -q origin estado && python3 -m lab.juizo_h46
"""
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

U = timezone.utc
DE = int(datetime(2026, 11, 16, tzinfo=U).timestamp() * 1000)
ATE = int(datetime(2026, 11, 23, tzinfo=U).timestamp() * 1000)


def acerto_ep(ops):
    por_vela = defaultdict(list)
    for t, g in ops:
        por_vela[t].append(g)
    medias = [sum(v) / len(v) for v in por_vela.values()]
    n_v = len(medias)
    m = sum(medias) / n_v
    dp = math.sqrt(sum((x - m) ** 2 for x in medias) / (n_v - 1))
    return sum(g for _, g in ops) / len(ops), dp / math.sqrt(n_v), n_v


def main():
    rev = subprocess.check_output(["git", "rev-parse", "--short", "origin/estado"], text=True).strip()
    v4 = json.loads(subprocess.check_output(["git", "show", "origin/estado:dados/cerebro_v4.json"]))
    ops = [(o[0], o[1] > 0) for lst in v4["ops"].values() for o in lst if DE <= o[0] < ATE]
    primeira = min(o[0] for lst in v4["ops"].values() for o in lst)
    print(f"ramo estado {rev}; {len(ops)} apostas de 16/11 00:00 a 22/11 24:00 UTC; aposta mais antiga guardada "
          f"{datetime.fromtimestamp(primeira / 1000, U):%d/%m %H:%M} UTC")
    noite = [o for o in ops if datetime.fromtimestamp(o[0] / 1000, U).hour >= 18]
    resto = [o for o in ops if datetime.fromtimestamp(o[0] / 1000, U).hour < 18]
    a_n, ep_n, v_n = acerto_ep(noite)
    a_r, ep_r, v_r = acerto_ep(resto)
    z = (a_n - 0.5) / ep_n
    print(f"18–24 h UTC: acerto {a_n:.2%} em {len(noite)} apostas ({v_n} velas), EP {ep_n:.2%}, z {z:+.2f} contra 50%")
    print(f"00–18 h UTC: acerto {a_r:.2%} em {len(resto)} apostas ({v_r} velas), EP {ep_r:.2%}")
    for h0 in (0, 6, 12, 18):
        f = [o for o in ops if datetime.fromtimestamp(o[0] / 1000, U).hour // 6 * 6 == h0]
        a, ep, v = acerto_ep(f)
        print(f"  faixa {h0:02d}–{h0 + 6:02d} h: {a:.2%} em {len(f)} apostas ({v} velas), EP {ep:.2%}")
    passa = a_n < 0.5 and z <= -2 and a_r >= 0.52
    print("Veredito H46:", "APROVADA" if passa else "REPROVADA",
          f"(18–24 h < 50% e z ≤ −2: {a_n < 0.5 and z <= -2}; outras ≥ 52%: {a_r >= 0.52})")


if __name__ == "__main__":
    main()
