"""Padrões gráficos clássicos (figuras geométricas) em velas de 1 h — só biblioteca padrão, usado no laboratório (H45) e no retrato do mercado.

Definições objetivas (as dos livros de análise técnica, escritas como regras para não haver interpretação):
  pivô de topo/fundo: máxima/mínima maior/menor que as P velas de cada lado (P = 3); só pivôs já confirmados.
  topo duplo: dois topos com diferença ≤ 1,5%, separados por ≥ 5 velas, vale entre eles ≥ 3% abaixo; CONFIRMA quando o fechamento rompe o
      vale (linha de pescoço) para baixo → baixa. fundo duplo: o espelho → alta.
  ombro-cabeça-ombro: três topos, o do meio ≥ 1,5% acima dos dois, ombros com diferença ≤ 3%; confirma no rompimento para baixo da menor
      mínima entre os topos → baixa. OCO invertido: o espelho → alta.
  triângulo (simétrico, ascendente, descendente): últimos 3 topos e 3 fundos em 40 velas; topos caindo (ou planos ±0,5%) e fundos subindo
      (ou planos); confirma no rompimento do último topo (→ alta) ou do último fundo (→ baixa).
  bandeira: mastro de ≥ 3 × ATR14 em até 6 velas, depois 3 a 10 velas de consolidação com amplitude ≤ 50% do mastro; confirma no rompimento
      da consolidação no sentido do mastro.
  estrutura: topos e fundos ascendentes (os 3 últimos de cada) = alta; descendentes = baixa; o evento é a virada para essa estrutura.
detectar() olha só as velas até a última (nada do futuro) e devolve os padrões que CONFIRMARAM na última vela e os que estão formados.
"""
P = 3


def pivos(h, l, p=P):
    n = len(h)
    topos, fundos = [], []
    for i in range(p, n - p):
        if h[i] == max(h[i - p:i + p + 1]) and h[i] > h[i - 1]:
            topos.append((i, h[i]))
        if l[i] == min(l[i - p:i + p + 1]) and l[i] < l[i - 1]:
            fundos.append((i, l[i]))
    return topos, fundos


def atr(h, l, c, n=14):
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    return sum(tr[-n:]) / min(n, len(tr))


def _plano(a, b, tol=0.005):
    return abs(b / a - 1) <= tol


def detectar(o, h, l, c):
    """Listas de velas de 1 h (a última é a mais recente, fechada). Devolve [{padrao, sentido, confirmado, nivel}]."""
    n = len(c)
    if n < 30:
        return []
    i = n - 1
    saida = []
    topos, fundos = pivos(h, l)
    # topo duplo / fundo duplo
    if len(topos) >= 2:
        (i1, a), (i2, b) = topos[-2], topos[-1]
        vale = min(l[i1:i2 + 1])
        if i2 - i1 >= 5 and abs(b / a - 1) <= 0.015 and (min(a, b) - vale) / vale >= 0.03 and i - i2 <= 15:
            conf = c[i] < vale <= c[i - 1]
            saida.append({"padrao": "topo duplo", "sentido": "baixa", "confirmado": conf, "nivel": vale})
    if len(fundos) >= 2:
        (i1, a), (i2, b) = fundos[-2], fundos[-1]
        pico = max(h[i1:i2 + 1])
        if i2 - i1 >= 5 and abs(b / a - 1) <= 0.015 and (pico - max(a, b)) / max(a, b) >= 0.03 and i - i2 <= 15:
            conf = c[i] > pico >= c[i - 1]
            saida.append({"padrao": "fundo duplo", "sentido": "alta", "confirmado": conf, "nivel": pico})
    # ombro-cabeça-ombro e invertido
    if len(topos) >= 3:
        (ia, a), (ib, b), (ic, cc) = topos[-3:]
        if b >= max(a, cc) * 1.015 and abs(cc / a - 1) <= 0.03 and i - ic <= 15:
            pescoco = min(min(l[ia:ib + 1]), min(l[ib:ic + 1]))
            saida.append({"padrao": "ombro-cabeça-ombro", "sentido": "baixa", "confirmado": c[i] < pescoco <= c[i - 1], "nivel": pescoco})
    if len(fundos) >= 3:
        (ia, a), (ib, b), (ic, cc) = fundos[-3:]
        if b <= min(a, cc) / 1.015 and abs(cc / a - 1) <= 0.03 and i - ic <= 15:
            pescoco = max(max(h[ia:ib + 1]), max(h[ib:ic + 1]))
            saida.append({"padrao": "OCO invertido", "sentido": "alta", "confirmado": c[i] > pescoco >= c[i - 1], "nivel": pescoco})
    # triângulos
    t3 = [x for x in topos if x[0] >= i - 40][-3:]
    f3 = [x for x in fundos if x[0] >= i - 40][-3:]
    if len(t3) == 3 and len(f3) == 3:
        th = [x[1] for x in t3]
        fl = [x[1] for x in f3]
        topos_caem = th[1] < th[0] * 0.998 and th[2] < th[1] * 0.998
        topos_planos = _plano(th[0], th[1]) and _plano(th[1], th[2])
        fundos_sobem = fl[1] > fl[0] * 1.002 and fl[2] > fl[1] * 1.002
        fundos_planos = _plano(fl[0], fl[1]) and _plano(fl[1], fl[2])
        tipo = ("triângulo simétrico" if topos_caem and fundos_sobem else "triângulo ascendente" if topos_planos and fundos_sobem
                else "triângulo descendente" if topos_caem and fundos_planos else None)
        if tipo:
            if c[i] > th[2] >= c[i - 1]:
                saida.append({"padrao": tipo, "sentido": "alta", "confirmado": True, "nivel": th[2]})
            elif c[i] < fl[2] <= c[i - 1]:
                saida.append({"padrao": tipo, "sentido": "baixa", "confirmado": True, "nivel": fl[2]})
            elif fl[2] < c[i] < th[2]:
                saida.append({"padrao": tipo, "sentido": "alta" if tipo == "triângulo ascendente" else "baixa" if tipo == "triângulo descendente" else "?",
                              "confirmado": False, "nivel": None})
    # bandeira
    a = atr(h[:-1], l[:-1], c[:-1])
    if a > 0:
        for cons in range(3, 11):
            fim_mastro = i - 1 - cons
            if fim_mastro < 8:
                break
            for k in range(2, 7):
                ini = fim_mastro - k
                mastro = c[fim_mastro] - c[ini]
                if abs(mastro) < 3 * a:
                    continue
                zona_h, zona_l = max(h[fim_mastro + 1:i]), min(l[fim_mastro + 1:i])
                if zona_h - zona_l > 0.5 * abs(mastro):
                    continue
                if mastro > 0 and c[i] > zona_h >= c[i - 1]:
                    saida.append({"padrao": "bandeira de alta", "sentido": "alta", "confirmado": True, "nivel": zona_h})
                elif mastro < 0 and c[i] < zona_l <= c[i - 1]:
                    saida.append({"padrao": "bandeira de baixa", "sentido": "baixa", "confirmado": True, "nivel": zona_l})
                break
            if saida and saida[-1]["padrao"].startswith("bandeira"):
                break
    # estrutura de topos e fundos (virada)
    if len(topos) >= 4 and len(fundos) >= 4:
        def estrutura(tt, ff):
            th, fl = [x[1] for x in tt[-3:]], [x[1] for x in ff[-3:]]
            if th[0] < th[1] < th[2] and fl[0] < fl[1] < fl[2]:
                return "alta"
            if th[0] > th[1] > th[2] and fl[0] > fl[1] > fl[2]:
                return "baixa"
            return None
        agora = estrutura(topos, fundos)
        antes = estrutura([x for x in topos if x[0] < (topos[-1][0] if topos[-1][0] >= fundos[-1][0] else fundos[-1][0])] or topos,
                          [x for x in fundos if x[0] < (topos[-1][0] if topos[-1][0] >= fundos[-1][0] else fundos[-1][0])] or fundos)
        ultimo_pivo = max(topos[-1][0], fundos[-1][0])
        if agora:
            saida.append({"padrao": f"estrutura de {agora} (topos e fundos {'ascendentes' if agora == 'alta' else 'descendentes'})", "sentido": agora,
                          "confirmado": agora != antes and ultimo_pivo == i - P, "nivel": None})
    return saida


def para_1h(k15):
    """Velas de 15 min da Binance ([t, o, h, l, c, v, ...], strings) → listas o, h, l, c de 1 h alinhadas na hora cheia (só horas completas)."""
    blocos = {}
    for x in k15:
        blocos.setdefault(int(x[0]) // 3_600_000, []).append(x)
    o, h, l, c = [], [], [], []
    for hora in sorted(blocos):
        b = blocos[hora]
        if len(b) != 4:
            continue
        o.append(float(b[0][1]))
        h.append(max(float(x[2]) for x in b))
        l.append(min(float(x[3]) for x in b))
        c.append(float(b[-1][4]))
    return o, h, l, c
