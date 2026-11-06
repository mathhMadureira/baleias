"""Cliente mínimo da Binance spot: preços públicos, conta e ordem a mercado. Recusa chave que permita saque."""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BINANCE_BASE", "https://api.binance.com")


def assinar(segredo: str, consulta: str) -> str:
    return hmac.new(segredo.encode(), consulta.encode(), hashlib.sha256).hexdigest()


class Binance:
    def __init__(self, chave=None, segredo=None, abrir=urllib.request.urlopen):
        self.chave = chave or os.environ.get("BINANCE_API_KEY", "")
        self.segredo = segredo or os.environ.get("BINANCE_API_SECRET", "")
        self.abrir = abrir

    def _pedir(self, metodo, caminho, params=None, assinado=False):
        params = dict(params or {})
        cabecalho = {}
        if assinado:
            if not self.chave or not self.segredo:
                raise RuntimeError("faltam BINANCE_API_KEY e BINANCE_API_SECRET no .env")
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            consulta = urllib.parse.urlencode(params)
            consulta += "&signature=" + assinar(self.segredo, consulta)
            cabecalho["X-MBX-APIKEY"] = self.chave
        else:
            consulta = urllib.parse.urlencode(params)
        url = f"{BASE}{caminho}" + (f"?{consulta}" if consulta else "")
        pedido = urllib.request.Request(url, method=metodo, headers=cabecalho)
        try:
            with self.abrir(pedido, timeout=15) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # A mensagem da Binance não contém a chave nem o segredo.
            raise RuntimeError(f"Binance {e.code}: {e.read()[:300]!r}") from None

    def livro(self, simbolo="BTCUSDT"):
        d = self._pedir("GET", "/api/v3/ticker/bookTicker", {"symbol": simbolo})
        return float(d["bidPrice"]), float(d["askPrice"])

    def restricoes(self):
        return self._pedir("GET", "/sapi/v1/account/apiRestrictions", assinado=True)

    def saldo(self, ativo):
        for b in self._pedir("GET", "/api/v3/account", assinado=True)["balances"]:
            if b["asset"] == ativo:
                return float(b["free"])
        return 0.0

    def taxa(self, simbolo="BTCUSDT"):
        d = self._pedir("GET", "/sapi/v1/asset/tradeFee", {"symbol": simbolo}, assinado=True)
        return float(d[0]["takerCommission"])

    def comprar_em_usdt(self, simbolo, usdt):
        return self._pedir("POST", "/api/v3/order", {"symbol": simbolo, "side": "BUY", "type": "MARKET", "quoteOrderQty": f"{usdt:.2f}"}, assinado=True)

    def vender_quantidade(self, simbolo, qtd):
        return self._pedir("POST", "/api/v3/order", {"symbol": simbolo, "side": "SELL", "type": "MARKET", "quantity": f"{qtd:.5f}"}, assinado=True)


def verificar_chave(cliente):
    """Só aceita chave sem saque. Devolve a lista de problemas (vazia = ok)."""
    r = cliente.restricoes()
    problemas = []
    if r.get("enableWithdrawals"):
        problemas.append("a chave permite SAQUE: crie outra sem essa permissão")
    if not r.get("enableSpotAndMarginTrading"):
        problemas.append("a chave não permite operar spot")
    if not r.get("ipRestrict"):
        problemas.append("a chave não está travada por IP (recomendado travar no IP desta máquina)")
    return problemas
