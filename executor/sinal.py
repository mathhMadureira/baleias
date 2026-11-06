"""Sinal ao vivo do robô: prevê o retorno de 15 min (o mesmo modelo da pesquisa) e mede a própria qualidade fora da amostra.

Duas travas antes de qualquer compra:
  1) evidência: o R² fora da amostra das últimas 2000 previsões precisa ser positivo (prever melhor que "fica parado");
  2) margem: a previsão pessimista (média − 1 desvio) precisa passar do custo de ida e volta.
"""
import json
import time
import urllib.request

from .pesquisa import BASE, Regressao, caracteristicas, velas

H = 15
JANELA_R2 = 2000


class SinalVivo:
    def __init__(self, simbolo="BTCUSDT", dias_aquecimento=3, historico=None):
        self.simbolo = simbolo
        self.v = historico if historico is not None else velas(simbolo, dias_aquecimento)
        self.modelo = Regressao(len(caracteristicas(self.v, 120)))
        self.fila, self.erros = [], []
        self.i = 120
        self._avancar()

    def _avancar(self):
        while self.i < len(self.v):
            while self.fila and self.fila[0][0] <= self.i:
                _, x, y_pred, j = self.fila.pop(0)
                y = (self.v[j + H][4] / self.v[j][4] - 1) * 100
                if self.modelo.n > 500:
                    self.erros.append(((y - y_pred) ** 2, y * y))
                    self.erros = self.erros[-JANELA_R2:]
                self.modelo.aprender(x, y)
            x = caracteristicas(self.v, self.i)
            m, _ = self.modelo.prever(x)
            self.fila.append((self.i + H, x, m, self.i))
            self.i += 1

    def r2(self):
        if len(self.erros) < 500:
            return None
        em, e0 = sum(a for a, _ in self.erros), sum(b for _, b in self.erros)
        return 1 - em / e0 if e0 else None

    def atualizar(self, abrir=urllib.request.urlopen):
        """Busca velas fechadas novas e avança o aprendizado; devolve a previsão mais recente."""
        agora = int(time.time() * 1000)
        url = f"{BASE}/api/v3/klines?symbol={self.simbolo}&interval=1m&startTime={self.v[-1][0] + 60_000}&limit=1000"
        with abrir(url, timeout=20) as r:
            novas = [k for k in json.load(r) if k[6] < agora]
        for k in novas:
            self.v.append((k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[8]), float(k[9])))
        self._avancar()
        self.v = self.v[-6000:]
        self.i = len(self.v)
        m, dp = self.modelo.prever(caracteristicas(self.v, len(self.v) - 1))
        return {"media": m, "desvio": dp, "r2": self.r2(), "t_ms": self.v[-1][0], "px": self.v[-1][4]}
