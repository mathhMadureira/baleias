"""Leis empíricas do BTC medidas como um físico mediria: memória por escala, previsibilidade da volatilidade e caudas.

Uso: python3 -m lab.fisica
"""
import math
import statistics as st

from . import padroes as P
from . import tartaruga as T


def razao_variancia(r, q):
    """Lo-MacKinlay: VR(q) = Var(soma de q retornos) / (q·Var(1)). >1 = tendência (memória positiva), <1 = reversão.
    z robusto a heterocedasticidade (Lo & MacKinlay 1988, eq. de z*)."""
    n = len(r)
    mu = sum(r) / n
    d = [x - mu for x in r]
    s1 = sum(x * x for x in d) / n
    soma = [0.0]
    for x in r:
        soma.append(soma[-1] + x)
    sq = sum((soma[i + q] - soma[i] - q * mu) ** 2 for i in range(n - q + 1)) / ((n - q + 1) * q)
    vr = sq / s1
    theta = 0.0
    den = sum(x * x for x in d) ** 2
    for j in range(1, q):
        delta = n * sum(d[t] ** 2 * d[t - j] ** 2 for t in range(j, n)) / den
        theta += (2 * (q - j) / q) ** 2 * delta
    return vr, math.sqrt(n) * (vr - 1) / math.sqrt(theta) if theta > 0 else 0.0


def caudas(r):
    m = st.fmean(r)
    s = st.pstdev(r)
    curtose = st.fmean([((x - m) / s) ** 4 for x in r])
    a = sorted((abs(x) for x in r), reverse=True)
    k = max(10, len(a) // 50)                  # 2% maiores movimentos
    hill = k / sum(math.log(a[i] / a[k]) for i in range(k))
    return curtose, hill


def har_rv(rv, corte):
    """HAR-RV (Corsi 2009) em log: prevê a volatilidade de amanhã com a de ontem, da semana e do mês. R² fora da amostra."""
    lr = [math.log(x) for x in rv]
    linhas = []
    for t in range(22, len(lr) - 1):
        linhas.append(([1.0, lr[t], st.fmean(lr[t - 4:t + 1]), st.fmean(lr[t - 21:t + 1])], lr[t + 1], t))
    tr = [(x, y) for x, y, t in linhas if t < corte]
    te = [(x, y) for x, y, t in linhas if t >= corte]
    # mínimos quadrados 4×4 sem numpy
    k = 4
    a = [[sum(x[i] * x[j] for x, _ in tr) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * y for x, y in tr) for i in range(k)]
    for i in range(k):
        piv = a[i][i]
        for j in range(i + 1, k):
            f = a[j][i] / piv
            a[j] = [a[j][c] - f * a[i][c] for c in range(k)]
            b[j] -= f * b[i]
    coef = [0.0] * k
    for i in reversed(range(k)):
        coef[i] = (b[i] - sum(a[i][c] * coef[c] for c in range(i + 1, k))) / a[i][i]
    media_tr = st.fmean(y for _, y in tr)
    sse = sum((y - sum(c * v for c, v in zip(coef, x))) ** 2 for x, y in te)
    sst = sum((y - media_tr) ** 2 for _, y in te)
    return 1 - sse / sst, coef


def r2_direcao(r, corte):
    """Mesmo teste para o retorno de amanhã: prever com o retorno de hoje (AR(1)), R² fora da amostra contra prever a média do treino."""
    tr = list(zip(r[:corte - 1], r[1:corte]))
    mx, my = st.fmean(x for x, _ in tr), st.fmean(y for _, y in tr)
    beta = sum((x - mx) * (y - my) for x, y in tr) / sum((x - mx) ** 2 for x, _ in tr)
    te = list(zip(r[corte - 1:-1], r[corte:]))
    sse = sum((y - (my + beta * (x - mx))) ** 2 for x, y in te)
    sst = sum((y - my) ** 2 for _, y in te)
    return 1 - sse / sst


def main():
    v = P.baixar()                                  # BTC 15 min desde 2020
    c = [x[4] for x in v]
    r15 = [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
    print(f"BTC 15 min: {len(r15)} retornos ({v[0][0]} → {v[-1][0]} ms)\n")
    print("1) MEMÓRIA POR ESCALA (razão de variância; >1 tendência, <1 reversão; |z|>2 é significativo)")
    for q, nome in ((2, "30 min"), (4, "1 h"), (16, "4 h"), (96, "1 dia")):
        vr, z = razao_variancia(r15[-120_000:], q)
        print(f"   base 15 min, horizonte {nome:6}: VR = {vr:.3f}  z = {z:+.2f}")
    d = T.baixar()
    for m in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        cd = [x[4] for x in d[m]]
        rd = [math.log(cd[i] / cd[i - 1]) for i in range(1, len(cd))]
        partes = []
        for q in (5, 20, 60):
            vr, z = razao_variancia(rd, q)
            partes.append(f"{q}d VR={vr:.2f} z={z:+.1f}")
        print(f"   {m[:-4]} diário ({len(rd)} dias): " + " | ".join(partes))
    print("\n2) CAUDAS (normal: curtose 3; índice de cauda α: quanto menor, mais gorda; α<4 = variância 'instável')")
    for nome, r in (("15 min", r15), ("diário", [math.log(d['BTCUSDT'][i][4] / d['BTCUSDT'][i - 1][4]) for i in range(1, len(d['BTCUSDT']))])):
        k, a = caudas(r)
        print(f"   BTC {nome}: curtose {k:.1f} | α (Hill, 2% maiores) {a:.2f}")
    print("\n3) O QUE É PREVISÍVEL: direção × volatilidade (fora da amostra, treino até 2023, teste 2024+)")
    dias = {}
    for t, x in zip((y[0] for y in v[1:]), r15):
        dias.setdefault(t // 86_400_000, []).append(x)
    chaves = sorted(k for k, xs in dias.items() if len(xs) >= 90)
    rv = [sum(x * x for x in dias[k]) for k in chaves]
    rdia = [sum(dias[k]) for k in chaves]
    corte = next(i for i, k in enumerate(chaves) if k * 86_400_000 >= 1_704_067_200_000)
    r2v, coef = har_rv(rv, corte)
    print(f"   Volatilidade de amanhã (HAR-RV, log): R² fora da amostra = {r2v:.3f}  (pesos dia/semana/mês: {coef[1]:.2f}/{coef[2]:.2f}/{coef[3]:.2f})")
    print(f"   Direção de amanhã (AR(1)):            R² fora da amostra = {r2_direcao(rdia, corte):+.4f}")


if __name__ == "__main__":
    main()
