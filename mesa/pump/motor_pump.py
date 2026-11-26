"""Motor do pump.fun NO PAPEL (26/11, dono: US$ 10 no pump.fun; 2 dias simulados antes do dinheiro real).

Preços reais, dinheiro simulado. Nenhuma carteira, nenhuma chave, nenhuma transação.
A cada CICLO_S:
  1. descobre moedas ativas na API pública do pump.fun (as que mais negociaram agora e as maiores na curva);
  2. lê o preço de cada uma DIRETO na Solana (conta da curva de lançamento: reservas virtuais → preço em SOL) e o SOL em US$ na Binance;
  3. guarda o histórico de preço (gráfico do painel) e decide:
     v2 entra se: 20+ min de vida, curva entre 60% e 92% vendida (perto da graduação), +5% em 10 min sem salto > 40% em 3 min,
               10 maiores carteiras com ≤ 25% do suprimento, e não foi operada nas últimas 2 h; posições vigiadas a cada 5 s;
     sai por: stop, alvo, stop móvel (depois de +ARMA guarda GUARDA do pico), prazo, ou graduação (sai da curva).
  Custos simulados: taxa do pump.fun 1% + derrapagem 1% em cada lado (4% ida e volta).
Estado: Shared/baleias/pump/estado.json. Uso: python3 -u motor_pump.py
"""
import base64
import json
import struct
import time
import urllib.request
from pathlib import Path

PASTA = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/pump")
EST = PASTA / "estado.json"
RPC = "https://api.mainnet-beta.solana.com"
API = "https://frontend-api-v3.pump.fun/coins?offset=0&limit=50&includeNsfw=false"
UA = {"User-Agent": "Mozilla/5.0"}
CICLO_S, CAPITAL, POS_USD, MAX_POS = 30, 10.0, 2.0, 3   # 30 s: a API do pump.fun recusa (429) leituras a cada 15 s
# v2 (26/11): v1 comprava o pico do impulso (+15% em 3 min) e as 3 primeiras caíram 22–38% em até 2 min (venda do criador e dos primeiros).
# Agora: moeda madura, perto da graduação, subindo devagar, sem concentração — e posições vigiadas a cada RAPIDO_S.
PROG_MIN, PROG_MAX, IDADE_MIN = 0.60, 0.92, 20          # progresso da curva (fração vendida) e idade mínima (min)
SUBIDA_10M_MIN, SALTO_3M_MAX, TOP10_MAX = 0.05, 0.40, 0.25
STOP, ALVO, ARMA, GUARDA, PRAZO_MIN = 0.10, 0.30, 0.12, 0.60, 90
RAPIDO_S = 5
TOKENS_CURVA = 793_100_000 * 10 ** 6                    # tokens reais à venda na curva do pump.fun (6 casas)
CUSTO_LADO = 0.02
HIST_S, ESFRIA_S = 3600, 2 * 3600


def _get(url, dados=None, t=15):
    req = urllib.request.Request(url, data=dados, headers={**UA, **({"Content-Type": "application/json"} if dados else {})})
    with urllib.request.urlopen(req, timeout=t) as r:
        return json.load(r)


def sol_usd():
    return float(_get("https://data-api.binance.vision/api/v3/ticker/price?symbol=SOLUSDT")["price"])


def precos(curvas):
    """{curva: (preço em SOL por token, graduada)} lendo as contas da curva na Solana (até 100 por chamada)."""
    out = {}
    for i in range(0, len(curvas), 100):
        lote = curvas[i:i + 100]
        r = _get(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts", "params": [lote, {"encoding": "base64"}]}).encode())
        for c, v in zip(lote, r["result"]["value"]):
            if not v:
                continue
            raw = base64.b64decode(v["data"][0])
            if len(raw) < 49:
                continue
            vt, vs, rt = struct.unpack_from("<QQQ", raw, 8)
            if vt:
                out[c] = ((vs / 1e9) / (vt / 1e6), bool(raw[48]), 1 - rt / TOKENS_CURVA)
    return out


def top10(mint, curva_ata):
    """Fração do suprimento nas 10 maiores carteiras, sem contar a conta da curva (onde ficam os tokens não vendidos)."""
    try:
        r = _get(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getTokenLargestAccounts", "params": [mint]}).encode())
        contas = [a for a in r["result"]["value"] if a["address"] != curva_ata]
        return sum(float(a["uiAmount"] or 0) for a in contas[:10]) / 1e9
    except Exception:
        return None


def vigiar(e):
    """A cada RAPIDO_S: só o preço das abertas e as saídas (o stop de 10% não pode virar 38%)."""
    if not e["abertas"]:
        return
    px = precos(sorted({p["curva"] for p in e["abertas"].values()}))
    for m, p in list(e["abertas"].items()):
        if p["curva"] in px:
            e["hist"].setdefault(m, []).append([round(time.time()), px[p["curva"]][0]])
    sair(e, px, time.time())
    e["patrimonio"] = patrimonio(e, px)
    e["atualizado"] = time.time()


def carregar():
    try:
        return json.loads(EST.read_text())
    except (OSError, ValueError):
        return {"inicio": time.time(), "caixa": CAPITAL, "capital": CAPITAL, "abertas": {}, "fechadas": [], "hist": {}, "info": {},
                "eventos": [], "curva": []}


def salvar(e):
    e["eventos"] = e["eventos"][-200:]
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = EST.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False))
    tmp.replace(EST)


def anotar(e, texto):
    e["eventos"].append({"t": time.time(), "texto": texto})
    print(time.strftime("%H:%M:%S"), texto, flush=True)


def patrimonio(e, px):
    """Abertas pelo preço de agora; sem preço, pelo último lido (nunca pelo de entrada, que esconderia perda ou ganho)."""
    tot = e["caixa"]
    for m, p in e["abertas"].items():
        preco = px[p["curva"]][0] if p["curva"] in px else ((e["hist"].get(m) or [[0, p["entrada"]]])[-1][1])
        tot += p["qtd"] * preco * e.get("sol", 0) * (1 - CUSTO_LADO)
    return tot


def sair(e, px, agora):
    sol = e.get("sol") or 0
    for m, p in list(e["abertas"].items()):
        if p["curva"] not in px:                            # a conta da curva sumiu: a moeda graduou e a curva foi fechada
            p["sem_curva"] = p.get("sem_curva", 0) + 1
            if p["sem_curva"] >= 3:
                h = e["hist"].get(m) or [[0, p["entrada"]]]
                ult = h[-1][1]
                valor = p["qtd"] * ult * sol * (1 - CUSTO_LADO)
                res = valor - p["usd"]
                e["caixa"] += valor
                e["fechadas"].append({**p, "mint": m, "saida": ult, "saida_t": agora, "resultado": round(res, 4),
                                      "motivo_saida": "curva fechada (graduou): sai no último preço lido"})
                del e["abertas"][m]
                anotar(e, f"{'✅' if res > 0 else '❌'} SAIU de {p['simbolo']}: {res:+.3f} US$ ({ult / p['entrada'] - 1:+.1%}, curva fechada / graduou)")
            continue
        p["sem_curva"] = 0
        preco, graduada = px[p["curva"]][:2]
        var = preco / p["entrada"] - 1
        p["pico"] = max(p.get("pico", 0.0), var)
        motivo = None
        if graduada:
            motivo = "graduou (saiu da curva)"
        elif var <= -STOP:
            motivo = f"stop −{STOP:.0%}"
        elif var >= ALVO:
            motivo = f"alvo +{ALVO:.0%}"
        elif p["pico"] >= ARMA and var <= GUARDA * p["pico"]:
            motivo = f"stop móvel (pico +{p['pico']:.0%})"
        elif agora - p["t"] > PRAZO_MIN * 60:
            motivo = f"prazo {PRAZO_MIN} min"
        if motivo:
            valor = p["qtd"] * preco * sol * (1 - CUSTO_LADO)
            res = valor - p["usd"]
            e["caixa"] += valor
            e["fechadas"].append({**p, "mint": m, "saida": preco, "saida_t": agora, "resultado": round(res, 4), "motivo_saida": motivo})
            del e["abertas"][m]
            anotar(e, f"{'✅' if res > 0 else '❌'} SAIU de {p['simbolo']}: {res:+.3f} US$ ({var:+.1%}, {motivo})")



def volta(e):
    agora = time.time()
    moedas = {}
    # 26/11: a API recusa (429) duas leituras seguidas; uma lista por volta, alternando, e espera crescente depois de recusa
    if agora >= e.get("api_livre_t", 0):
        q = ("sort=last_trade_timestamp&order=DESC", "sort=market_cap&order=DESC")[e.get("api_vez", 0) % 2]
        e["api_vez"] = e.get("api_vez", 0) + 1
        try:
            for x in _get(f"{API}&{q}"):
                if isinstance(x, dict) and x.get("bonding_curve") and not x.get("is_banned"):
                    e.setdefault("conhecidas", {})[x["mint"]] = {k: x.get(k) for k in ("mint", "bonding_curve", "associated_bonding_curve", "symbol", "name", "created_timestamp")}
            e["api_espera"] = 0
        except Exception as ex:
            e["api_espera"] = min(600, max(60, 2 * e.get("api_espera", 0)))
            e["api_livre_t"] = agora + e["api_espera"]
            print(f"descoberta falhou ({ex}); espero {e['api_espera']} s", flush=True)
    for m, x in list((e.get("conhecidas") or {}).items()):   # as já conhecidas continuam sendo lidas na Solana, mesmo sem a API
        if agora * 1000 - float(x.get("created_timestamp") or 0) > 24 * 3600 * 1000:
            e["conhecidas"].pop(m, None)
        else:
            moedas[m] = x
    for m, p in e["abertas"].items():                    # as abertas sempre são lidas
        moedas.setdefault(m, {"mint": m, "bonding_curve": p["curva"], "symbol": p["simbolo"], "created_timestamp": p.get("criada_ms", 0)})
    e["sol"] = sol = sol_usd()
    px = precos(sorted({x["bonding_curve"] for x in moedas.values()}))
    for m, x in moedas.items():
        c = x["bonding_curve"]
        if c not in px:
            continue
        e["info"][m] = {"simbolo": x.get("symbol"), "curva": c, "criada_ms": x.get("created_timestamp"), "nome": x.get("name")}
        h = e["hist"].setdefault(m, [])
        h.append([round(agora), px[c][0]])
        e["hist"][m] = [p for p in h if agora - p[0] <= HIST_S]
    # limpar histórico de quem sumiu há mais de 1 h
    for m in [m for m, h in e["hist"].items() if not h or agora - h[-1][0] > HIST_S]:
        e["hist"].pop(m, None)
        e["info"].pop(m, None)

    sair(e, px, agora)

    # entradas
    recentes = {x["mint"] for x in e["fechadas"] if agora - x["saida_t"] < ESFRIA_S}
    cands = []
    for m, x in moedas.items():
        if m in e["abertas"] or m in recentes or x["bonding_curve"] not in px:
            continue
        preco, graduada, prog = px[x["bonding_curve"]]
        idade = (agora * 1000 - float(x.get("created_timestamp") or 0)) / 60000
        mcap = preco * sol * 1e9
        h = e["hist"].get(m, [])
        j10 = [v for t, v in h if agora - t <= 610]
        j3 = [v for t, v in h if agora - t <= 190]
        if graduada or idade < IDADE_MIN or not (PROG_MIN <= prog <= PROG_MAX) or len(j10) < 20 or len(j3) < 4:
            continue
        sub10, salto3 = j10[-1] / j10[0] - 1, j3[-1] / min(j3) - 1
        if sub10 >= SUBIDA_10M_MIN and salto3 <= SALTO_3M_MAX and j3[-1] >= j3[0]:
            cands.append((sub10, m, x, preco, mcap, prog))
    escolhidos = []
    for sub10, m, x, preco, mcap, prog in sorted(cands, reverse=True)[:3]:
        top = top10(m, x.get("associated_bonding_curve"))
        if top is None or top > TOP10_MAX:
            anotar(e, f"⛔ {x.get('symbol')}: 10 maiores carteiras com {top if top is None else f'{top:.0%}'} do suprimento; não entra")
            continue
        escolhidos.append((sub10, m, x, preco, mcap, prog, top))
    for subiu, m, x, preco, mcap, prog, top in escolhidos:
        if len(e["abertas"]) >= MAX_POS or e["caixa"] < POS_USD:
            break
        qtd = POS_USD * (1 - CUSTO_LADO) / (preco * sol)
        e["caixa"] -= POS_USD
        e["abertas"][m] = {"simbolo": x.get("symbol"), "curva": x["bonding_curve"], "entrada": preco, "qtd": qtd, "usd": POS_USD, "t": agora,
                           "criada_ms": x.get("created_timestamp"), "mcap_entrada": round(mcap), "pico": 0.0,
                           "motivo": f"curva {prog:.0%}, +{subiu:.0%} em 10 min, 10 maiores {top:.0%}, mercado US$ {mcap:,.0f}"}
        anotar(e, f"🟢 ENTROU em {x.get('symbol')} (papel): US$ {POS_USD:.2f}, curva {prog:.0%}, +{subiu:.0%} em 10 min, 10 maiores {top:.0%}, mercado US$ {mcap:,.0f}")
    e["patrimonio"] = patrimonio(e, px)
    e["curva"].append([round(agora), round(e["patrimonio"], 4)])
    e["curva"] = e["curva"][-3000:]
    e["atualizado"] = agora
    e["lidas"] = len(px)


def main():
    e = carregar()
    proxima = 0.0
    while True:
        t0 = time.time()
        try:
            if t0 >= proxima:
                volta(e)
                proxima = time.time() + CICLO_S
            else:
                vigiar(e)
            salvar(e)
        except Exception as ex:
            print(f"erro: {type(ex).__name__}: {ex}", flush=True)
        time.sleep(max(1, RAPIDO_S - (time.time() - t0)))


if __name__ == "__main__":
    main()
