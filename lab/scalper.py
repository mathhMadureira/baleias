"""H24: saídas de scalper (alvo/stop fixos curtos, tempo máximo) sobre entradas do espaço duplo e entradas aleatórias."""
import json
import math
import random
import statistics as st
import time

from baleias import config

from .velez import sinais as sinais_velez

CUSTO = 0.001
MAX_VELAS = 6
PARES = [(0.003, 0.003), (0.005, 0.005), (0.008, 0.004), (0.010, 0.005)]


def sair(v, i, lado, alvo, stop):
    """Entra no fechamento da vela i; percorre as próximas velas: stop primeiro se ambos cabem na mesma vela."""
    e = v[i][4]
    for j in range(i + 1, min(i + 1 + MAX_VELAS, len(v))):
        h, l = v[j][2], v[j][3]
        if lado > 0:
            if l <= e * (1 - stop):
                return -stop - CUSTO
            if h >= e * (1 + alvo):
                return alvo - CUSTO
        else:
            if h >= e * (1 + stop):
                return -stop - CUSTO
            if l <= e * (1 - alvo):
                return alvo - CUSTO
    j = min(i + MAX_VELAS, len(v) - 1)
    return lado * (v[j][4] / e - 1) - CUSTO


def rodar():
    d = json.load(open(config.RAIZ / "lab" / "cripto_5m.json"))
    series = {m: [(int(time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M"))) * 1000, x[1], x[2], x[3], x[4]) for x in vs] for m, vs in d.items() if len(vs) > 1000}
    todos = sorted(x[0] for vs in series.values() for x in vs)
    corte = todos[len(todos) // 2]
    rnd = random.Random(7)
    res = {}
    for m, v in series.items():
        sg = sinais_velez(v)
        livre_v = livre_a = 0
        for i in range(210, len(v) - 1):
            per = "1ª metade" if v[i][0] < corte else "2ª metade"
            lado = sg[i].get("espaco_duplo")
            if lado and i >= livre_v:
                for alvo, stop in PARES:
                    res.setdefault(("espaço duplo", alvo, stop, per), []).append(sair(v, i, lado, alvo, stop))
                livre_v = i + MAX_VELAS
            if i >= livre_a and i % 12 == 0:
                lado_a = rnd.choice((1, -1))
                for alvo, stop in PARES:
                    res.setdefault(("aleatória", alvo, stop, per), []).append(sair(v, i, lado_a, alvo, stop))
                livre_a = i + MAX_VELAS
    for entrada in ("espaço duplo", "aleatória"):
        for alvo, stop in PARES:
            partes = []
            ok = True
            for per in ("1ª metade", "2ª metade"):
                xs = res.get((entrada, alvo, stop, per), [])
                m_, t = st.fmean(xs), st.fmean(xs) / (st.stdev(xs) / math.sqrt(len(xs)))
                ac = sum(x > 0 for x in xs) / len(xs)
                ok = ok and m_ > 0 and t > 2
                partes.append(f"{per}: {len(xs):5} op, acerto {ac:.0%}, média {m_ * 100:+.3f}% (t {t:+.1f})")
            equilibrio = (stop + CUSTO) / (alvo + stop)
            print(f"{entrada:13} alvo {alvo * 100:.1f}% stop {stop * 100:.1f}% (empata com {equilibrio:.0%}) | " + " | ".join(partes) + (" | PASSA" if ok else ""))


if __name__ == "__main__":
    rodar()
