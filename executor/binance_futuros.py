"""Binance USDⓈ-M Futures (testnet por padrão), só biblioteca padrão: ordens limitadas "só maker" (GTX), a mercado, cancelar,
posições, saldo e os limites de cada moeda. A chave fica no .env (BINANCE_TESTNET_API_KEY/SECRET), nunca no código.

Uso: f = Futuros.do_env(); f.saldo_usdt(); f.ordem_limit("BTCUSDT", "BUY", 0.002, 70000)
Para a conta real: BINANCE_FUT_BASE=https://fapi.binance.com e as chaves BINANCE_API_KEY/SECRET — só com BINANCE_REAL=1.
"""
import hashlib
import hmac
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"
TESTNET = "https://testnet.binancefuture.com"


class ErroFuturos(Exception):
    pass


class Futuros:
    def __init__(self, chave, segredo, base=TESTNET):
        self.chave, self.segredo, self.base = chave, segredo, base.rstrip("/")
        self.desvio_ms = 0
        self._regras = {}
        self.sincronizar()

    @classmethod
    def do_env(cls, real=False):
        env = dict(l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l) if ENV.exists() else {}
        if real:
            if os.environ.get("BINANCE_REAL") != "1":
                raise ErroFuturos("conta real só com BINANCE_REAL=1")
            return cls(env["BINANCE_API_KEY"], env["BINANCE_API_SECRET"], os.environ.get("BINANCE_FUT_BASE", "https://fapi.binance.com"))
        return cls(env["BINANCE_TESTNET_API_KEY"], env["BINANCE_TESTNET_API_SECRET"], os.environ.get("BINANCE_FUT_BASE", TESTNET))

    # ---------- transporte ----------
    def _pedir(self, metodo, caminho, params=None, assinado=False, _tentativa=0):
        params = dict(params or {})
        if assinado:
            params["timestamp"] = int(time.time() * 1000) + self.desvio_ms
            params["recvWindow"] = 10000
            q = urllib.parse.urlencode(params)
            params["signature"] = hmac.new(self.segredo.encode(), q.encode(), hashlib.sha256).hexdigest()
        q = urllib.parse.urlencode(params)
        url = f"{self.base}{caminho}" + (f"?{q}" if q and metodo == "GET" else "")
        dados = q.encode() if metodo != "GET" else None
        req = urllib.request.Request(url, data=dados, method=metodo, headers={"X-MBX-APIKEY": self.chave, "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode(errors="replace")[:300]
            if '"code":-1021' in corpo and _tentativa == 0:   # relógio fora da janela: ressincroniza e tenta uma vez
                self.sincronizar()
                limpos = {k: v for k, v in params.items() if k not in ("signature", "timestamp", "recvWindow")}
                return self._pedir(metodo, caminho, limpos, assinado, _tentativa=1)
            raise ErroFuturos(f"{e.code} {corpo}") from None

    def sincronizar(self):
        with urllib.request.urlopen(f"{self.base}/fapi/v1/time", timeout=15) as r:
            self.desvio_ms = json.load(r)["serverTime"] - int(time.time() * 1000)

    # ---------- leitura ----------
    def saldo_usdt(self):
        for b in self._pedir("GET", "/fapi/v2/balance", assinado=True):
            if b["asset"] == "USDT":
                return float(b["availableBalance"]), float(b["balance"])
        return 0.0, 0.0

    def posicoes(self):
        """{symbol: quantidade com sinal (negativa = vendido)} só das posições abertas."""
        return {p["symbol"]: float(p["positionAmt"]) for p in self._pedir("GET", "/fapi/v2/positionRisk", assinado=True) if float(p["positionAmt"]) != 0}

    def livro(self, symbol):
        d = self._pedir("GET", "/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        return float(d["bidPrice"]), float(d["askPrice"])

    def regras(self, symbol):
        """Limites da moeda: passo de quantidade, passo de preço, nocional mínimo."""
        if not self._regras:
            for s in self._pedir("GET", "/fapi/v1/exchangeInfo")["symbols"]:
                f = {x["filterType"]: x for x in s["filters"]}
                self._regras[s["symbol"]] = {"step": float(f["LOT_SIZE"]["stepSize"]), "min_qtd": float(f["LOT_SIZE"]["minQty"]),
                                             "tick": float(f["PRICE_FILTER"]["tickSize"]), "min_nocional": float(f.get("MIN_NOTIONAL", {}).get("notional", 5))}
        return self._regras[symbol]

    def quantidade(self, symbol, nocional_usd, preco):
        """Quantidade válida para um nocional em US$ AO PREÇO DA ORDEM (a corretora confere o mínimo pelo preço da ordem, não pelo de mercado)."""
        r = self.regras(symbol)
        q = max(nocional_usd, r["min_nocional"]) / preco
        q = math.ceil(q / r["step"]) * r["step"]
        casas = max(0, -int(math.floor(math.log10(r["step"]))))
        return round(max(q, r["min_qtd"]), casas)

    def preco_redondo(self, symbol, preco, lado):
        """Preço no passo da moeda: compra arredonda para baixo, venda para cima (nunca cruza o livro por arredondamento)."""
        tick = self.regras(symbol)["tick"]
        n = preco / tick
        n = math.floor(n) if lado == "BUY" else math.ceil(n)
        casas = max(0, -int(math.floor(math.log10(tick))))
        return round(n * tick, casas)

    # ---------- ordens ----------
    def alavancagem(self, symbol, x):
        return self._pedir("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": int(x)}, assinado=True)

    def ordem_limit(self, symbol, lado, qtd, preco, so_maker=True, reduce_only=False):
        """Ordem limitada. so_maker=True (GTX): se fosse executar na hora como tomador, a corretora a rejeita/expira."""
        p = {"symbol": symbol, "side": lado, "type": "LIMIT", "quantity": qtd, "price": preco, "timeInForce": "GTX" if so_maker else "GTC"}
        if reduce_only:
            p["reduceOnly"] = "true"
        return self._pedir("POST", "/fapi/v1/order", p, assinado=True)

    def ordem_mercado(self, symbol, lado, qtd, reduce_only=False):
        p = {"symbol": symbol, "side": lado, "type": "MARKET", "quantity": qtd}
        if reduce_only:
            p["reduceOnly"] = "true"
        return self._pedir("POST", "/fapi/v1/order", p, assinado=True)

    def consultar(self, symbol, order_id):
        d = self._pedir("GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, assinado=True)
        return {"status": d["status"], "executada": float(d["executedQty"]), "preco_medio": float(d["avgPrice"] or 0)}

    def cancelar(self, symbol, order_id):
        return self._pedir("DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, assinado=True)

    def cancelar_todas(self, symbol):
        return self._pedir("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol}, assinado=True)
