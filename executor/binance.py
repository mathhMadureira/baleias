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


    def precos(self, simbolos):
        d = self._pedir("GET", "/api/v3/ticker/price", {"symbols": json.dumps(list(simbolos), separators=(",", ":"))})
        return {x["symbol"]: float(x["price"]) for x in d}

    def regras(self, simbolo):
        """Filtros da corretora: passo de quantidade, passo de preço e nocional mínimo."""
        cache = self.__dict__.setdefault("_regras", {})
        if simbolo not in cache:
            info = self._pedir("GET", "/api/v3/exchangeInfo", {"symbol": simbolo})["symbols"][0]
            f = {x["filterType"]: x for x in info["filters"]}
            cache[simbolo] = {"passo_qtd": float(f["LOT_SIZE"]["stepSize"]), "passo_preco": float(f["PRICE_FILTER"]["tickSize"]),
                              "minimo": float((f.get("NOTIONAL") or f.get("MIN_NOTIONAL") or {}).get("minNotional", 5))}
        return cache[simbolo]

    def comprar_mercado(self, simbolo, usdt):
        """Compra a mercado; devolve (quantidade líquida de taxa, preço médio, USDT gasto)."""
        r = self.comprar_em_usdt(simbolo, usdt)
        base = simbolo[:-4]
        taxa_base = sum(float(f["commission"]) for f in r.get("fills", []) if f.get("commissionAsset") == base)
        qtd = float(r["executedQty"]) - taxa_base
        gasto = float(r["cummulativeQuoteQty"])
        return arredondar(qtd, self.regras(simbolo)["passo_qtd"]), gasto / float(r["executedQty"]), gasto

    def vender_mercado(self, simbolo, qtd):
        qtd = arredondar(qtd, self.regras(simbolo)["passo_qtd"])
        r = self._pedir("POST", "/api/v3/order", {"symbol": simbolo, "side": "SELL", "type": "MARKET", "quantity": formatar(qtd)}, assinado=True)
        recebido = float(r["cummulativeQuoteQty"])
        return recebido / float(r["executedQty"]), recebido

    def colocar_stop(self, simbolo, qtd, stop, folga=0.005):
        """Stop guardado na corretora (STOP_LOSS_LIMIT): dispara em `stop` e vende até `folga` abaixo. Funciona com a máquina desligada."""
        rg = self.regras(simbolo)
        qtd = arredondar(qtd, rg["passo_qtd"])
        r = self._pedir("POST", "/api/v3/order", {"symbol": simbolo, "side": "SELL", "type": "STOP_LOSS_LIMIT", "timeInForce": "GTC",
                                                  "quantity": formatar(qtd), "stopPrice": formatar(arredondar(stop, rg["passo_preco"])),
                                                  "price": formatar(arredondar(stop * (1 - folga), rg["passo_preco"]))}, assinado=True)
        return r["orderId"]

    def cancelar(self, simbolo, ordem):
        return self._pedir("DELETE", "/api/v3/order", {"symbol": simbolo, "orderId": ordem}, assinado=True)

    def consultar(self, simbolo, ordem):
        r = self._pedir("GET", "/api/v3/order", {"symbol": simbolo, "orderId": ordem}, assinado=True)
        executado = float(r["executedQty"])
        return r["status"], (float(r["cummulativeQuoteQty"]) / executado if executado else None)


def arredondar(x, passo):
    """Para baixo, no múltiplo do passo (a corretora recusa casas a mais)."""
    from decimal import Decimal, ROUND_DOWN
    p = Decimal(str(passo)).normalize()
    return float((Decimal(str(x)) / p).to_integral_value(rounding=ROUND_DOWN) * p)


def formatar(x):
    return f"{x:.10f}".rstrip("0").rstrip(".")


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
