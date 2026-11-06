"""Hipótese 2 ao vivo: carteira de tendência de 20 dias em cripto, um registro por dia UTC fechado (lab/PROTOCOLO_LAB.md)."""
import json
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

from .tendencia import CRIPTO

INICIO = "2026-11-07"   # primeiro dia contado
L = 20
CUSTO = 0.0010
ESQUEMA = """CREATE TABLE IF NOT EXISTS lab_tendencia(
  dia TEXT PRIMARY KEY, posicoes TEXT, ret_estrategia REAL, ret_base REAL, custo REAL, t_ms INTEGER)"""


def fechamentos(simbolo, desde, abrir=urllib.request.urlopen):
    """{dia ISO: fechamento}, só de dias UTC já fechados."""
    t0 = int(datetime.fromisoformat(desde).replace(tzinfo=timezone.utc).timestamp() * 1000)
    url = f"https://api.binance.com/api/v3/klines?symbol={simbolo}&interval=1d&startTime={t0}&limit=1000"
    with abrir(url, timeout=30) as r:
        lote = json.load(r)
    agora = time.time() * 1000
    return {datetime.fromtimestamp(k[0] / 1000, timezone.utc).date().isoformat(): float(k[4]) for k in lote if k[6] < agora}


def posicoes(series, dia):
    """Comprado (1) ou fora (0) para o dia seguinte, usando só fechamentos até `dia`."""
    ref = (date.fromisoformat(dia) - timedelta(days=L)).isoformat()
    return {a: int(s[dia] / s[ref] - 1 > 0) for a, s in series.items() if dia in s and ref in s}


def atualizar(c, buscar=fechamentos, hoje=None):
    """Registra cada dia fechado desde INICIO que ainda não foi registrado. Idempotente."""
    c.execute(ESQUEMA)
    hoje = hoje or datetime.now(timezone.utc).date()
    desde = (date.fromisoformat(INICIO) - timedelta(days=L + 3)).isoformat()
    series = {a: buscar(a, desde) for a in CRIPTO}
    feitos = 0
    d = date.fromisoformat(INICIO)
    while d < hoje:
        dia, ontem = d.isoformat(), (d - timedelta(days=1)).isoformat()
        if not c.execute("SELECT 1 FROM lab_tendencia WHERE dia=?", (dia,)).fetchone():
            pos = posicoes(series, ontem)
            rets = {a: series[a][dia] / series[a][ontem] - 1 for a in pos if dia in series[a]}
            if len(rets) < len(pos) or not pos:
                break  # dia ainda sem dados completos
            ant = c.execute("SELECT posicoes FROM lab_tendencia WHERE dia=?", (ontem,)).fetchone()
            pos_ant = json.loads(ant["posicoes"]) if ant else {a: 0 for a in pos}
            peso = 1 / len(CRIPTO)
            custo = sum(abs(pos[a] - pos_ant.get(a, 0)) for a in pos) * peso * CUSTO
            r_est = sum(pos[a] * rets[a] * peso for a in rets) - custo
            r_base = sum(rets.values()) / len(rets)
            c.execute("INSERT INTO lab_tendencia VALUES(?,?,?,?,?,strftime('%s','now')*1000)", (dia, json.dumps(pos), r_est, r_base, custo))
            feitos += 1
        d += timedelta(days=1)
    c.commit()
    return feitos


def resumo(c):
    from .tendencia import metricas
    try:
        linhas = c.execute("SELECT * FROM lab_tendencia ORDER BY dia").fetchall()
    except Exception:
        linhas = []
    est = [x["ret_estrategia"] for x in linhas]
    base = [x["ret_base"] for x in linhas]
    acum = lambda rs: __import__("math").prod(1 + r for r in rs) - 1 if rs else None
    ultimo = linhas[-1] if linhas else None
    return {"dias": len(linhas), "faltam_para_180": max(0, 180 - len(linhas)), "acumulado": acum(est), "acumulado_base": acum(base),
            "metricas": metricas(est, 365) if len(est) >= 30 else None, "metricas_base": metricas(base, 365) if len(base) >= 30 else None,
            "posicao_atual": json.loads(ultimo["posicoes"]) if ultimo else None, "ultimo_dia": ultimo["dia"] if ultimo else None}
