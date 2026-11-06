"""Estratégia (revisada em 2026-11-06 depois da pesquisa em executor/pesquisa.py): prevê o RETORNO de 15 min e só compra quando
o modelo prova, fora da amostra, que prevê melhor que o acaso (R² > 0) e a previsão pessimista passa do custo. Vende 15 min depois.
Travas: US$ 10 por operação, uma posição por vez, perda máxima no dia, arquivo PARAR."""
import json
import math
import os
import sqlite3
import time
from datetime import date
from pathlib import Path

from baleias import config
from .binance import Binance, verificar_chave

SIMBOLO = "BTCUSDT"
VALOR_USDT = float(os.environ.get("ROBO_VALOR_USDT", "10"))
PERDA_DIA_MAXIMA = float(os.environ.get("ROBO_PERDA_DIA", "2"))
STOP_PCT = float(os.environ.get("ROBO_STOP_PCT", "0.5"))  # vende se cair isto (%) desde a compra
SEGURAR_S = 15 * 60
TAXA_SUPOSTA = 0.001  # taxa padrão da Binance spot; no modo real é lida da conta
PARAR = Path(__file__).resolve().parent.parent / "PARAR"

ESQUEMA = """CREATE TABLE IF NOT EXISTS robo_operacoes(
  id INTEGER PRIMARY KEY, modo TEXT, previsao_id INTEGER UNIQUE, prob REAL, t_compra INTEGER, px_compra REAL, qtd REAL, custo_compra REAL,
  t_venda INTEGER, px_venda REAL, receita_venda REAL, resultado_usdt REAL, detalhe TEXT, braco TEXT, segurar_min INTEGER, lado TEXT)"""


def real():
    return os.environ.get("BINANCE_REAL") == "1"


def abrir():
    from . import adaptativo
    c = sqlite3.connect(config.BANCO)
    c.row_factory = sqlite3.Row
    c.execute(ESQUEMA)
    for col in ("braco TEXT", "segurar_min INTEGER", "lado TEXT"):
        try:
            c.execute(f"ALTER TABLE robo_operacoes ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    c.executescript(adaptativo.ESQUEMA)
    return c


def resultado_hoje(c, modo):
    inicio = int(time.mktime(date.today().timetuple()) * 1000)
    return c.execute("SELECT COALESCE(SUM(resultado_usdt),0) FROM robo_operacoes WHERE modo=? AND t_venda>=?", (modo, inicio)).fetchone()[0]


def decidir(sinal, custo_pct, perda_hoje, aberta, parar):
    """Regra pura (testável): devolve o motivo de não comprar, ou None para comprar."""
    if parar:
        return "arquivo PARAR presente"
    if aberta:
        return "já existe posição aberta"
    if perda_hoje <= -PERDA_DIA_MAXIMA:
        return f"perda do dia atingiu US$ {PERDA_DIA_MAXIMA}"
    # Travas de evidência e de custo removidas a pedido do dono em 2026-11-06: compra sempre que o modelo prevê alta.
    if sinal is None:
        return "sem previsão recente"
    return None


def passo(c, b, sinal_vivo, agora_s=None):
    agora_s = agora_s or time.time()
    from . import adaptativo
    s = sinal_vivo.atualizar() if sinal_vivo else None
    if s and agora_s * 1000 - s["t_ms"] > 150_000:
        s = None  # previsão velha não vale
    if s:
        # O aprendizado registra a oportunidade mesmo com posição aberta: aprende com todas, não só com as que executou.
        adaptativo.registrar_oportunidade(c, s["t_ms"], s["px"], s["media"])
    modo = "real" if real() else "simulado"
    aberta = c.execute("SELECT * FROM robo_operacoes WHERE modo=? AND t_venda IS NULL", (modo,)).fetchone()
    motivo_venda = None
    if aberta:
        bid, ask = b.livro(SIMBOLO)
        vendido = aberta["lado"] == "venda"
        if vendido and ask >= aberta["px_compra"] * (1 + STOP_PCT / 100):
            motivo_venda = f"stop de {STOP_PCT}%"
        elif not vendido and bid <= aberta["px_compra"] * (1 - STOP_PCT / 100):
            motivo_venda = f"stop de {STOP_PCT}%"
        elif agora_s * 1000 - aberta["t_compra"] >= (aberta["segurar_min"] or SEGURAR_S // 60) * 60_000:
            motivo_venda = f"{aberta['segurar_min'] or SEGURAR_S // 60} min"
    if motivo_venda and aberta["lado"] == "venda":
        # Só existe no simulado: recompra no preço de venda do livro (ask), pagando a taxa nas duas pontas.
        resultado = aberta["qtd"] * (aberta["px_compra"] * (1 - TAXA_SUPOSTA) - ask * (1 + TAXA_SUPOSTA))
        c.execute("UPDATE robo_operacoes SET t_venda=?, px_venda=?, receita_venda=?, resultado_usdt=? WHERE id=?",
                  (int(agora_s * 1000), ask, aberta["custo_compra"] + resultado, resultado, aberta["id"]))
        c.commit()
        return f"zerou a venda ({motivo_venda}): {resultado:+.4f} USDT"
    if motivo_venda:
        if modo == "real":
            o = b.vender_quantidade(SIMBOLO, aberta["qtd"])
            receita = float(o["cummulativeQuoteQty"]) - sum(float(f["commission"]) for f in o.get("fills", []) if f["commissionAsset"] == "USDT")
            px = receita / aberta["qtd"]
            detalhe = json.dumps(o)[:2000]
        else:
            px = bid
            receita = aberta["qtd"] * bid * (1 - TAXA_SUPOSTA)
            detalhe = None
        c.execute("UPDATE robo_operacoes SET t_venda=?, px_venda=?, receita_venda=?, resultado_usdt=?, detalhe=COALESCE(detalhe,'')||? WHERE id=?",
                  (int(agora_s * 1000), px, receita, receita - aberta["custo_compra"], detalhe or "", aberta["id"]))
        c.commit()
        return f"vendeu ({motivo_venda}): {receita - aberta['custo_compra']:+.4f} USDT"
    motivo = decidir(s, 2 * TAXA_SUPOSTA * 100, resultado_hoje(c, modo), aberta is not None, PARAR.exists())
    if motivo:
        return motivo
    braco = adaptativo.escolher(c, s["media"])
    if braco is None:
        return f"aprendizado escolheu NÃO operar agora (previsto {s['media']:+.3f}%)"
    lado, _, segurar = adaptativo.parametros(braco)
    if lado == "venda" and modo == "real":
        return "venda na queda só no simulado (falta conta de margem/futuros liberada)"
    previsao = {"id": s["t_ms"], "prob_alta": s["media"]}
    if c.execute("SELECT 1 FROM robo_operacoes WHERE previsao_id=?", (previsao["id"],)).fetchone():
        return "previsão já usada"
    bid, ask = b.livro(SIMBOLO)
    if lado == "venda":
        qtd = math.floor(VALOR_USDT / bid * 1e5) / 1e5
        c.execute("INSERT INTO robo_operacoes(modo,previsao_id,prob,t_compra,px_compra,qtd,custo_compra,braco,segurar_min,lado) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (modo, s["t_ms"], s["media"], int(agora_s * 1000), bid, qtd, qtd * bid, braco, segurar, "venda"))
        c.commit()
        return f"vendeu na queda {qtd} BTC a {bid:.2f} (previsto {s['media']:+.3f}%, versão {braco})"
    if modo == "real":
        o = b.comprar_em_usdt(SIMBOLO, VALOR_USDT)
        bruto = float(o["executedQty"])
        taxa_btc = sum(float(f["commission"]) for f in o.get("fills", []) if f["commissionAsset"] == "BTC")
        qtd = math.floor((bruto - taxa_btc) * 1e5) / 1e5
        custo = float(o["cummulativeQuoteQty"])
        px = custo / bruto
        detalhe = json.dumps(o)[:2000]
    else:
        # Igual à Binance: a ordem compra o múltiplo de 0,00001 BTC que cabe nos US$ e cobra só por ele;
        # a taxa sai do BTC recebido. (Antes o custo era sempre US$ 10 cheios: cada operação "perdia" o arredondamento.)
        px = ask
        bruto = math.floor(VALOR_USDT / ask * 1e5) / 1e5
        qtd = bruto * (1 - TAXA_SUPOSTA)
        custo = bruto * ask
        detalhe = None
    c.execute("INSERT INTO robo_operacoes(modo,previsao_id,prob,t_compra,px_compra,qtd,custo_compra,detalhe,braco,segurar_min,lado) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (modo, previsao["id"], previsao["prob_alta"], int(agora_s * 1000), px, qtd, custo, detalhe, braco, segurar, "compra"))
    c.commit()
    return f"comprou {qtd} BTC a {px:.2f} (previsto {previsao['prob_alta']:+.3f}%, versão {braco})"


def rodar():
    b = Binance()
    if real():
        problemas = verificar_chave(b)
        if any("SAQUE" in p or "não permite" in p for p in problemas):
            raise SystemExit("recusado: " + "; ".join(problemas))
        for p in problemas:
            print("aviso:", p, flush=True)
        global TAXA_SUPOSTA
        TAXA_SUPOSTA = b.taxa(SIMBOLO)
        print(f"modo REAL, taxa da conta {TAXA_SUPOSTA:.4%}, US$ {VALOR_USDT} por operação", flush=True)
    else:
        print("modo SIMULADO (preços reais da Binance, sem ordens)", flush=True)
    c = abrir()
    from .sinal import SinalVivo
    print("aquecendo o modelo com 3 dias de velas de 1 min…", flush=True)
    sinal_vivo = SinalVivo()
    ultimo = None
    while True:
        try:
            from . import adaptativo
            adaptativo.resolver(c, STOP_PCT, 2 * TAXA_SUPOSTA * 100)
        except Exception as e:
            print("aprendizado falhou:", type(e).__name__, str(e)[:150], flush=True)
        try:
            msg = passo(c, b, sinal_vivo)
        except Exception as e:
            msg = f"erro: {type(e).__name__}: {str(e)[:200]}"
        c.execute("CREATE TABLE IF NOT EXISTS robo_estado(id INTEGER PRIMARY KEY CHECK(id=1), t_ms INTEGER, msg TEXT)")
        c.execute("INSERT INTO robo_estado VALUES(1, ?, ?) ON CONFLICT(id) DO UPDATE SET t_ms=excluded.t_ms, msg=excluded.msg", (int(time.time() * 1000), msg))
        c.commit()
        from baleias import saude
        saude.bater(c, "robo", msg)
        if msg != ultimo:
            print(time.strftime("%F %T"), msg, flush=True)
            ultimo = msg
        time.sleep(20)


if __name__ == "__main__":
    rodar()
