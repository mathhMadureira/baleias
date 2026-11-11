"""Motor de tempo real do painel /ao-vivo.

Cada fonte roda numa thread própria e reconecta sozinha:
- Binance spot (WebSocket): negócios gigantes do BTC, 24 h de todas as moedas (mapa de calor do mercado), velas de 15 min (padrões H6).
- Binance futuros (WebSocket): liquidações.
- Hyperliquid (WebSocket): negócios grandes e as entradas/saídas das carteiras-baleia acompanhadas (até 10, limite da API).
- Book do BTC na Binance (REST a cada 10 s): mapa de calor de liquidez.
- Robô (banco, só leitura): cada entrada e saída.
- B3 (Yahoo, ^BVSP 1 min): sem dado em tempo real gratuito; mostra o atraso medido.

Notificações: tudo vai para o feed da página (que avisa no navegador); os eventos marcados vão também para o Telegram, se configurado,
agrupados para não estourar o limite de mensagens. Padrões de vela vêm com a estatística medida (H6) — nenhum passou no teste.
"""
import collections
import json
import math
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from . import alerta, config
from .ws import WS

BINANCE_SPOT = "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/!miniTicker@arr/btcusdt@kline_15m"
BINANCE_FUT = "wss://fstream.binance.com/stream?streams=!forceOrder@arr"
HYPERLIQUID = "wss://api.hyperliquid.xyz/ws"
MOEDAS_HL = ("BTC", "ETH", "SOL", "HYPE")
LIMIAR_BINANCE = 500_000       # US$ por negócio agregado
LIMIAR_BINANCE_AVISO = 2_000_000
LIMIAR_HL = 500_000
LIMIAR_LIQ = 250_000
LIMIAR_LIQ_AVISO = 1_000_000
LIMIAR_FILL_BALEIA = 10_000
FAIXA_LIVRO = 0.01             # ±1% em volta do preço
PASSO_LIVRO = 25.0             # US$ por faixa de preço
COLUNAS_CALOR = 180            # 30 min a cada 10 s
ESTAVEIS = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "USD1", "BFUSD", "XUSD", "USDE"}


# ---------- funções puras (testadas) ----------

def de_aggtrade(d):
    nocional = float(d["p"]) * float(d["q"])
    if nocional < LIMIAR_BINANCE:
        return None
    lado = "venda" if d["m"] else "compra"   # m = comprador é o passivo, logo quem agrediu foi o vendedor
    return {"tipo": "baleia_binance", "lado": lado, "nocional": nocional, "px": float(d["p"]),
            "texto": f"🐳 Binance: {lado.upper()} agressora de US$ {nocional:,.0f} em BTC a {float(d['p']):,.1f}",
            "notificar": nocional >= LIMIAR_BINANCE_AVISO}


def de_liquidacao(d):
    o = d["o"]
    px = float(o.get("ap") or o["p"])
    nocional = px * float(o.get("z") or o["q"])
    if nocional < LIMIAR_LIQ:
        return None
    quem = "comprados (long)" if o["S"] == "SELL" else "vendidos (short)"
    return {"tipo": "liquidacao", "moeda": o["s"], "nocional": nocional, "px": px,
            "texto": f"💥 Liquidação de {quem} em {o['s']}: US$ {nocional:,.0f} a {px:,.4g}",
            "notificar": nocional >= LIMIAR_LIQ_AVISO}


def de_hl_trade(t):
    nocional = float(t["px"]) * float(t["sz"])
    if nocional < LIMIAR_HL:
        return None
    lado = "compra" if t["side"] == "B" else "venda"
    return {"tipo": "baleia_hl", "moeda": t["coin"], "lado": lado, "nocional": nocional, "px": float(t["px"]),
            "texto": f"🐋 Hyperliquid: {lado.upper()} agressora de US$ {nocional:,.0f} em {t['coin']} a {float(t['px']):,.4g}",
            "notificar": False}


def de_hl_fill(usuario, f):
    nocional = float(f["px"]) * float(f["sz"])
    if nocional < LIMIAR_FILL_BALEIA:
        return None
    direcao = f.get("dir") or ("Compra" if f.get("side") == "B" else "Venda")
    traducao = {"Open Long": "ABRIU COMPRADO", "Open Short": "ABRIU VENDIDO", "Close Long": "FECHOU COMPRADO",
                "Close Short": "FECHOU VENDIDO", "Long > Short": "VIROU para VENDIDO", "Short > Long": "VIROU para COMPRADO"}
    acao = traducao.get(direcao, direcao.upper())
    pnl = float(f.get("closedPnl") or 0)
    extra = f" | resultado fechado US$ {pnl:+,.0f}" if pnl else ""
    return {"tipo": "carteira", "carteira": usuario, "moeda": f["coin"], "acao": acao, "nocional": nocional, "px": float(f["px"]),
            "texto": f"🎯 Carteira {usuario[:8]}… {acao} {f['coin']} — US$ {nocional:,.0f} a {float(f['px']):,.4g}{extra}",
            "notificar": True}


def mercado_de_tickers(lista):
    """Top moedas em USDT por volume, com variação de 24 h — dados do mapa de calor do mercado."""
    saida = []
    for e in lista:
        s = e["s"]
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        if base in ESTAVEIS or base.endswith(("UP", "DOWN", "BULL", "BEAR")):
            continue
        o, c = float(e["o"]), float(e["c"])
        if o <= 0:
            continue
        saida.append({"s": base, "p": c, "pct": (c / o - 1) * 100, "vq": float(e["q"])})
    return saida


def faixas_livro(bids, asks, preco, passo=PASSO_LIVRO, faixa=FAIXA_LIVRO):
    """Liquidez em US$ por faixa de preço (só ±faixa em volta do preço). Chave = piso da faixa."""
    lim_baixo, lim_alto = preco * (1 - faixa), preco * (1 + faixa)
    saida = {}
    for lado in (bids, asks):
        for px, qtd in lado:
            px, qtd = float(px), float(qtd)
            if lim_baixo <= px <= lim_alto:
                chave = round(px // passo * passo, 2)
                saida[chave] = saida.get(chave, 0.0) + px * qtd
    return saida


def texto_padroes(ativos, tabela, horizontes=("15min", "1h", "4h")):
    linhas = []
    for nome in ativos:
        partes = []
        for hz in horizontes:
            x = tabela.get(f"{nome}|{hz}")
            if not x:
                continue
            te = x["teste"]
            partes.append(f"{hz}: {te.get('chance_alta', 0):.0%} alta, {te.get('retorno_medio_pct', 0):+.3f}%")
        paga = any(tabela.get(f"{nome}|{hz}", {}).get("passou") for hz in horizontes)
        linhas.append(f"• {nome} ({'; '.join(partes)}) {'✅ paga o custo' if paga else '⚠ não paga o custo'}")
    return "\n".join(linhas)


def paredes(bids, asks, preco, perto=0.002, longe=0.005):
    """Lado a lado do book: liquidez a ±0,2% do preço e a maior 'parede' (faixa de US$ 25) de cada lado até ±0,5%."""
    def lado(ordens, sinal):
        soma, faixas = 0.0, {}
        for px, q in ordens:
            px, q = float(px), float(q)
            dist = (px / preco - 1) * sinal
            if 0 <= dist <= perto:
                soma += px * q
            if 0 <= dist <= longe:
                chave = round(px // PASSO_LIVRO * PASSO_LIVRO, 2)
                faixas[chave] = faixas.get(chave, 0.0) + px * q
        maior = max(faixas.items(), key=lambda x: x[1]) if faixas else (None, 0.0)
        return soma, maior
    compra, parede_c = lado(bids, -1)
    venda, parede_v = lado(asks, 1)
    return {"compra_perto": compra, "venda_perto": venda, "parede_compra": parede_c, "parede_venda": parede_v}


def _us(x):
    return f"US$ {x / 1e6:,.1f} mi" if abs(x) >= 1e6 else f"US$ {x / 1e3:,.0f} mil"


def traduzir(j, media_volume=None):
    """Traduz 5 min de fluxo em português. `j`: px0, px1, compra, venda (agressão, US$), liq_long, liq_short, livro (de paredes())."""
    linhas = []
    var = (j["px1"] / j["px0"] - 1) * 100 if j.get("px0") else 0.0
    total = j["compra"] + j["venda"]
    fatia = j["compra"] / total if total else 0.5
    delta = j["compra"] - j["venda"]
    if fatia > 0.55:
        quem = f"compradores agressivos dominaram ({fatia:.0%} do volume, saldo {_us(delta)})"
    elif fatia < 0.45:
        quem = f"vendedores agressivos dominaram ({1 - fatia:.0%} do volume, saldo {_us(delta)})"
    else:
        quem = f"equilíbrio entre compradores e vendedores ({fatia:.0%} de compra)"
    linhas.append(f"Preço {var:+.2f}% em 5 min; {quem}.")
    if media_volume:
        r = total / media_volume
        if r >= 1.8 or r <= 0.5:
            linhas.append(f"Volume {r:.1f}× o normal da última hora — {'mercado acordado' if r >= 1.8 else 'mercado parado'}.")
    if var > 0.05 and delta > 0:
        leitura = "alta com força: compradores pagando o preço de quem vende."
    elif var > 0.05 and delta <= 0:
        leitura = "alta sem agressão compradora: falta vendedor, não sobra comprador (alta frágil)."
    elif var < -0.05 and delta < 0:
        leitura = "queda com força: vendedores aceitando preços piores para sair."
    elif var < -0.05 and delta >= 0:
        leitura = "compradores agredindo e o preço caindo: alguém grande está vendendo passivamente (absorção)."
    elif abs(delta) > 0.15 * total and total:
        leitura = f"{'compra' if delta > 0 else 'venda'} agressiva sem mover o preço: está sendo absorvida por ordens paradas."
    else:
        leitura = "sem direção clara."
    linhas.append("Leitura: " + leitura)
    if j.get("liq_long", 0) + j.get("liq_short", 0) >= 250_000:
        lado = "comprados (quem apostou na alta)" if j["liq_long"] >= j["liq_short"] else "vendidos (quem apostou na queda)"
        linhas.append(f"Liquidações: {_us(j['liq_long'])} de comprados e {_us(j['liq_short'])} de vendidos — os {lado} foram forçados a sair.")
    lv = j.get("livro")
    if lv and lv["compra_perto"] and lv["venda_perto"]:
        r = lv["compra_perto"] / lv["venda_perto"]
        if r >= 1.5 or r <= 0.67:
            linhas.append(f"Book a ±0,2%: {r:.1f}× mais dinheiro {'comprando' if r >= 1.5 else 'vendendo'} do que {'vendendo' if r >= 1.5 else 'comprando'} (ordens podem ser canceladas).")
        for nome, (px, usd) in (("compra", lv["parede_compra"]), ("venda", lv["parede_venda"])):
            if px and usd >= 2_000_000:
                linhas.append(f"Parede de {nome}: {_us(usd)} em {px:,.0f} ({(px / j['px1'] - 1) * 100:+.2f}%).")
    return "\n".join(linhas)


# ---------- motor ----------

MAX_MESMO_LADO = int(os.environ.get("ROBO_MAX_MESMO_LADO", "2"))   # freio de correlação: as moedas andam juntas, então 5 vendidas
                                                                   # ao mesmo tempo são uma aposta só no mercado inteiro


def lado_cheio(abertas, lado):
    return sum(1 for p in abertas.values() if p.get("lado", "compra") == lado) >= MAX_MESMO_LADO

def dormir(segundos):
    """Como time.sleep, mas pelo relógio de parede: se a máquina dormiu, acorda logo na volta (o sleep comum continuaria contando)."""
    fim = time.time() + segundos
    while (falta := fim - time.time()) > 0:
        time.sleep(min(falta, 15))


class Motor:
    def __init__(self, abrir=None, enviar=alerta.enviar, agora=time.time):
        """`abrir`: função que devolve uma conexão só de leitura ao banco (uma por thread; sqlite não gosta de conexão compartilhada)."""
        self.trava = threading.Lock()
        self.eventos = collections.deque(maxlen=600)
        self.seq = 0
        self.fontes = {}
        self.mercado = {}
        self.calor = collections.deque(maxlen=COLUNAS_CALOR)
        self.calor_seq = 0
        self.preco = None
        self.b3 = None
        self.velas15 = []
        self.abrir = abrir
        self.enviar = enviar
        self.agora = agora
        self.pendentes = []
        self.ultimo_robo = None
        self.arquivo = config.RAIZ / "ao_vivo.jsonl"
        self.fluxo = {"compra": 0.0, "venda": 0.0, "liq_long": 0.0, "liq_short": 0.0}
        self.livro_atual = None
        self.volumes = collections.deque(maxlen=12)
        self.tartaruga = None
        self.rapido = None
        self.mapa = None
        self.vortice = None
        self.cerebro = None
        self.varredura = {"moedas": {}, "log": collections.deque(maxlen=80), "voltas": 0}
        self._cbr = None
        self.scalper = None

    # estado
    def fonte(self, nome, ok, erro=None):
        with self.trava:
            f = self.fontes.setdefault(nome, {"msgs": 0})
            f.update(ok=ok, t=self.agora(), erro=erro)
            if ok:
                f["msgs"] += 1

    def evento(self, ev):
        if not ev:
            return
        with self.trava:
            self.seq += 1
            ev = {"id": self.seq, "t": self.agora(), **ev}
            self.eventos.append(ev)
            if ev.get("notificar"):
                self.pendentes.append(ev["texto"])
        try:
            with open(self.arquivo, "a") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def instantaneo(self, desde=0, calor_desde=0):
        with self.trava:
            return {
                "agora": self.agora(),
                "fontes": {k: dict(v) for k, v in self.fontes.items()},
                "eventos": [e for e in self.eventos if e["id"] > desde],
                "mercado": sorted(self.mercado.values(), key=lambda x: -x["vq"])[:48],
                "preco": self.preco,
                "b3": self.b3,
                "tartaruga": self.tartaruga,
                "calor_seq": self.calor_seq,
                "calor": list(self.calor)[-max(0, min(len(self.calor), self.calor_seq - calor_desde)):] if self.calor_seq > calor_desde else [],
            }

    # laço genérico com reconexão
    def _laco(self, nome, funcao, pausa=5):
        while True:
            try:
                funcao()
            except Exception as e:
                self.fonte(nome, False, f"{type(e).__name__}: {str(e)[:80]}")
            time.sleep(pausa)

    def _binance_spot(self):
        ws = WS.conectar(BINANCE_SPOT)
        ws.s.settimeout(120)
        self.fonte("binance", True)
        try:
            while True:
                m = json.loads(ws.receber())
                stream, d = m.get("stream", ""), m.get("data")
                if stream.endswith("@aggTrade"):
                    self.preco = float(d["p"])
                    with self.trava:
                        self.fluxo["venda" if d["m"] else "compra"] += float(d["p"]) * float(d["q"])
                    self.evento(de_aggtrade(d))
                elif stream == "!miniTicker@arr":
                    with self.trava:
                        for x in mercado_de_tickers(d):
                            self.mercado[x["s"]] = x
                elif stream.endswith("@kline_15m") and d["k"]["x"]:
                    self._vela_fechada(d["k"])
                self.fonte("binance", True)
        finally:
            ws.fechar()

    def _carregar_velas15(self):
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=130"
        with urllib.request.urlopen(url, timeout=20) as r:
            k = json.load(r)
        self.velas15 = [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in k[:-1]]

    def _vela_fechada(self, k):
        from lab import padroes
        if not self.velas15:
            self._carregar_velas15()
        else:
            self.velas15.append((k["t"], float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["v"])))
            self.velas15 = self.velas15[-130:]
        arq = config.RAIZ / "lab" / "padroes_tabela.json"
        if len(self.velas15) < 101 or not arq.exists():
            return
        ativos = [p for p in padroes.detectar(self.velas15)[-1] if p not in ("tendencia_alta", "tendencia_baixa")]
        if ativos:
            tabela = json.loads(arq.read_text())
            self.evento({"tipo": "padrao", "texto": f"🕯 BTC 15 min fechou ({self.velas15[-1][4]:,.0f}) com padrões:\n" + texto_padroes(ativos, tabela),
                         "notificar": True, "padroes": ativos})

    def _binance_futuros(self):
        ws = WS.conectar(BINANCE_FUT)
        ws.s.settimeout(300)   # liquidações podem ficar minutos sem acontecer; a Binance manda ping a cada ~3 min
        ws.ao_ping = lambda: self.fonte("liquidacoes", True)   # conexão viva conta como fonte viva
        self.fonte("liquidacoes", True)
        try:
            while True:
                m = json.loads(ws.receber())
                o = m["data"]["o"]
                if o["s"] == "BTCUSDT":
                    with self.trava:
                        self.fluxo["liq_long" if o["S"] == "SELL" else "liq_short"] += float(o.get("ap") or o["p"]) * float(o.get("z") or o["q"])
                self.evento(de_liquidacao(m["data"]))
                self.fonte("liquidacoes", True)
        finally:
            ws.fechar()

    def _carteiras(self):
        if self.abrir is None:
            return []
        c = self.abrir()
        try:
            return [x[0] for x in c.execute("SELECT carteira FROM carteiras WHERE ativa=1 ORDER BY nota DESC LIMIT 10").fetchall()]
        finally:
            c.close()

    def _hyperliquid(self):
        ws = WS.conectar(HYPERLIQUID)
        ws.s.settimeout(70)
        for moeda in MOEDAS_HL:
            ws.enviar_json({"method": "subscribe", "subscription": {"type": "trades", "coin": moeda}})
        carteiras = self._carteiras()
        for c in carteiras:
            ws.enviar_json({"method": "subscribe", "subscription": {"type": "userFills", "user": c}})
        self.fonte("hyperliquid", True)
        ultimo_ping = time.monotonic()
        try:
            while True:
                if time.monotonic() - ultimo_ping > 45:
                    ws.enviar_json({"method": "ping"})
                    ultimo_ping = time.monotonic()
                m = json.loads(ws.receber())
                canal = m.get("channel")
                if canal == "trades":
                    for t in m["data"]:
                        self.evento(de_hl_trade(t))
                elif canal == "userFills" and not m["data"].get("isSnapshot"):
                    for f in m["data"]["fills"]:
                        self.evento(de_hl_fill(m["data"]["user"], f))
                self.fonte("hyperliquid", True)
        finally:
            ws.fechar()

    def _livro(self):
        while True:
            with urllib.request.urlopen("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5000", timeout=20) as r:
                d = json.load(r)
            preco = self.preco or (float(d["bids"][0][0]) + float(d["asks"][0][0])) / 2
            faixas = faixas_livro(d["bids"], d["asks"], preco)
            self.livro_atual = paredes(d["bids"], d["asks"], preco)
            with self.trava:
                self.calor.append({"t": self.agora(), "px": preco, "f": faixas})
                self.calor_seq += 1
            self.fonte("livro", True)
            time.sleep(10)

    def _robo(self):
        if self.abrir is None:
            return
        c = self.abrir()
        while True:
            linhas = c.execute("SELECT id, lado, px_compra, px_venda, resultado_usdt, braco FROM robo_operacoes ORDER BY id DESC LIMIT 5").fetchall()
            self.novidades_robo(linhas)
            self.fonte("robo", True)
            time.sleep(5)

    def novidades_robo(self, linhas):
        """Compara as últimas operações com a leitura anterior; a primeira leitura só memoriza (não repete o passado)."""
        estado = {x[0]: (x[3] is not None) for x in linhas}
        if self.ultimo_robo is not None:
            for x in reversed(linhas):
                antes = self.ultimo_robo.get(x[0])
                if antes is None:
                    self.evento({"tipo": "robo", "texto": f"🤖 Robô ENTROU {(x[1] or 'compra').upper()} a {x[2]:,.1f} (versão {x[5]}, simulado)", "notificar": True})
                if x[3] is not None and not antes:
                    self.evento({"tipo": "robo", "texto": f"🤖 Robô SAIU a {x[3]:,.1f}: {x[4]:+.3f} USDT (simulado)", "notificar": True})
        self.ultimo_robo = estado

    def _b3(self):
        while True:
            req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval=1m&range=1d",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)["chart"]["result"][0]
            meta = d["meta"]
            t = meta.get("regularMarketTime")
            with self.trava:
                self.b3 = {"ibov": meta.get("regularMarketPrice"), "anterior": meta.get("chartPreviousClose"),
                           "t": t, "atraso_s": (self.agora() - t) if t else None}
            self.fonte("b3", True)
            time.sleep(60)

    def _leitura(self):
        """A cada 5 min: traduz o fluxo do BTC e grava as medidas com o preço (H7 mede depois se antecipam algo)."""
        px0 = None
        while True:
            dormir(300 - time.time() % 300)
            with self.trava:
                j, self.fluxo = dict(self.fluxo), {"compra": 0.0, "venda": 0.0, "liq_long": 0.0, "liq_short": 0.0}
            px1 = self.preco
            if px0 and px1:
                j.update(px0=px0, px1=px1, livro=self.livro_atual)
                media = sum(self.volumes) / len(self.volumes) if self.volumes else None
                self.evento({"tipo": "leitura", "texto": "📖 " + traduzir(j, media), "notificar": False, "medidas": j})
                self.volumes.append(j["compra"] + j["venda"])
                try:
                    with open(config.RAIZ / "leitura_mercado.jsonl", "a") as f:
                        f.write(json.dumps({"t": int(time.time()), **j}) + "\n")
                except OSError:
                    pass
            px0 = px1
            self.fonte("leitura", True)

    def _tartaruga(self):
        """Mostra o robô Tartaruga (que roda no serviço baleias-robo) e repassa cada decisão dele como evento notificado."""
        estado = config.RAIZ / "robo_tartaruga.json"
        eventos = config.RAIZ / "robo_eventos.jsonl"
        posicao = eventos.stat().st_size if eventos.exists() else 0
        while True:
            if eventos.exists():
                tamanho = eventos.stat().st_size
                if tamanho < posicao:
                    posicao = 0
                with open(eventos) as f:
                    f.seek(posicao)
                    for linha in f:
                        try:
                            x = json.loads(linha)
                        except ValueError:
                            continue
                        self.evento({"tipo": "tartaruga", "texto": x["texto"], "notificar": True})
                    posicao = f.tell()
            if estado.exists():
                try:
                    e = json.loads(estado.read_text())
                except ValueError:
                    e = None
                if e:
                    rs = [f["R"] for f in e["fechadas"]]
                    with self.trava:
                        self.tartaruga = {"patrimonio": e.get("patrimonio"), "inicio": e.get("inicio"), "real": bool(e.get("modo_real")),
                                          "abertas": [{"moeda": m[:-4], "entrada": p["entrada"], "stop": p["stop"], "qtd": p["qtd"]} for m, p in e["abertas"].items()],
                                          "fechadas": len(rs), "media_R": sum(rs) / len(rs) if rs else None, "radar": e.get("radar", []),
                                          "atualizado": e.get("atualizado")}
            self.fonte("tartaruga", True)
            time.sleep(5)

    def _velas_rapidas(self, intervalo, moedas):
        """Últimas 80 velas FECHADAS de cada moeda (a vela em andamento fica de fora)."""
        from lab import tartaruga as T
        saida, agora_ms = {}, time.time() * 1000
        for m in moedas:
            try:
                with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={m}&interval={intervalo}&limit=241", timeout=20) as r:
                    k = json.load(r)
            except OSError:
                continue
            saida[m] = [[time.strftime("%Y-%m-%d %H:%M", time.gmtime(x[0] / 1000)), float(x[1]), float(x[2]), float(x[3]), float(x[4])]
                        for x in k if x[6] < agora_ms]
            self.__dict__.setdefault("_brutas", {})[m] = [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]))
                                                          for x in k if x[6] < agora_ms]
            time.sleep(0.05)
        return saida

    def _consultar_livro(self, dados, precos, e, ouvir):
        """Antes de entrar num rompimento, o robô rápido consulta os métodos COMPROVADOS do Livro do cérebro na mesma moeda.
        Se votarem contra (desce), a entrada não acontece nesta vela — é assim que ele aprende com o cérebro."""
        from lab import tartaruga as T
        from . import cerebro as C
        arq = config.RAIZ / "livro_metodos.json"
        try:
            livro = json.loads(arq.read_text())["metodos"]
        except (OSError, ValueError, KeyError):
            return precos
        if not any(m["classe"] == "comprovado" for m in livro):
            return precos
        filtrado = dict(precos)
        for m, vs in dados.items():
            if m in e["abertas"] or len(vs) < 120 or not T.sinais(vs, len(vs) - 1, "compra"):
                continue
            velas = [(0, v[1], v[2], v[3], v[4], 1.0) for v in vs[-120:]]
            voto, usados = C.votar_comprovados(livro, C.caracteristicas(velas))
            if voto < 0:
                filtrado.pop(m, None)
                ouvir({"t": time.time(), "texto": f"🧠➜ {m[:-4]} rompeu, mas o Livro do cérebro votou contra ({', '.join(usados)}): entrada evitada."})
        return filtrado

    def _aquecer_cerebro_rapido(self, cbr, intervalo):
        """Vive as últimas ~1000 velas (do tempo gráfico do robô) das 33 moedas em sequência (prevê, espera 1 h, confere) antes de ir ao vivo."""
        from lab import tartaruga as T
        from . import cerebro as C
        series = {}
        for m in T.MOEDAS_ROBO:                        # 3 páginas de 1000 velas: vários humores de mercado, não só o das últimas horas
            vs, fim = [], None
            try:
                for _ in range(3):
                    url = f"{T.DADOS}/api/v3/klines?symbol={m}&interval={intervalo}&limit=1000" + (f"&endTime={fim}" if fim else "")
                    with urllib.request.urlopen(url, timeout=30) as r:
                        k = json.load(r)
                    if not k:
                        break
                    vs = [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in k if x[6] < time.time() * 1000] + vs
                    fim = k[0][0] - 1
                    time.sleep(0.05)
            except OSError:
                continue
            series[m] = vs
        tamanho = min(len(v) for v in series.values())
        for i in range(C.JANELA, tamanho):
            for m, v in series.items():
                janela = v[len(v) - tamanho + max(0, i - C.JANELA - 20):len(v) - tamanho + i + 1]
                cbr.resolver(m, janela)
                cbr.observar(m, janela[-C.JANELA:])
        cbr._anotar(time.time() * 1000, f"🧠 Aquecimento do robô rápido: viveu {tamanho - C.JANELA} velas de {intervalo} em {len(series)} moedas "
                                        f"({(tamanho - C.JANELA) * len(series)} previsões conferidas {C.HORIZONTE} velas depois).")

    def _cerebro_rapido_passo(self, cbr, dados, precos, e, corretora, ouvir):
        """A cada vela de 5 min: confere as previsões de 1 h atrás, prevê todas as moedas (comprar OU vender a descoberto),
        corrige a própria confiança pelo que já acertou e entra nas de maior valor esperado."""
        from lab import tartaruga as T
        from executor import tartaruga_exec as X
        from . import cerebro as C
        brutas = getattr(self, "_brutas", {})
        X.stops_perdidos(e, corretora, dados)
        rel = C.autoanalise(e["fechadas"])                    # autoconhecimento: o que minhas operações dizem sobre mim
        novas = [c for c in rel["conclusoes"] if c not in cbr.__dict__.get("conclusoes_vistas", [])]
        for c in novas:
            cbr._anotar(time.time() * 1000, "📊 Autoanálise: " + c)
            ouvir({"t": time.time(), "texto": "📊 Autoanálise: " + c})
        cbr.conclusoes_vistas = rel["conclusoes"]
        cbr.autoanalise = rel
        oportunidades = []
        for m, v in brutas.items():
            if len(v) < C.JANELA + 1:
                continue
            cbr.resolver(m, v[-(C.JANELA + 21):])
            prob, ev, f, lado = cbr.observar(m, v[-C.JANELA:])
            p_lado = prob if lado == "compra" else 1 - prob
            p_cal = C.prob_calibrada(p_lado, rel)
            ev_aj = (2 * p_cal - 1) * f["_mov"] - C.CUSTO_PERP - rel["margem_lado"].get(lado, 0.0)
            oportunidades.append({"moeda": m[:-4], "prob": prob, "ev": ev_aj, "lado": lado, "p_lado": p_lado, "p_cal": p_cal, "par": m,
                                  "geladeira": m in rel["geladeira"]})
        oportunidades.sort(key=lambda x: -x["p_cal"])   # pela confiança, não pelo tamanho do movimento (senão só as pequenas ganham a vez)
        cbr.oportunidades = oportunidades[:33]
        if X.PARAR.exists():
            return
        for o in oportunidades:
            m = o["par"]
            if (o["ev"] <= 0 or o["geladeira"] or m in e["abertas"] or m not in precos or lado_cheio(e["abertas"], o["lado"])
                    or corretora.usdt_livre() < X.ORCAMENTO_FIXO / X.ALAV_PERP):
                continue
            n = T.atr(dados[m])[-1] if m in dados and len(dados[m]) > 21 else None
            if not n:
                continue
            X.entrar(e, corretora, m, precos[m], n,
                     f"cérebro: {o['p_cal']:.1%} de acerto calibrado, valor esperado {o['ev'] * 100:+.2f}%", lado=o["lado"], custo_lado=0.0005)
            if m in e["abertas"]:
                e["abertas"][m].update({"prob_lado": o["p_cal"], "ev": o["ev"], "hora": time.gmtime().tm_hour})

    def _robo_rapido(self):
        """Teste ao vivo, simulado: as mesmas regras da Tartaruga em velas curtas (ROBO_RAPIDO=1h por padrão), para operar no dia.
        Decide a cada vela fechada; stop conferido a cada 5 s com o preço ao vivo. Não usa dinheiro real."""
        from lab import tartaruga as T
        from executor import tartaruga_exec as X
        intervalo = os.environ.get("ROBO_RAPIDO", "1m")                        # pedido do dono: velas de 1 min
        passo = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}[intervalo]
        capital = float(os.environ.get("ROBO_RAPIDO_CAPITAL", "10"))            # conta do robô rápido: US$ 10 no total (pedido do dono)
        limite_dia = float(os.environ.get("ROBO_RAPIDO_PERDA_DIA", str(capital * 0.10)))   # perde no máximo 10% da conta por dia
        piso = capital * 0.5                                                    # abaixo de metade da conta, para de vez
        meta_dia = float(os.environ.get("ROBO_RAPIDO_META_DIA", "100"))         # meta do dono: para ao ganhar isto no período
        meta_dias = int(os.environ.get("ROBO_RAPIDO_META_DIAS", "2"))           # período da meta: blocos de 2 dias UTC
        X.ORCAMENTO_FIXO = float(os.environ.get("ROBO_RAPIDO_ORCAMENTO", "5"))   # US$ por operação (mínimo da Binance ≈ US$ 5)
        max_velas = int(os.environ.get("ROBO_RAPIDO_MAX_VELAS", "12"))          # não segurar demais: no máximo 12 velas (1 h em 5 min)
        X.PARAR = config.RAIZ / "PARAR_RAPIDO"                                # neste processo só o robô rápido usa o tartaruga_exec
        arq = config.RAIZ / f"robo_rapido_{intervalo}.json"
        e = json.loads(arq.read_text()) if arq.exists() else X.novo_estado(capital)
        e.setdefault("eventos", [])
        corretora = X.Simulada(None, e)

        def ouvir(linha):
            texto = "⚡ " + linha["texto"].replace("🐢 Robô ", "Robô rápido ").replace(" [simulado]", "")
            e["eventos"] = ([{"t": linha["t"], "texto": texto}] + e["eventos"])[:100]
            self.evento({"tipo": "rapido", "texto": texto, "notificar": True})
        X.ouvinte = ouvir                       # neste processo o tartaruga_exec só é usado pelo robô rápido
        dados = {}
        modo = os.environ.get("ROBO_RAPIDO_MODO", "cerebro")   # "cerebro" (padrão) ou "tartaruga" (rompimento puro)
        cbr, arq_cbr = None, config.RAIZ / f"cerebro_rapido_{intervalo}_moedas.json"   # um cérebro isolado por moeda e por tempo gráfico
        if modo == "cerebro":
            from . import cerebro as C
            cbr = C.CerebrosPorMoeda(json.loads(arq_cbr.read_text()) if arq_cbr.exists() else None)
            self._cbr = cbr
            if not cbr.passos:
                self._aquecer_cerebro_rapido(cbr, intervalo)
                arq_cbr.write_text(json.dumps(cbr.exportar()))
        while True:
            with self.trava:
                precos = {f"{s}USDT": x["p"] for s, x in self.mercado.items()}
            agora = time.time()
            ultima_fechada = time.strftime("%Y-%m-%d %H:%M", time.gmtime(agora - agora % passo - passo))
            if precos:
                hoje = time.strftime("%Y-%m-%d", time.gmtime(agora))
                fechado_hoje = sum(f["resultado_usd"] for f in e["fechadas"] if time.strftime("%Y-%m-%d", time.gmtime(f["saida_t"])) == hoje)
                bloco = int(agora // 86400) // meta_dias                          # bloco de N dias em que estamos
                fechado_bloco = sum(f["resultado_usd"] for f in e["fechadas"] if int(f["saida_t"] // 86400) // meta_dias == bloco)
                fim_bloco = (bloco + 1) * meta_dias * 86400
                aberto = sum(X._valor(p, precos.get(m, p["entrada"])) - p["gasto"] for m, p in e["abertas"].items())
                meta_batida = fechado_bloco >= meta_dia
                quebrou = X.patrimonio(e, precos, corretora) < piso
                if quebrou and not e.get("quebrou"):
                    e["quebrou"] = True
                    ouvir({"t": agora, "texto": f"⛔ Conta abaixo de US$ {piso:.2f} (metade dos US$ {capital:.0f}). Robô rápido parado de vez até você decidir."})
                travado = fechado_hoje + aberto <= -limite_dia or meta_batida or e.get("quebrou", False)
                if travado and not X.PARAR.exists():
                    X.PARAR.touch()
                    if meta_batida:
                        ouvir({"t": agora, "texto": f"🎯 META ATINGIDA: +{fechado_bloco:.2f} USDT no período de {meta_dias} dias. "
                                                    f"Sem novas entradas até {time.strftime('%d/%m %H:%M', time.gmtime(fim_bloco))} UTC."})
                    else:
                        ouvir({"t": agora, "texto": f"🛑 Limite de perda do dia: {fechado_hoje + aberto:+.2f} USDT. Sem novas entradas até 00:00 UTC (stops seguem)."})
                elif not travado and X.PARAR.exists() and e.get("dia_trava") != (f"bloco{bloco}" if e.get("trava_meta") else hoje):
                    X.PARAR.unlink()
                if travado:
                    e["trava_meta"] = meta_batida
                    e["dia_trava"] = f"bloco{bloco}" if meta_batida else hoje
                e["resultado_hoje"] = fechado_hoje + aberto
                e["resultado_bloco"] = fechado_bloco + aberto
                e["fim_bloco"] = fim_bloco
            if precos and e.get("ultima_vela") != ultima_fechada and agora % passo > 15:
                dados = self._velas_rapidas(intervalo, T.MOEDAS_ROBO)
                if modo == "cerebro":
                    with X.TRAVA:
                        self._cerebro_rapido_passo(cbr, dados, precos, e, corretora, ouvir)
                    tmp = arq_cbr.with_suffix(".tmp")
                    tmp.write_text(json.dumps(cbr.exportar()))
                    tmp.replace(arq_cbr)
                else:
                    precos = self._consultar_livro(dados, precos, e, ouvir)
                    with X.TRAVA:
                        X.passo_diario(e, corretora, dados, precos)
                for p in e["abertas"].values():
                    p.setdefault("conferido_ate", ultima_fechada)
                e["ultima_vela"] = ultima_fechada
            if precos:
                with X.TRAVA:
                    X.checar_stops(e, corretora, precos)
                    for m in list(e["abertas"]):           # tempo máximo: não segurar a operação demais
                        if agora - e["abertas"][m]["entrada_t"] >= max_velas * passo and m in precos:
                            X._sair(e, corretora, m, f"tempo máximo ({max_velas} velas)", precos[m])
                e["patrimonio"] = X.patrimonio(e, precos, corretora)
                if dados:
                    e["radar"] = X.radar(dados, precos)
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(e))
                tmp.replace(arq)
                rs = [f["R"] for f in e["fechadas"]]
                with self.trava:
                    self.rapido = {"intervalo": intervalo, "patrimonio": e["patrimonio"], "resultado_hoje": e.get("resultado_hoje", 0.0),
                                   "limite_dia": limite_dia, "capital_inicial": capital, "quebrou": e.get("quebrou", False), "meta_dia": meta_dia, "meta_dias": meta_dias, "resultado_bloco": e.get("resultado_bloco", 0.0),
                                   "fim_bloco": e.get("fim_bloco"), "orcamento": X.ORCAMENTO_FIXO, "max_velas": max_velas,
                                   "travado": X.PARAR.exists(), "inicio": e["inicio"], "ultima_vela": e.get("ultima_vela"),
                                   "proxima": agora - agora % passo + passo + 15,
                                   "posicoes": [{"moeda": m[:-4], "entrada": p["entrada"], "stop": p["stop"], "preco": precos.get(m),
                                                 "resultado": X._valor(p, precos.get(m, p["entrada"])) - p["gasto"]} for m, p in e["abertas"].items()],
                                   "operacoes": len(rs), "acerto": sum(r > 0 for r in rs) / len(rs) if rs else None,
                                   "media_R": sum(rs) / len(rs) if rs else None, "eventos": e["eventos"][:30],
                                   "radar": e.get("radar", [])[:8], "todas": sorted(m[:-4] for m in T.MOEDAS_ROBO), "modo": modo,
                                   "cerebro": cbr and {"oportunidades": [{k: o.get(k) for k in ("moeda", "prob", "ev", "lado")} for o in cbr.oportunidades[:8]],
                                                       "autoanalise": getattr(cbr, "autoanalise", None),
                                                       "acerto": (sum(cbr.historico[-500:]) / len(cbr.historico[-500:])) if cbr.historico else None,
                                                       "n": len(cbr.historico),
                                                       "sinapses": sum(1 for x in cbr.sinapses if x["status"] == "ativa"),
                                                       "rede": {"acertos": sum(x["acertos"] for x in cbr.sinapses if x["id"] == "rede_neural"),
                                                                "previsoes": sum(x["previsoes"] for x in cbr.sinapses if x["id"] == "rede_neural")},
                                                       "diario": cbr.diario[-6:][::-1]}}
            self.fonte("rapido", True)
            time.sleep(5)

    def velas_ao_vivo(self, moeda, intervalo="1h", n=100):
        """Velas recentes com a vela em formação atualizada pelo preço ao vivo, canais da estratégia e marcas do robô rápido."""
        from lab import tartaruga as T
        m = moeda.upper()[:12] + "USDT"
        chave = (m, intervalo)
        cache = self.__dict__.setdefault("_cache_velas", {})
        if chave not in cache or time.time() - cache[chave][0] > 20:
            with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={m}&interval={intervalo}&limit={n + T.ENTRADA + 1}", timeout=20) as r:
                cache[chave] = (time.time(), json.load(r))
        k = cache[chave][1]
        vs = [[time.strftime("%Y-%m-%d %H:%M", time.gmtime(x[0] / 1000)), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in k]
        with self.trava:
            vivo = self.mercado.get(m[:-4], {}).get("p")
        if vivo and vs:                     # a última vela é a de agora: fecha no preço ao vivo
            vs[-1][4] = vivo
            vs[-1][2], vs[-1][3] = max(vs[-1][2], vivo), min(vs[-1][3], vivo)
        n_atr = T.atr(vs)
        saida = []
        for i in range(max(T.ENTRADA, len(vs) - n), len(vs)):
            saida.append({"d": vs[i][0], "o": vs[i][1], "h": vs[i][2], "l": vs[i][3], "c": vs[i][4], "vivo": i == len(vs) - 1,
                          "entrada": max(v[2] for v in vs[i - T.ENTRADA:i]), "saida": min(v[3] for v in vs[i - T.SAIDA:i]),
                          "stop2n": vs[i][4] - T.STOP_N * n_atr[i] if n_atr[i] else None})
        marcas = []
        arq = config.RAIZ / ("robo_tartaruga.json" if intervalo == "1d" else f"robo_rapido_{intervalo}.json")
        if arq.exists():
            try:
                e = json.loads(arq.read_text())
            except ValueError:
                e = {}
            for o in [f for f in e.get("fechadas", []) if f["moeda"] == m] + [p for k2, p in e.get("abertas", {}).items() if k2 == m]:
                marcas.append({"t": o["entrada_t"], "px": o["entrada"], "tipo": "entrada"})
                if o.get("saida_t"):
                    marcas.append({"t": o["saida_t"], "px": o["saida"], "tipo": "saida"})
        return {"moeda": m[:-4], "velas": saida, "marcas": marcas}

    def _mapa(self):
        """Mapa do mercado inteiro (pares USDT da Binance com volume ≥ US$ 1 mi/dia), a cada 30 min: força relativa,
        distância até o rompimento de 55 dias, volatilidade, liquidez e o termômetro geral (amplitude)."""
        from lab import tartaruga as T
        while True:
            with urllib.request.urlopen(f"{T.DADOS}/api/v3/ticker/24hr", timeout=30) as r:
                todos = json.load(r)
            pares = [x for x in todos if x["symbol"].isascii() and x["symbol"].endswith("USDT") and x["symbol"][:-4] not in ESTAVEIS
                     and not x["symbol"][:-4].endswith(("UP", "DOWN", "BULL", "BEAR")) and float(x["quoteVolume"]) >= 1e6]
            pares.sort(key=lambda x: -float(x["quoteVolume"]))
            linhas = []
            for posicao, x in enumerate(pares):
                m = x["symbol"]
                try:
                    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={m}&interval=1d&limit=61", timeout=20) as r:
                        k = json.load(r)[:-1]          # só dias fechados
                except OSError:
                    continue
                if len(k) < 30:
                    continue
                c = [float(v[4]) for v in k]
                vs = [[v[0], float(v[1]), float(v[2]), float(v[3]), float(v[4])] for v in k]
                n = T.atr(vs)[-1]
                px = float(x["lastPrice"])
                janela = vs[-T.ENTRADA:] if len(vs) >= T.ENTRADA else vs
                maxima = max(v[2] for v in janela)
                linhas.append({"moeda": m[:-4], "preco": px, "d1": float(x["priceChangePercent"]), "d7": (c[-1] / c[-8] - 1) * 100,
                               "d28": (c[-2] / c[-30] - 1) * 100 if len(c) >= 30 else None,
                               "falta": (maxima / px - 1) * 100, "vol": T.STOP_N * n / px * 100 if n else None,
                               "volume": float(x["quoteVolume"]), "liquida": posicao < 40, "robo": m in T.MOEDAS_ROBO,
                               "acima_mm50": len(c) >= 50 and c[-1] > sum(c[-50:]) / 50, "rompeu": c[-1] > max(v[2] for v in vs[-T.ENTRADA - 1:-1])})
                time.sleep(0.08)
            com28 = sorted((l["d28"] for l in linhas if l["d28"] is not None))
            for l in linhas:
                l["forca"] = (sum(v <= l["d28"] for v in com28) / len(com28) * 100) if l["d28"] is not None and com28 else None
            d7 = sorted(l["d7"] for l in linhas)
            with self.trava:
                self.mapa = {"t": time.time(), "moedas": linhas,
                             "termometro": {"analisadas": len(linhas), "acima_mm50": sum(l["acima_mm50"] for l in linhas) / max(1, len(linhas)) * 100,
                                            "romperam": sum(l["rompeu"] for l in linhas), "mediana_7d": d7[len(d7) // 2] if d7 else None,
                                            "subindo_24h": sum(l["d1"] > 0 for l in linhas) / max(1, len(linhas)) * 100}}
            self.fonte("mapa", True)
            dormir(1800)

    def _vortice(self):
        """H19 ao vivo: a cada vela de 15 min do BTC fechada, prevê a próxima pelo Vórtice INVERTIDO (só quando CHOP < 38,2)
        e confere na vela seguinte. Placar com intervalo de Wilson. Arquivo: dados/h19_vortice.jsonl."""
        import math
        from lab import tartaruga as T
        arq = config.RAIZ / "h19_vortice.jsonl"
        registros = [json.loads(x) for x in arq.read_text().splitlines()] if arq.exists() else []
        n, lim = 14, 38.2
        while True:
            with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=1000", timeout=20) as r:
                k = [x for x in json.load(r) if x[6] < time.time() * 1000]
            v = [(x[0], float(x[2]), float(x[3]), float(x[4])) for x in k]
            fech = {x[0]: x[3] for x in v}
            mudou = False
            for rg in registros:                       # confere previsões pendentes
                if not rg.get("resolvida") and rg["alvo"] in fech:
                    if rg.get("aposta"):                 # vela sem aposta (mercado sem direção) só é marcada como vista
                        sobe = fech[rg["alvo"]] > rg["px"]
                        rg["acertou"] = (rg["aposta"] == "sobe") == sobe if fech[rg["alvo"]] != rg["px"] else None
                    rg["resolvida"] = True
                    mudou = True
            for rg in registros:                       # previsão cuja vela de conferência já saiu da janela: perdida
                if not rg.get("resolvida") and rg["alvo"] < v[0][0]:
                    rg["resolvida"], rg["perdida"] = True, True
                    mudou = True
            v = v[-40:]
            ultima = v[-1][0]
            if not any(rg["t"] == ultima for rg in registros):
                h, l, c = [x[1] for x in v], [x[2] for x in v], [x[3] for x in v]
                i = len(v) - 1
                tr = [max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1])) for j in range(i - n + 1, i + 1)]
                faixa = max(h[i - n + 1:i + 1]) - min(l[i - n + 1:i + 1])
                chop = 100 * math.log10(sum(tr) / faixa) / math.log10(n) if faixa > 0 and sum(tr) > 0 else 100
                vip = sum(abs(h[j] - l[j - 1]) for j in range(i - n + 1, i + 1))
                vim = sum(abs(l[j] - h[j - 1]) for j in range(i - n + 1, i + 1))
                rg = {"t": ultima, "px": c[i], "alvo": ultima + 900_000, "chop": round(chop, 1), "acertou": None}
                if chop < lim and vip != vim:
                    rg["aposta"] = "desce" if vip > vim else "sobe"        # invertido
                registros.append(rg)
                mudou = True
            if mudou:
                arq.write_text("\n".join(json.dumps(x) for x in registros[-5000:]) + "\n")
            feitas = [x for x in registros if x.get("aposta") and x.get("resolvida") and x["acertou"] is not None]
            a, t = sum(x["acertou"] for x in feitas), len(feitas)
            if t:
                f = a / t
                z = 1.96
                centro = (f + z * z / (2 * t)) / (1 + z * z / t)
                meia = z * math.sqrt(f * (1 - f) / t + z * z / (4 * t * t)) / (1 + z * z / t)
                ic = [centro - meia, centro + meia]
            else:
                ic = [None, None]
            pend = next((x for x in reversed(registros) if x.get("aposta") and not x.get("resolvida")), None)
            with self.trava:
                self.vortice = {"apostas": t, "acertos": a, "acerto": a / t if t else None, "ic": ic, "desde": registros[0]["t"] if registros else None,
                                "ultima_chop": registros[-1]["chop"] if registros else None,
                                "pendente": pend and {"aposta": pend["aposta"], "px": pend["px"], "alvo": pend["alvo"]},
                                "ultimas": [{"t": x["t"], "aposta": x["aposta"], "acertou": x["acertou"]} for x in feitas[-12:]]}
            self.fonte("vortice", True)
            time.sleep(30)

    def _cerebro(self):
        """Cérebro de day trade. Com CEREBRO_NUVEM=1 (padrão), quem pensa é o GitHub Actions a cada 15 min e aqui só se espelha o
        estado (ramo `estado`). Sem isso, roda aqui mesmo (baleias/cerebro.py), com aquecimento e revivendo pausas."""
        import subprocess
        from lab import tartaruga as T
        from . import cerebro as C
        arq = config.RAIZ / "cerebro.json"
        nuvem = os.environ.get("CEREBRO_NUVEM", "1") == "1"
        repo = str(config.RAIZ.parent)

        def velas(limite=1000, fim=None):
            url = f"{T.DADOS}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit={limite}" + (f"&endTime={fim}" if fim else "")
            with urllib.request.urlopen(url, timeout=30) as r:
                return [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in json.load(r) if x[6] < time.time() * 1000]

        def publicar(cb):
            livro = cb.livro()
            tmp = (config.RAIZ / "livro_metodos.json").with_suffix(".tmp")
            tmp.write_text(json.dumps({"t": time.time(), "metodos": livro}, ensure_ascii=False))
            tmp.replace(config.RAIZ / "livro_metodos.json")
            C.escrever_livro_md(livro, config.RAIZ / "LIVRO_DE_METODOS.md")
            with self.trava:
                self.cerebro = cb.resumo() | {"livro": livro, "onde": "nuvem (GitHub Actions, a cada 15 min)" if nuvem else "esta máquina"}

        visto = None
        while True:
            try:
                if nuvem:
                    subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", "estado"], timeout=60, capture_output=True)
                    r = subprocess.run(["git", "-C", repo, "show", "origin/estado:dados/cerebro.json"], timeout=60, capture_output=True, text=True)
                    if r.returncode == 0 and r.stdout:
                        cb = C.Cerebro(json.loads(r.stdout))
                        if visto is not None:
                            for d in cb.diario[visto:]:
                                if any(m in d["texto"] for m in ("NOVA SINAPSE", "PROMOVIDA", "PODADA", "Teto")):
                                    self.evento({"tipo": "cerebro", "notificar": True, "texto": d["texto"]})
                        visto = len(cb.diario)
                        publicar(cb)
                        r2 = subprocess.run(["git", "-C", repo, "show", "origin/estado:dados/cerebro_v2.json"], timeout=60, capture_output=True, text=True)
                        if r2.returncode == 0 and r2.stdout:
                            v2 = C.CerebroV2(json.loads(r2.stdout))
                            with self.trava:
                                self.cerebro["v2"] = v2.resumo()
                    self.fonte("cerebro", True)
                    time.sleep(120)
                    continue
                cb = C.Cerebro(json.loads(arq.read_text()) if arq.exists() else None)
                if not cb.passos:
                    hist = sorted({x[0]: x for x in velas(1000, int(time.time() * 1000) - 1000 * 900_000) + velas(1000)}.values())
                    C.avancar(cb, hist)
                for texto, notificar in C.avancar(cb, velas(1000)):
                    self.evento({"tipo": "cerebro", "notificar": notificar, "texto": texto})
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(cb.exportar()))
                tmp.replace(arq)
                publicar(cb)
                self.fonte("cerebro", True)
            except (OSError, ValueError, subprocess.SubprocessError) as ex:
                self.fonte("cerebro", False, f"{type(ex).__name__}")
            time.sleep(20)

    def _varredura(self):
        """Varre as 33 moedas sem parar (uma a cada ~1,5 s): preço ao vivo + vela em formação → o cérebro do robô rápido avalia
        (sem registrar), mais distância do rompimento e espaço duplo do Velez. É prévia: a decisão real é no fechamento da vela."""
        from lab import tartaruga as T
        from . import cerebro as C
        i = 0
        while True:
            brutas = getattr(self, "_brutas", {})
            moedas = [m for m in T.MOEDAS_ROBO if m in brutas and len(brutas[m]) >= C.JANELA]
            if not moedas or not self._cbr:
                self.fonte("varredura", True)
                time.sleep(5)
                continue
            m = moedas[i % len(moedas)]
            i += 1
            with self.trava:
                px = self.mercado.get(m[:-4], {}).get("p")
            v = brutas[m]
            if px:
                ult = v[-1]
                agora_ms = int(time.time() * 1000)
                formando = (ult[0] + 300_000, ult[4], max(ult[4], px), min(ult[4], px), px, 0.0)
                janela = (v + [formando])[-C.JANELA:] if agora_ms >= ult[0] + 300_000 else v[-C.JANELA:]
                try:
                    prob, ev, f, ops, lado = self._cbr.avaliar(m, janela)
                except (ValueError, ZeroDivisionError, IndexError):
                    continue
                maxima = max(x[2] for x in v[-T.ENTRADA:])
                linha = {"moeda": m[:-4], "preco": px, "prob": prob, "ev": ev, "lado": lado, "falta": (maxima / px - 1) * 100,
                         "espaco": f.get("espaco", 0.0), "votos": sum(1 for x in ops.values() if x), "t": time.time()}
                sinal = (f"🟢 OPORTUNIDADE de {'COMPRA' if lado == 'compra' else 'VENDA'}") if ev > 0 else ("🔵 espaço duplo" if f.get("espaco") else ("🟡 perto do rompimento" if linha["falta"] < 0.3 else "sem sinal"))
                linha["sinal"] = sinal
                with self.trava:
                    self.varredura["moedas"][m[:-4]] = linha
                    self.varredura["log"].appendleft({"t": time.time(), "texto": f"🔎 {m[:-4]:6} {px:,.6g} | chance de subir em 12 velas: {prob:.1%} | melhor lado: {lado} VE {ev * 100:+.2f}% | "
                                                                             f"rompimento {'ROMPEU' if linha['falta'] <= 0 else f'+{linha['falta']:.2f}%'} | "
                                                                             f"{linha['votos']} sinapses opinaram | {sinal}"})
                    if i % len(moedas) == 0:
                        self.varredura["voltas"] += 1
            self.fonte("varredura", True)
            time.sleep(1.5)

    def _scalper(self):
        """Robô scalper (decisão do dono, 2026-11-11): conta própria de US$ 10, segue as apostas do Cérebro v3 (o aprovado na mesa)
        em cada moeda: entra na direção da aposta da vela de 15 min, realiza o lucro em +0,5%, corta em −0,5% e sai no fim da
        vela apostada. Perpétuo simulado (compra ou vende), US$ 5 por posição com margem 5×.
        Segue as regras da mesa: botão PARAR, perda máxima de US$ 1 no dia e piso de US$ 5."""
        from executor import tartaruga_exec as X
        from . import mesa
        alvo, stop, max_s, orcamento = 0.005, 0.005, 1800, 5.0
        capital = 10.0
        limite_dia, piso = capital * 0.10, capital * 0.50
        parar = Path(X.__file__).resolve().parent.parent / "PARAR"   # o botão geral do dono (o robô rápido usa o PARAR_RAPIDO)
        arq = config.RAIZ / "robo_scalper.json"
        e = json.loads(arq.read_text()) if arq.exists() else X.novo_estado(capital)
        e.setdefault("eventos", [])
        corretora = X.Simulada(None, e)
        e.setdefault("sinais_feitos", [])  # cada aposta do v3 só é seguida uma vez
        visto = time.time()               # última vez que o laço conferiu as posições com o preço ao vivo
        gravado = None

        def ouvir(linha):
            texto = "✂ " + linha["texto"].replace("🐢 Robô ", "Scalper ").replace(" [simulado]", "")
            e["eventos"] = ([{"t": time.time(), "texto": texto}] + e["eventos"])[:100]
            self.evento({"tipo": "scalper", "texto": texto, "notificar": False})

        def sair(m, motivo, px):
            with X.configurado(ouvir, orcamento):
                X._sair(e, corretora, m, motivo, px)

        def perdido(m, p, desde):
            """Máquina dormiu: confere nas velas de 1 min se o alvo ou o stop foi tocado nesse tempo (os dois na mesma vela = stop)."""
            url = f"https://api.binance.com/api/v3/klines?symbol={m}&interval=1m&startTime={int(desde * 1000)}&limit=1000"
            with urllib.request.urlopen(url, timeout=20) as r:
                velas = json.load(r)
            venda = p.get("lado") == "venda"
            alvo_px = p["entrada"] * (1 - alvo if venda else 1 + alvo)
            stop_px = p["entrada"] * (1 + stop if venda else 1 - stop)
            for k in velas:
                t, o, h, l = k[0] / 1000, float(k[1]), float(k[2]), float(k[3])
                if t >= p.get("fim_t", p["entrada_t"] + max_s):
                    return "fim da vela do v3 (máquina desligada)", o
                if (h >= stop_px) if venda else (l <= stop_px):
                    return "stop −0,5% (máquina desligada)", (max(o, stop_px) if venda else min(o, stop_px))
                if (l <= alvo_px) if venda else (h >= alvo_px):
                    return "lucro realizado +0,5% (máquina desligada)", alvo_px
            return None, None

        def gelada(m):
            """Geladeira do próprio scalper: 3 perdas seguidas na moeda nas últimas 12 h = fica de fora até passar."""
            ult = [f for f in e["fechadas"] if f.get("moeda", f.get("m")) == m and time.time() - f["saida_t"] < 12 * 3600][-3:]
            return len(ult) == 3 and all(f["resultado_usd"] < 0 for f in ult)

        while True:
            with self.trava:
                precos = {f"{k}USDT": x["p"] for k, x in self.mercado.items()}
            agora = time.time()
            if agora - visto > 60:                             # a máquina parou: julgar o que aconteceu enquanto isso
                for m in list(e["abertas"]):
                    try:
                        motivo, px = perdido(m, e["abertas"][m], visto)
                    except (OSError, ValueError):
                        continue
                    if motivo:
                        sair(m, motivo, px)
            visto = agora
            for m in list(e["abertas"]):                      # saídas de scalper, conferidas a cada 3 s com o preço ao vivo
                p, px = e["abertas"][m], precos.get(m)
                if px is None:
                    continue
                sinal = -1 if p.get("lado") == "venda" else 1
                ganho = sinal * (px / p["entrada"] - 1)
                motivo = ("lucro realizado +0,5%" if ganho >= alvo else "stop −0,5%" if ganho <= -stop
                          else "fim da vela do v3" if agora >= p.get("fim_t", p["entrada_t"] + max_s) else None)
                if motivo:
                    sair(m, motivo, px)
            hoje = time.strftime("%Y-%m-%d", time.gmtime(agora))
            aberto = sum(X._valor(p, precos.get(m, p["entrada"])) - p["gasto"] for m, p in e["abertas"].items())
            resultado_hoje = sum(f["resultado_usd"] for f in e["fechadas"] if time.strftime("%Y-%m-%d", time.gmtime(f["saida_t"])) == hoje) + aberto
            patrimonio = X.patrimonio(e, precos, corretora)
            trava = ("botão PARAR ligado" if parar.exists() else
                     f"perda do dia {resultado_hoje:+.2f} (limite −{limite_dia:.2f})" if resultado_hoje <= -limite_dia else
                     f"conta abaixo de US$ {piso:.0f}" if patrimonio < piso else None)
            if trava and e.get("trava") != f"{hoje} {trava}":
                ouvir({"texto": f"🛑 Scalper sem novas entradas: {trava}. As saídas continuam."})
            e["trava"] = f"{hoje} {trava}" if trava else None
            try:
                sinais = mesa.sinais_v3()
            except (OSError, ValueError, subprocess.SubprocessError):
                sinais = []
            for s in sorted(sinais, key=lambda s: -abs(s["prob"] - 0.5)):   # as apostas mais confiantes primeiro
                m, chave = s["par"], f"{s['par']}@{s['t']}"
                inicio, fim = s["t"] / 1000 + 900, s["t"] / 1000 + 1800       # a vela apostada: do fechamento da vela t até o da seguinte
                if chave in e["sinais_feitos"] or not (inicio <= agora <= fim - 120):
                    continue
                if (trava or gelada(m) or m in e["abertas"] or m not in precos or lado_cheio(e["abertas"], s["lado"])
                        or e["caixa"] < orcamento / X.ALAV_PERP):
                    continue
                e["sinais_feitos"] = (e["sinais_feitos"] + [chave])[-500:]
                andou = (precos[m] / s["px"] - 1) * (1 if s["lado"] == "compra" else -1)
                if andou >= alvo / 2:                                        # o movimento já aconteceu: não entra atrasado
                    continue
                n_scalper = precos[m] * stop / 2                             # o stop do executor é 2N: assim fica exatamente a 0,5%
                with X.configurado(ouvir, orcamento):
                    X.entrar(e, corretora, m, precos[m], n_scalper,
                             f"Cérebro v3 aposta {'▲ sobe' if s['lado'] == 'compra' else '▼ desce'} ({max(s['prob'], 1 - s['prob']):.1%}); lucro em +0,5% / stop −0,5%",
                             lado=s["lado"], custo_lado=0.0005)
                if m in e["abertas"]:
                    e["abertas"][m]["fim_t"] = fim
            e["patrimonio"] = patrimonio = X.patrimonio(e, precos, corretora)
            mudou = (len(e["fechadas"]), tuple(e["abertas"]), e["trava"])
            if mudou != gravado or int(agora) % 60 < 3:      # grava ao abrir/fechar posição e, fora isso, 1 vez por minuto
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(e))
                tmp.replace(arq)
                gravado = mudou
            rs = e["fechadas"]
            with self.trava:
                self.scalper = {"patrimonio": patrimonio, "resultado_hoje": resultado_hoje, "trava": trava,
                                "abertas": [{"moeda": m[:-4], "lado": p.get("lado"), "entrada": p["entrada"],
                                             "resultado": X._valor(p, precos.get(m, p["entrada"])) - p["gasto"]} for m, p in e["abertas"].items()],
                                "fechadas": len(rs), "ganhos": sum(1 for f in rs if f["resultado_usd"] > 0), "eventos": e["eventos"][:12]}
            self.fonte("scalper", True)
            time.sleep(3)

    def _gravador(self):
        """A cada 5 min grava, das 33 moedas do robô, o topo do livro, o open interest e o funding do perpétuo (dados que a Binance
        não guarda de graça para trás). Base para testar as medidas 4, 7, 8 e 11 do estudo de previsibilidade. Arquivo por dia."""
        from lab import tartaruga as T
        pasta = config.RAIZ / "gravacao"
        pasta.mkdir(exist_ok=True)
        base = "https://fapi.binance.com/fapi/v1"
        while True:
            with urllib.request.urlopen(f"{base}/ticker/bookTicker", timeout=20) as r:
                livro = {x["symbol"]: x for x in json.load(r)}
            with urllib.request.urlopen(f"{base}/premiumIndex", timeout=20) as r:
                indice = {x["symbol"]: x for x in json.load(r)}
            t = int(time.time())
            linhas = []
            for par in T.MOEDAS_ROBO:
                b, i = livro.get(par), indice.get(par)
                if not b:
                    continue                                  # moeda sem perpétuo na Binance
                try:
                    with urllib.request.urlopen(f"{base}/openInterest?symbol={par}", timeout=20) as r:
                        oi = float(json.load(r)["openInterest"])
                except (OSError, ValueError, KeyError):
                    oi = None
                linhas.append({"t": t, "par": par, "bid": float(b["bidPrice"]), "ask": float(b["askPrice"]), "bq": float(b["bidQty"]),
                               "aq": float(b["askQty"]), "oi": oi, "funding": i and float(i["lastFundingRate"]), "marca": i and float(i["markPrice"])})
                time.sleep(0.1)
            with open(pasta / time.strftime("%Y-%m-%d.jsonl", time.gmtime(t)), "a") as f:
                f.writelines(json.dumps(x) + "\n" for x in linhas)
            if t // 3600 != getattr(self, "_mineracao_h", None):          # 1 vez por hora: dados dos mineradores (filtro lento, H26/estudo)
                self._mineracao_h = t // 3600
                try:
                    with urllib.request.urlopen("https://mempool.space/api/v1/difficulty-adjustment", timeout=20) as r:
                        dif = json.load(r)
                    with urllib.request.urlopen("https://mempool.space/api/v1/mining/hashrate/1w", timeout=20) as r:
                        hr = json.load(r)
                    with urllib.request.urlopen("https://mempool.space/api/v1/fees/recommended", timeout=20) as r:
                        taxas = json.load(r)
                    with open(pasta / "mineracao.jsonl", "a") as f:
                        f.write(json.dumps({"t": t, "hashrate_ehs": hr["currentHashrate"] / 1e18, "dificuldade": hr["currentDifficulty"],
                                            "ajuste_previsto_pct": dif["difficultyChange"], "progresso_pct": dif["progressPercent"],
                                            "taxa_rapida_sat_vb": taxas["fastestFee"]}) + "\n")
                except (OSError, ValueError, KeyError):
                    pass
            self.fonte("gravador", True)
            dormir(300 - time.time() % 300)

    def _telegram(self):
        while True:
            time.sleep(20)
            with self.trava:
                lote, self.pendentes = self.pendentes[:10], self.pendentes[10:]
            if lote:
                self.enviar("\n\n".join(lote) + "\n\nTeste, não recomendação.")

    def iniciar(self):
        for nome, f, laco in (("binance", self._binance_spot, True), ("liquidacoes", self._binance_futuros, True),
                              ("hyperliquid", self._hyperliquid, True), ("livro", self._livro, True),
                              ("robo", self._robo, True), ("b3", self._b3, True), ("leitura", self._leitura, True), ("tartaruga", self._tartaruga, True), ("rapido", self._robo_rapido, True), ("mapa", self._mapa, True), ("vortice", self._vortice, True), ("cerebro", self._cerebro, True), ("varredura", self._varredura, True), ("scalper", self._scalper, True), ("gravador", self._gravador, True), ("telegram", self._telegram, False)):
            alvo = (lambda n=nome, fn=f: self._laco(n, fn)) if laco else f
            threading.Thread(target=alvo, name=f"tr-{nome}", daemon=True).start()
        return self
