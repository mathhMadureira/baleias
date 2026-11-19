"""H68 — o Caçador: varredura contínua de oportunidades na nuvem, com juiz automático (regra e juiz em lab/PROTOCOLO_LAB.md, antes de ligar).

A cada rodada do laço de cerebro.yml (~3 min), só dados públicos, nenhuma ordem, nenhuma chave:
  1. ticker de 24 h de todos os pares da Binance à vista (uma chamada) → universo: pares USDT em negociação com volume ≥ US$ 500 mil
     (a nuvem não alcança a API de futuros: bloqueio regional, não contornado); exchangeInfo a cada 60 min → listagens novas;
  2. velas de 1 min de cada par do universo → explosões de 1, 5 e 15 min (z do retorno e do volume);
  3. nas candidatas (até 80): velas de 15 min e 1 h → tendência se formando (MM20 em 15 min, 1 h, 4 h), rompimento de 24 h, padrões gráficos;
  4. cada oportunidade vira um evento do juiz (resolvido 15 e 60 min depois, − 0,12%), com um evento de CONTROLE aleatório no mesmo instante;
  5. a cada 15 min, memecoins novas de DEX (DexScreener, GeckoTerminal), com filtros de segurança — só informação.
Grava SÓ dados/oportunidades.json.

Uso: BALEIAS_DADOS=.../estado/dados python -m executor.cacador_nuvem
"""
import json
import math
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from baleias import config

DADOS = "https://data-api.binance.vision/api/v3"
ARQ = "oportunidades.json"
VOL_MIN, CUSTO, Z_MIN, VOL_REL_MIN = 500_000.0, 0.0012, 3.0, 3.0
JANELAS, BASE = (1, 5, 15), 120
HORIZONTES = (15, 60)
MAX_CAND, MAX_EVENTOS, REPETE_S, INFO_S, DEX_S = 80, 25, 30 * 60, 3600, 15 * 60
TIPOS = ("explosao_1m", "explosao_5m", "explosao_15m", "tendencia", "rompimento_24h", "padrao_15m", "padrao_1h")
T_MIN, N_MIN = 2.69, 300                     # Bonferroni para 14 tentativas (7 sinais × 2 horizontes), 5% unilateral; e ≥ 2 pedido pelo chefe
MEMES = {"DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "BRETT", "POPCAT", "FARTCOIN", "PNUT", "PENGU", "TRUMP", "MEME", "NEIRO", "TURBO",
         "MOODENG", "GOAT", "MOG", "BOME", "SPX", "PEOPLE", "DOGS", "NOT", "MEW", "GIGA", "PONKE", "ACT", "CHILLGUY", "USELESS", "PUMP",
         "1000SATS", "1000CAT", "1000CHEEMS", "BABYDOGE", "BANANAS31", "BROCCOLI714", "MUBARAK", "TST", "SATS", "CAT", "CHEEMS"}
UA = {"User-Agent": "baleias/1.0", "Accept": "application/json"}


def _get(url, t=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t) as r:
        return json.load(r)


def e_meme(par):
    b = par[:-4]
    return b in MEMES or b.removeprefix("1000") in MEMES


# ---------------- universo ----------------
def filtrar(simbolos_usdt, ticker):
    """Pares USDT em negociação, volume ≥ VOL_MIN, sem estáveis/fiduciárias, ações tokenizadas e alavancados (regras de lab/universo.py)."""
    from lab.universo import ESTAVEIS
    vol = {x["symbol"]: float(x.get("quoteVolume") or 0) for x in ticker}
    todos = set(simbolos_usdt)
    out = []
    for s in simbolos_usdt:
        b = s[:-4]
        if b in ESTAVEIS or not b.isascii() or vol.get(s, 0) < VOL_MIN:
            continue
        if (len(b) >= 4 and b.endswith("B") and b != "SHIB") or b == "MUB":
            continue
        if any(b.endswith(suf) and f"{b[:-len(suf)]}USDT" in todos for suf in ("UP", "DOWN", "BULL", "BEAR")):
            continue
        out.append(s)
    return sorted(out, key=lambda s: (not e_meme(s), -vol.get(s, 0)))


def novas_listagens(conhecidos, agora_lista, t, antigas):
    """Par que aparece no exchangeInfo e não estava na lista anterior (a primeira leitura só guarda a lista). Guarda por 72 h."""
    novas = [{"par": s, "desde_t": t} for s in sorted(set(agora_lista) - set(conhecidos))] if conhecidos else []
    return [x for x in antigas + novas if t - x["desde_t"] <= 72 * 3600]


# ---------------- sinais ----------------
def sinais_1m(k):
    """k: velas de 1 min FECHADAS [t, o, h, l, c, v, t_fecha, v_usd, ...]. Devolve ([sinais], z_max, ret_1h)."""
    if len(k) < BASE + max(JANELAS) + 1:
        return [], 0.0, None
    c = [float(x[4]) for x in k]
    v = [float(x[7]) for x in k]
    L = len(c) - 1
    ini = L - max(JANELAS) - BASE
    rets = [math.log(c[i] / c[i - 1]) for i in range(ini + 1, L - max(JANELAS) + 1) if c[i - 1] > 0 and c[i] > 0]
    sig = (sum(r * r for r in rets) / len(rets)) ** 0.5 if rets else 0.0
    vbase = sum(v[ini:L - max(JANELAS) + 1]) / (BASE + 1)
    out, zmax = [], 0.0
    for w in JANELAS:
        if c[L - w] <= 0 or c[L] <= 0 or sig <= 0:
            continue
        z = math.log(c[L] / c[L - w]) / (sig * math.sqrt(w))
        vrel = (sum(v[L - w + 1:L + 1]) / (w * vbase)) if vbase > 0 else 0.0
        zmax = max(zmax, abs(z))
        if abs(z) >= Z_MIN and vrel >= VOL_REL_MIN:
            out.append({"tipo": f"explosao_{w}m", "lado": "compra" if z > 0 else "venda", "tempo": f"{w}m", "z": round(z, 2),
                        "vol_rel": round(vrel, 1), "invalidacao": c[L - w],
                        "gatilho": f"{w} min {100 * (c[L] / c[L - w] - 1):+.2f}% (z {z:+.1f}), volume {vrel:.1f}× o normal"})
    ret1h = round(100 * (c[L] / c[L - 60] - 1), 2) if len(c) > 60 and c[L - 60] > 0 else None
    return out, round(zmax, 2), ret1h


def mm20(c):
    return sum(c[-20:]) / 20 if len(c) >= 20 else None


def para_4h(k1h):
    """Velas de 1 h fechadas → fechamentos de 4 h (blocos de 4 alinhados no fim)."""
    c = [float(x[4]) for x in k1h]
    return c[len(c) % 4 + 3::4]


def sinais_grafico(px, k15, k1h):
    """Tendência se formando, rompimento de 24 h e padrões confirmados. k15/k1h: velas FECHADAS. Devolve ([sinais], tempos a favor por lado)."""
    out = []
    c15, c1h = [float(x[4]) for x in k15], [float(x[4]) for x in k1h]
    c4h = para_4h(k1h)
    a_favor = {"compra": 0, "venda": 0}
    lados = {}
    for nome, c in (("15m", c15), ("1h", c1h), ("4h", c4h)):
        m = mm20(c)
        if m:
            lados[nome] = "compra" if c[-1] > m else "venda"
            a_favor[lados[nome]] += 1
    if len(lados) == 3 and len(set(lados.values())) == 1 and len(c15) >= 21:
        lado = lados["15m"]
        m_ant = sum(c15[-21:-1]) / 20
        cruzou = (c15[-2] <= m_ant) if lado == "compra" else (c15[-2] >= m_ant)
        if cruzou:
            out.append({"tipo": "tendencia", "lado": lado, "tempo": "15m/1h/4h", "invalidacao": round(mm20(c15), 10),
                        "gatilho": f"cruzou a MM20 de 15 min e está do mesmo lado em 1 h e 4 h ({'acima' if lado == 'compra' else 'abaixo'} nos 3)"})
    if len(k15) >= 97:
        hi = max(float(x[2]) for x in k15[-97:-1])
        lo = min(float(x[3]) for x in k15[-97:-1])
        if px > hi and c15[-1] <= hi:
            out.append({"tipo": "rompimento_24h", "lado": "compra", "tempo": "24h", "invalidacao": hi,
                        "gatilho": f"rompeu a máxima de 24 h ({hi:.6g}) a {px:.6g}"})
        elif px < lo and c15[-1] >= lo:
            out.append({"tipo": "rompimento_24h", "lado": "venda", "tempo": "24h", "invalidacao": lo,
                        "gatilho": f"rompeu a mínima de 24 h ({lo:.6g}) a {px:.6g}"})
    from lab import padroes_graficos as PG
    for nome, k in (("15m", k15), ("1h", k1h)):
        if len(k) < 40:
            continue
        try:
            achados = PG.detectar([float(x[1]) for x in k], [float(x[2]) for x in k], [float(x[3]) for x in k], [float(x[4]) for x in k])
        except Exception:
            achados = []
        for a in achados:
            if a.get("confirmado") and a.get("sentido") in ("alta", "baixa"):
                lado = "compra" if a["sentido"] == "alta" else "venda"
                out.append({"tipo": f"padrao_{nome}", "lado": lado, "tempo": nome, "padrao": a.get("padrao"),
                            "invalidacao": float(k[-1][3]) if lado == "compra" else float(k[-1][2]),
                            "gatilho": f"{a.get('padrao')} confirmado em {nome} ({a['sentido']})"})
                break
    return out, a_favor


def sugestao(px, lado, invalidacao, tempo):
    """Stop até o nível de invalidação (0,3–4%), alvo ≥ 3 × o stop e ≥ 1% (decisão do dono, 19/11; teto 5%), prazo pelo tempo gráfico."""
    dist = abs(px / invalidacao - 1) if invalidacao else 0.015
    stop = round(min(0.04, max(0.003, dist)), 4)
    alvo = round(min(0.05, max(3 * stop, 0.01)), 4)
    prazo = 60 if alvo <= 0.015 else 120 if alvo <= 0.03 else 240      # REGRAS.md §5 (19/11): prazo pelo alvo, igual para operadores e Caçador
    return {"stop_pct": stop, "alvo_pct": alvo, "max_min": prazo}


def forca(z, a_favor, vol_rel, meme):
    return int(min(100, round(12 * abs(z or 0) + 15 * a_favor + 8 * min(5.0, vol_rel or 0) + (10 if meme else 0))))


# ---------------- juiz ----------------
def registrar(e, ops, t, lidas, rnd=random):
    """Oportunidades novas → eventos do juiz (até MAX_EVENTOS, sem repetir (moeda, sinal, lado) em 30 min), cada um com um controle aleatório.
    lidas: {par: (preço, t_ms do fechamento do último minuto)}. Devolve os eventos novos."""
    ult = {k: v for k, v in (e.get("ultimos") or {}).items() if t - v < REPETE_S}
    novos = []
    for o in sorted(ops, key=lambda o: -o["forca"]):
        chave = f"{o['par']}|{o['tipo']}|{o['lado']}"
        if chave in ult or o["par"] not in lidas or len(novos) >= 2 * MAX_EVENTOS:
            continue
        ult[chave] = t
        px, tm = lidas[o["par"]]
        novos.append({"tipo": o["tipo"], "par": o["par"], "lado": o["lado"], "px": px, "tm": tm})
        cp = rnd.choice(sorted(lidas))
        novos.append({"tipo": "controle", "par": cp, "lado": rnd.choice(("compra", "venda")), "px": lidas[cp][0], "tm": lidas[cp][1]})
    e["ultimos"] = ult
    e["pendentes"] = (e.get("pendentes") or []) + novos
    return novos


def somar(placar, tipo, h, tm, r):
    hora = str(int(tm // 3_600_000))
    g = placar.setdefault(tipo, {}).setdefault(str(h), {}).setdefault(hora, [0, 0.0, 0])
    g[0] += 1
    g[1] += r
    g[2] += 1 if r > 0 else 0


def alvos(e, agora_ms):
    """(par, t_ms) dos minutos que já fecharam e resolvem algum evento pendente."""
    out = set()
    for ev in e.get("pendentes") or []:
        for h in HORIZONTES:
            alvo = ev["tm"] + (h - 1) * 60_000
            if f"r{h}" not in ev and agora_ms >= alvo + 60_000:
                out.add((ev["par"], alvo))
    return out


def resolver(e, preco_em, agora_ms):
    """preco_em(par, t_ms) → fechamento do minuto que ABRE em t_ms (vela histórica), ou None. Cada evento: 15 e 60 min depois da entrada."""
    placar = e.setdefault("placar", {})
    ficam = []
    for ev in e.get("pendentes") or []:
        for h in HORIZONTES:
            k = f"r{h}"
            alvo = ev["tm"] + (h - 1) * 60_000          # tm = fim do minuto da entrada; o minuto h depois abre em tm + (h−1) min
            if k in ev or agora_ms < alvo + 60_000:
                continue
            p = preco_em(ev["par"], alvo)
            if p is None:
                continue
            r = (p / ev["px"] - 1) * (1 if ev["lado"] == "compra" else -1) - CUSTO
            ev[k] = r
            somar(placar, ev["tipo"], h, ev["tm"], r)
        if all(f"r{h}" in ev for h in HORIZONTES) or agora_ms - ev["tm"] > 6 * 3_600_000:
            continue
        ficam.append(ev)
    e["pendentes"] = ficam


def avaliar(placar):
    """Juiz da H68 por sinal e horizonte: n, média, t agrupado pela hora, blocos (terços das horas), acerto; validade pelo controle."""
    out = {}
    for tipo, por_h in placar.items():
        for h, horas in por_h.items():
            gs = [horas[x] for x in sorted(horas, key=int)]
            n = sum(g[0] for g in gs)
            if not n:
                continue
            media = sum(g[1] for g in gs) / n
            G = len(gs)
            var = (G / (G - 1)) * sum((g[1] - g[0] * media) ** 2 for g in gs) / n ** 2 if G > 1 else None
            ep = var ** 0.5 if var else None
            terc = [gs[i * G // 3:(i + 1) * G // 3] for i in range(3)]
            blocos = [round(100 * sum(g[1] for g in b) / sum(g[0] for g in b), 3) if b and sum(g[0] for g in b) else None for b in terc]
            out.setdefault(tipo, {})[h] = {"n": n, "media_pct": round(100 * media, 3), "ep_pct": round(100 * ep, 3) if ep else None,
                                           "t": round(media / ep, 2) if ep else None, "acerto": round(sum(g[2] for g in gs) / n, 3),
                                           "horas": G, "blocos_pct": blocos}
    for tipo, por_h in out.items():
        for h, x in por_h.items():
            c = (out.get("controle") or {}).get(h)
            valido = bool(c and c["ep_pct"] and abs(c["media_pct"] + 100 * CUSTO) <= 2 * c["ep_pct"])
            x["controle_ok"] = valido
            if tipo != "controle":
                x["passa"] = bool(valido and x["n"] >= N_MIN and x["media_pct"] > 0 and (x["t"] or 0) >= T_MIN
                                  and sum(1 for b in x["blocos_pct"] if b is not None and b > 0) >= 2)
    return out


# ---------------- DEX (só informação) ----------------
def dex_filtrar(pares, agora_ms):
    """Pares de DEX → os que passam nos filtros de segurança da H68 (liquidez, idade, compras e vendas, volume)."""
    out = []
    for p in pares:
        liq = float((p.get("liquidez") or 0))
        idade_min = (agora_ms - (p.get("criado_ms") or agora_ms)) / 60_000
        if liq >= 50_000 and idade_min >= 30 and (p.get("compras_1h") or 0) >= 10 and (p.get("vendas_1h") or 0) >= 10 and (p.get("volume_1h") or 0) >= 25_000:
            out.append({**p, "idade_min": int(idade_min), "maiores_detentores": "não sei (a API pública não traz)"})
    return sorted(out, key=lambda p: -p["volume_1h"])[:15]


def dex(agora_ms):
    pares = []
    try:
        prof = _get("https://api.dexscreener.com/token-profiles/latest/v1")
        por_rede = {}
        for x in prof:
            por_rede.setdefault(x.get("chainId"), []).append(x.get("tokenAddress"))
        for rede, ends in list(por_rede.items())[:4]:
            for p in _get(f"https://api.dexscreener.com/tokens/v1/{rede}/{','.join(ends[:30])}"):
                tx = (p.get("txns") or {}).get("h1") or {}
                pares.append({"fonte": "dexscreener", "rede": rede, "simbolo": (p.get("baseToken") or {}).get("symbol"),
                              "endereco": (p.get("baseToken") or {}).get("address"), "liquidez": (p.get("liquidity") or {}).get("usd"),
                              "criado_ms": p.get("pairCreatedAt"), "compras_1h": tx.get("buys"), "vendas_1h": tx.get("sells"),
                              "volume_1h": (p.get("volume") or {}).get("h1"), "var_1h": (p.get("priceChange") or {}).get("h1"), "url": p.get("url")})
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        for x in _get("https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1").get("data", []):
            a = x.get("attributes") or {}
            tx = (a.get("transactions") or {}).get("h1") or {}
            criado = a.get("pool_created_at")
            pares.append({"fonte": "geckoterminal", "rede": "solana", "simbolo": str(a.get("name", "")).split(" / ")[0],
                          "endereco": a.get("address"), "liquidez": float(a.get("reserve_in_usd") or 0),
                          "criado_ms": int(time.mktime(time.strptime(criado[:19], "%Y-%m-%dT%H:%M:%S")) * 1000 - time.timezone * 1000) if criado else None,
                          "compras_1h": tx.get("buys"), "vendas_1h": tx.get("sells"), "volume_1h": float((a.get("volume_usd") or {}).get("h1") or 0),
                          "var_1h": (a.get("price_change_percentage") or {}).get("h1"), "url": f"https://www.geckoterminal.com/solana/pools/{a.get('address')}"})
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {"t": agora_ms / 1000, "lidos": len(pares), "aprovados": dex_filtrar(pares, agora_ms),
            "aviso": "só informação: os operadores operam a Binance (simulado/teste), não DEX"}


# ---------------- rodada ----------------
def velas(par, iv, limite):
    try:
        k = _get(f"{DADOS}/klines?symbol={par}&interval={iv}&limit={limite}")
        return par, [x for x in k if int(x[6]) < time.time() * 1000]
    except (OSError, ValueError):
        return par, []


def preco_em(par, t_ms):
    try:
        k = _get(f"{DADOS}/klines?symbol={par}&interval=1m&startTime={int(t_ms)}&limit=1")
        return float(k[0][4]) if k and int(k[0][0]) == int(t_ms) and int(k[0][6]) < time.time() * 1000 else None
    except (OSError, ValueError, IndexError):
        return None


def main():
    t0 = time.time()
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    try:
        e = json.loads(arq.read_text()) if arq.exists() else {}
    except ValueError:
        e = {}
    agora = time.time()
    ticker = _get(f"{DADOS}/ticker/24hr", 60)
    info = e.get("simbolos") or {}
    if agora - info.get("t", 0) > INFO_S or not info.get("lista"):
        try:
            lista = sorted(s["symbol"] for s in _get(f"{DADOS}/exchangeInfo?permissions=SPOT", 90)["symbols"]
                           if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING")
            e["novas_listagens"] = novas_listagens(info.get("lista") or [], lista, agora, e.get("novas_listagens") or [])
            info = {"t": agora, "lista": lista}
        except (OSError, ValueError, KeyError):
            pass
    e["simbolos"] = info
    univ = filtrar(info.get("lista") or [x["symbol"] for x in ticker if x["symbol"].endswith("USDT")], ticker)
    tk = {x["symbol"]: x for x in ticker}
    with ThreadPoolExecutor(16) as ex:
        k1 = dict(ex.map(lambda p: velas(p, "1m", BASE + max(JANELAS) + 6), univ))
    lidas, s1, zmax, r1h = {}, {}, {}, {}
    for par, k in k1.items():
        if len(k) < BASE + max(JANELAS) + 1:
            continue
        lidas[par] = (float(k[-1][4]), int(k[-1][6]) + 1)
        s1[par], zmax[par], r1h[par] = sinais_1m(k)
    novas = {x["par"] for x in e.get("novas_listagens") or []}
    perto = [p for p in lidas if p in tk and float(tk[p]["highPrice"]) > 0 and
             (lidas[p][0] >= 0.995 * float(tk[p]["highPrice"]) or lidas[p][0] <= 1.005 * float(tk[p]["lowPrice"]))]
    cand = list(dict.fromkeys([p for p in lidas if s1[p]] + [p for p in lidas if e_meme(p)] + [p for p in lidas if p in novas]
                              + sorted(lidas, key=lambda p: -abs(float(tk.get(p, {}).get("priceChangePercent") or 0)))[:20]
                              + sorted(lidas, key=lambda p: -abs(r1h[p] or 0))[:20] + perto))[:MAX_CAND]
    with ThreadPoolExecutor(10) as ex:
        k15 = dict(ex.map(lambda p: velas(p, "15m", 100), cand))
        k60 = dict(ex.map(lambda p: velas(p, "1h", 100), cand))
    ops = []
    for par in lidas:
        sg, af = (sinais_grafico(lidas[par][0], k15.get(par) or [], k60.get(par) or []) if par in cand else ([], {"compra": 0, "venda": 0}))
        for s in s1[par] + sg:
            ops.append({"par": par, "moeda": par[:-4], **s, "preco": lidas[par][0], "t": int(agora), "meme": e_meme(par),
                        "nova_listagem": par in novas, "tempos_mm20_a_favor": af.get(s["lado"], 0) if par in cand else None,
                        "var_24h": float(tk.get(par, {}).get("priceChangePercent") or 0), "var_1h": r1h[par],
                        "sugestao": sugestao(lidas[par][0], s["lado"], s.get("invalidacao"), s.get("tempo")),
                        "forca": forca(s.get("z") or zmax[par], af.get(s["lado"], 0), s.get("vol_rel") or 0, e_meme(par))})
    ops.sort(key=lambda o: (not o["meme"], -o["forca"]))
    reais = sorted(ops, key=lambda o: -o["forca"])[:MAX_EVENTOS]
    novos = registrar(e, reais, agora, lidas)
    agora_ms = int(time.time() * 1000)
    precisa = sorted(alvos(e, agora_ms))
    with ThreadPoolExecutor(10) as ex:
        precos = dict(zip(precisa, ex.map(lambda a: preco_em(*a), precisa)))
    resolver(e, lambda par, t: precos.get((par, t)), agora_ms)
    e["juiz_h68"] = avaliar(e.get("placar") or {})
    if agora - (e.get("dex") or {}).get("t", 0) > DEX_S:
        e["dex"] = dex(agora_ms)
    recentes = [o for o in (e.get("oportunidades") or []) if agora - o["t"] <= 30 * 60 and (o["par"], o["tipo"], o["lado"]) not in
                {(x["par"], x["tipo"], x["lado"]) for x in ops}]
    e["oportunidades"] = sorted(ops + recentes, key=lambda o: (not o["meme"], -o["forca"], -o["t"]))[:60]
    e["t"] = agora
    e["universo"] = {"pares_usdt_negociando": len(info.get("lista") or []), "universo": len(univ), "lidas_1m": len(lidas),
                     "candidatas_15m_1h": len(cand), "sinais_rodada": len(ops), "eventos_novos": sum(1 for x in novos if x["tipo"] != "controle"),
                     "pendentes": len(e.get("pendentes") or []), "segundos": round(time.time() - t0, 1)}
    tmp = arq.with_name(ARQ + ".tmp")                  # troca atômica: o limite de 150 s da nuvem nunca deixa o arquivo pela metade
    tmp.write_text(json.dumps(e, ensure_ascii=False))
    tmp.replace(arq)
    u = e["universo"]
    print(f"🔭 Caçador: {u['lidas_1m']} de {u['universo']} pares lidos em 1 min · {u['candidatas_15m_1h']} em 15 min/1 h · {u['sinais_rodada']} sinais "
          f"· {u['eventos_novos']} eventos novos · {u['pendentes']} no juiz · {u['segundos']} s")
    for o in e["oportunidades"][:5]:
        print(f"   {o['moeda']} {o['lado']} {o['tipo']} força {o['forca']}: {o['gatilho']}")


if __name__ == "__main__":
    main()
