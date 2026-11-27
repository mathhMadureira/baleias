"""Conta de demonstração de cada operador (H71, lab/PROTOCOLO_LAB.md): executa a decisão do agente com ordens reais numa corretora de TESTE.

Uso (sempre com python3 -I, no fim da rotina de operar, depois do `operar.py gravar`):
  python3 -I corretora.py <agente>            → uma rodada: concilia a conta, stop móvel, prazos, segue a decisão, grava dados/corretora_<agente>.json
  python3 -I corretora.py <agente> --conta    → só mostra saldo, posições e gatilhos (não muda nada)
  python3 -I corretora.py <agente> --validar  → só leitura (saldo e regras de um contrato): é o teste antes de destravar uma corretora
Mapa (H71): laboratorio → Gate Futures TestNet · treinador → Bybit Demo Trading · guardiao → BingX VST. Dinheiro fictício; nunca dinheiro real.
Segurança: cada corretora fala SÓ com o endereço de demonstração dela e PARA em qualquer outro; a chave vem do cofre do OpenBot e nunca é impressa
nem gravada; duas rodadas da mesma conta nunca ao mesmo tempo (trava de arquivo). Regras de stop, alvo e prazo: REGRAS.md §5 (as da execução).
"""
import fcntl
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, "/home/servidor-de-producao/baleias")
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
from executor.robo_claude_nuvem import parametros, tamanho  # noqa: E402
from executor.stop_movel import GUARDA, armar_em  # noqa: E402

COFRE = Path("/home/servidor-de-producao/.config/OpenBot/agent-api-keys/.vault/agent-85eaa35b-7f9b-407c-839d-fed207b6b72d")
PASTA = AQUI / "corretoras"
REDE_RUIM = ("timeout", "HTTPError", "URLError", "109500", "não consegui", "recusou o stop", "Connection")
REDE_CALMA_S = 300                       # 27/11: com a API instável, cada abre-e-fecha forçado custa taxa e deslizamento
GARANTIA_ARMA, GARANTIA_PCT, MOVEL_ARMA_MAX = 0.02, 0.0015, 0.035   # 27/11 (H83, "menos e maiores"): antes 0,8% e 1,5% cortavam a tendência no começo   # 26/11 (dono): com 20×, +1% no preço ≈ +6% da carteira; garantia a +0,8%, móvel até +1,5%   # dono (25/11): posição que passou de +2% não volta a ser perda (stop = entrada + 0,15% de taxas)
CAPITAL, PISO, MAX_POS, MAX_NOC, VALIDADE_S, MAX_HORAS = 10.0, 5.0, 8, 1.5, 75 * 60, 24   # R2: 8 posições
TRAILER = "Co-authored-by: OpenBot <335604065+openbotgit[bot]@users.noreply.github.com>"


class ErroCorretora(Exception):
    pass


def faltam(pos):
    """REGRAS §5 (R2): entrada nova só com stop_pct escrito na decisão (nada de stop padrão); alvo e prazo são opcionais."""
    return [k for k in ("stop_pct",) if not isinstance((pos or {}).get(k), (int, float))]


def saidas_desde(e, d):
    """20/11: moedas que saíram (stop, alvo, prazo) depois da LEITURA em que a decisão se baseou não reentram até uma decisão nova.
    (1ª versão comparava com a hora da publicação: o stop de NEAR executou às 14:21:26, entre a leitura das 14:20 e a decisão das 14:23:35, e a moeda
    reabriu.) Sem leitura_t na decisão, vale a decisão − 15 min. A inversão de lado pedida pela decisão não bloqueia."""
    d = d if isinstance(d, dict) else {"t": d}
    corte = float(d.get("leitura_t") or float(d.get("t") or 0) - 900)
    return {f.get("moeda") for f in e.get("fechadas") or [] if max(float(f.get("saida_t") or 0), float(f.get("registrada_t") or 0)) >= corte
            and "inverteu o lado" not in str(f.get("motivo_saida") or f.get("motivo") or "")}


def _chave(nome):
    return (COFRE / nome).read_text().strip()


# ======================= corretoras =======================
class Gate:
    """Gate Futures TestNet (APIv4, futuros USDT, modo de posição única). Assinatura HMAC-SHA512 de método\\ncaminho\\nquery\\nsha512(corpo)\\nts."""
    NOME, BASE, PRE, VALIDADO = "Gate Futures TestNet", "https://api-testnet.gateapi.io", "/api/v4", True

    def __init__(self, chave=None, segredo=None):
        self.chave = chave if chave is not None else _chave("GATE_TESTNET_API_KEY")
        self.segredo = segredo if segredo is not None else _chave("GATE_TESTNET_API_SECRET")
        self._contratos = {}

    def _pedir(self, metodo, caminho, query=None, corpo=None, assinado=True):
        q = urllib.parse.urlencode(query or {})
        b = json.dumps(corpo) if corpo is not None else ""
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if assinado:
            ts = str(int(time.time() + self.desvio_s()))                   # 20/11: relógio do servidor (o NTP desta máquina está desligado)
            texto = "\n".join([metodo, self.PRE + caminho, q, hashlib.sha512(b.encode()).hexdigest(), ts])
            h.update({"KEY": self.chave, "Timestamp": ts, "SIGN": hmac.new(self.segredo.encode(), texto.encode(), hashlib.sha512).hexdigest()})
        url = self.BASE + self.PRE + caminho + ("?" + q if q else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=b.encode() or None, headers=h, method=metodo), timeout=20) as r:
                txt = r.read()
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as ex:
            raise ErroCorretora(f"Gate {metodo} {caminho}: HTTP {ex.code} {ex.read()[:200].decode(errors='ignore')}") from None
        except (OSError, ValueError) as ex:
            raise ErroCorretora(f"Gate {metodo} {caminho}: {type(ex).__name__}") from None

    _desvio = None

    def desvio_s(self):
        if self._desvio is None:
            try:
                with urllib.request.urlopen(self.BASE + self.PRE + "/spot/time", timeout=15) as r:
                    self._desvio = json.load(r)["server_time"] / 1000 - time.time()
            except (OSError, ValueError, KeyError, TypeError):
                self._desvio = 0.0
        return self._desvio

    @staticmethod
    def simbolo(par):
        return par[:-4] + "_USDT"

    def saldo(self):
        a = self._pedir("GET", "/futures/usdt/accounts")
        return float(a["total"]), float(a["available"])

    def contrato(self, par):
        s = self.simbolo(par)
        if s not in self._contratos:
            try:
                c = self._pedir("GET", f"/futures/usdt/contracts/{s}", assinado=False)
            except ErroCorretora:
                c = None
            self._contratos[s] = None if not c or c.get("in_delisting") else {
                "mult": float(c["quanto_multiplier"]), "minimo": int(c["order_size_min"]), "tick": float(c["order_price_round"]),
                "alav_max": float(c["leverage_max"]), "preco": float(c.get("last_price") or c["mark_price"])}
        return self._contratos[s]

    def preco(self, par):
        self._contratos.pop(self.simbolo(par), None)
        c = self.contrato(par)
        if not c:
            raise ErroCorretora(f"{par}: não existe na Gate")
        return c["preco"]

    def alavancagem(self, par, n):
        self._pedir("POST", f"/futures/usdt/positions/{self.simbolo(par)}/leverage", query={"leverage": str(int(n))})

    def mercado(self, par, lado, contratos, reduzir=False):
        corpo = {"contract": self.simbolo(par), "size": int(contratos) * (1 if lado == "compra" else -1), "price": "0", "tif": "ioc", "text": "t-baleias"}
        if reduzir:
            corpo["reduce_only"] = True
        o = self._pedir("POST", "/futures/usdt/orders", corpo=corpo)
        feitos = abs(int(o.get("size", 0))) - abs(int(o.get("left", 0)))
        return {"id": str(o["id"]), "preco": float(o.get("fill_price") or 0), "contratos": feitos}

    def gatilho(self, par, lado_pos, contratos, preco, tipo):
        """Gatilho reduce-only que fecha a posição: tipo 'stop' (contra) ou 'alvo' (a favor). Preço pelo último negócio."""
        c = self.contrato(par)
        px = round(round(preco / c["tick"]) * c["tick"], 10)
        sobe = (tipo == "alvo") == (lado_pos == "compra")           # alvo da compra e stop da venda disparam com o preço subindo
        corpo = {"initial": {"contract": self.simbolo(par), "size": -int(contratos) if lado_pos == "compra" else int(contratos), "price": "0",
                             "tif": "ioc", "reduce_only": True, "text": "t-baleias"},
                 "trigger": {"strategy_type": 0, "price_type": 0, "price": f"{px:.10g}", "rule": 1 if sobe else 2, "expiration": 0}}
        o = self._pedir("POST", "/futures/usdt/price_orders", corpo=corpo)
        return {"id": str(o["id"]), "preco": px}

    def cancelar(self, id_, par=None):
        try:
            self._pedir("DELETE", f"/futures/usdt/price_orders/{id_}")
        except ErroCorretora:
            pass                                                        # já executou ou já foi cancelado: a conciliação confere

    def gatilhos_abertos(self):
        return {str(o["id"]): o["initial"]["contract"].replace("_USDT", "USDT") for o in self._pedir("GET", "/futures/usdt/price_orders", {"status": "open"})}

    def posicoes(self):
        out = {}
        for p in self._pedir("GET", "/futures/usdt/positions"):
            if int(p.get("size") or 0):
                out[p["contract"].replace("_USDT", "USDT")] = {"contratos": int(p["size"]), "entrada": float(p["entry_price"]),
                                                               "marca": float(p["mark_price"]), "pnl": float(p["unrealised_pnl"])}
        return out

    def execucoes(self, par, desde_ms):
        out = []
        for t in self._pedir("GET", "/futures/usdt/my_trades", {"contract": self.simbolo(par), "limit": 100}):
            if float(t["create_time"]) * 1000 >= desde_ms - 2000:
                out.append({"t_ms": float(t["create_time"]) * 1000, "contratos": int(t["size"]), "preco": float(t["price"]), "taxa": float(t.get("fee") or 0)})
        return out

    def velas_1m(self, par, desde_ms):
        k = self._pedir("GET", "/futures/usdt/candlesticks", {"contract": self.simbolo(par), "interval": "1m", "from": int(desde_ms // 1000),
                                                               "to": int(time.time())}, assinado=False)
        agora = time.time()
        return [(int(x["t"]) * 1000, float(x["h"]), float(x["l"])) for x in k if int(x["t"]) + 60 <= agora]


class Bybit:
    """Bybit Demo Trading (v5, linear, modo de posição única). Chave da Demo Trading trocada em 20/11 (leitura OK em api-demo.bybit.com).
    VALIDADO = "saldo": as ordens se liberam sozinhas quando o saldo de demonstração for > 0 (o dono põe o saldo fictício pela tela);
    com saldo 0 a ferramenta PARA sem enviar nada. Escrita pela documentação v5: a 1ª ordem real é a validação (stop recusado = fecha na hora)."""
    NOME, BASE, VALIDADO = "Bybit Demo Trading", "https://api-demo.bybit.com", "saldo"

    def __init__(self, chave=None, segredo=None):
        self.chave = chave if chave is not None else _chave("BYBIT_DEMO_API_KEY")
        self.segredo = segredo if segredo is not None else _chave("BYBIT_DEMO_API_SECRET")

    desvio_ms = None                                                     # relógio da Bybit − relógio daqui (como o desvio do testnet.py)

    def _relogio(self):
        if self.desvio_ms is None:
            try:
                with urllib.request.urlopen(f"{self.BASE}/v5/market/time", timeout=15) as r:
                    self.desvio_ms = int(json.load(r)["result"]["timeNano"]) // 1_000_000 - int(time.time() * 1000)
            except (OSError, ValueError, KeyError):
                self.desvio_ms = 0
        return int(time.time() * 1000) + self.desvio_ms

    def _pedir(self, metodo, caminho, params=None, assinado=True, _de_novo=True):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        ts, janela = str(self._relogio()), "20000"   # 20/11: "10002 ... server timestamp or recv_window" com a rede lenta daqui
        if metodo == "GET":
            q, corpo = urllib.parse.urlencode(params), b""
            carga = q
        else:
            q, corpo = "", json.dumps(params).encode()
            carga = corpo.decode()
        h = {"Content-Type": "application/json"}
        if assinado:
            h.update({"X-BAPI-API-KEY": self.chave, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": janela,
                      "X-BAPI-SIGN": hmac.new(self.segredo.encode(), (ts + self.chave + janela + carga).encode(), hashlib.sha256).hexdigest()})
        try:
            with urllib.request.urlopen(urllib.request.Request(self.BASE + caminho + ("?" + q if q else ""), data=corpo or None, headers=h,
                                                               method=metodo), timeout=20) as r:
                d = json.load(r)
        except (OSError, ValueError) as ex:
            raise ErroCorretora(f"Bybit {caminho}: {type(ex).__name__}") from None
        if d.get("retCode") == 10002 and _de_novo:                       # horário fora da janela: acerta o relógio e tenta uma vez de novo
            self.desvio_ms = None
            return self._pedir(metodo, caminho, params, assinado, _de_novo=False)
        if d.get("retCode") != 0:
            raise ErroCorretora(f"Bybit {caminho}: {d.get('retCode')} {str(d.get('retMsg'))[:150]}")
        return d.get("result") or {}

    def saldo(self):
        w = self._pedir("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})["list"][0]
        return float(w.get("totalEquity") or 0), float(w.get("totalAvailableBalance") or 0)

    def contrato(self, par):
        r = self._pedir("GET", "/v5/market/instruments-info", {"category": "linear", "symbol": par}, assinado=False).get("list") or []
        if not r or r[0].get("status") != "Trading":
            return None
        i = r[0]
        return {"mult": float(i["lotSizeFilter"]["qtyStep"]), "minimo": max(1, round(float(i["lotSizeFilter"]["minOrderQty"]) / float(i["lotSizeFilter"]["qtyStep"]))),
                "tick": float(i["priceFilter"]["tickSize"]), "alav_max": float(i["leverageFilter"]["maxLeverage"]), "preco": self.preco(par)}

    def preco(self, par):
        return float(self._pedir("GET", "/v5/market/tickers", {"category": "linear", "symbol": par}, assinado=False)["list"][0]["lastPrice"])

    def alavancagem(self, par, n):
        try:
            self._pedir("POST", "/v5/position/set-leverage", {"category": "linear", "symbol": par, "buyLeverage": str(n), "sellLeverage": str(n)})
        except ErroCorretora as ex:
            if "110043" not in str(ex):                                  # "leverage not modified" não é erro
                raise

    def _qtd(self, par, contratos):
        return f"{contratos * self.contrato(par)['mult']:.10g}"

    def mercado(self, par, lado, contratos, reduzir=False):
        o = self._pedir("POST", "/v5/order/create", {"category": "linear", "symbol": par, "side": "Buy" if lado == "compra" else "Sell",
                                                      "orderType": "Market", "qty": self._qtd(par, contratos), "reduceOnly": reduzir, "positionIdx": 0})
        h = {}
        for i in range(5):                                               # a execução pode demorar a aparecer no histórico
            time.sleep(1 + i)
            h = (self._pedir("GET", "/v5/order/history", {"category": "linear", "orderId": o["orderId"]}).get("list") or [{}])[0]
            if h.get("orderStatus") in ("Filled", "Cancelled", "Rejected", "PartiallyFilledCanceled") and float(h.get("cumExecQty") or 0) >= 0:
                break
        mult = self.contrato(par)["mult"]
        return {"id": o["orderId"], "preco": float(h.get("avgPrice") or 0), "contratos": round(float(h.get("cumExecQty") or 0) / mult)}

    def gatilho(self, par, lado_pos, contratos, preco, tipo):
        c = self.contrato(par)
        px = round(round(preco / c["tick"]) * c["tick"], 10)
        sobe = (tipo == "alvo") == (lado_pos == "compra")
        o = self._pedir("POST", "/v5/order/create", {"category": "linear", "symbol": par, "side": "Sell" if lado_pos == "compra" else "Buy",
                                                      "orderType": "Market", "qty": self._qtd(par, contratos), "reduceOnly": True, "positionIdx": 0,
                                                      "triggerPrice": f"{px:.10g}", "triggerDirection": 1 if sobe else 2, "triggerBy": "LastPrice"})
        return {"id": o["orderId"], "preco": px}

    def cancelar(self, id_, par=None):
        try:
            self._pedir("POST", "/v5/order/cancel", {"category": "linear", "symbol": par, "orderId": id_})
        except ErroCorretora:
            pass

    def gatilhos_abertos(self):
        return {o["orderId"]: o["symbol"] for o in self._pedir("GET", "/v5/order/realtime", {"category": "linear", "settleCoin": "USDT",
                                                                                              "orderFilter": "StopOrder"}).get("list") or []}

    def posicoes(self):
        out = {}
        for p in self._pedir("GET", "/v5/position/list", {"category": "linear", "settleCoin": "USDT"}).get("list") or []:
            q = float(p.get("size") or 0)
            if q:
                mult = self.contrato(p["symbol"])["mult"]
                out[p["symbol"]] = {"contratos": round(q / mult) * (1 if p["side"] == "Buy" else -1), "entrada": float(p["avgPrice"]),
                                    "marca": float(p["markPrice"]), "pnl": float(p.get("unrealisedPnl") or 0)}
        return out

    def execucoes(self, par, desde_ms):
        mult = self.contrato(par)["mult"]
        return [{"t_ms": float(x["execTime"]), "contratos": round(float(x["execQty"]) / mult) * (1 if x["side"] == "Buy" else -1),
                 "preco": float(x["execPrice"]), "taxa": float(x.get("execFee") or 0)}
                for x in self._pedir("GET", "/v5/execution/list", {"category": "linear", "symbol": par, "startTime": int(desde_ms - 2000)}).get("list") or []]

    def velas_1m(self, par, desde_ms):
        k = self._pedir("GET", "/v5/market/kline", {"category": "linear", "symbol": par, "interval": "1", "start": int(desde_ms), "limit": 1000},
                        assinado=False).get("list") or []
        agora = time.time() * 1000
        return sorted((int(x[0]), float(x[2]), float(x[3])) for x in k if int(x[0]) + 60_000 <= agora)


def _ms(v):
    """Hora em ms: aceita número (ms) ou texto ISO ('2026-11-23T22:30:44.000Z'), como a BingX VST manda em filledTm."""
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        from datetime import datetime
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000


def _foco_pode(corretora):
    """Chave central da equipe (mesa/foco.py → Shared/baleias/FOCO.json). Sem a chave ou com erro: NÃO abre (seguro)."""
    import importlib.util
    for arq in (Path(__file__).resolve().parent.parent / "foco.py", Path("/home/servidor-de-producao/OpenBot/Shared/baleias/foco.py")):
        if arq.exists():
            try:
                spec = importlib.util.spec_from_file_location("foco_equipe", arq)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                return m.pode_operar(corretora)
            except Exception as ex:                                    # chave quebrada: não abre
                return False, f"chave de foco com erro ({type(ex).__name__})"
    return False, "chave de foco (foco.py) não encontrada"


class BingX:
    """BingX VST (futuros perpétuos de demonstração, open-api-vst.bingx.com). TRAVADA (VALIDADO = False) até `--validar` passar
    (19/11: a chave recusou o IP desta máquina; a mesma chave vale na conta real, então o endereço é conferido antes de tudo)."""
    NOME, BASE, VALIDADO = "BingX VST", "https://open-api-vst.bingx.com", "saldo"   # 20/11: IP liberado e leitura OK (100.000 VST)

    def __init__(self, chave=None, segredo=None):
        self.chave = chave if chave is not None else _chave("BINGX_VST_API_KEY")
        self.segredo = segredo if segredo is not None else _chave("BINGX_VST_API_SECRET")

    @staticmethod
    def simbolo(par):
        return par[:-4] + "-USDT"

    desvio_ms = None                                                     # 20/11: relógio daqui 3,85 s atrás do da BingX ("109400 timestamp is invalid")

    def _relogio(self):
        if self.desvio_ms is None:
            try:
                with urllib.request.urlopen(f"{self.BASE}/openApi/swap/v2/server/time", timeout=15) as r:
                    self.desvio_ms = int(json.load(r)["data"]["serverTime"]) - int(time.time() * 1000)
            except (OSError, ValueError, KeyError, TypeError):
                self.desvio_ms = 0
        return int(time.time() * 1000) + self.desvio_ms

    def _pedir(self, metodo, caminho, params=None, assinado=True, _de_novo=True):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        if assinado:
            params["timestamp"] = str(self._relogio())
            params["recvWindow"] = "20000"
        q = "&".join(f"{k}={params[k]}" for k in sorted(params))
        if assinado:
            q += "&signature=" + hmac.new(self.segredo.encode(), q.encode(), hashlib.sha256).hexdigest()
        h = {"X-BX-APIKEY": self.chave} if assinado else {}
        for tentativa in range(3 if metodo == "GET" else 1):            # 23/11: rede instável até a VST; só leituras repetem (ordem nunca, para não dobrar)
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{self.BASE}{caminho}?{q}", headers=h, method=metodo), timeout=20) as r:
                    d = json.load(r)
                break
            except (OSError, ValueError) as ex:
                if tentativa == (2 if metodo == "GET" else 0):
                    raise ErroCorretora(f"BingX {caminho}: {type(ex).__name__}") from None
                time.sleep(1.5)
        if d.get("code") == 109400 and _de_novo and assinado:             # horário fora da janela: mede o relógio de novo e tenta uma vez
            self.desvio_ms = None
            return self._pedir(metodo, caminho, {k: v for k, v in params.items() if k not in ("timestamp", "recvWindow")}, assinado, _de_novo=False)
        if d.get("code") not in (0, None):
            raise ErroCorretora(f"BingX {caminho}: {d.get('code')} {str(d.get('msg'))[:150]}")
        return d.get("data")

    def saldo(self):
        b = self._pedir("GET", "/openApi/swap/v2/user/balance")["balance"]
        return float(b.get("equity") or 0), float(b.get("availableMargin") or 0)

    _contratos = None                                                    # 23/11: a lista é lida uma vez por rodada (TimeoutError repetido em /quote/contracts)

    def contrato(self, par):
        if self._contratos is None:
            self._contratos = self._pedir("GET", "/openApi/swap/v2/quote/contracts", assinado=False) or []
        for c in self._contratos:
            if c.get("symbol") == self.simbolo(par):
                passo = 10 ** -int(c.get("quantityPrecision", 0))
                return {"mult": passo, "minimo": max(1, round(float(c.get("tradeMinQuantity") or passo) / passo)),
                        "tick": 10 ** -int(c.get("pricePrecision", 2)), "alav_max": 20.0, "preco": self.preco(par)}
        return None

    def preco(self, par):
        return float(self._pedir("GET", "/openApi/swap/v2/quote/price", {"symbol": self.simbolo(par)}, assinado=False)["price"])

    def alavancagem(self, par, n):
        for lado in ("LONG", "SHORT"):
            self._pedir("POST", "/openApi/swap/v2/trade/leverage", {"symbol": self.simbolo(par), "side": lado, "leverage": int(n)})

    _hedge = None                                                        # 23/11: a VST estava em modo hedge e recusava positionSide BOTH (109400)

    def hedge(self):
        """True se a conta está em modo hedge (dualSidePosition). Hedge: positionSide LONG/SHORT e sem reduceOnly (a BingX recusa);
        a ordem de saída (lado oposto no mesmo positionSide) só reduz, nunca inverte. One-way: BOTH + reduceOnly."""
        if self._hedge is None:
            d = self._pedir("GET", "/openApi/swap/v1/positionSide/dual") or {}
            self._hedge = str(d.get("dualSidePosition")).lower() == "true"
        return self._hedge

    def _lado_pos(self, lado_pos, reduzir):
        if self.hedge():
            return {"positionSide": "LONG" if lado_pos == "compra" else "SHORT"}
        return {"positionSide": "BOTH", "reduceOnly": "true" if reduzir else None}

    def mercado(self, par, lado, contratos, reduzir=False):
        mult = self.contrato(par)["mult"]
        lado_pos = ("venda" if lado == "compra" else "compra") if reduzir else lado
        o = self._pedir("POST", "/openApi/swap/v2/trade/order", {"symbol": self.simbolo(par), "side": "BUY" if lado == "compra" else "SELL",
                                                                 "type": "MARKET", "quantity": f"{contratos * mult:.10g}",
                                                                 **self._lado_pos(lado_pos, reduzir)})["order"]
        return {"id": str(o["orderId"]), "preco": float(o.get("avgPrice") or 0), "contratos": round(float(o.get("executedQty") or 0) / mult)}

    def gatilho(self, par, lado_pos, contratos, preco, tipo):
        c = self.contrato(par)
        px = round(round(preco / c["tick"]) * c["tick"], 10)
        o = self._pedir("POST", "/openApi/swap/v2/trade/order", {"symbol": self.simbolo(par), "side": "SELL" if lado_pos == "compra" else "BUY",
                                                                 "type": "STOP_MARKET" if tipo == "stop" else "TAKE_PROFIT_MARKET",
                                                                 "quantity": f"{contratos * c['mult']:.10g}", "stopPrice": f"{px:.10g}",
                                                                 "workingType": "CONTRACT_PRICE", **self._lado_pos(lado_pos, True)})["order"]
        return {"id": str(o["orderId"]), "preco": px}

    def cancelar(self, id_, par=None):
        try:
            self._pedir("DELETE", "/openApi/swap/v2/trade/order", {"symbol": self.simbolo(par) if par else None, "orderId": id_})
        except ErroCorretora:
            pass

    def gatilhos_abertos(self):
        return {str(o["orderId"]): o["symbol"].replace("-USDT", "USDT") for o in (self._pedir("GET", "/openApi/swap/v2/trade/openOrders") or {}).get("orders", [])
                if o.get("type") in ("STOP_MARKET", "TAKE_PROFIT_MARKET")}

    def posicoes(self):
        out = {}
        for p in self._pedir("GET", "/openApi/swap/v2/user/positions") or []:
            q = float(p.get("positionAmt") or 0)
            if q:
                par = p["symbol"].replace("-USDT", "USDT")
                mult = self.contrato(par)["mult"]
                out[par] = {"contratos": round(abs(q) / mult) * (-1 if p.get("positionSide") == "SHORT" or q < 0 else 1),
                            "entrada": float(p["avgPrice"]), "marca": float(p.get("markPrice") or p["avgPrice"]), "pnl": float(p.get("unrealizedProfit") or 0)}
        return out

    def execucoes(self, par, desde_ms):
        mult = self.contrato(par)["mult"]
        d = self._pedir("GET", "/openApi/swap/v2/trade/allFillOrders", {"symbol": self.simbolo(par), "startTs": int(desde_ms - 2000),
                                                                        "endTs": int(time.time() * 1000)}) or {}
        # 27/11: a VST às vezes manda volume "0" (SOL ficou fantasma 10 min); aí a quantidade sai do valor em USDT ÷ preço
        qtd = lambda x: float(x.get("volume") or 0) or (float(x.get("amount") or 0) / float(x["price"]) if float(x.get("price") or 0) else 0)
        return [{"t_ms": _ms(x.get("filledTm") or x.get("time")), "contratos": round(qtd(x) / mult) * (1 if x["side"] == "BUY" else -1),
                 "preco": float(x["price"]), "taxa": abs(float(x.get("commission") or 0))} for x in d.get("fill_orders", [])]

    def velas_1m(self, par, desde_ms):
        k = self._pedir("GET", "/openApi/swap/v3/quote/klines", {"symbol": self.simbolo(par), "interval": "1m", "startTime": int(desde_ms), "limit": 1000},
                        assinado=False) or []
        agora = time.time() * 1000
        return [(int(x["time"]), float(x["high"]), float(x["low"])) for x in k if int(x["time"]) + 60_000 <= agora]


CONTAS = {"laboratorio": BingX, "treinador": Bybit, "guardiao": BingX}   # 24/11 (dono): carteira única de teste na BingX VST; só o Laboratório (operador) opera
ENDERECOS = {Gate: "https://api-testnet.gateapi.io", Bybit: "https://api-demo.bybit.com", BingX: "https://open-api-vst.bingx.com"}


def conectar(agente, permitir_travada=False):
    """A corretora de demonstração do agente. PARA se o endereço não for o de demonstração, se BINANCE_REAL estiver ligado ou se a corretora
    ainda não foi validada (só a validação de leitura pode usar uma travada)."""
    cls = CONTAS.get(agente)
    if not cls:
        raise SystemExit(f"PARE: {agente!r} não tem conta de demonstração (H71: laboratorio, treinador, guardiao). Nada foi feito.")
    if os.environ.get("BINANCE_REAL") == "1":
        raise SystemExit("PARE: BINANCE_REAL=1 está ligado. Esta ferramenta só opera contas de DEMONSTRAÇÃO. Nada foi feito.")
    if cls.BASE != ENDERECOS[cls]:
        raise SystemExit(f"PARE: o endereço de {cls.NOME} ({cls.BASE}) não é o de demonstração. Nada foi feito.")
    if not cls.VALIDADO and not permitir_travada:
        raise SystemExit(f"PARE: {cls.NOME} ainda não foi validada (rode --validar com a chave de demonstração; a ferramenta não envia ordem). Nada foi feito.")
    c = cls()
    if cls.VALIDADO == "saldo" and not permitir_travada:            # libera sozinha quando a conta de demonstração tiver saldo fictício
        try:
            total = c.saldo()[0]
        except (ErroCorretora, KeyError, IndexError, TypeError, ValueError) as ex:
            raise SystemExit(f"PARE: {cls.NOME}: não consegui ler o saldo de demonstração ({str(ex)[:120]}). Nada foi feito.") from None
        if total <= 0:
            raise SystemExit(f"PARE: {cls.NOME} ainda sem saldo de demonstração (0); o dono põe o saldo fictício pela tela. Nada foi feito.")
    return c


# ======================= motor (o mesmo para as três) =======================
class Conta:
    def __init__(self, agente, corretora, arquivo=None):
        self.agente, self.c = agente, corretora
        self.arq = Path(arquivo) if arquivo else PASTA / f"{agente}.json"
        self.e = self.carregar()

    def carregar(self):
        if self.arq.exists():
            try:
                return json.loads(self.arq.read_text())
            except ValueError:
                os.replace(self.arq, self.arq.with_name(f"{self.arq.name}.corrompido-{int(time.time())}"))
        return {"inicio": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "corretora": self.c.NOME, "capital_inicial": CAPITAL,
                "caixa": CAPITAL, "patrimonio": CAPITAL, "abertas": {}, "fechadas": [], "eventos": []}

    def salvar(self):
        self.arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.arq.with_suffix(".tmp")
        with open(tmp, "w") as f:
            f.write(json.dumps(self.e, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.arq)

    def anotar(self, texto):
        if texto.startswith(("🚨", "⚠")) and any(k in texto for k in REDE_RUIM):   # 27/11 (Engenheiro): rede instável → sem entrada nova
            self.e["rede_ruim_t"] = time.time()
        self.e["eventos"] = ([{"t": time.time(), "texto": texto}] + self.e.get("eventos", []))[:100]
        print(time.strftime("%H:%M:%S", time.gmtime()), "UTC", texto, flush=True)

    def realizado(self):
        return float(self.e["caixa"]) + sum(float(p["gasto"]) for p in self.e["abertas"].values())

    # ---- resultado pela corretora ----
    def registrar_fechada(self, par, motivo):
        p = self.e["abertas"][par]
        ex = self.c.execucoes(par, p["entrada_ms"])
        saidas = [x for x in ex if (x["contratos"] < 0) == (p["lado"] == "compra") and x["t_ms"] >= p["entrada_ms"] - 2000]
        if not saidas or sum(abs(x["contratos"]) for x in saidas) < p["contratos"]:
            raise ErroCorretora(f"{par}: a corretora ainda não mostra a saída inteira")
        mult = p["mult"]
        sinal = 1 if p["lado"] == "compra" else -1
        q_s = sum(abs(x["contratos"]) for x in saidas)
        saida = sum(abs(x["contratos"]) * x["preco"] for x in saidas) / q_s
        taxa_ent = p.get("taxa_entrada")
        if taxa_ent is None:                                               # não lida na entrada (rede): as execuções de entrada, desde a ordem
            taxa_ent = sum(x["taxa"] for x in ex if (x["contratos"] > 0) == (p["lado"] == "compra") and x["t_ms"] >= p["entrada_ms"])
        taxas = taxa_ent + sum(x["taxa"] for x in saidas)
        res = sinal * (saida - p["entrada"]) * p["contratos"] * mult - taxas
        self.e["caixa"] = float(self.e["caixa"]) + p["gasto"] + res
        for k in ("stop", "alvo"):
            self._cancelar(par, p.get(k))
        if motivo is None:
            perto = lambda a, b: abs(a / b - 1) < 0.003
            motivo = ("alvo na corretora" if p.get("alvo") and perto(saida, p["alvo"]["preco"]) else
                      f"stop {'móvel' if p.get('stop_tipo') == 'móvel' else 'de segurança'} na corretora")
        p["registrada_t"] = time.time()                                    # 25/11: hora em que o motor SOUBE da saída (máquina dormindo)
        self.e["fechadas"].append({**{k: v for k, v in p.items() if k not in ("stop", "alvo")}, "saida": saida, "saida_t": max(x["t_ms"] for x in saidas) / 1000,
                                   "motivo_saida": motivo, "resultado_usd": res, "taxas": taxas, "stop_final": (p.get("stop") or {}).get("preco")})
        self.e["fechadas"] = self.e["fechadas"][-2000:]
        del self.e["abertas"][par]
        self.anotar(f"{'✅' if res > 0 else '❌'} SAIU da {'COMPRA' if p['lado'] == 'compra' else 'VENDA'} em {par[:-4]} a {saida:.6g} ({motivo}): {res:+.4f} USDT")

    def _cancelar(self, par, st):
        if st:
            self.c.cancelar(st["id"], par)

    def fechar(self, par, motivo):
        p = self.e["abertas"][par]
        self._cancelar(par, p.get("stop"))
        self._cancelar(par, p.get("alvo"))
        q = self.c.posicoes().get(par, {}).get("contratos", 0)
        if q:
            self.c.mercado(par, "venda" if q > 0 else "compra", abs(q), reduzir=True)
        for _ in range(5):
            try:
                return self.registrar_fechada(par, motivo)
            except ErroCorretora:
                time.sleep(1.5)
        self.anotar(f"⚠️ {par}: fechei a mercado mas a corretora ainda não mostra a saída; confiro na próxima rodada")

    def abrir(self, par, lado, motivo, decisao_t, prm):
        pode, porque = _foco_pode({"Gate": "gate", "Bybit": "bybit", "BingX": "bingx"}.get(type(self.c).__name__, "?"))
        if not pode:
            return self.anotar(f"{par[:-4]}: {porque}; não entra")
        falta = faltam(prm)
        if falta:
            return self.anotar(f"{par[:-4]}: a decisão não traz {', '.join(falta)}; não entra (REGRAS §5)")
        pedido = {"noc": prm.get("nocional_usd"), "alav": prm.get("alav")}   # 25/11: o motor pode pedir tamanho e alavancagem
        plano = {k: prm[k] for k in ("plano_agente", "movel_arma", "movel_guarda", "ordem", "conf", "por") if prm.get(k) is not None}
        prm = parametros(prm)                                              # REGRAS.md §5: os valores que a execução aplica
        ctr = self.c.contrato(par)
        if not ctr:
            return self.anotar(f"{par[:-4]}: não existe em {self.c.NOME}; não entra (H71)")
        noc, alav = tamanho(self.realizado())
        noc *= 4 / MAX_POS                                                 # R2: até 8 posições, cada uma com metade (exposição total igual)
        if isinstance(pedido["noc"], (int, float)) and pedido["noc"] > 0 and isinstance(pedido["alav"], (int, float)):
            alav = int(max(1, min(50, pedido["alav"])))                   # dono (25/11): "nada de caçar centavos" — posições maiores
            noc = float(pedido["noc"])
        usada, recusa = None, ""
        for a in [x for x in (alav, 10, 5, 3, 2, 1) if x <= min(alav, ctr["alav_max"])]:
            try:
                self.c.alavancagem(par, a)
                usada = a
                break
            except ErroCorretora as ex_:
                recusa = str(ex_)[:80]
                continue
        if usada is None:
            return self.anotar(f"{par[:-4]}: a corretora recusou as alavancagens; não entra")
        if usada < alav and isinstance(pedido["noc"], (int, float)) and pedido["noc"] > 0:
            noc = noc * usada / alav                                      # 25/11: mesma margem, alavancagem menor
            self.anotar(f"{par[:-4]}: a corretora recusou {alav}× ({recusa}); entro a {usada}× com a mesma margem")
        elif usada < alav:
            noc = min(noc, self.realizado() * usada / MAX_POS)
        if float(self.e["caixa"]) < noc / usada - 1e-9:
            noc = float(self.e["caixa"]) * usada * 0.995
        px = self.c.preco(par)
        contratos = max(ctr["minimo"], int(noc / (px * ctr["mult"])))
        if contratos * px * ctr["mult"] > MAX_NOC * noc or noc <= 0:
            return self.anotar(f"{par[:-4]}: lote mínimo da corretora (US$ {contratos * px * ctr['mult']:.2f}) passa de {MAX_NOC} × a posição (US$ {noc:.2f}); não entra (H71)")
        t0 = time.time() * 1000
        o = self.c.mercado(par, lado, contratos)
        if o["contratos"] <= 0 or o["preco"] <= 0:
            return self.anotar(f"{par[:-4]}: ordem a mercado {o['id']} não executou")
        ent, q = o["preco"], o["contratos"]
        time.sleep(1)
        try:                                                               # auditoria 20/11: erro de rede aqui não pode deixar a posição fora do estado e sem stop
            taxa_ent = sum(x["taxa"] for x in self.c.execucoes(par, t0) if (x["contratos"] > 0) == (lado == "compra"))
        except Exception as ex_:                                           # 23/11: ValueError (filledTm em texto) deixou WLFI fora do estado e sem stop
            taxa_ent = None                                                # não é zero: registrar_fechada lê a taxa de entrada na saída
            self.anotar(f"⚠️ {par[:-4]}: taxa de entrada não lida agora ({str(ex_)[:80]}); leio na saída")
        gasto = q * ent * ctr["mult"] / usada
        self.e["caixa"] = float(self.e["caixa"]) - gasto
        self.e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": ent, "entrada_t": t0 / 1000, "entrada_ms": t0,
                                  "contratos": q, "mult": ctr["mult"], "nocional": q * ent * ctr["mult"], "gasto": gasto, "alav": usada, "motivo": str(motivo)[:300],
                                  "decisao_t": decisao_t, "entrada_id": o["id"], "pico": 0.0, "stop_tipo": "segurança",
                                  "taxa_entrada": taxa_ent, **prm, **plano}
        self.salvar()                                                      # a posição existe na corretora: fica no estado antes do próximo passo
        sp, ap = prm["stop_pct"], prm.get("alvo_pct")
        try:
            self.e["abertas"][par]["stop"] = self.c.gatilho(par, lado, q, ent * (1 - sp if lado == "compra" else 1 + sp), "stop")
        except Exception as ex_:                                           # qualquer falha aqui: nunca deixar a posição sem stop
            self.anotar(f"🚨 {par[:-4]}: a corretora recusou o stop ({str(ex_)[:160]}); fecho a posição agora (nunca sem stop)")
            return self.fechar(par, "stop recusado pela corretora: fechada na hora")
        if ap:
            try:
                self.e["abertas"][par]["alvo"] = self.c.gatilho(par, lado, q, ent * (1 + ap if lado == "compra" else 1 - ap), "alvo")
            except ErroCorretora as ex_:
                self.anotar(f"⚠️ {par[:-4]}: a corretora recusou o alvo ({str(ex_)[:120]}); fica só o stop")
        a = self.e["abertas"][par]
        self.anotar(f"ENTROU {'COMPRADO' if lado == 'compra' else 'VENDIDO'} em {par[:-4]}: {q} contrato(s) a {ent:.6g} (US$ {a['nocional']:.2f}, {usada}×, "
                    f"ordem {o['id']}); stop {a['stop']['preco']} (−{sp:.2%}, gatilho {a['stop']['id']})"
                    + (f"; alvo {a['alvo']['preco']} (+{ap:.2%}, gatilho {a['alvo']['id']})" if a.get("alvo") else "") + f"; prazo {prm.get('max_min')} min")

    # ---- rodada ----
    def conciliar(self):
        pos = self.c.posicoes()
        for par in list(self.e["abertas"]):
            if par not in pos:
                try:
                    self.registrar_fechada(par, None)                     # o stop ou o alvo executou enquanto ninguém olhava
                except ErroCorretora as ex:
                    self.anotar(f"⚠️ {par}: posição sumiu da conta e a saída ainda não aparece ({str(ex)[:80]})")
        vivos = self.c.gatilhos_abertos()
        # 27/11: primeiro repõe stops/alvos ausentes; só depois limpa o que sobrar.
        # Antes a ordem era inversa: o novo ID era gravado depois da varredura e
        # ficava "desconhecido" na rodada seguinte, sendo cancelado pela limpeza.
        for par, x in pos.items():
            if par not in self.e["abertas"]:
                self.c.mercado(par, "venda" if x["contratos"] > 0 else "compra", abs(x["contratos"]), reduzir=True)
                self.anotar(f"🧹 posição desconhecida fechada a mercado: {par} {x['contratos']:+d}")
        meus_ids = {p[k]["id"] for p in self.e["abertas"].values() for k in ("stop", "alvo") if p.get(k)}
        if meus_ids - set(vivos):                                # 27/11: rede instável devolve lista parcial → relê antes de repor
            try:                                                 # (antes: repunha, e o antigo voltava como "desconhecido")
                vivos = {**vivos, **self.c.gatilhos_abertos()}
            except ErroCorretora:
                pass
        for par, p in list(self.e["abertas"].items()):
            st = p.get("stop")
            if par in pos and (not st or st["id"] not in vivos):
                preco = st["preco"] if st else p["entrada"] * (1 - p["stop_pct"] if p["lado"] == "compra" else 1 + p["stop_pct"])
                try:
                    p["stop"] = self.c.gatilho(par, p["lado"], p["contratos"], preco, "stop")
                    self.anotar(f"🛡 {par[:-4]}: stop não estava na corretora; guardei de novo a {p['stop']['preco']}")
                except ErroCorretora as ex:
                    self.anotar(f"🚨 {par[:-4]}: sem stop e a corretora recusou ({str(ex)[:100]}); fecho")
                    self.fechar(par, "stop recusado pela corretora: fechada na hora")
                    continue
            al = p.get("alvo")
            if par in pos and p.get("alvo_pct") and (not al or al["id"] not in vivos):   # 25/11: o alvo sumido também volta
                preco = al["preco"] if al else p["entrada"] * (1 + p["alvo_pct"] if p["lado"] == "compra" else 1 - p["alvo_pct"])
                try:
                    p["alvo"] = self.c.gatilho(par, p["lado"], p["contratos"], preco, "alvo")
                    self.anotar(f"🎯 {par[:-4]}: alvo não estava na corretora; guardei de novo a {p['alvo']['preco']}")
                except ErroCorretora as ex:
                    self.anotar(f"⚠️ {par[:-4]}: alvo não voltou ({str(ex)[:100]}); fica só o stop")
        self.e["conciliado_t"] = time.time()
        # Agora "meus" já inclui os IDs recém-gravados → limpeza não os cancela
        meus = {p[k]["id"] for p in self.e["abertas"].values() for k in ("stop", "alvo") if p.get(k)}
        for id_, par in vivos.items():
            p_ = self.e["abertas"].get(par)
            if p_ and not ((p_.get("stop") or {}).get("id") in vivos):   # posição aberta sem stop conhecido: protege o único gatilho
                continue
            if id_ not in meus:
                self._cancelar(par, {"id": id_})
                self.anotar(f"🧹 gatilho desconhecido cancelado na conta: {par} ({id_})")

    def mover_stops(self):
        for par in list(self.e["abertas"]):
            p = self.e["abertas"][par]
            compra = p["lado"] == "compra"
            for t, h, l in self.c.velas_1m(par, max(p["entrada_ms"], p.get("movel_ate", 0))):
                p["pico"] = max(p.get("pico", 0.0), (h / p["entrada"] - 1) if compra else (1 - l / p["entrada"]))
                p["movel_ate"] = t + 60_000
            if p.get("plano_agente"):                                          # 27/11: plano do agente — sem garantia nem trava automáticas;
                arma, gar_arma, trava = float(p.get("movel_arma") or 99), 99, 0.0  # stop móvel só se o agente pediu (movel_arma)
                guarda = float(p.get("movel_guarda") or GUARDA)
            else:
                arma = min(armar_em(p.get("alvo_pct"), p.get("movel", True)), MOVEL_ARMA_MAX)
                gar_arma, guarda = GARANTIA_ARMA, GUARDA
                trava = float(p.get("trava") or 0)                             # trava da carteira (motor): guarda parte do lucro do conjunto
            if p["pico"] < arma and p["pico"] < gar_arma and not trava:
                continue
            g = guarda * p["pico"] if p["pico"] >= arma else (GARANTIA_PCT if p["pico"] >= gar_arma else 0.0)
            g = max(g, trava)
            if g <= 0:
                continue
            novo = p["entrada"] * (1 + g if compra else 1 - g)
            atual = (p.get("stop") or {}).get("preco")
            if atual is not None and ((novo <= atual) if compra else (novo >= atual)):
                continue
            px = self.c.preco(par)
            if (px <= novo) if compra else (px >= novo):
                self.fechar(par, f"stop móvel (pico +{p['pico']:.2%}, guardou +{g:.2%}; preço já no nível)")
                continue
            velho = p.get("stop")
            try:
                p["stop"] = self.c.gatilho(par, p["lado"], p["contratos"], novo, "stop")
            except ErroCorretora as ex:
                self.anotar(f"⚠️ {par[:-4]}: não consegui subir o stop ({str(ex)[:100]}); o anterior continua")
                continue
            self._cancelar(par, velho)
            p["stop_tipo"] = "móvel" if g != GARANTIA_PCT else "garantia"
            self.anotar(f"⤴ {par[:-4]}: {'lucro garantido, stop' if g == GARANTIA_PCT else 'stop móvel'} {velho and velho['preco']} → {p['stop']['preco']} (pico +{p['pico']:.2%})")

    def patrimonio(self):
        pos = self.c.posicoes()
        total = float(self.e["caixa"])
        for par, p in self.e["abertas"].items():
            x = pos.get(par, {})
            p["preco_corretora"], p["resultado_aberto"] = x.get("marca", p["entrada"]), x.get("pnl", 0.0)
            total += p["gasto"] + p["resultado_aberto"]
        self.e["patrimonio"] = total
        return total

    def rodada(self, d, agora=None):
        try:
            self._rodada(d, agora)
        finally:                                                           # auditoria 20/11: erro no meio não perde o que a rodada já fez na corretora
            self.e["atualizado"] = time.time()
            self.salvar()

    def _rodada(self, d, agora=None):
        agora = agora or time.time()
        self.conciliar()
        self.mover_stops()
        for par in list(self.e["abertas"]):
            mm = self.e["abertas"][par].get("max_min")
            if agora - self.e["abertas"][par]["entrada_t"] > (mm or MAX_HORAS * 60) * 60:
                self.fechar(par, f"prazo da operação ({mm:.0f} min)" if mm else f"tempo máximo ({MAX_HORAS} h)")
        if d and agora - float(d.get("t", 0)) <= VALIDADE_S:
            nova = d["t"] != self.e.get("decisao_seguida_t")
            self.e["decisao_seguida_t"] = d["t"]
            if nova:
                self.e["decisao_entradas"] = {"t": d["t"], "pares": list(self.e["abertas"])}
            querer = {}
            for x in d.get("posicoes") or []:
                par = str(x.get("moeda", "")).upper()
                querer[par if par.endswith("USDT") else par + "USDT"] = (x.get("lado"), x.get("motivo", ""), x)
            for par in (list(self.e["abertas"]) if nova else []):
                if par not in querer:
                    self.fechar(par, "fora da lista de posições do agente")
                elif querer[par][0] != self.e["abertas"][par]["lado"]:
                    self.fechar(par, "o agente inverteu o lado")
            ja = set(self.e.get("decisao_entradas", {}).get("pares", [])) | saidas_desde(self.e, d)
            calma = time.time() - float(self.e.get("rede_ruim_t") or 0)
            if calma < REDE_CALMA_S:
                if querer and not self.e.get("_avisou_rede"):
                    print(f"sem entrada nova: erro de rede/stop recusado há {calma:.0f} s (espera {REDE_CALMA_S} s)", flush=True)
                self.e["_avisou_rede"] = True
            else:
                self.e.pop("_avisou_rede", None)
            if self.patrimonio() >= PISO and calma >= REDE_CALMA_S:
                for par, (lado, motivo, x) in querer.items():
                    bloq = par in ja and not (isinstance(x, dict) and x.get("plano_agente"))   # 27/11: ordem do agente/dono não cai na trava de reentrada
                    if par not in self.e["abertas"] and not bloq and len(self.e["abertas"]) < MAX_POS and lado in ("compra", "venda"):
                        try:
                            self.abrir(par, lado, motivo, d["t"], x)
                            if par in self.e["abertas"]:
                                self.e.setdefault("decisao_entradas", {"t": d["t"], "pares": []})["pares"].append(par)
                        except ErroCorretora as ex:
                            self.anotar(f"⚠️ {par[:-4]}: entrada falhou ({str(ex)[:150]})")
        self.patrimonio()


# ======================= ramo estado =======================
def publicar(agente, e):
    import operar as OP
    c = OP.clone(agente)
    alvo = f"dados/corretora_{agente}.json"
    ultimo = ""
    for k in range(1, 6):
        try:
            OP.atualizar(c)
            (c / alvo).write_text(json.dumps(e, ensure_ascii=False))
            OP.git(c, "add", alvo)
            mudou = OP.git(c, "diff", "--cached", "--name-only").stdout.split()
            if not mudou:
                return "nada novo"
            if mudou != [alvo]:
                raise RuntimeError(f"o commit mexeria em outros arquivos: {mudou}")
            OP.git(c, *OP.AUTOR, "commit", "-q", "-m", f"corretora {agente} {time.strftime('%H:%M', time.gmtime())}", "-m", TRAILER)
            r = OP.git(c, "push", "-q", "origin", "HEAD:estado", check=False)
            if r.returncode == 0:
                return OP.git(c, "rev-parse", "--short", "HEAD").stdout.strip()
            ultimo = (r.stderr or r.stdout)[:200]
        except Exception as ex:                                            # noqa: BLE001 — git, rede ou disco: tenta de novo
            ultimo = str(ex)[:200]
        time.sleep(3 * k)
    return f"push falhou 5 vezes: {ultimo}"


def decisao(agente):
    import operar as OP
    c = OP.clone(agente)
    OP.atualizar(c)
    return OP.ler_json(c, f"decisao_{agente}.json", {}) or {}


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    agente, opc = sys.argv[1], sys.argv[2:3]
    if opc == ["--validar"]:
        c = conectar(agente, permitir_travada=True)
        try:
            total, livre = c.saldo()
            ctr = c.contrato("BTCUSDT")
            print(f"{c.NOME} ({c.BASE}): leitura OK · saldo de demonstração {total:.2f} (livre {livre:.2f}) · BTCUSDT "
                  f"{'existe' if ctr else 'não encontrado'}{' · já VALIDADA para ordens' if c.VALIDADO is True else ' · ordens liberam sozinhas quando o saldo for > 0' if c.VALIDADO == 'saldo' else ' · ordens continuam TRAVADAS até a liberação no código'}")
        except (ErroCorretora, KeyError, IndexError, TypeError) as ex:
            print(f"{c.NOME}: validação FALHOU ({str(ex)[:200]}); nada foi feito")
            raise SystemExit(1)
        return
    if agente == "laboratorio" and opc != ["--conta"] and os.environ.get("BALEIAS_MOTOR") != "1":
        raise SystemExit("PARE: a carteira única é executada só pelo motor (mesa/operar/motor.py, serviço baleias-motor). "
                         "Comande pelo motor: python3 -I motor.py set|sair|bloquear ... Nada foi feito.")
    c = conectar(agente)
    PASTA.mkdir(exist_ok=True)
    with open(PASTA / f"{agente}.lock", "w") as trava:
        fcntl.flock(trava, fcntl.LOCK_EX)                                  # duas rodadas da mesma conta mandariam ordens em dobro
        conta = Conta(agente, c)
        if opc == ["--conta"]:
            print(c.NOME, "saldo (total, livre):", c.saldo())
            print("posições:", c.posicoes())
            print("gatilhos vivos:", c.gatilhos_abertos())
            return
        conta.rodada(decisao(agente))
        commit = publicar(agente, conta.e)
        e = conta.e
        print(f"🏦 {agente} em {c.NOME}: patrimônio US$ {e['patrimonio']:.4f} · caixa {e['caixa']:.4f} · {len(e['abertas'])} abertas · "
              f"{len(e['fechadas'])} fechadas · estado {commit}")


if __name__ == "__main__":
    main()
