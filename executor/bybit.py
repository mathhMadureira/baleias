"""Cliente mínimo da Bybit (API V5, spot, conta unificada) com a mesma interface do cliente da Binance usado pelo robô.

Assinatura: HMAC-SHA256(segredo, timestamp + chave + recv_window + (query do GET | corpo JSON do POST)).
Stop: ordem condicional de venda a mercado (orderFilter=StopOrder) guardada na Bybit — executa com a máquina desligada.
Recusa chave com permissão de saque.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .binance import arredondar, formatar

BASE = os.environ.get("BYBIT_BASE", "https://api.bybit.com")
RECV = "5000"


def assinar(segredo, ts, chave, carga):
    return hmac.new(segredo.encode(), f"{ts}{chave}{RECV}{carga}".encode(), hashlib.sha256).hexdigest()


class Bybit:
    nome = "Bybit"

    def __init__(self, chave=None, segredo=None, abrir=urllib.request.urlopen):
        self.chave = chave or os.environ.get("BYBIT_API_KEY", "")
        self.segredo = segredo or os.environ.get("BYBIT_API_SECRET", "")
        self.abrir = abrir
        self._regras = {}

    def _pedir(self, metodo, caminho, params=None, assinado=False):
        params = dict(params or {})
        cab = {"Content-Type": "application/json"}
        if metodo == "GET":
            carga = urllib.parse.urlencode(params)
            url, corpo = f"{BASE}{caminho}" + (f"?{carga}" if carga else ""), None
        else:
            carga = json.dumps(params, separators=(",", ":"))
            url, corpo = f"{BASE}{caminho}", carga.encode()
        if assinado:
            if not self.chave or not self.segredo:
                raise RuntimeError("faltam BYBIT_API_KEY e BYBIT_API_SECRET no .env")
            ts = str(int(time.time() * 1000))
            cab.update({"X-BAPI-API-KEY": self.chave, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": RECV,
                        "X-BAPI-SIGN": assinar(self.segredo, ts, self.chave, carga)})
        pedido = urllib.request.Request(url, data=corpo, method=metodo, headers=cab)
        try:
            with self.abrir(pedido, timeout=15) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Bybit HTTP {e.code}: {e.read()[:300]!r}") from None
        if d.get("retCode") != 0:
            # A mensagem da Bybit não contém a chave nem o segredo.
            raise RuntimeError(f"Bybit {d.get('retCode')}: {d.get('retMsg')}")
        return d["result"]

    # ---- público ----
    def precos(self, simbolos):
        lista = self._pedir("GET", "/v5/market/tickers", {"category": "spot"})["list"]
        quero = set(simbolos)
        return {x["symbol"]: float(x["lastPrice"]) for x in lista if x["symbol"] in quero}

    def regras(self, simbolo):
        if simbolo not in self._regras:
            x = self._pedir("GET", "/v5/market/instruments-info", {"category": "spot", "symbol": simbolo})["list"][0]
            self._regras[simbolo] = {"passo_qtd": float(x["lotSizeFilter"]["basePrecision"]), "passo_preco": float(x["priceFilter"]["tickSize"]),
                                     "minimo": float(x["lotSizeFilter"].get("minOrderAmt", 5)), "negocia": x["status"] == "Trading"}
        return self._regras[simbolo]

    def negociaveis(self):
        lista = self._pedir("GET", "/v5/market/instruments-info", {"category": "spot", "limit": 1000})["list"]
        return {x["symbol"] for x in lista if x["status"] == "Trading"}

    # ---- conta ----
    def restricoes(self):
        return self._pedir("GET", "/v5/user/query-api", assinado=True)

    def saldo(self, ativo):
        r = self._pedir("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": ativo}, assinado=True)
        for conta in r["list"]:
            for c in conta.get("coin", []):
                if c["coin"] == ativo:
                    return float(c.get("walletBalance") or 0) - float(c.get("locked") or 0)
        return 0.0

    def _ordem(self, simbolo, ordem, filtro=None):
        p = {"category": "spot", "symbol": simbolo, "orderId": ordem}
        if filtro:
            p["orderFilter"] = filtro
        for caminho in ("/v5/order/realtime", "/v5/order/history"):
            lista = self._pedir("GET", caminho, p, assinado=True)["list"]
            if lista:
                return lista[0]
        return None

    def comprar_mercado(self, simbolo, usdt):
        """Compra a mercado em USDT; devolve (quantidade líquida da taxa, preço médio, USDT gasto)."""
        r = self._pedir("POST", "/v5/order/create", {"category": "spot", "symbol": simbolo, "side": "Buy", "orderType": "Market",
                                                     "qty": f"{usdt:.2f}", "marketUnit": "quoteCoin"}, assinado=True)
        o = None
        for _ in range(10):
            o = self._ordem(simbolo, r["orderId"])
            if o and o["orderStatus"] in ("Filled", "PartiallyFilledCanceled", "Cancelled"):
                break
            time.sleep(0.5)
        qtd, gasto = float(o["cumExecQty"]), float(o["cumExecValue"])
        if qtd <= 0:
            raise RuntimeError(f"compra de {simbolo} não executou (status {o['orderStatus']})")
        taxa = float(o.get("cumExecFee") or 0)            # na compra spot a Bybit cobra a taxa na moeda comprada
        return arredondar(qtd - taxa, self.regras(simbolo)["passo_qtd"]), gasto / qtd, gasto

    def vender_mercado(self, simbolo, qtd):
        qtd = arredondar(qtd, self.regras(simbolo)["passo_qtd"])
        r = self._pedir("POST", "/v5/order/create", {"category": "spot", "symbol": simbolo, "side": "Sell", "orderType": "Market",
                                                     "qty": formatar(qtd)}, assinado=True)
        o = None
        for _ in range(10):
            o = self._ordem(simbolo, r["orderId"])
            if o and o["orderStatus"] in ("Filled", "PartiallyFilledCanceled", "Cancelled"):
                break
            time.sleep(0.5)
        exec_qtd, valor = float(o["cumExecQty"]), float(o["cumExecValue"])
        taxa = float(o.get("cumExecFee") or 0)            # na venda a taxa sai em USDT
        return (valor / exec_qtd if exec_qtd else 0.0), valor - taxa

    def colocar_stop(self, simbolo, qtd, stop):
        rg = self.regras(simbolo)
        r = self._pedir("POST", "/v5/order/create", {"category": "spot", "symbol": simbolo, "side": "Sell", "orderType": "Market",
                                                     "qty": formatar(arredondar(qtd, rg["passo_qtd"])),
                                                     "triggerPrice": formatar(arredondar(stop, rg["passo_preco"])),
                                                     "orderFilter": "StopOrder"}, assinado=True)
        return r["orderId"]

    def cancelar(self, simbolo, ordem):
        return self._pedir("POST", "/v5/order/cancel", {"category": "spot", "symbol": simbolo, "orderId": ordem, "orderFilter": "StopOrder"},
                           assinado=True)

    def consultar(self, simbolo, ordem):
        """Mesmo formato da Binance: ('FILLED', preço médio) quando o stop executou."""
        o = self._ordem(simbolo, ordem, "StopOrder") or self._ordem(simbolo, ordem)
        if not o:
            return "DESCONHECIDO", None
        qtd = float(o.get("cumExecQty") or 0)
        status = "FILLED" if o["orderStatus"] == "Filled" else o["orderStatus"].upper()
        return status, (float(o["cumExecValue"]) / qtd if qtd else None)


def verificar_chave(cliente):
    """Só aceita chave sem saque. Devolve a lista de problemas (vazia = ok)."""
    r = cliente.restricoes()
    problemas = []
    perm = json.dumps(r.get("permissions", {}))
    if "Withdraw" in perm:
        problemas.append("a chave permite SAQUE: crie outra sem essa permissão")
    if "SpotTrade" not in perm:
        problemas.append("a chave não permite operar spot (marque Spot → Trade)")
    if str(r.get("readOnly")) == "1":
        problemas.append("a chave não permite operar: está como somente leitura")
    if not r.get("ips") or r.get("ips") == ["*"]:
        problemas.append("a chave não está travada por IP (recomendado travar no IP desta máquina)")
    return problemas
