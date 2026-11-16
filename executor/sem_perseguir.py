"""H55 — não perseguir o movimento de 15 min (pedido do dono 16/11: "tire esse negócio de rompimento de entrada").

Medido em 1455 operações da mesa (lab/PROTOCOLO_LAB.md, H55): entrar a favor do movimento de 15 min deu −0,070/op; contra, −0,008/op
(3 de 3 blocos de tempo). Exigir os 5 tempos gráficos a favor (15m, 1h, 4h, 1d, 1w) deu −0,054/op: pior.
Regra: não compra com o preço acima da média das 20 últimas velas de 15 min; não vende abaixo dela. Sem velas suficientes: não bloqueia.
"""
N = 20


def persegue(lado, velas, preco=None):
    """velas: velas de 15 min fechadas ([t, o, h, l, c, ...], strings da Binance ou números). True = a entrada perseguiria o movimento."""
    try:
        c = [float(x[4]) for x in (velas or [])[-N:]]
    except (TypeError, ValueError, IndexError):
        return False
    if len(c) < N:
        return False
    p = float(preco) if preco else c[-1]
    media = sum(c) / N
    return p > media if lado == "compra" else p < media
