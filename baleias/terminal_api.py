"""Dados do terminal do robô (/): estado do robô, velas com os canais da estratégia, curva do teste e placar do laboratório."""
import json
import threading
import time
from pathlib import Path

from . import config

ESTADO = config.RAIZ / "robo_tartaruga.json"
PLACAR = Path(__file__).resolve().parent.parent / "lab" / "placar.json"
_trava = threading.Lock()
_backtest = {"pronto": False}


def _estado():
    try:
        return json.loads(ESTADO.read_text())
    except (OSError, ValueError):
        return None


def robo(precos_vivos=None):
    e = _estado()
    if not e:
        return {"ligado": False}
    precos_vivos = precos_vivos or {}
    radar = {r["moeda"]: r for r in e.get("radar", [])}
    posicoes = []
    for m, p in e.get("abertas", {}).items():
        px = precos_vivos.get(m[:-4]) or radar.get(m[:-4], {}).get("preco") or p["entrada"]
        resultado = p["qtd"] * px - p["gasto"]
        posicoes.append({"moeda": m[:-4], "entrada": p["entrada"], "preco": px, "stop": p["stop"], "qtd": p["qtd"], "gasto": p["gasto"],
                         "resultado": resultado, "R": resultado / p["risco_usd"] if p["risco_usd"] else 0,
                         "ate_stop_pct": (p["stop"] / px - 1) * 100, "desde": p["entrada_t"]})
    fechadas = e.get("fechadas", [])
    rs = [f["R"] for f in fechadas]
    curva = e.get("curva", [])
    pico = max([c[1] for c in curva] + [e.get("patrimonio") or 0]) if curva else e.get("patrimonio")
    agora = time.gmtime()
    proxima = time.mktime(time.strptime(time.strftime("%Y-%m-%d", agora), "%Y-%m-%d")) - time.timezone + 86400 + 120
    inicial = 0.0 if e.get("modo_real") else 700.0
    return {
        "ligado": True, "real": bool(e.get("modo_real")), "inicio": e.get("inicio"), "atualizado": e.get("atualizado"),
        "patrimonio": e.get("patrimonio"), "inicial": inicial, "caixa": e.get("caixa"),
        "queda_atual": (e["patrimonio"] / pico - 1) if pico else 0,
        "posicoes": posicoes, "radar": e.get("radar", []), "curva": curva,
        "fechadas": [{k: f.get(k) for k in ("moeda", "entrada", "saida", "motivo", "resultado_usd", "R", "entrada_t", "saida_t")} for f in fechadas[-50:]],
        "stats": {"operacoes": len(rs), "acerto": sum(r > 0 for r in rs) / len(rs) if rs else None,
                  "media_R": sum(rs) / len(rs) if rs else None, "soma_R": sum(rs) if rs else 0},
        "proxima_decisao": proxima,
    }


def velas(moeda, dias=200):
    """Velas diárias da moeda com os canais da estratégia (entrada: máxima de 55; saída: mínima de 20) e as operações do robô nela."""
    from lab import tartaruga as T
    try:
        dados = json.loads(T.CACHE_ROBO.read_text())
    except (OSError, ValueError):
        return {"erro": "sem dados ainda"}
    m = moeda.upper() + "USDT"
    vs = dados.get(m)
    if not vs:
        return {"erro": "moeda fora do universo do robô"}
    n = T.atr(vs)
    saida = []
    for i in range(max(T.ENTRADA, len(vs) - dias), len(vs)):
        saida.append({"d": vs[i][0], "o": vs[i][1], "h": vs[i][2], "l": vs[i][3], "c": vs[i][4],
                      "entrada": max(v[2] for v in vs[i - T.ENTRADA:i]), "saida": min(v[3] for v in vs[i - T.SAIDA:i]),
                      "stop2n": vs[i][4] - T.STOP_N * n[i] if n[i] else None})
    e = _estado() or {}
    ops = [f for f in e.get("fechadas", []) if f["moeda"] == m] + [p for k, p in e.get("abertas", {}).items() if k == m]
    marcas = []
    for o in ops:
        marcas.append({"t": o["entrada_t"], "px": o["entrada"], "tipo": "entrada"})
        if o.get("saida_t"):
            marcas.append({"t": o["saida_t"], "px": o["saida"], "tipo": "saida"})
    return {"moeda": moeda.upper(), "velas": saida, "marcas": marcas}


def _calcular_backtest():
    from lab import tartaruga as T
    try:
        dados = json.loads(T.CACHE_ROBO.read_text())
    except (OSError, ValueError):
        return
    curva, ops = T.simular(dados, "2024-01-01", time.strftime("%Y-%m-%d"), ("compra",), alav_max=1.0)
    m = T.metricas(curva, ops)
    dias = sorted(curva)
    with _trava:
        _backtest.update(pronto=True, curva=[[d, round(curva[d] * 700, 2)] for d in dias],
                         stats={k: m[k] for k in ("operacoes", "ao_ano", "maior_queda", "acerto", "ganho_medio_R", "perda_media_R",
                                                  "expectativa_R", "profit_factor", "meses_positivos", "pior_mes", "melhor_mes")},
                         ultimas=[{k: o[k] for k in ("moeda", "entrada_dia", "saida_dia", "R")} for o in ops[-12:]],
                         calculado=time.time())


def backtest():
    with _trava:
        pronto = _backtest.get("pronto")
        idade = time.time() - _backtest.get("calculado", 0)
    if not pronto or idade > 6 * 3600:
        threading.Thread(target=_calcular_backtest, daemon=True).start()
    with _trava:
        return dict(_backtest)


def lab():
    try:
        return json.loads(PLACAR.read_text())
    except (OSError, ValueError):
        return []
