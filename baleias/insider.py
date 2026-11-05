"""Teste das compras de diretores: entra na abertura do dia útil seguinte à publicação e sai ~1 mês depois.

Controle: o S&P 500 (SPY) no mesmo período. O alvo do aprendizado é o excesso sobre o SPY já descontado o custo.
"""
from datetime import date, timedelta

from . import config
from .aprendizado import Modelo, aprovado

FONTE = "insider"


def avaliar(evento, serie, spy, dias=config.INSIDER_DIAS_UTEIS):
    if not serie or not spy:
        return None
    pub = evento["data"]
    i = next((k for k, (d, _, _) in enumerate(serie) if d > pub), None)
    if i is None or i + dias - 1 >= len(serie):
        return None
    d_ent, entrada = serie[i][0], serie[i][1]
    d_sai, saida = serie[i + dias - 1][0], serie[i + dias - 1][2]
    curto = serie[min(i + config.INSIDER_DIAS_CURTO - 1, len(serie) - 1)][2]
    s = {d: (o, c) for d, o, c in spy}
    if d_ent not in s or d_sai not in s:
        return None
    r = saida / entrada - 1
    r_spy = s[d_sai][1] / s[d_ent][0] - 1
    previo = serie[i - 1][2] / serie[i - 21][2] - 1 if i >= 21 else None
    custo = 2 * config.INSIDER_CUSTO_LADO
    return {"d_entrada": d_ent, "d_saida": d_sai, "entrada": entrada, "saida": saida, "bruto": r, "spy": r_spy,
            "liquido": r - custo, "excesso": r - r_spy - custo, "r_curto": curto / entrada - 1 - custo, "previo": previo}


def caracteristicas(evento, cluster, previo):
    v = evento["valor"]
    valor = "50-250k" if v < 250_000 else "250k-1M" if v < 1_000_000 else ">1M"
    preco = "<5" if evento["preco"] < 5 else "5-20" if evento["preco"] < 20 else ">20"
    queda = "desconhecido" if previo is None else "sim" if previo < -0.10 else "nao"
    return ["vies", f"cargo:{evento['cargo']}", f"valor:{valor}", f"preco:{preco}", f"cluster:{'sim' if cluster else 'nao'}", f"queda_previa:{queda}"]


def cluster(evento, anteriores, dias=30):
    """Outro dono diferente comprou a mesma ação nos 30 dias anteriores."""
    limite = (date.fromisoformat(evento["data"]) - timedelta(days=dias)).isoformat()
    return any(a["ticker"] == evento["ticker"] and a["dono"] != evento["dono"] and limite <= a["data"] < evento["data"] for a in anteriores)


def _ms(d):
    from datetime import datetime, timezone
    return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp() * 1000)


def backtest(eventos, precos, inicio: date, fim: date):
    from .backtest import prequencial
    spy = precos.diario("SPY", inicio, fim)
    vistos, base = [], []
    for n, e in enumerate(eventos):
        if n % 100 == 0:
            print(f"  {n}/{len(eventos)}", flush=True)
        cl = cluster(e, vistos)
        vistos.append(e)
        a = avaliar(e, precos.diario(e["ticker"], inicio, fim), spy)
        if not a:
            continue
        base.append({**a, "ticker": e["ticker"], "nomes": caracteristicas(e, cl, a["previo"]), "liquido_cru": a["liquido"],
                     "liquido": a["excesso"], "controle": a["spy"] - 2 * config.INSIDER_CUSTO_LADO,
                     "t_entrada": _ms(a["d_entrada"]), "t_saida": _ms(a["d_saida"]) + 1})
    return prequencial(base)
