"""Previsão de direção do BTC em 1, 5 e 15 minutos, com aprendizado online e placar honesto.

A cada minuto fechado: calcula características só com velas já fechadas, prevê a probabilidade de alta, grava, e só depois
do horizonte confere. O modelo (regressão logística online) aprende apenas com previsões já resolvidas.
"""
import json
import math

HORIZONTES = (1, 5, 15)
MOEDA = "BTC"


def caracteristicas(fechamentos, volumes):
    """Da mais antiga para a mais recente; precisa de 61 velas. Tudo em escala parecida (retornos em %)."""
    c = fechamentos
    r = lambda k: (c[-1] / c[-1 - k] - 1) * 100
    rets = [(c[i] / c[i - 1] - 1) * 100 for i in range(len(c) - 30, len(c))]
    vol = math.sqrt(sum(x * x for x in rets) / len(rets))
    v_rel = volumes[-1] / (sum(volumes[-31:-1]) / 30) if sum(volumes[-31:-1]) > 0 else 1.0
    return {"vies": 1.0, "r1": r(1), "r5": r(5), "r15": r(15), "r60": r(60), "vol30": vol, "vol_rel": min(v_rel, 5.0) - 1.0,
            "r1_x_vol": r(1) * (min(v_rel, 5.0) - 1.0)}


class Logistica:
    def __init__(self, taxa=0.02, l2=1e-3):
        self.w, self.taxa, self.l2, self.n = {}, taxa, l2, 0

    def prob(self, x):
        z = sum(self.w.get(k, 0.0) * v for k, v in x.items())
        return 1 / (1 + math.exp(-max(-30, min(30, z))))

    def aprender(self, x, subiu):
        erro = (1.0 if subiu else 0.0) - self.prob(x)
        for k, v in x.items():
            self.w[k] = self.w.get(k, 0.0) * (1 - self.taxa * self.l2) + self.taxa * erro * v
        self.n += 1

    def para_json(self):
        return json.dumps({"w": self.w, "n": self.n})

    @classmethod
    def de_json(cls, t):
        d = json.loads(t)
        m = cls()
        m.w, m.n = d["w"], d["n"]
        return m


def empate(payout):
    """Taxa de acerto para empatar numa binária que paga `payout` (0,85 = 85%) e perde 100%."""
    return 1 / (1 + payout)


def placar(acertos, total):
    """Taxa de acerto com intervalo de Wilson de 95%."""
    if total == 0:
        return None
    p, z = acertos / total, 1.96
    centro = (p + z * z / (2 * total)) / (1 + z * z / total)
    meia = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return {"n": total, "taxa": p, "baixo": centro - meia, "alto": centro + meia}
