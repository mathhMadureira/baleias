"""Memória que aprende: regressão bayesiana online. Cada sinal resolvido ajusta os pesos e reduz a incerteza.

Prever e aprender são separados de propósito: `prever` nunca recebe o resultado, e o resultado só chega a `aprender`
depois de resolvido. É isso que torna a medida do aprendizado honesta.
"""
import json
import math

from . import config


class Modelo:
    def __init__(self, variancia_prior=config.VARIANCIA_PRIOR, ruido=config.RUIDO_INICIAL, esquecimento=config.ESQUECIMENTO):
        self.variancia_prior = variancia_prior
        self.ruido = ruido
        self.esquecimento = esquecimento
        self.indice = {}
        self.pesos = []
        self.cov = []
        self.n = 0

    def _i(self, nome):
        if nome not in self.indice:
            self.indice[nome] = len(self.pesos)
            self.pesos.append(0.0)
            for linha in self.cov:
                linha.append(0.0)
            self.cov.append([0.0] * (len(self.pesos) - 1) + [self.variancia_prior])
        return self.indice[nome]

    def prever(self, nomes):
        """Devolve média e desvio do retorno líquido esperado, em %. Característica nova entra só com a incerteza do prior."""
        media, var = 0.0, 0.0
        conhecidas = [self.indice[n] for n in nomes if n in self.indice]
        for i in conhecidas:
            media += self.pesos[i]
            var += sum(self.cov[i][j] for j in conhecidas)
        var += self.variancia_prior * sum(1 for n in nomes if n not in self.indice)
        return media, math.sqrt(max(var, 0.0))

    def aprender(self, nomes, resultado_pct):
        idx = [self._i(n) for n in nomes]
        tamanho = len(self.pesos)
        px = [sum(self.cov[l][i] for i in idx) for l in range(tamanho)]
        xpx = sum(px[i] for i in idx)
        erro = resultado_pct - sum(self.pesos[i] for i in idx)
        denom = self.ruido + xpx
        ganho = [p / denom for p in px]
        for l in range(tamanho):
            self.pesos[l] += ganho[l] * erro
        for l in range(tamanho):
            for c in range(tamanho):
                self.cov[l][c] = (self.cov[l][c] - ganho[l] * px[c]) / self.esquecimento
        # O ruído acompanha o erro observado, devagar e com piso, para o modelo não ficar confiante demais.
        self.ruido = max(0.25, 0.99 * self.ruido + 0.01 * erro * erro)
        self.n += 1
        return erro

    def peso(self, nome):
        if nome not in self.indice:
            return None
        i = self.indice[nome]
        return self.pesos[i], math.sqrt(max(self.cov[i][i], 0.0))

    def para_json(self):
        return json.dumps({"indice": self.indice, "pesos": self.pesos, "cov": self.cov, "n": self.n, "ruido": self.ruido,
                           "variancia_prior": self.variancia_prior, "esquecimento": self.esquecimento})

    @classmethod
    def de_json(cls, texto):
        d = json.loads(texto)
        m = cls(d["variancia_prior"], d["ruido"], d["esquecimento"])
        m.indice, m.pesos, m.cov, m.n = d["indice"], d["pesos"], d["cov"], d["n"]
        return m


def aprovado(modelo, nomes, resolvidos, minimo=config.SINAIS_PARA_ALERTAR, z=config.Z_DECISAO):
    media, desvio = modelo.prever(nomes)
    return resolvidos >= minimo and media - z * desvio > 0, media, desvio


def media_ic(valores):
    """Média e intervalo aproximado de 95%. Devolve None abaixo de 2 valores."""
    n = len(valores)
    if n < 2:
        return None
    m = sum(valores) / n
    v = sum((x - m) ** 2 for x in valores) / (n - 1)
    e = 1.96 * math.sqrt(v / n)
    return {"n": n, "media": m, "baixo": m - e, "alto": m + e}


def licoes(linhas, minimo=20):
    """Regras que os dados sustentam até agora. São candidatas: muitas comparações geram achados por acaso."""
    grupos = {}
    for caracteristicas_sinal, liquido in linhas:
        for nome in caracteristicas_sinal:
            if nome != "vies":
                grupos.setdefault(nome, []).append(liquido)
    saida = []
    for nome, valores in grupos.items():
        ic = media_ic(valores)
        if ic and ic["n"] >= minimo and (ic["baixo"] > 0 or ic["alto"] < 0):
            saida.append({"caracteristica": nome, **ic, "efeito": "ganha" if ic["baixo"] > 0 else "perde"})
    return sorted(saida, key=lambda x: -abs(x["media"]))
