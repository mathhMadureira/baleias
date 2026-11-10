"""H23: método de Oliver Velez (180, estado estreito, vela elefante, espaço duplo) medido no histórico."""
import json
import math
import statistics as st
import time

from . import padroes as P


def sinais(v):
    """v: velas (t, o, h, l, c, ...). Devolve por vela um dict {regra: +1/−1} (decidido no fechamento, sem olhar à frente)."""
    o, h, l, c = ([x[k] for x in v] for k in (1, 2, 3, 4))
    n = len(v)
    s20, s200, faixa_m = [None] * n, [None] * n, [None] * n
    a20 = a200 = af = 0.0
    for i in range(n):
        a20 += c[i] - (c[i - 20] if i >= 20 else 0)
        a200 += c[i] - (c[i - 200] if i >= 200 else 0)
        af += (h[i] - l[i]) - ((h[i - 20] - l[i - 20]) if i >= 20 else 0)
        if i >= 199:
            s20[i], s200[i] = a20 / 20, a200 / 200
        if i >= 20:
            faixa_m[i] = (af - (h[i] - l[i])) / 19 if i else None
    saida = [dict() for _ in range(n)]
    for i in range(210, n):
        p, m20, m200 = c[i], s20[i], s200[i]
        alta_q, baixa_q = p > m20 > m200, p < m20 < m200
        if c[i - 1] < o[i - 1] and c[i] > o[i] and c[i] >= o[i - 1] and o[i] <= c[i - 1] and alta_q:
            saida[i]["180_alta"] = 1
        if c[i - 1] > o[i - 1] and c[i] < o[i] and c[i] <= o[i - 1] and o[i] >= c[i - 1] and baixa_q:
            saida[i]["180_baixa"] = -1
        elefante = faixa_m[i] and (h[i] - l[i]) > 2 * faixa_m[i]
        estreito = abs(m20 - m200) / p < 0.012 and abs(s20[i] / s20[i - 10] - 1) < 0.003
        if elefante and estreito:
            if c[i] > max(m20, m200) and c[i] > o[i]:
                saida[i]["estreito_rompe"] = 1
            elif c[i] < min(m20, m200) and c[i] < o[i]:
                saida[i]["estreito_rompe"] = -1
        if elefante and alta_q and c[i] > o[i]:
            saida[i]["elefante_quadro"] = 1
        if elefante and baixa_q and c[i] < o[i]:
            saida[i]["elefante_quadro"] = -1
        if p > m20 * 1.03 and p > m200 * 1.03:
            saida[i]["espaco_duplo"] = -1
        if p < m20 * 0.97 and p < m200 * 0.97:
            saida[i]["espaco_duplo"] = 1
    return saida


def wilson(a, n, z=1.96):
    if not n:
        return 0.0, 1.0
    f = a / n
    c = (f + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(f * (1 - f) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def medir(series, corte_ms, horizontes=(1, 4, 12)):
    """series: {nome: velas}. Retorno na direção do sinal (%) e acerto, por regra × horizonte × período, sem sobreposição."""
    res = {}
    for v in series.values():
        c = [x[4] for x in v]
        sg = sinais(v)
        for hz in horizontes:
            livre = {}
            for i, d in enumerate(sg):
                if i + hz >= len(v):
                    break
                for regra, lado in d.items():
                    if i < livre.get(regra, -1):
                        continue
                    livre[regra] = i + hz
                    r = (c[i + hz] / c[i] - 1) * 100 * lado
                    per = "treino" if v[i][0] < corte_ms else "teste"
                    res.setdefault((regra, hz, per), []).append(r)
    return res


def relatorio(res, rot_hz):
    linhas = []
    regras = sorted({k[0] for k in res})
    for regra in regras:
        for hz in sorted({k[1] for k in res if k[0] == regra}):
            a, b = res.get((regra, hz, "treino"), []), res.get((regra, hz, "teste"), [])
            if len(a) < 30 or len(b) < 30:
                continue
            ta = st.fmean(a) / (st.stdev(a) / math.sqrt(len(a)))
            tb = st.fmean(b) / (st.stdev(b) / math.sqrt(len(b)))
            aa, ab = sum(x > 0 for x in a), sum(x > 0 for x in b)
            spot = abs(st.fmean(a)) > 0.2 and abs(ta) > 3.2 and st.fmean(a) * st.fmean(b) > 0 and abs(st.fmean(b)) > 0.2 and abs(tb) > 2
            binario = all(x / n >= 0.53 and wilson(x, n)[0] > 0.51 for x, n in ((aa, len(a)), (ab, len(b))))
            linhas.append(f"{regra:16} {rot_hz(hz):6} | treino {len(a):5} op, {st.fmean(a):+.3f}%, t {ta:+.1f}, acerto {aa / len(a):.1%} | "
                          f"teste {len(b):5} op, {st.fmean(b):+.3f}%, t {tb:+.1f}, acerto {ab / len(b):.1%} | "
                          f"{'PASSA spot' if spot else ''}{' PASSA binário' if binario else ''}")
    return linhas


if __name__ == "__main__":
    btc = P.baixar()
    print("== BTC 15 min (treino 2020–23, teste 2024+)")
    for l in relatorio(medir({"BTC": btc}, 1704067200000), lambda h: f"{h * 15}min"):
        print("  " + l)
    print("\n== 33 moedas, 5 min, 60 dias (metades)")
    d = json.load(open(P.config.RAIZ / "lab" / "cripto_5m.json"))
    series = {m: [(int(time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M"))) * 1000, x[1], x[2], x[3], x[4]) for x in vs] for m, vs in d.items() if len(vs) > 1000}
    todos = sorted(x[0] for vs in series.values() for x in vs)
    for l in relatorio(medir(series, todos[len(todos) // 2]), lambda h: f"{h * 5}min"):
        print("  " + l)
