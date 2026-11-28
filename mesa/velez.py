"""Método Oliver Velez em código (28/11/2026, H90; regras e fontes em equipe/livro_velez.md).

Vela: [t, abertura, máxima, mínima, fechamento, volume]. Médias SIMPLES (Velez): MMA8, MMA20, MMA200.
Parâmetros que as fontes não dão em número foram FIXADOS aqui antes de medir (livro, seção "o que escolhemos"):
  barra grande (elefante)  = range ≥ 2× o range médio das 20 anteriores e corpo ≥ 70% do range
  barra pequena (NRB)      = range ≤ 0,6× o range médio das 20 anteriores
  pavio (BT/TT)            = pavio ≥ 50% do range e corpo no terço oposto
  estado estreito          = |MMA20 − MMA200| < 0,5 ATR
  "perto" de uma média     = até 0,5 ATR
Cada sinal: {"i", "setup", "lado", "gatilho", "stop", "filtro"}; entrada no rompimento da vela-sinal, stop no outro extremo
(o stop de Velez: logo além da barra de entrada). filtro=True quando o estado 20/200 está a favor do lado (imagem de força).
"""
O, H, L, C = 1, 2, 3, 4


def sma(xs, n, i):
    return sum(xs[i - n + 1:i + 1]) / n if i >= n - 1 else None


def _atr(v, i, n=14):
    if i < n:
        return None
    return sum(max(v[k][H] - v[k][L], abs(v[k][H] - v[k - 1][C]), abs(v[k][L] - v[k - 1][C])) for k in range(i - n + 1, i + 1)) / n


def _rng(b):
    return max(b[H] - b[L], 1e-12)


def estado(v, i, cl=None):
    """Estado das médias de Velez na vela i: 'alta' (imagem de força: preço > MMA20 subindo > MMA200), 'baixa', 'estreito' ou 'neutro'."""
    cl = cl or [b[C] for b in v]
    m20, m20a, m200, a = sma(cl, 20, i), sma(cl, 20, i - 3), sma(cl, 200, i), _atr(v, i)
    if None in (m20, m20a, m200, a):
        return None, {}
    d = {"m8": sma(cl, 8, i), "m20": m20, "m200": m200, "atr": a, "m20_sobe": m20 > m20a}
    if abs(m20 - m200) < 0.5 * a:
        return "estreito", d
    if v[i][C] > m20 > m200 and m20 > m20a:
        return "alta", d
    if v[i][C] < m20 < m200 and m20 < m20a:
        return "baixa", d
    return "neutro", d


def sinais(v, so_ultima=False):
    out = []
    cl = [b[C] for b in v]
    ini = max(205, len(v) - 2) if so_ultima else 205
    for i in range(ini, len(v)):
        est, d = estado(v, i, cl)
        if est is None:
            continue
        b, p = v[i], v[i - 1]
        a, m20 = d["atr"], d["m20"]
        mr = sum(_rng(v[k]) for k in range(i - 20, i)) / 20
        verde, verm = b[C] > b[O], b[C] < b[O]
        corpo = abs(b[C] - b[O])

        def add(setup, lado, sinal_bar=b):
            g = sinal_bar[H] if lado == "compra" else sinal_bar[L]
            s = sinal_bar[L] if lado == "compra" else sinal_bar[H]
            out.append({"i": i, "setup": setup, "lado": lado, "gatilho": g, "stop": s,
                        "filtro": est == ("alta" if lado == "compra" else "baixa")})

        # RBI / GBI — barra 1 da cor da tendência, barra 2 pequena contrária, entrada no rompimento da barra 2
        if p[C] > p[O] and verm and _rng(b) <= 0.7 * mr and b[L] >= p[L]:
            add("RBI", "compra")
        if p[C] < p[O] and verde and _rng(b) <= 0.7 * mr and b[H] <= p[H]:
            add("GBI", "venda")
        # Bull 180 / Bear 180 — barra forte de uma cor seguida de barra forte da cor oposta que fecha além do extremo dela
        pc = abs(p[C] - p[O]) / _rng(p)
        if p[C] < p[O] and pc >= 0.6 and verde and corpo / _rng(b) >= 0.6 and b[C] > p[H]:
            add("Bull 180", "compra")
        if p[C] > p[O] and pc >= 0.6 and verm and corpo / _rng(b) >= 0.6 and b[C] < p[L]:
            add("Bear 180", "venda")
        # Barra elefante de ignição — perto da MMA20 (Velez: não jogue elefante longe de tudo)
        if _rng(b) >= 2 * mr and corpo / _rng(b) >= 0.7 and abs(b[O] - m20) <= 1.0 * a:
            add("Elefante ignição", "compra" if verde else "venda")
        # BT / TT na MMA20 (gatilho de Velez na r20 / d20)
        inf, sup = min(b[O], b[C]) - b[L], b[H] - max(b[O], b[C])
        if inf >= 0.5 * _rng(b) and min(b[O], b[C]) >= b[L] + 0.66 * _rng(b) and abs(b[L] - m20) <= 0.5 * a:
            add("BT na MMA20", "compra")
        if sup >= 0.5 * _rng(b) and max(b[O], b[C]) <= b[H] - 0.66 * _rng(b) and abs(b[H] - m20) <= 0.5 * a:
            add("TT na MMA20", "venda")
        # Lei dos 3–5 barras: 3 a 5 máximas (mínimas) descendentes (ascendentes) seguidas; entra no rompimento da última
        def seq(cmp):
            k = 0
            while k < 6 and cmp(v[i - k], v[i - k - 1]):
                k += 1
            return k
        nd = seq(lambda x, y: x[H] < y[H])
        if 3 <= nd <= 5:
            add("Recuo 3-5 barras", "compra")
        nu = seq(lambda x, y: x[L] > y[L])
        if 3 <= nu <= 5:
            add("Repique 3-5 barras", "venda")
        # NRB perto da MMA20 — barra estreita antes da explosão; entra a favor do estado
        if _rng(b) <= 0.6 * mr and abs(b[C] - m20) <= 0.5 * a and est in ("alta", "baixa"):
            add("NRB na MMA20", "compra" if est == "alta" else "venda")
        # CDB / CAS — climático: 5+ barras da mesma cor, a última a maior, longe da MMA20 (≥ 2 ATR); vira com barra oposta
        ult = v[i - 6:i]
        if all(x[C] < x[O] for x in ult[1:]) and _rng(ult[-1]) == max(_rng(x) for x in ult) and m20 - p[C] >= 2 * a and verde:
            add("CDB (fundo climático)", "compra")
        if all(x[C] > x[O] for x in ult[1:]) and _rng(ult[-1]) == max(_rng(x) for x in ult) and p[C] - m20 >= 2 * a and verm:
            add("CAS (topo climático)", "venda")
        # Falso rompimento — a vela passa da máxima (mínima) das 20 anteriores e fecha de volta dentro; opera o lado contrário
        mx, mn = max(x[H] for x in v[i - 20:i]), min(x[L] for x in v[i - 20:i])
        if b[H] > mx and b[C] < mx:
            add("Falso rompimento de topo", "venda")
        if b[L] < mn and b[C] > mn:
            add("Falso rompimento de fundo", "compra")
    return out


def leitura(v):
    """Para a checagem ao vivo: estado 20/200 agora e os setups de Velez na última vela fechada."""
    i = len(v) - 1
    est, d = estado(v, i)
    return est, d, [s for s in sinais(v, so_ultima=True) if s["i"] == i]
