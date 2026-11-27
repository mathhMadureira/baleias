"""Checagem obrigatória antes de cada entrada (27/11, dono: "vender em região de suporte, parabéns pela burrice; estude suporte e resistência,
velas de retração e de reversão, pavio, força vendedora e compradora, livro de ordens").

Lê dados públicos da BingX (perpétuos) e responde, para COMPRA e para VENDA, se a entrada passa, com os motivos em números:
  1. Suporte e resistência  — níveis de 15 min onde o preço virou (pivôs com toques); vender a menos de 1 ATR do suporte ou
                               comprar a menos de 1 ATR da resistência = BARRADO (o erro da ZEC: venda 0,6% acima de um fundo de 3 velas).
  2. Pavios                  — nas últimas 3 velas de 5 min: pavio inferior grande (≥ 2× o corpo) = compradores defendendo; superior = vendedores.
  3. Velas de reversão       — martelo / estrela cadente / engolfo nas últimas velas de 5 e 15 min, contra o lado = BARRADO.
  4. Retração                — depois de queda, velas verdes seguidas fechando acima da anterior = repique em curso (não vender no repique
                               começando; vender quando o repique falhar).
  5. Força compradora × vendedora — últimos 500 negócios: volume de quem agrediu na compra / na venda (agressor = taker).
  6. Livro de ordens         — soma de ordens até 0,5% de cada lado: paredes de compra embaixo seguram o preço; de venda em cima, travam.
  7. Médias 8/20/200 (15 min) — a favor do lado.
Uso: python3 -I checagem.py ZEC        → imprime e devolve 0 se algum lado passa, 3 se nenhum.
"""
import json
import sys
import urllib.request

API = "https://open-api.bingx.com/openApi/swap"


def _get(caminho, tentativas=3):
    import time
    for k in range(tentativas):
        req = urllib.request.Request(API + caminho, headers={"User-Agent": "Mozilla/5.0"})
        r = json.load(urllib.request.urlopen(req, timeout=15))
        if "data" in r:
            return r["data"]
        time.sleep(1.5 * (k + 1))                      # a BingX às vezes responde sem 'data' (limite de pedidos)
    raise RuntimeError(f"BingX sem dados: {str(r)[:120]}")


def velas(m, iv, n):
    d = _get(f"/v3/quote/klines?symbol={m}-USDT&interval={iv}&limit={n}")
    return [[float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]), float(x["volume"])] for x in sorted(d, key=lambda x: x["time"])]


def ema(xs, n):
    a, e = 2 / (n + 1), sum(xs[:n]) / n
    for x in xs[n:]:
        e = a * x + (1 - a) * e
    return e


def atr(v, n=14):
    tr = [max(h - l, abs(h - v[i - 1][3]), abs(l - v[i - 1][3])) for i, (o, h, l, c, _) in enumerate(v) if i]
    return sum(tr[-n:]) / n


def niveis(v, k=3, tol=None):
    """Pivôs de topo/fundo (k velas de cada lado) agrupados por proximidade (tol = 0,5 ATR). Devolve [(preço, toques, 'sup'|'res')]."""
    tol = tol or atr(v) * 0.5
    pts = []
    for i in range(k, len(v) - 1):
        janela = v[max(0, i - k):i + k + 1]
        if v[i][2] == min(x[2] for x in janela):
            pts.append(v[i][2])
        if v[i][1] == max(x[1] for x in janela):
            pts.append(v[i][1])
    grupos = []
    for p in sorted(pts):
        if grupos and p - grupos[-1][-1] <= tol:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    c = v[-1][3]
    return [(sum(g) / len(g), len(g), "sup" if sum(g) / len(g) < c else "res") for g in grupos]


def pavios(v):
    out = []
    for o, h, l, c, _ in v[-3:]:
        corpo = max(abs(c - o), 1e-12)
        inf, sup = min(o, c) - l, h - max(o, c)
        out.append(("inferior" if inf >= 2 * corpo and inf > sup else "superior" if sup >= 2 * corpo and sup > inf else None))
    return out


def reversao(v):
    """Martelo, estrela cadente e engolfo nas 2 últimas velas fechadas."""
    achados = []
    for i in (-3, -2):
        o, h, l, c, _ = v[i]
        po, ph, pl, pc, _ = v[i - 1]
        corpo, rng = abs(c - o), max(h - l, 1e-12)
        if corpo / rng < 0.35 and min(o, c) - l > 2 * corpo and pc < po:
            achados.append(("martelo", "compra"))
        if corpo / rng < 0.35 and h - max(o, c) > 2 * corpo and pc > po:
            achados.append(("estrela cadente", "venda"))
        if c > o and pc < po and c >= po and o <= pc:
            achados.append(("engolfo de alta", "compra"))
        if c < o and pc > po and c <= po and o >= pc:
            achados.append(("engolfo de baixa", "venda"))
    return achados


def forca(m):
    t = _get(f"/v2/quote/trades?symbol={m}-USDT&limit=500")
    compra = sum(float(x["quoteQty"]) for x in t if not x["isBuyerMaker"])
    venda = sum(float(x["quoteQty"]) for x in t if x["isBuyerMaker"])
    return compra, venda


def livro(m, c, faixa=0.005):
    d = _get(f"/v2/quote/depth?symbol={m}-USDT&limit=100")
    bid = sum(float(p) * float(q) for p, q in d["bids"] if float(p) >= c * (1 - faixa))
    ask = sum(float(p) * float(q) for p, q in d["asks"] if float(p) <= c * (1 + faixa))
    return bid, ask


def checar(m):
    m = m.upper().replace("USDT", "").replace("-", "")
    v15, v5 = velas(m, "15m", 300), velas(m, "5m", 60)
    c, a = v15[-1][3], atr(v15)
    cl15 = [x[3] for x in v15]
    e8, e20, e200 = ema(cl15, 8), ema(cl15, 20), ema(cl15, 200)
    nv = niveis(v15[-120:])
    sup = max((n for n in nv if n[2] == "sup"), key=lambda n: n[0], default=None)
    res = min((n for n in nv if n[2] == "res"), key=lambda n: n[0], default=None)
    pv, rv5, rv15 = pavios(v5), reversao(v5), reversao(v15)
    verdes = 0
    for x in reversed(v5[:-1]):
        if x[3] > x[0]:
            verdes += 1
        else:
            break
    fc, fv = forca(m)
    lb, la = livro(m, c)
    L = [f"{m} {c:g} | ATR 15m {a:.4g} ({a / c:.2%})",
         f"Suporte: {sup[0]:.6g} ({sup[1]} toques, {(c - sup[0]) / a:.2f} ATR abaixo)" if sup else "Suporte: nenhum nas últimas 30 h",
         f"Resistência: {res[0]:.6g} ({res[1]} toques, {(res[0] - c) / a:.2f} ATR acima)" if res else "Resistência: nenhuma nas últimas 30 h",
         f"Médias 15m: MME8 {e8:.6g} | MME20 {e20:.6g} | MME200 {e200:.6g} → {'baixa alinhada' if c < e8 < e20 < e200 else 'alta alinhada' if c > e8 > e20 > e200 else 'misturadas'}",
         f"Pavios (3 últimas de 5m): {pv}",
         f"Reversão: 5m {rv5 or '—'} | 15m {rv15 or '—'}",
         f"Retração: {verdes} velas verdes seguidas no 5m",
         f"Força (500 negócios): compra US$ {fc:,.0f} × venda US$ {fv:,.0f} → {fc / max(fv, 1):.2f}",
         f"Livro ±0,5%: compra US$ {lb:,.0f} × venda US$ {la:,.0f} → {lb / max(la, 1):.2f}"]
    veredito = {}
    for lado in ("venda", "compra"):
        b = []
        if lado == "venda":
            if sup and (c - sup[0]) / a < 1.0:
                b.append(f"colado no SUPORTE ({(c - sup[0]) / a:.2f} ATR, {sup[1]} toques)")
            if "inferior" in pv:
                b.append("pavio inferior recente: compradores defendendo")
            if any(s == "compra" for _, s in rv5 + rv15):
                b.append("vela de reversão de ALTA: " + ", ".join(n for n, s in rv5 + rv15 if s == "compra"))
            if verdes >= 2:
                b.append(f"repique em curso ({verdes} verdes): espere o repique falhar")
            if fc / max(fv, 1) > 1.2:
                b.append(f"força COMPRADORA {fc / max(fv, 1):.2f}×")
            if lb / max(la, 1) > 1.5:
                b.append(f"livro com parede de COMPRA {lb / max(la, 1):.2f}×")
            if not c < e20:
                b.append("preço acima da MME20")
        else:
            if res and (res[0] - c) / a < 1.0:
                b.append(f"colado na RESISTÊNCIA ({(res[0] - c) / a:.2f} ATR, {res[1]} toques)")
            if "superior" in pv:
                b.append("pavio superior recente: vendedores defendendo")
            if any(s == "venda" for _, s in rv5 + rv15):
                b.append("vela de reversão de BAIXA: " + ", ".join(n for n, s in rv5 + rv15 if s == "venda"))
            if fv / max(fc, 1) > 1.2:
                b.append(f"força VENDEDORA {fv / max(fc, 1):.2f}×")
            if la / max(lb, 1) > 1.5:
                b.append(f"livro com parede de VENDA {la / max(lb, 1):.2f}×")
            if not c > e20:
                b.append("preço abaixo da MME20")
        veredito[lado] = b
        L.append(f"{lado.upper()}: " + ("PASSA" if not b else "BARRADA — " + "; ".join(b)))
    return "\n".join(L), veredito


if __name__ == "__main__":
    texto, v = checar(sys.argv[1] if len(sys.argv) > 1 else "BTC")
    print(texto)
    sys.exit(0 if any(not b for b in v.values()) else 3)
