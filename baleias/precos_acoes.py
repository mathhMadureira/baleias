"""Preços diários de ações americanas pelo Yahoo Finance. Fonte NÃO oficial: pode mudar ou parar sem aviso."""
import json
import time
import urllib.request
from datetime import date, datetime, timezone


class Cliente:
    def __init__(self, abrir=urllib.request.urlopen, intervalo=0.5):
        self.abrir, self.intervalo, self.ultimo, self.cache = abrir, intervalo, 0.0, {}

    def diario(self, ticker, inicio: date, fim: date):
        """Lista de (dia ISO, abertura, fechamento), em ordem, sem dias faltando valor. None se o ticker não existir."""
        chave = (ticker, inicio, fim)
        if chave in self.cache:
            return self.cache[chave]
        espera = self.ultimo + self.intervalo - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        self.ultimo = time.monotonic()
        p1 = int(datetime(inicio.year, inicio.month, inicio.day, tzinfo=timezone.utc).timestamp())
        p2 = int(datetime(fim.year, fim.month, fim.day, tzinfo=timezone.utc).timestamp()) + 86400
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={p1}&period2={p2}&interval=1d"
        try:
            with self.abrir(urllib.request.Request(url, headers={"User-Agent": "baleias-monitor"}), timeout=30) as r:
                d = json.load(r)["chart"]["result"][0]
        except (OSError, KeyError, IndexError, TypeError, ValueError):
            self.cache[chave] = None
            return None
        q = d["indicators"]["quote"][0]
        tz = d.get("meta", {}).get("gmtoffset", 0)
        serie = [(datetime.fromtimestamp(t + tz, timezone.utc).date().isoformat(), o, c)
                 for t, o, c in zip(d.get("timestamp") or [], q.get("open") or [], q.get("close") or []) if o and c]
        self.cache[chave] = serie
        return serie
