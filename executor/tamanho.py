"""H58 — tamanho da posição proporcional à carteira (reinvestir o lucro; encolher na perda). Medido antes de ligar (lab/PROTOCOLO_LAB.md):
nas operações antigas da mesa, carteiras somadas 78,45 → 81,91 e nenhum robô abaixo do piso (antes 1); a variante do vídeo (60% do caixa
livre) piorou (70,26, 2 robôs abaixo do piso) e ficou fora.

nocional = FATOR × patrimônio realizado (caixa + margem das abertas, sem o resultado aberto). Com US$ 10, FATOR 2,5 dá os US$ 25 de antes.
"""
FATOR, ALAV = 2.5, 10.0


def nocional(e):
    """Nocional da próxima posição, ou 0 se a margem dela não cabe no caixa."""
    realizado = float(e.get("caixa", 0)) + sum(float(q.get("gasto", q.get("margem", 0)) or 0) for q in (e.get("abertas") or {}).values())
    n = max(0.0, FATOR * realizado)
    return n if n > 0 and float(e.get("caixa", 0)) >= n / ALAV - 1e-9 else 0.0
