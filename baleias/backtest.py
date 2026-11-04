"""Backtest prequencial: o modelo só enxerga o que já teria sido resolvido no instante de cada sinal.

Viés conhecido: as carteiras vêm do ranking de hoje. É otimista por construção e não libera dinheiro.
"""
import bisect
import json

from . import config, sinais as S
from .aprendizado import Modelo, aprovado, media_ic

CINCO_MIN = 300_000


def _serie(velas):
    v = sorted(velas, key=lambda x: x["t"])
    return v, [x["t"] for x in v]


def avaliar(sinal, velas, tempos, atraso=config.ATRASO_BACKTEST_MS, horizonte=config.HORIZONTE_MS):
    """Entrada na abertura da primeira vela depois do sinal mais o atraso; saída no fechamento no horizonte."""
    alvo = sinal["fim"] + atraso
    i = bisect.bisect_left(tempos, alvo)
    if i >= len(velas):
        return None
    t_entrada = tempos[i]
    j = bisect.bisect_left(tempos, t_entrada + horizonte) - 1
    if j <= i or tempos[j] + CINCO_MIN < t_entrada + horizonte:
        return None
    entrada, saida = float(velas[i]["o"]), float(velas[j]["c"])
    caminho = velas[i:j + 1]
    previo = None
    k = bisect.bisect_left(tempos, t_entrada - 15 * 60_000)
    if k < i:
        previo = S.retorno_bruto(sinal["lado"], float(velas[k]["o"]), entrada)
    melhor, pior = S.extremos(sinal["lado"], entrada, caminho)
    return {"t_entrada": t_entrada, "t_saida": t_entrada + horizonte, "entrada": entrada, "saida": saida, "previo": previo,
            "melhor": melhor, "pior": pior, "bruto": S.retorno_bruto(sinal["lado"], entrada, saida),
            "liquido": S.retorno_liquido(sinal["lado"], sinal["moeda"], entrada, saida)}


def prequencial(eventos, minimo=config.SINAIS_PARA_ALERTAR):
    """`eventos`: dicts com t_entrada, t_saida, nomes e liquido. Prevê na entrada; aprende só depois da saída."""
    modelo = Modelo()
    pendentes, saida = [], []
    for e in sorted(eventos, key=lambda x: x["t_entrada"]):
        while pendentes and pendentes[0]["t_saida"] <= e["t_entrada"]:
            feito = pendentes.pop(0)
            modelo.aprender(feito["nomes"], feito["liquido"] * 100)
        ok, media, desvio = aprovado(modelo, e["nomes"], modelo.n, minimo)
        saida.append({**e, "aprovado": ok, "previsto": media, "desvio": desvio, "aprendidos": modelo.n})
        bisect.insort(pendentes, e, key=lambda x: x["t_saida"])
    return saida, modelo


def resumo(linhas):
    pct = lambda chave, ls: media_ic([x[chave] * 100 for x in ls])
    aprovados = [x for x in linhas if x["aprovado"]]
    metade = len(linhas) // 2
    return {"todos": pct("liquido", linhas), "controle": pct("controle", linhas), "aprovados": pct("liquido", aprovados),
            "controle_dos_aprovados": pct("controle", aprovados),
            "primeira_metade": pct("liquido", linhas[:metade]), "segunda_metade": pct("liquido", linhas[metade:]),
            "aprovados_segunda_metade": pct("liquido", [x for x in linhas[metade:] if x["aprovado"]])}


def rodar(cliente, carteiras, agora_ms, dias=14):
    inicio = agora_ms - dias * 86_400_000
    brutos = []
    for c in carteiras:
        for s in S.detectar(cliente.operacoes_todas(c, inicio, agora_ms), agora_ms):
            s["carteira"] = c
            brutos.append(s)
    moedas = {s["moeda"] for s in brutos}
    series = {m: _serie(cliente.velas(m, "5m", inicio - 3_600_000, agora_ms)) for m in moedas}
    brutos.sort(key=lambda x: x["t"])
    eventos, recentes = [], []
    for s in brutos:
        recentes = [r for r in recentes if s["t"] - r["t"] <= 6 * 3_600_000]
        consenso = any(r["moeda"] == s["moeda"] and r["lado"] == s["lado"] and r["carteira"] != s["carteira"] for r in recentes)
        recentes.append(s)
        velas, tempos = series[s["moeda"]]
        a = avaliar(s, velas, tempos)
        if not a:
            continue
        lado_c = S.lado_controle(s["tids"][0])
        eventos.append({**a, "moeda": s["moeda"], "lado": s["lado"], "carteira": s["carteira"],
                        "nomes": S.caracteristicas(s["carteira"], s["moeda"], s["lado"], s["tipo"], s["nocional"], consenso, a["previo"]),
                        "controle": S.retorno_liquido(lado_c, s["moeda"], a["entrada"], a["saida"]),
                        "classe": S.classificar_erro(a["bruto"], a["liquido"], a["melhor"], a["pior"], a["previo"], False)})
    linhas, modelo = prequencial(eventos)
    return linhas, modelo, {"sinais_detectados": len(brutos), "moedas": len(moedas), "carteiras": len(carteiras), "dias": dias}
