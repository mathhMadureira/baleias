"""Universo de moedas dos robôs: TODAS as moedas da Binance com par USDT à vista, em negociação, com volume ≥ MINIMO em 24 h
(decisão do dono, 2026-11-13: "os robôs devem olhar todas as moedas que estão na Binance, já que tudo vai ser operado dentro dela").

Exclui moedas estáveis e fiduciárias (não têm direção para prever) e tokens alavancados (BTCUP, ETHDOWN...). As 33 moedas de sempre
(lab.tartaruga.MOEDAS_ROBO) ficam mesmo abaixo do mínimo. Se a Binance não responder, volta às 33. Resultado em cache por 1 h.
Uso: from lab import universo as U; U.moedas()
"""
import json
import os
import time
import urllib.request

from lab import tartaruga as T

MINIMO = float(os.environ.get("UNIVERSO_VOLUME_MIN", "1000000"))      # US$ 1 milhão em 24 h: tira só os mercados mortos
ESTAVEIS = {"USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USD1", "USDE", "USDS", "RLUSD", "XUSD", "BFUSD", "AEUR", "EURI", "EUR", "TRY", "BRL",
            "GBP", "AUD", "JPY", "ARS", "UAH", "ZAR", "PAXG", "XAUT", "RWUSD", "WBTC", "WBETH", "BNSOL", "WBNB"}
_cache = {"t": 0.0, "moedas": None}


def moedas(minimo=MINIMO):
    if _cache["moedas"] and time.time() - _cache["t"] < 3600:
        return _cache["moedas"]
    try:
        with urllib.request.urlopen(f"{T.DADOS}/api/v3/exchangeInfo", timeout=60) as r:
            info = json.load(r)
        with urllib.request.urlopen(f"{T.DADOS}/api/v3/ticker/24hr", timeout=60) as r:
            volume = {x["symbol"]: float(x["quoteVolume"]) for x in json.load(r)}
    except (OSError, ValueError, KeyError):
        return list(T.MOEDAS_ROBO)
    simbolos = {s["symbol"] for s in info["symbols"]}
    saida = []
    for s in info["symbols"]:
        if s["quoteAsset"] != "USDT" or s["status"] != "TRADING":
            continue
        b = s["baseAsset"]
        if b in ESTAVEIS or not b.isascii():
            continue
        if (len(b) >= 4 and b.endswith("B") and b not in {"SHIB"}) or b in {"MUB"}:      # ações tokenizadas (NVDAB, TSLAB, MUB...): horário de bolsa, não é cripto
            continue
        alavancado = any(b.endswith(suf) and f"{b[:-len(suf)]}USDT" in simbolos for suf in ("UP", "DOWN", "BULL", "BEAR"))
        if alavancado or volume.get(s["symbol"], 0.0) < minimo:
            continue
        saida.append(s["symbol"])
    for m in T.MOEDAS_ROBO:
        if m not in saida:
            saida.append(m)
    saida.sort(key=lambda m: -volume.get(m, 0.0))
    _cache.update(t=time.time(), moedas=saida)
    return saida


if __name__ == "__main__":
    ms = moedas()
    print(len(ms), "moedas:", " ".join(m[:-4] for m in ms))
