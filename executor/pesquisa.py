"""Pesquisa no histórico de 1 min da Binance: algum horizonte e limiar vence o custo, prevendo o RETORNO (não só a direção)?

Prequencial: em cada minuto prevê com o que já aprendeu; aprende o exemplo de t−h só quando ele se resolve em t.
Primeira hipótese, fixada antes de rodar: horizonte 15 min, entra se (média − 1 desvio) > custo. As outras combinações são exploratórias.
"""
import json
import math
import sys
import time
import urllib.request

BASE = "https://api.binance.com"
HORIZONTES = (5, 15, 60)


def velas(simbolo, dias, intervalo="1m"):
    fim = int(time.time() * 1000)
    t, saida = fim - dias * 86_400_000, []
    while t < fim:
        url = f"{BASE}/api/v3/klines?symbol={simbolo}&interval={intervalo}&startTime={t}&limit=1000"
        with urllib.request.urlopen(url, timeout=30) as r:
            lote = json.load(r)
        if not lote:
            break
        saida += lote
        t = lote[-1][0] + 60_000
        time.sleep(0.15)
    # [t, o, h, l, c, v, T, quote_v, n_trades, taker_buy_base, taker_buy_quote, _]
    return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[8]), float(k[9])) for k in saida]


def caracteristicas(v, i):
    """Só usa velas até i (inclusive). Retornos em %."""
    c = lambda k: v[k][4]
    r = lambda k: (c(i) / c(i - k) - 1) * 100
    rets = [(c(j) / c(j - 1) - 1) * 100 for j in range(i - 29, i + 1)]
    vol = math.sqrt(sum(x * x for x in rets) / 30) + 1e-6
    fluxo = lambda a, b: sum(2 * v[j][7] - v[j][5] for j in range(a, b + 1)) / max(sum(v[j][5] for j in range(a, b + 1)), 1e-9)
    neg = lambda a, b: sum(v[j][6] for j in range(a, b + 1))
    faixa = (max(v[j][2] for j in range(i - 14, i + 1)) - min(v[j][3] for j in range(i - 14, i + 1))) / c(i) * 100
    return [1.0, r(1) / vol, r(5) / vol, r(15) / vol, r(60) / vol, vol, fluxo(i - 4, i), fluxo(i - 14, i),
            neg(i - 4, i) / max(neg(i - 64, i - 5) / 12, 1) - 1, faixa / vol]


class Regressao:
    """Regressão linear bayesiana online (mínimos quadrados recursivos com esquecimento)."""

    def __init__(self, n, prior=10.0, esquecimento=0.9995):
        self.w = [0.0] * n
        self.P = [[prior if i == j else 0.0 for j in range(n)] for i in range(n)]
        self.lam, self.ruido, self.n = esquecimento, 0.05, 0

    def prever(self, x):
        m = sum(a * b for a, b in zip(self.w, x))
        Px = [sum(self.P[i][j] * x[j] for j in range(len(x))) for i in range(len(x))]
        return m, math.sqrt(max(sum(a * b for a, b in zip(x, Px)), 0) + self.ruido)

    def aprender(self, x, y):
        n = len(x)
        Px = [sum(self.P[i][j] * x[j] for j in range(n)) for i in range(n)]
        d = self.lam + sum(a * b for a, b in zip(x, Px))
        k = [p / d for p in Px]
        e = y - sum(a * b for a, b in zip(self.w, x))
        self.w = [w + ki * e for w, ki in zip(self.w, k)]
        self.P = [[(self.P[i][j] - k[i] * Px[j]) / self.lam for j in range(n)] for i in range(n)]
        self.ruido = 0.995 * self.ruido + 0.005 * e * e
        self.n += 1


def simular(v, h, z, custo_pct, inicio=120):
    """Uma posição por vez, só compra. Devolve retornos líquidos (%) por operação e o placar das previsões."""
    modelo = Regressao(len(caracteristicas(v, inicio)))
    fila, ops, livre_em, erros_m, erros_0 = [], [], 0, 0.0, 0.0
    for i in range(inicio, len(v) - h):
        while fila and fila[0][0] <= i:
            _, x, y = fila.pop(0)
            modelo.aprender(x, y)
        x = caracteristicas(v, i)
        m, dp = modelo.prever(x)
        y = (v[i + h][4] / v[i][4] - 1) * 100
        if modelo.n > 500:
            erros_m += (y - m) ** 2
            erros_0 += y ** 2
            if i >= livre_em and m - z * dp > custo_pct:
                ops.append(y - custo_pct)
                livre_em = i + h
        fila.append((i + h, x, y))
    return ops, (1 - erros_m / erros_0) if erros_0 else None


def ic(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return {"n": n, "media": m, "baixo": m - 1.96 * s / math.sqrt(n), "alto": m + 1.96 * s / math.sqrt(n), "soma": sum(xs)}


if __name__ == "__main__":
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    v = velas("BTCUSDT", dias)
    print(f"velas de 1 min: {len(v)} ({dias} dias)", flush=True)
    for custo in (0.20, 0.15):
        for h in HORIZONTES:
            for z in (0.0, 1.0):
                ops, r2 = simular(v, h, z, custo)
                r = ic(ops)
                marca = " <- hipótese principal" if (h, z, custo) == (15, 1.0, 0.20) else ""
                txt = "nenhuma operação" if not r else f"{r['n']} ops, média {r['media']:+.4f}% [{r['baixo']:+.4f}, {r['alto']:+.4f}], soma {r['soma']:+.2f}%"
                print(f"custo {custo:.2f}% | h={h:>2} min | z={z} | R² fora da amostra {r2:+.5f} | {txt}{marca}", flush=True)
