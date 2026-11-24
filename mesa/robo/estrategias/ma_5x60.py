"""H79 (PROTOCOLO_LAB.md): cruzamento de médias de 5 × 60 dias no log do preço, BTC + ETH, 0,5 cada. Só no papel até o juízo de 23/02/2027."""
import math


class Estrategia:
    simbolos = ["BTCUSDT", "ETHUSDT"]
    tempo = "1d"
    historico = 61

    def pesos(self, velas):
        out = {}
        for s in self.simbolos:
            lp = [math.log(c) for _, c in velas[s]]
            if len(lp) < 60:
                continue
            curta, longa = sum(lp[-5:]) / 5, sum(lp[-60:]) / 60
            out[s] = 0.5 if curta > longa else -0.5 if curta < longa else 0.0
        return out
