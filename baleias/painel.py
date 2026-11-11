"""Painel local, só de leitura, no estilo terminal (ideia do OpenTerminal: widgets densos, tema escuro, atualização contínua).

Escuta só em 127.0.0.1. O banco é aberto em modo somente leitura.
"""
import json
import os
import time
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import banco, config
from .aprendizado import Modelo, media_ic

FONTE = "ao_vivo"
HTML = Path(__file__).with_name("painel.html")
HTML_AO_VIVO = Path(__file__).with_name("ao_vivo.html")
HTML_TERMINAL = Path(__file__).with_name("terminal.html")


def abrir_leitura(caminho=None):
    caminho = caminho or config.BANCO
    c = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _ic(valores):
    r = media_ic(valores)
    return r and {k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()}


def estado(c, fonte=FONTE):
    linhas = c.execute(
        "SELECT s.id, s.carteira, s.moeda, s.lado, s.tipo, s.nocional, s.t_sinal_ms, s.px_entrada, s.previsto, s.desvio, s.aprovado, s.alertado, "
        "r.liquido, r.controle_liquido, r.classe, r.px_saida FROM sinais s LEFT JOIN resultados r ON r.sinal_id=s.id WHERE s.fonte=? ORDER BY s.t_sinal_ms",
        (fonte,)).fetchall()
    resolvidos = [x for x in linhas if x["liquido"] is not None]
    aprovados = [x for x in resolvidos if x["aprovado"]]
    metade = len(resolvidos) // 2
    pct = lambda ls, k: [x[k] * 100 for x in ls]
    erros = [abs(x["previsto"] - x["liquido"] * 100) for x in resolvidos]
    classes = {}
    for x in resolvidos:
        classes[x["classe"]] = classes.get(x["classe"], 0) + 1
    r = c.execute("SELECT estado FROM modelo WHERE fonte=?", (fonte,)).fetchone()
    modelo = Modelo.de_json(r["estado"]) if r else Modelo()
    carteiras = []
    for w in c.execute("SELECT * FROM carteiras ORDER BY ativa DESC, nota DESC"):
        meus = [x for x in linhas if x["carteira"] == w["carteira"]]
        feitos = [x["liquido"] * 100 for x in meus if x["liquido"] is not None]
        p = modelo.peso(f"carteira:{w['carteira']}")
        carteiras.append({"carteira": w["carteira"], "ativa": bool(w["ativa"]), "conta": w["conta"], "sinais": len(meus),
                          "resolvidos": len(feitos), "media": round(sum(feitos) / len(feitos), 4) if feitos else None,
                          "peso": p and [round(p[0], 4), round(p[1], 4)], "motivo_saida": w["motivo_saida"]})
    licoes = [dict(l) for l in c.execute("SELECT caracteristica, efeito, n, media, baixo, alto FROM licoes WHERE fonte=? ORDER BY ABS(media) DESC", (fonte,))]
    noticias = [dict(n) for n in c.execute(
        "SELECT n.moeda, n.titulo, n.fonte, n.link, n.t_ms, n.sinal_id FROM noticias n JOIN sinais s ON s.id=n.sinal_id WHERE s.fonte=? "
        "ORDER BY n.t_ms DESC LIMIT 25", (fonte,))]
    rastros = [dict(r) for r in c.execute(
        "SELECT r.sinal_id, r.evento, r.t_ms, s.moeda, s.lado, s.carteira FROM rastros r JOIN sinais s ON s.id=r.sinal_id WHERE s.fonte=? "
        "ORDER BY r.t_ms DESC LIMIT 25", (fonte,))]
    ins = [dict(x) for x in c.execute(
        "SELECT s.acesso, s.data, s.ticker, s.cargo, s.valor, s.preco, s.previsto, s.desvio, s.aprovado, r.excesso, r.bruto, r.spy "
        "FROM insider_sinais s LEFT JOIN insider_resultados r ON r.acesso=s.acesso ORDER BY s.t_ms DESC LIMIT 40")]
    feitos = [x["excesso"] * 100 for x in c.execute("SELECT excesso FROM insider_resultados")]
    from . import previsao_vivo
    try:
        ops = [dict(x) for x in c.execute("SELECT modo, COALESCE(lado,'compra') lado, prob, t_compra, px_compra, t_venda, px_venda, resultado_usdt FROM robo_operacoes ORDER BY id DESC LIMIT 30")]
        tot = {m: c.execute("SELECT COUNT(*), COALESCE(SUM(resultado_usdt),0), SUM(resultado_usdt>0) FROM robo_operacoes WHERE modo=? AND t_venda IS NOT NULL", (m,)).fetchone()
               for m in ("simulado", "real")}
        est = c.execute("SELECT t_ms, msg FROM robo_estado WHERE id=1").fetchone() if c.execute("SELECT 1 FROM sqlite_master WHERE name='robo_estado'").fetchone() else None
        try:
            from executor import adaptativo
            versoes = adaptativo.painel(c)
        except Exception:
            versoes = []
        robo = {"versoes": versoes, "estado": dict(est) if est else None, "operacoes": ops, "totais": {m: {"n": t[0], "usdt": round(t[1], 4), "ganhos": t[2] or 0} for m, t in tot.items()}}
    except sqlite3.OperationalError:
        robo = {"operacoes": [], "totais": {}}
    from lab import ao_vivo
    try:
        fr = c.execute("SELECT estado FROM lab_funding WHERE id=1").fetchone()
        funding = json.loads(fr["estado"]) if fr else None
    except sqlite3.OperationalError:
        funding = None
    from lab import generativa
    from . import saude
    return {
        "servicos": saude.estado(c),
        "generativa": generativa.resumo(c),
        "generativa_v2": generativa.resumo(c, "llm_previsoes_v2"),
        "funding": funding,
        "tendencia": ao_vivo.resumo(c),
        "robo": robo,
        "previsao": previsao_vivo.resumo(c),
        "insider": {"compras": ins, "total": c.execute("SELECT COUNT(*) FROM insider_sinais").fetchone()[0],
                    "resolvidas": len(feitos), "excesso": _ic(feitos)},
        "noticias": noticias,
        "rastros": rastros,
        "resumo": {"sinais": len(linhas), "resolvidos": len(resolvidos), "aprovados_resolvidos": len(aprovados),
                   "aprendidos": modelo.n, "todos": _ic(pct(resolvidos, "liquido")), "controle": _ic(pct(resolvidos, "controle_liquido")),
                   "aprovados": _ic(pct(aprovados, "liquido")), "primeira_metade": _ic(pct(resolvidos[:metade], "liquido")),
                   "segunda_metade": _ic(pct(resolvidos[metade:], "liquido"))},
        "protocolo": {"para_alertar": [len(resolvidos), config.SINAIS_PARA_ALERTAR], "aprovados_para_testar": [len(aprovados), 100],
                      "para_decidir": [len(resolvidos), 300]},
        "curva_erro": [round(e, 4) for e in erros],
        "curva_resultado": [round(x["liquido"] * 100, 4) for x in resolvidos],
        "classes": classes,
        "licoes": licoes,
        "carteiras": carteiras,
        "sinais": [{k: x[k] for k in x.keys()} | {"liquido": x["liquido"] and round(x["liquido"] * 100, 4)} for x in linhas[-60:][::-1]],
    }


class Manipulador(BaseHTTPRequestHandler):
    conexao = None
    motor = None

    def _enviar(self, codigo, corpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://unpkg.com/lightweight-charts@4.2.3/")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/estado":
            self._enviar(200, json.dumps(estado(self.conexao)).encode(), "application/json")
        elif self.path.startswith("/api/ao-vivo"):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            num = lambda k: int(q.get(k, ["0"])[0] or 0)
            corpo = self.motor.instantaneo(num("desde"), num("calor")) if self.motor else {"erro": "motor desligado"}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path == "/ao-vivo":
            self._enviar(200, HTML_AO_VIVO.read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/api/robo"):
            from . import terminal_api
            vivos = {}
            if self.motor:
                with self.motor.trava:
                    vivos = {k: v["p"] for k, v in self.motor.mercado.items()}
            self._enviar(200, json.dumps(terminal_api.robo(vivos)).encode(), "application/json")
        elif self.path.startswith("/api/velas?"):
            from . import terminal_api
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            self._enviar(200, json.dumps(terminal_api.velas(q.get("m", ["BTC"])[0][:12])).encode(), "application/json")
        elif self.path.startswith("/api/backtest"):
            from . import terminal_api
            self._enviar(200, json.dumps(terminal_api.backtest()).encode(), "application/json")
        elif self.path.startswith("/api/velas-rapidas"):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            iv = q.get("iv", ["1h"])[0]
            iv = iv if iv in ("1m", "5m", "15m", "1h", "4h", "1d") else "5m"
            try:
                corpo = self.motor.velas_ao_vivo(q.get("m", ["BTC"])[0], iv) if self.motor else {"erro": "motor desligado"}
            except Exception as e:
                corpo = {"erro": type(e).__name__}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/rapido"):
            corpo = self.motor.rapido if self.motor and self.motor.rapido else {"carregando": True}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/replay"):
            from . import terminal_api
            self._enviar(200, json.dumps(terminal_api.replay()).encode(), "application/json")
        elif self.path.startswith("/api/scalper"):
            corpo = self.motor.scalper if self.motor and self.motor.scalper else {"carregando": True}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/varredura"):
            if self.motor:
                with self.motor.trava:
                    corpo = {"moedas": list(self.motor.varredura["moedas"].values()), "log": list(self.motor.varredura["log"])[:25],
                             "voltas": self.motor.varredura["voltas"], "agora": time.time()}
            else:
                corpo = {"moedas": [], "log": []}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/mesa"):
            from . import mesa
            try:
                corpo = mesa.mesa()
            except Exception as e:                         # rede/git fora do ar: responde o erro em vez de derrubar a conexão
                corpo = {"erro": type(e).__name__}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/realizados"):
            from . import mesa
            try:
                corpo = mesa.realizados()
            except Exception as e:                         # rede/git fora do ar: responde o erro em vez de derrubar a conexão
                corpo = {"erro": type(e).__name__}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/moedas-cerebros"):
            from . import mesa
            try:
                corpo = mesa.cerebros_por_moeda()
            except Exception as e:                         # rede/git fora do ar: responde o erro em vez de derrubar a conexão
                corpo = {"erro": type(e).__name__}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/cerebro"):
            corpo = self.motor.cerebro if self.motor and self.motor.cerebro else {"carregando": True}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/vortice"):
            corpo = self.motor.vortice if self.motor and self.motor.vortice else {"carregando": True}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/mapa"):
            corpo = self.motor.mapa if self.motor and self.motor.mapa else {"carregando": True}
            self._enviar(200, json.dumps(corpo).encode(), "application/json")
        elif self.path.startswith("/api/funding"):
            from . import terminal_api
            self._enviar(200, json.dumps(terminal_api.funding()).encode(), "application/json")
        elif self.path.startswith("/api/lab"):
            from . import terminal_api
            self._enviar(200, json.dumps(terminal_api.lab()).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._enviar(200, HTML_TERMINAL.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/baleias":
            self._enviar(200, HTML.read_bytes(), "text/html; charset=utf-8")
        else:
            self._enviar(404, b"{}", "application/json")

    def log_message(self, *a):
        pass


def servir(porta=8787):
    banco.abrir().close()  # garante que o esquema existe antes de abrir só leitura
    Manipulador.conexao = abrir_leitura()
    if os.environ.get("BALEIAS_SEM_TEMPO_REAL") != "1":
        from .tempo_real import Motor
        Manipulador.motor = Motor(abrir=abrir_leitura).iniciar()
    ThreadingHTTPServer(("127.0.0.1", porta), Manipulador).serve_forever()
