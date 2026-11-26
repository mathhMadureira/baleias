"""Motor do pump.fun NO PAPEL (26/11, dono: US$ 10 no pump.fun; 2 dias simulados antes do dinheiro real).

Preços reais, dinheiro simulado. Nenhuma carteira, nenhuma chave, nenhuma transação.
A cada CICLO_S:
  1. descobre moedas ativas na API pública do pump.fun (as que mais negociaram agora e as maiores na curva);
  2. lê o preço de cada uma DIRETO na Solana (conta da curva de lançamento: reservas virtuais → preço em SOL) e o SOL em US$ na Binance;
  3. guarda o histórico de preço (gráfico do painel) e decide:
     entra se: 10+ min de vida, não graduada, valor de mercado entre MCAP_MIN e MCAP_MAX, subiu ≥ IMPULSO nos últimos 3 min
               com 3 leituras seguidas subindo, e não foi operada nas últimas 2 h;
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
CICLO_S, CAPITAL, POS_USD, MAX_POS = 15, 10.0, 2.5, 4
MCAP_MIN, MCAP_MAX, IMPULSO = 8_000, 60_000, 0.15
STOP, ALVO, ARMA, GUARDA, PRAZO_MIN = 0.12, 0.35, 0.15, 0.60, 45
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
            vt, vs = struct.unpack_from("<QQ", raw, 8)
            if vt:
                out[c] = ((vs / 1e9) / (vt / 1e6), bool(raw[48]))
    return out


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
    return e["caixa"] + sum(p["qtd"] * px.get(p["curva"], (p["entrada"],))[0] * e.get("sol", 0) * (1 - CUSTO_LADO)
                            for p in e["abertas"].values())


def volta(e):
    agora = time.time()
    moedas = {}
    for q in ("sort=last_trade_timestamp&order=DESC", "sort=market_cap&order=DESC"):
        try:
            for x in _get(f"{API}&{q}"):
                if isinstance(x, dict) and x.get("bonding_curve") and not x.get("is_banned"):
                    moedas[x["mint"]] = x
        except Exception as ex:
            print("descoberta falhou:", ex, flush=True)
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

    # saídas
    for m, p in list(e["abertas"].items()):
        if p["curva"] not in px:
            continue
        preco, graduada = px[p["curva"]]
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

    # entradas
    recentes = {x["mint"] for x in e["fechadas"] if agora - x["saida_t"] < ESFRIA_S}
    cands = []
    for m, x in moedas.items():
        if m in e["abertas"] or m in recentes or x["bonding_curve"] not in px:
            continue
        preco, graduada = px[x["bonding_curve"]]
        idade = (agora * 1000 - float(x.get("created_timestamp") or 0)) / 60000
        mcap = preco * sol * 1e9
        h = e["hist"].get(m, [])
        janela = [v for t, v in h if agora - t <= 190]
        if graduada or idade < 10 or not (MCAP_MIN <= mcap <= MCAP_MAX) or len(janela) < 4:
            continue
        subiu = janela[-1] / janela[0] - 1
        seguidas = all(janela[i] < janela[i + 1] for i in range(len(janela) - 3, len(janela) - 1))
        if subiu >= IMPULSO and seguidas:
            cands.append((subiu, m, x, preco, mcap))
    for subiu, m, x, preco, mcap in sorted(cands, reverse=True):
        if len(e["abertas"]) >= MAX_POS or e["caixa"] < POS_USD:
            break
        qtd = POS_USD * (1 - CUSTO_LADO) / (preco * sol)
        e["caixa"] -= POS_USD
        e["abertas"][m] = {"simbolo": x.get("symbol"), "curva": x["bonding_curve"], "entrada": preco, "qtd": qtd, "usd": POS_USD, "t": agora,
                           "criada_ms": x.get("created_timestamp"), "mcap_entrada": round(mcap), "pico": 0.0,
                           "motivo": f"subiu {subiu:+.0%} em 3 min, valor de mercado US$ {mcap:,.0f}"}
        anotar(e, f"🟢 ENTROU em {x.get('symbol')} (papel): US$ {POS_USD:.2f}, subiu {subiu:+.0%} em 3 min, mercado US$ {mcap:,.0f}")
    e["patrimonio"] = patrimonio(e, px)
    e["curva"].append([round(agora), round(e["patrimonio"], 4)])
    e["curva"] = e["curva"][-3000:]
    e["atualizado"] = agora
    e["lidas"] = len(px)


def main():
    e = carregar()
    while True:
        t0 = time.time()
        try:
            volta(e)
            salvar(e)
        except Exception as ex:
            print(f"erro: {type(ex).__name__}: {ex}", flush=True)
        time.sleep(max(3, CICLO_S - (time.time() - t0)))


if __name__ == "__main__":
    main()
