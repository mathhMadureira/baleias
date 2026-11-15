"""Regra do dono (14–15/11): "se o mercado está em tendência de baixa, entra vendido; se está em tendência de alta, entra comprado; segura".
O regime é a amplitude do mercado: a fração das moedas do universo que sobem em 24 h e em 4 h (velas fechadas de 15 min).
  baixa: ≤ 30% das moedas subindo em 24 h e ≤ 60% em 4 h (a baixa do dia não está sendo desfeita por um repique forte)
  alta:  ≥ 70% subindo em 24 h e ≥ 40% em 4 h
  senão: neutro (os robôs operam os dois lados, como antes)
Limiares fixados antes de ligar (H44, lab/PROTOCOLO_LAB.md); mudam só por variável de ambiente.
"""
import os

BAIXA_24, BAIXA_4 = float(os.environ.get("REGIME_BAIXA_24", "30")), float(os.environ.get("REGIME_BAIXA_4", "60"))
ALTA_24, ALTA_4 = float(os.environ.get("REGIME_ALTA_24", "70")), float(os.environ.get("REGIME_ALTA_4", "40"))


def de_amplitude(subindo_24, subindo_4):
    """Percentuais (0–100) de moedas subindo em 24 h e 4 h → "baixa", "alta" ou None."""
    if subindo_24 is None or subindo_4 is None:
        return None
    if subindo_24 <= BAIXA_24 and subindo_4 <= BAIXA_4:
        return "baixa"
    if subindo_24 >= ALTA_24 and subindo_4 >= ALTA_4:
        return "alta"
    return None


def de_velas(velas, agora_ms=None):
    """{par: velas de 15 min (já filtradas para fechadas)} → (regime, subindo_24 %, subindo_4 %)."""
    r24, r4 = [], []
    for k in velas.values():
        if len(k) < 97:
            continue
        c = [float(x[4]) for x in k[-97:]]
        r24.append(c[-1] > c[0])
        r4.append(c[-1] > c[-17])
    if len(r24) < 10:
        return None, None, None
    s24, s4 = 100 * sum(r24) / len(r24), 100 * sum(r4) / len(r4)
    return de_amplitude(s24, s4), round(s24, 1), round(s4, 1)


def lado_permitido(regime):
    """Lado em que os robôs podem entrar: "venda" na baixa, "compra" na alta, None = os dois."""
    return {"baixa": "venda", "alta": "compra"}.get(regime)
