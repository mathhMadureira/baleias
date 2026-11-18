"""H63 — "monitor fomo": raspagem das melhores carteiras da Hyperliquid para os agentes (regra e juiz em lab/PROTOCOLO_LAB.md, antes de rodar).

A cada rodada da nuvem:
  1. a cada 24 h, o ranking público (stats-data.hyperliquid.xyz) → as 40 carteiras pelo filtro fixo da H63;
  2. as posições abertas delas (clearinghouseState) e os preços de meio (allMids), API pública, só leitura;
  3. o "feed": aberturas e fechamentos desde a rodada anterior; cada abertura vira um evento que é resolvido entre 60 e 75 min depois
     (retorno no lado da carteira − 0,12% de custo): é o juiz automático da hipótese;
  4. o resumo por moeda (compradas, vendidas, valor líquido, aberturas na última hora) para os agentes.
Grava dados/carteiras_top.json. Nenhuma ordem, nenhuma chave. Endereços são públicos (ranking público da Hyperliquid).

Uso: BALEIAS_DADOS=.../estado/dados python -m executor.carteiras_nuvem
"""
import json
import time
import urllib.request

from baleias import config

RANKING = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
INFO = "https://api.hyperliquid.xyz/info"
N_CARTEIRAS, CONTA_MIN, ROI_MES_MIN, GIRO_MIN = 40, 50_000.0, 0.05, 10.0
RENOVAR_S, CUSTO, H_MIN, H_MAX = 24 * 3600, 0.0012, 60 * 60, 75 * 60
ARQ = "carteiras_top.json"


def _post(corpo, t=30):
    req = urllib.request.Request(INFO, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=t) as r:
        return json.load(r)


def par_binance(coin):
    """Moeda da Hyperliquid → par USDT da Binance (kPEPE é PEPE em lotes de 1000; moedas de outros dex, com ':', ficam de fora)."""
    if ":" in coin:
        return None
    return (coin[1:] if coin.startswith("k") and coin[1:].isupper() else coin) + "USDT"


def selecionar(linhas):
    """Filtro fixo da H63 sobre as linhas do ranking. Devolve [{endereco, conta, roi_mes, roi_semana, giro}] (as N de maior ROI do mês)."""
    out = []
    for x in linhas:
        try:
            w = {k: v for k, v in x["windowPerformances"]}
            conta = float(x["accountValue"])
            mes, sem, tudo = w["month"], w["week"], w["allTime"]
            if conta < CONTA_MIN or float(mes["pnl"]) <= 0 or float(sem["pnl"]) <= 0 or float(tudo["pnl"]) <= 0:
                continue
            roi, giro = float(mes["roi"]), float(mes["vlm"]) / conta
            if roi < ROI_MES_MIN or giro < GIRO_MIN:
                continue
            out.append({"endereco": x["ethAddress"], "conta": round(conta), "roi_mes": round(roi, 4), "roi_semana": round(float(sem["roi"]), 4),
                        "giro": round(giro, 1)})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    return sorted(out, key=lambda c: -c["roi_mes"])[:N_CARTEIRAS]


def posicoes(estado_conta):
    """clearinghouseState → {coin: {lado, valor_usd, entrada, alavancagem}}."""
    out = {}
    for a in estado_conta.get("assetPositions") or []:
        p = a.get("position") or {}
        szi = float(p.get("szi") or 0)
        if szi:
            out[p["coin"]] = {"lado": "compra" if szi > 0 else "venda", "valor_usd": round(float(p.get("positionValue") or 0), 2),
                              "entrada": float(p.get("entryPx") or 0), "alavancagem": (p.get("leverage") or {}).get("value")}
    return out


def diferencas(antes, agora_pos, mids, t):
    """Compara as posições {endereco: {coin: pos}} da rodada anterior com as de agora. Devolve eventos de abertura e fechamento."""
    ev = []
    for end, pos in agora_pos.items():
        if end not in antes:                              # carteira nova na lista: o que ela já tinha não é abertura
            continue
        velhas = antes[end]
        for coin, p in pos.items():
            v = velhas.get(coin)
            if (not v or v["lado"] != p["lado"]) and coin in mids:
                ev.append({"t": int(t), "tipo": "abriu", "carteira": end, "coin": coin, "par": par_binance(coin), "lado": p["lado"],
                           "valor_usd": p["valor_usd"], "px": float(mids[coin])})
        for coin, v in velhas.items():
            if coin not in pos or pos[coin]["lado"] != v["lado"]:
                ev.append({"t": int(t), "tipo": "fechou", "carteira": end, "coin": coin, "par": par_binance(coin), "lado": v["lado"]})
    return ev


def resolver(eventos, mids, t):
    """Aberturas com idade entre H_MIN e H_MAX ganham o resultado; passou de H_MAX sem resolver → descartada (janela perdida)."""
    for e in eventos:
        if e["tipo"] != "abriu" or "resultado" in e or e.get("descartado"):
            continue
        idade = t - e["t"]
        if idade > H_MAX:
            e["descartado"] = True
        elif idade >= H_MIN and e["coin"] in mids and e["px"]:
            s = 1 if e["lado"] == "compra" else -1
            e["resultado"] = round(s * (float(mids[e["coin"]]) / e["px"] - 1) - CUSTO, 6)
            e["resolvido_t"] = int(t)
    return eventos


def resumo(pos_por_carteira, eventos, t):
    """Por moeda: quantas das carteiras estão compradas/vendidas, valor líquido e aberturas na última hora."""
    m = {}
    for pos in pos_por_carteira.values():
        for coin, p in pos.items():
            x = m.setdefault(coin, {"coin": coin, "par": par_binance(coin), "compradas": 0, "vendidas": 0, "liquido_usd": 0.0,
                                    "abriram_1h_compra": 0, "abriram_1h_venda": 0})
            x["compradas" if p["lado"] == "compra" else "vendidas"] += 1
            x["liquido_usd"] += p["valor_usd"] if p["lado"] == "compra" else -p["valor_usd"]
    for e in eventos:
        if e["tipo"] == "abriu" and t - e["t"] <= 3600 and e["coin"] in m:
            m[e["coin"]]["abriram_1h_" + e["lado"]] += 1
    for x in m.values():
        x["liquido_usd"] = round(x["liquido_usd"])
    return sorted(m.values(), key=lambda x: -(x["compradas"] + x["vendidas"]))


def avaliar(eventos):
    """O juiz da H63 (descrição corrente): n, média, t por hora de abertura."""
    r = [e for e in eventos if "resultado" in e]
    if not r:
        return {"n": 0}
    por_hora = {}
    for e in r:
        por_hora.setdefault(e["t"] // 3600, []).append(e["resultado"])
    medias = [sum(v) / len(v) for v in por_hora.values()]
    n_h, m = len(medias), sum(medias) / len(medias)
    dp = (sum((x - m) ** 2 for x in medias) / (n_h - 1)) ** 0.5 if n_h > 1 else 0.0
    return {"n": len(r), "horas": n_h, "media": round(sum(e["resultado"] for e in r) / len(r), 6), "t_por_hora": round(m / (dp / n_h ** 0.5), 2) if dp else None,
            "acerto": round(sum(e["resultado"] > 0 for e in r) / len(r), 3)}


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"carteiras": [], "selecionadas_t": 0, "posicoes": {}, "eventos": []}
    agora = time.time()
    if agora - e.get("selecionadas_t", 0) > RENOVAR_S or not e.get("carteiras"):
        try:
            with urllib.request.urlopen(urllib.request.Request(RANKING, headers={"User-Agent": "baleias/1.0"}), timeout=120) as r:
                e["carteiras"] = selecionar(json.load(r).get("leaderboardRows") or [])
            e["selecionadas_t"] = int(agora)
        except (OSError, ValueError) as ex:
            print(f"🐋 Carteiras: ranking fora do ar ({str(ex)[:80]}); sigo com a lista anterior")
    try:
        mids = _post({"type": "allMids"})
    except (OSError, ValueError) as ex:
        print(f"🐋 Carteiras: preços fora do ar ({str(ex)[:80]}); nada feito nesta rodada")
        return
    pos = {}
    for c in e["carteiras"]:
        try:
            pos[c["endereco"]] = posicoes(_post({"type": "clearinghouseState", "user": c["endereco"]}))
        except (OSError, ValueError):
            if c["endereco"] in e.get("posicoes", {}):
                pos[c["endereco"]] = e["posicoes"][c["endereco"]]          # sem resposta: mantém a anterior (não inventa abertura nem fechamento)
        time.sleep(0.1)
    novos = diferencas(e.get("posicoes", {}), pos, mids, agora)
    e["eventos"] = resolver((e.get("eventos", []) + novos)[-6000:], mids, agora)
    e["posicoes"], e["t"] = pos, int(agora)
    e["moedas"] = resumo(pos, e["eventos"], agora)
    e["feed"] = [x for x in e["eventos"] if agora - x["t"] <= 3600][-60:][::-1]
    e["juiz_h63"] = avaliar(e["eventos"])
    arq.write_text(json.dumps(e, ensure_ascii=False))
    print(f"🐋 Carteiras (H63): {len(pos)} de {len(e['carteiras'])} lidas · {len(novos)} mudanças nesta rodada · "
          f"{sum(1 for x in novos if x['tipo'] == 'abriu')} aberturas · juiz {e['juiz_h63']}")


if __name__ == "__main__":
    main()
