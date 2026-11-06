"""Estratégia: segue a previsão de 5 min do BTC. Spot não vende a descoberto, então só compra quando a previsão de alta é forte
e vende 5 minutos depois. Travas: US$ 10 por operação, uma posição por vez, perda máxima no dia, arquivo PARAR."""
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
PROB_MINIMA = float(os.environ.get("ROBO_PROB_MINIMA", "0.60"))
APRENDIZADO_MINIMO = int(os.environ.get("ROBO_APRENDIZADO_MINIMO", "300"))
PERDA_DIA_MAXIMA = float(os.environ.get("ROBO_PERDA_DIA", "2"))
SEGURAR_S = 5 * 60
TAXA_SUPOSTA = 0.001  # taxa padrão da Binance spot; no modo real é lida da conta
PARAR = Path(__file__).resolve().parent.parent / "PARAR"

ESQUEMA = """CREATE TABLE IF NOT EXISTS robo_operacoes(
  id INTEGER PRIMARY KEY, modo TEXT, previsao_id INTEGER UNIQUE, prob REAL, t_compra INTEGER, px_compra REAL, qtd REAL, custo_compra REAL,
  t_venda INTEGER, px_venda REAL, receita_venda REAL, resultado_usdt REAL, detalhe TEXT)"""


def real():
    return os.environ.get("BINANCE_REAL") == "1"


def abrir():
    c = sqlite3.connect(config.BANCO)
    c.row_factory = sqlite3.Row
    c.execute(ESQUEMA)
    return c


def resultado_hoje(c, modo):
    inicio = int(time.mktime(date.today().timetuple()) * 1000)
    return c.execute("SELECT COALESCE(SUM(resultado_usdt),0) FROM robo_operacoes WHERE modo=? AND t_venda>=?", (modo, inicio)).fetchone()[0]


def modelo_n(c):
    r = c.execute("SELECT estado FROM modelo WHERE fonte='previsao_btc'").fetchone()
    return json.loads(json.loads(r["estado"])["5"])["n"] if r else 0


def decidir(previsao, n_aprendido, perda_hoje, aberta, parar):
    """Regra pura (testável): devolve o motivo de não comprar, ou None para comprar."""
    if parar:
        return "arquivo PARAR presente"
    if aberta:
        return "já existe posição aberta"
    if perda_hoje <= -PERDA_DIA_MAXIMA:
        return f"perda do dia atingiu US$ {PERDA_DIA_MAXIMA}"
    if n_aprendido < APRENDIZADO_MINIMO:
        return f"modelo de 5 min aprendeu com {n_aprendido} de {APRENDIZADO_MINIMO} previsões"
    if previsao is None or previsao["prob_alta"] < PROB_MINIMA:
        return "previsão de alta abaixo do limite"
    return None


def passo(c, b, agora_s=None):
    agora_s = agora_s or time.time()
    modo = "real" if real() else "simulado"
    aberta = c.execute("SELECT * FROM robo_operacoes WHERE modo=? AND t_venda IS NULL", (modo,)).fetchone()
    if aberta and agora_s * 1000 - aberta["t_compra"] >= SEGURAR_S * 1000:
        bid, _ = b.livro(SIMBOLO)
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
        return f"vendeu: {receita - aberta['custo_compra']:+.4f} USDT"
    previsao = c.execute("SELECT * FROM previsoes WHERE horizonte=5 ORDER BY t_base_ms DESC LIMIT 1").fetchone()
    if previsao and agora_s * 1000 - previsao["t_base_ms"] > 150_000:
        previsao = None  # previsão velha não vale
    motivo = decidir(previsao, modelo_n(c), resultado_hoje(c, modo), aberta is not None, PARAR.exists())
    if motivo:
        return motivo
    if c.execute("SELECT 1 FROM robo_operacoes WHERE previsao_id=?", (previsao["id"],)).fetchone():
        return "previsão já usada"
    _, ask = b.livro(SIMBOLO)
    if modo == "real":
        o = b.comprar_em_usdt(SIMBOLO, VALOR_USDT)
        bruto = float(o["executedQty"])
        taxa_btc = sum(float(f["commission"]) for f in o.get("fills", []) if f["commissionAsset"] == "BTC")
        qtd = math.floor((bruto - taxa_btc) * 1e5) / 1e5
        custo = float(o["cummulativeQuoteQty"])
        px = custo / bruto
        detalhe = json.dumps(o)[:2000]
    else:
        px = ask
        qtd = math.floor(VALOR_USDT / ask * (1 - TAXA_SUPOSTA) * 1e5) / 1e5
        custo = VALOR_USDT
        detalhe = None
    c.execute("INSERT INTO robo_operacoes(modo,previsao_id,prob,t_compra,px_compra,qtd,custo_compra,detalhe) VALUES(?,?,?,?,?,?,?,?)",
              (modo, previsao["id"], previsao["prob_alta"], int(agora_s * 1000), px, qtd, custo, detalhe))
    c.commit()
    return f"comprou {qtd} BTC a {px:.2f} (prob {previsao['prob_alta']:.2f})"


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
    ultimo = None
    while True:
        try:
            msg = passo(c, b)
        except Exception as e:
            msg = f"erro: {type(e).__name__}: {str(e)[:200]}"
        if msg != ultimo:
            print(time.strftime("%F %T"), msg, flush=True)
            ultimo = msg
        time.sleep(20)


if __name__ == "__main__":
    rodar()
