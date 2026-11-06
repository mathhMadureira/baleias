"""Séries diárias de fechamento: Binance (cripto) e Yahoo (fundos americanos). Cache em dados/lab/."""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from baleias import config

CACHE = config.RAIZ / "lab"


def _baixar_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "baleias-lab"}), timeout=60) as r:
        return json.load(r)


def binance(simbolo):
    """{dia ISO: fechamento} desde a listagem."""
    t, serie = 1_500_000_000_000, {}
    while True:
        lote = _baixar_json(f"https://api.binance.com/api/v3/klines?symbol={simbolo}&interval=1d&startTime={t}&limit=1000")
        if not lote:
            break
        for k in lote:
            serie[datetime.fromtimestamp(k[0] / 1000, timezone.utc).date().isoformat()] = float(k[4])
        if len(lote) < 1000:
            break
        t = lote[-1][0] + 86_400_000
        time.sleep(0.2)
    return serie


def yahoo(ticker):
    d = _baixar_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1=1167609600&period2={int(time.time())}&interval=1d&events=div")
    r = d["chart"]["result"][0]
    fech = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    return {datetime.fromtimestamp(t, timezone.utc).date().isoformat(): c for t, c in zip(r["timestamp"], fech) if c}


def carregar(universo, ativos, baixar):
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / f"{universo}.json"
    if arq.exists():
        return json.loads(arq.read_text())
    dados = {}
    for a in ativos:
        try:
            dados[a] = baixar(a)
            print(f"  {a}: {len(dados[a])} dias", flush=True)
        except Exception as e:
            print(f"  {a}: falhou ({type(e).__name__})", flush=True)
    arq.write_text(json.dumps(dados))
    return dados
