"""Padrões de day trade em código (27/11, dono: "os agentes têm de aprender a fundo LTA, LTB, reversão, Bull 180 etc.
e criar uma engenharia em cima desses estudos").

Cada detector lê velas FECHADAS [t, abertura, máxima, mínima, fechamento, volume] (mais antiga primeiro) e devolve SINAIS
no fechamento da vela i, com gatilho, stop e lado. As mesmas funções servem ao teste nos dados (lab/h85_padroes.py) e à
leitura ao vivo (scanner → equipe/padroes.json), para que o agente veja na hora o MESMO padrão cujo resultado foi medido.

Definições (fontes públicas, conferidas em 27/11; variantes existem — estas são as que o código usa):
  LTA / LTB       linha de tendência de alta (por dois fundos ascendentes) / de baixa (por dois topos descendentes),
                  pivôs de 3 velas de cada lado. Sinais: toque na LTA com fechamento acima (compra), perda da LTA (venda),
                  rompimento da LTB (compra), toque na LTB com fechamento abaixo (venda).
  Bull 180 / Bear 180 (Oliver Velez): vela verde que supera a máxima de uma vela vermelha anterior (Bull); vela vermelha que perde
                  a mínima de uma verde anterior (Bear). Aqui: confirmado no FECHAMENTO além da máxima/mínima anterior.
  9.1 (Larry Williams, MME 9): a média vira (de descendente para ascendente = compra); compra no rompimento da máxima da vela que
                  virou a média, stop na mínima dela. 9.2: média subindo e fechamento abaixo da mínima anterior → compra no
                  rompimento da máxima dessa vela, stop na mínima.
  PFR (Stormer): mínima menor que as duas anteriores e fechamento maior que o anterior (compra); espelhado para venda.
  123 (fundo): vela do meio com a menor mínima das três; compra no rompimento da máxima da 3ª, stop na mínima da 2ª.
  Inside bar: máxima ≤ máxima anterior e mínima ≥ mínima anterior; entra no rompimento a favor da EMA 20.
  Fundo duplo / topo duplo: dois pivôs no mesmo nível (±0,6%) com um pivô contrário entre eles; confirma no fechamento além
                  do pivô do meio (a "linha do pescoço").
  Divergência de IFR(14): preço faz fundo mais baixo e o IFR faz fundo mais alto (compra); espelhado para venda.
Contexto de cada sinal: "a favor" se o lado concorda com a EMA 20 inclinada e o preço do mesmo lado da EMA 200, senão "contra".
"""
from __future__ import annotations

T, O, H, L, C, V = range(6)
PIVO = 3


def ema(xs, n):
    if not xs:
        return []
    k, out = 2 / (n + 1), [xs[0]]
    for x in xs[1:]:
        out.append(out[-1] + k * (x - out[-1]))
    return out


def atr(v, n=14):
    tr = [v[0][H] - v[0][L]] + [max(v[i][H], v[i - 1][C]) - min(v[i][L], v[i - 1][C]) for i in range(1, len(v))]
    return ema(tr, n)


def ifr(cs, n=14):
    g = [0.0] + [max(0.0, cs[i] - cs[i - 1]) for i in range(1, len(cs))]
    p = [0.0] + [max(0.0, cs[i - 1] - cs[i]) for i in range(1, len(cs))]
    mg, mp = ema(g, 2 * n - 1), ema(p, 2 * n - 1)
    return [100 - 100 / (1 + (a / b)) if b > 0 else 100.0 for a, b in zip(mg, mp)]


def pivos(v, ate, k=PIVO):
    """Pivôs CONFIRMADOS até a vela `ate` (o pivô em j só existe depois de k velas à direita): ([(j, mínima)], [(j, máxima)])."""
    fundos, topos = [], []
    for j in range(k, ate - k + 1):
        if all(v[j][L] < v[j - x][L] for x in range(1, k + 1)) and all(v[j][L] <= v[j + x][L] for x in range(1, k + 1)):
            fundos.append((j, v[j][L]))
        if all(v[j][H] > v[j - x][H] for x in range(1, k + 1)) and all(v[j][H] >= v[j + x][H] for x in range(1, k + 1)):
            topos.append((j, v[j][H]))
    return fundos, topos


def _linha(p1, p2, i):
    (j1, y1), (j2, y2) = p1, p2
    return y1 + (y2 - y1) * (i - j1) / (j2 - j1)


def contexto(lado, e20, e200, c, i):
    sobe = e20[i] > e20[i - 3]
    a_favor = (sobe and c > e200[i]) if lado == "compra" else ((not sobe) and c < e200[i])
    return "a favor" if a_favor else "contra"


def sinais(v, so_ultima=False):
    """Todos os sinais da série (ou só os da última vela fechada). Cada sinal: dict(i, padrao, lado, gatilho, stop, contexto, nota)."""
    n = len(v)
    if n < 60:
        return []
    cs = [x[C] for x in v]
    e9, e20, e200, a, rsi = ema(cs, 9), ema(cs, 20), ema(cs, 200), atr(v), ifr(cs)
    out = []
    inicio = n - 1 if so_ultima else 210
    import bisect
    F_all, T_all = pivos(v, n - 1)                       # pivô em j só vale a partir de j + PIVO (confirmado)
    Fj, Tj = [j for j, _ in F_all], [j for j, _ in T_all]
    for i in range(max(inicio, 30), n):
        b, p, pp = v[i], v[i - 1], v[i - 2]
        verde, verm = b[C] > b[O], b[C] < b[O]

        def add(padrao, lado, gatilho, stop, nota=""):
            if stop is None or gatilho is None or (lado == "compra" and stop >= gatilho) or (lado == "venda" and stop <= gatilho):
                return
            out.append({"i": i, "t": b[T], "padrao": padrao, "lado": lado, "gatilho": gatilho, "stop": stop,
                        "contexto": contexto(lado, e20, e200, b[C], i), "nota": nota})

        # Bull 180 / Bear 180 (Velez): cor oposta à anterior e fechamento além do extremo dela
        if verde and p[C] < p[O] and b[C] > p[H]:
            add("Bull 180", "compra", b[C], min(b[L], p[L]), f"dist. EMA20 {(b[C] / e20[i] - 1) * 100:+.2f}%")
        if verm and p[C] > p[O] and b[C] < p[L]:
            add("Bear 180", "venda", b[C], max(b[H], p[H]), f"dist. EMA20 {(b[C] / e20[i] - 1) * 100:+.2f}%")
        # 9.1 e 9.2 (MME 9)
        if e9[i] > e9[i - 1] and e9[i - 1] <= e9[i - 2]:
            add("9.1", "compra", b[H], b[L])
        if e9[i] < e9[i - 1] and e9[i - 1] >= e9[i - 2]:
            add("9.1", "venda", b[L], b[H])
        if e9[i] > e9[i - 1] > e9[i - 2] and b[C] < p[L]:
            add("9.2", "compra", b[H], b[L])
        if e9[i] < e9[i - 1] < e9[i - 2] and b[C] > p[H]:
            add("9.2", "venda", b[L], b[H])
        # PFR (Stormer)
        if b[L] < p[L] and b[L] < pp[L] and b[C] > p[C]:
            add("PFR", "compra", b[H], b[L])
        if b[H] > p[H] and b[H] > pp[H] and b[C] < p[C]:
            add("PFR", "venda", b[L], b[H])
        # 123 (a vela do meio tem o extremo; entra no rompimento da 3ª)
        if p[L] < pp[L] and p[L] < b[L]:
            add("123", "compra", b[H], p[L])
        if p[H] > pp[H] and p[H] > b[H]:
            add("123", "venda", b[L], p[H])
        # Inside bar a favor da EMA 20
        if b[H] <= p[H] and b[L] >= p[L]:
            if e20[i] > e20[i - 3]:
                add("Inside bar", "compra", b[H], b[L])
            else:
                add("Inside bar", "venda", b[L], b[H])
        # pivôs confirmados até i: LTA, LTB, fundo/topo duplo, divergência de IFR
        fundos = F_all[max(0, bisect.bisect_right(Fj, i - PIVO) - 6):bisect.bisect_right(Fj, i - PIVO)]
        topos = T_all[max(0, bisect.bisect_right(Tj, i - PIVO) - 6):bisect.bisect_right(Tj, i - PIVO)]
        tol = 0.25 * a[i]
        if len(fundos) >= 2:
            f1, f2 = fundos[-2], fundos[-1]
            if f2[1] > f1[1] and f2[0] - f1[0] >= 5:                      # LTA: dois fundos ascendentes
                y, y_ant = _linha(f1, f2, i), _linha(f1, f2, i - 1)
                if b[L] <= y + tol and b[C] > y and i - f2[0] >= 3:
                    add("LTA toque", "compra", b[H], min(b[L], y) - 0.5 * a[i], f"linha {y:.6g}")
                if b[C] < y - tol and p[C] >= y_ant:
                    add("LTA perdida", "venda", b[C], max(b[H], y) + 0.5 * a[i], f"linha {y:.6g}")
            if abs(f2[1] / f1[1] - 1) <= 0.006 and f2[0] - f1[0] >= 6:     # fundo duplo
                meio = [t_ for t_ in topos if f1[0] < t_[0] < f2[0]]
                if meio:
                    pesc = max(m_[1] for m_ in meio)
                    if b[C] > pesc and p[C] <= pesc:
                        add("Fundo duplo", "compra", b[C], min(f1[1], f2[1]), f"pescoço {pesc:.6g}")
            if f2[1] < f1[1] and rsi[f2[0]] > rsi[f1[0]] + 2 and i - f2[0] == PIVO:   # divergência de IFR (alta)
                add("Divergência IFR", "compra", b[H], f2[1], f"IFR {rsi[f1[0]]:.0f}→{rsi[f2[0]]:.0f}")
        if len(topos) >= 2:
            t1, t2 = topos[-2], topos[-1]
            if t2[1] < t1[1] and t2[0] - t1[0] >= 5:                      # LTB: dois topos descendentes
                y, y_ant = _linha(t1, t2, i), _linha(t1, t2, i - 1)
                if b[H] >= y - tol and b[C] < y and i - t2[0] >= 3:
                    add("LTB toque", "venda", b[L], max(b[H], y) + 0.5 * a[i], f"linha {y:.6g}")
                if b[C] > y + tol and p[C] <= y_ant:
                    add("LTB rompida", "compra", b[C], min(b[L], y) - 0.5 * a[i], f"linha {y:.6g}")
            if abs(t2[1] / t1[1] - 1) <= 0.006 and t2[0] - t1[0] >= 6:     # topo duplo
                meio = [f_ for f_ in fundos if t1[0] < f_[0] < t2[0]]
                if meio:
                    pesc = min(m_[1] for m_ in meio)
                    if b[C] < pesc and p[C] >= pesc:
                        add("Topo duplo", "venda", b[C], max(t1[1], t2[1]), f"pescoço {pesc:.6g}")
            if t2[1] > t1[1] and rsi[t2[0]] < rsi[t1[0]] - 2 and i - t2[0] == PIVO:   # divergência de IFR (baixa)
                add("Divergência IFR", "venda", b[L], t2[1], f"IFR {rsi[t1[0]]:.0f}→{rsi[t2[0]]:.0f}")
    return out


def linhas_agora(v):
    """Estado atual das linhas de tendência (para o agente ver mesmo sem sinal): LTA e LTB com nível e distância do preço."""
    if len(v) < 60:
        return {}
    i = len(v) - 1
    fundos, topos = pivos(v, i)
    out, c = {}, v[i][C]
    if len(fundos) >= 2 and fundos[-1][1] > fundos[-2][1]:
        y = _linha(fundos[-2], fundos[-1], i)
        out["LTA"] = {"nivel": y, "dist_pct": round((c / y - 1) * 100, 2), "estado": "acima" if c >= y else "perdida"}
    if len(topos) >= 2 and topos[-1][1] < topos[-2][1]:
        y = _linha(topos[-2], topos[-1], i)
        out["LTB"] = {"nivel": y, "dist_pct": round((c / y - 1) * 100, 2), "estado": "abaixo" if c <= y else "rompida"}
    return out


def simular(v, s, alvo_r=2.0, max_barras=16, custo=0.0012):
    """Resultado de UM sinal em R e em % líquido: entra se a vela seguinte tocar o gatilho (ou na abertura, se abrir além);
    sai no stop, no alvo (alvo_r × risco) ou no fechamento da vela max_barras. Stop e alvo na mesma vela = stop (conservador)."""
    i, compra = s["i"], s["lado"] == "compra"
    if i + 1 >= len(v):
        return None
    nx = v[i + 1]
    g = s["gatilho"]
    if compra:
        if nx[H] < g:
            return None
        ent = max(g, nx[O])
    else:
        if nx[L] > g:
            return None
        ent = min(g, nx[O])
    risco = (ent - s["stop"]) if compra else (s["stop"] - ent)
    if risco <= 0 or risco / ent > 0.08:
        return None
    alvo = ent + alvo_r * risco if compra else ent - alvo_r * risco
    saida = None
    for k in range(i + 1, min(len(v), i + 1 + max_barras)):
        b = v[k]
        bate_stop = b[L] <= s["stop"] if compra else b[H] >= s["stop"]
        bate_alvo = b[H] >= alvo if compra else b[L] <= alvo
        if bate_stop:
            saida = s["stop"]
            break
        if bate_alvo:
            saida = alvo
            break
    if saida is None:
        saida = v[min(len(v) - 1, i + max_barras)][C]
    bruto = (saida / ent - 1) if compra else (1 - saida / ent)
    return {"r": ((saida - ent) if compra else (ent - saida)) / risco, "liq": bruto - custo, "risco_pct": risco / ent}


def estrutura(v, janela=96):
    """27/11 (dono, imagem da BOME: "entrou comprado na resistência; o movimento já tinha passado; a entrada certa era no começo,
    onde está o stop"). Mede, na última vela fechada: resistência e suporte mais próximos (pivôs das últimas `janela` velas,
    com quantos toques), quanto o movimento já andou desde o último fundo/topo (em % e em ATR) e onde o preço está no range."""
    if len(v) < 60:
        return {}
    i = len(v) - 1
    c, a = v[i][C], atr(v)[i]
    fundos, topos = pivos(v, i)
    ini = max(0, i - janela)
    tops = [y for j, y in topos if j >= ini]
    funds = [y for j, y in fundos if j >= ini]
    acima = sorted(y for y in tops if y > c)
    abaixo = sorted((y for y in funds if y < c), reverse=True)
    toques = lambda y, lst: sum(1 for z in lst if abs(z / y - 1) <= 0.004)
    hi = max(x[H] for x in v[ini:]); lo = min(x[L] for x in v[ini:])
    j_lo = max(range(ini, i + 1), key=lambda k: -v[k][L]); j_hi = max(range(ini, i + 1), key=lambda k: v[k][H])
    ult_fundo = min(x[L] for x in v[max(ini, i - 24):])            # fundo das últimas 24 velas
    ult_topo = max(x[H] for x in v[max(ini, i - 24):])
    out = {"preco": c, "atr_pct": round(a / c * 100, 3), "range_pos_pct": round((c - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0,
           "subiu_do_fundo_atr": round((c - ult_fundo) / a, 2) if a else None, "caiu_do_topo_atr": round((ult_topo - c) / a, 2) if a else None,
           "subiu_do_fundo_pct": round((c / ult_fundo - 1) * 100, 2), "caiu_do_topo_pct": round((1 - c / ult_topo) * 100, 2),
           "ultimo_fundo": ult_fundo, "ultimo_topo": ult_topo}
    if acima:
        out["resistencia"] = {"nivel": acima[0], "dist_pct": round((acima[0] / c - 1) * 100, 2), "dist_atr": round((acima[0] - c) / a, 2), "toques": toques(acima[0], tops)}
    elif hi > c:
        out["resistencia"] = {"nivel": hi, "dist_pct": round((hi / c - 1) * 100, 2), "dist_atr": round((hi - c) / a, 2), "toques": 1}
    if abaixo:
        out["suporte"] = {"nivel": abaixo[0], "dist_pct": round((1 - abaixo[0] / c) * 100, 2), "dist_atr": round((c - abaixo[0]) / a, 2), "toques": toques(abaixo[0], funds)}
    elif lo < c:
        out["suporte"] = {"nivel": lo, "dist_pct": round((1 - lo / c) * 100, 2), "dist_atr": round((c - lo) / a, 2), "toques": 1}
    return out


def leitura_entrada(lado, est):
    """Frases de AVISO para uma entrada, a partir da estrutura (sem regra: o agente decide)."""
    av = []
    if not est:
        return av
    if lado == "compra":
        r = est.get("resistencia")
        if r and r["dist_atr"] < 1.0:
            av.append(f"compra colada na RESISTÊNCIA {r['nivel']:.6g} (a {r['dist_pct']:.2f}%, {r['dist_atr']:.1f} ATR, {r['toques']} toque(s)): pouco espaço para subir")
        if (est.get("subiu_do_fundo_atr") or 0) >= 3 or est.get("range_pos_pct", 0) >= 85:
            av.append(f"o movimento JÁ ANDOU: +{est['subiu_do_fundo_pct']:.2f}% ({est['subiu_do_fundo_atr']:.1f} ATR) desde o fundo {est['ultimo_fundo']:.6g}; "
                      f"preço no topo do range ({est['range_pos_pct']:.0f}%). A entrada boa era perto do fundo; espere recuo")
    else:
        s = est.get("suporte")
        if s and s["dist_atr"] < 1.0:
            av.append(f"venda colada no SUPORTE {s['nivel']:.6g} (a {s['dist_pct']:.2f}%, {s['dist_atr']:.1f} ATR, {s['toques']} toque(s)): pouco espaço para cair")
        if (est.get("caiu_do_topo_atr") or 0) >= 3 or est.get("range_pos_pct", 100) <= 15:
            av.append(f"a queda JÁ ANDOU: −{est['caiu_do_topo_pct']:.2f}% ({est['caiu_do_topo_atr']:.1f} ATR) desde o topo {est['ultimo_topo']:.6g}; "
                      f"preço no fundo do range ({est['range_pos_pct']:.0f}%). A entrada boa era perto do topo; espere repique")
    return av
