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
import os
import threading
import time
import urllib.request

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
        ws.s.settimeout(600)   # liquidações podem ficar minutos sem acontecer; a Binance manda ping a cada ~3 min
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
            time.sleep(300 - time.time() % 300)
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
                with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={m}&interval={intervalo}&limit=81", timeout=20) as r:
                    k = json.load(r)
            except OSError:
                continue
            saida[m] = [[time.strftime("%Y-%m-%d %H:%M", time.gmtime(x[0] / 1000)), float(x[1]), float(x[2]), float(x[3]), float(x[4])]
                        for x in k if x[6] < agora_ms]
            time.sleep(0.05)
        return saida

    def _robo_rapido(self):
        """Teste ao vivo, simulado: as mesmas regras da Tartaruga em velas curtas (ROBO_RAPIDO=1h por padrão), para operar no dia.
        Decide a cada vela fechada; stop conferido a cada 5 s com o preço ao vivo. Não usa dinheiro real."""
        from lab import tartaruga as T
        from executor import tartaruga_exec as X
        intervalo = os.environ.get("ROBO_RAPIDO", "5m")
        passo = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}[intervalo]
        limite_dia = float(os.environ.get("ROBO_RAPIDO_PERDA_DIA", "100"))      # teto de perda por dia (US$), pedido do dono
        X.PARAR = config.RAIZ / "PARAR_RAPIDO"                                # neste processo só o robô rápido usa o tartaruga_exec
        arq = config.RAIZ / f"robo_rapido_{intervalo}.json"
        e = json.loads(arq.read_text()) if arq.exists() else X.novo_estado(700.0)
        e.setdefault("eventos", [])
        corretora = X.Simulada(None, e)

        def ouvir(linha):
            texto = "⚡ " + linha["texto"].replace("🐢 Robô ", "Robô rápido ").replace(" [simulado]", "")
            e["eventos"] = ([{"t": linha["t"], "texto": texto}] + e["eventos"])[:100]
            self.evento({"tipo": "rapido", "texto": texto, "notificar": True})
        X.ouvinte = ouvir                       # neste processo o tartaruga_exec só é usado pelo robô rápido
        dados = {}
        while True:
            with self.trava:
                precos = {f"{s}USDT": x["p"] for s, x in self.mercado.items()}
            agora = time.time()
            ultima_fechada = time.strftime("%Y-%m-%d %H:%M", time.gmtime(agora - agora % passo - passo))
            if precos:
                hoje = time.strftime("%Y-%m-%d", time.gmtime(agora))
                fechado_hoje = sum(f["resultado_usd"] for f in e["fechadas"] if time.strftime("%Y-%m-%d", time.gmtime(f["saida_t"])) == hoje)
                aberto = sum(p["qtd"] * precos.get(m, p["entrada"]) - p["gasto"] for m, p in e["abertas"].items())
                travado = fechado_hoje + aberto <= -limite_dia
                if travado and not X.PARAR.exists():
                    X.PARAR.touch()
                    ouvir({"t": agora, "texto": f"🛑 Teto do dia atingido: {fechado_hoje + aberto:+.2f} USDT hoje. Sem novas entradas até 00:00 UTC (stops seguem)."})
                elif not travado and X.PARAR.exists() and e.get("dia_trava") != hoje:
                    X.PARAR.unlink()
                if travado:
                    e["dia_trava"] = hoje
                e["resultado_hoje"] = fechado_hoje + aberto
            if precos and e.get("ultima_vela") != ultima_fechada and agora % passo > 15:
                dados = self._velas_rapidas(intervalo, T.MOEDAS_ROBO)
                X.passo_diario(e, corretora, dados, precos)
                for p in e["abertas"].values():
                    p.setdefault("conferido_ate", ultima_fechada)
                e["ultima_vela"] = ultima_fechada
            if precos:
                X.checar_stops(e, corretora, precos)
                e["patrimonio"] = X.patrimonio(e, precos, corretora)
                if dados:
                    e["radar"] = X.radar(dados, precos)
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(e))
                tmp.replace(arq)
                rs = [f["R"] for f in e["fechadas"]]
                with self.trava:
                    self.rapido = {"intervalo": intervalo, "patrimonio": e["patrimonio"], "resultado_hoje": e.get("resultado_hoje", 0.0),
                                   "limite_dia": limite_dia, "travado": X.PARAR.exists(), "inicio": e["inicio"], "ultima_vela": e.get("ultima_vela"),
                                   "proxima": agora - agora % passo + passo + 15,
                                   "posicoes": [{"moeda": m[:-4], "entrada": p["entrada"], "stop": p["stop"], "preco": precos.get(m),
                                                 "resultado": p["qtd"] * precos.get(m, p["entrada"]) - p["gasto"]} for m, p in e["abertas"].items()],
                                   "operacoes": len(rs), "acerto": sum(r > 0 for r in rs) / len(rs) if rs else None,
                                   "media_R": sum(rs) / len(rs) if rs else None, "eventos": e["eventos"][:30],
                                   "radar": e.get("radar", [])[:8], "todas": sorted(m[:-4] for m in T.MOEDAS_ROBO)}
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
            time.sleep(1800)

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
                              ("robo", self._robo, True), ("b3", self._b3, True), ("leitura", self._leitura, True), ("tartaruga", self._tartaruga, True), ("rapido", self._robo_rapido, True), ("mapa", self._mapa, True), ("telegram", self._telegram, False)):
            alvo = (lambda n=nome, fn=f: self._laco(n, fn)) if laco else f
            threading.Thread(target=alvo, name=f"tr-{nome}", daemon=True).start()
        return self
