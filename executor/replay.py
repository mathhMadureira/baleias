"""Replay: o MESMO código do robô (tartaruga_exec) operando dia após dia sobre o histórico real, com relógio simulado.

Cada dia: as velas até o fechamento do dia anterior são a informação disponível; a execução sai pela abertura do dia (como o robô
ao vivo, que roda logo depois das 00:00 UTC); stops conferidos pela mínima de cada dia (stops_perdidos). Gera um quadro por dia
para o terminal animar.
"""
import calendar
import json
import time

from baleias import config
from lab import tartaruga as T

from . import tartaruga_exec as X

ARQUIVO = config.RAIZ / "replay.json"


def _ts(dia, segundos=600):
    return calendar.timegm(time.strptime(dia, "%Y-%m-%d")) + segundos


def rodar(inicio="2024-01-01", capital=700.0, dados=None):
    dados = dados or T.baixar(T.MOEDAS_ROBO, T.CACHE_ROBO)
    idx = {m: {v[0]: k for k, v in enumerate(vs)} for m, vs in dados.items()}
    dias = sorted({v[0] for vs in dados.values() for v in vs if v[0] >= inicio})
    e = X.novo_estado(capital)
    corretora = X.Simulada(None, e)
    quadros, novos = [], []
    relogio_antes, ouvinte_antes = X.relogio, X.ouvinte
    X.ouvinte = novos.append
    try:
        for i in range(1, len(dias)):
            ontem, hoje = dias[i - 1], dias[i]
            X.relogio = lambda d=hoje: _ts(d)
            visiveis = {m: vs[:idx[m][ontem] + 1] for m, vs in dados.items() if ontem in idx[m] and hoje in idx[m]}
            abertura = {m: dados[m][idx[m][hoje]][1] for m in visiveis}
            X.passo_diario(e, corretora, visiveis, abertura)
            fecho = {m: dados[m][idx[m][hoje]][4] for m in visiveis}
            patrimonio = e["caixa"] + sum(p["qtd"] * fecho.get(m, p["entrada"]) for m, p in e["abertas"].items())
            quadros.append({"d": hoje, "pat": round(patrimonio, 2),
                            "pos": [{"m": m[:-4], "entrada": p["entrada"], "stop": p["stop"], "px": fecho.get(m), "qtd": p["qtd"],
                                     "res": round(p["qtd"] * fecho.get(m, p["entrada"]) - p["gasto"], 2)} for m, p in e["abertas"].items()],
                            "ev": [x["texto"].replace(" [simulado]", "").replace(" (atingido com a máquina desligada)", "") for x in novos]})
            novos.clear()
    finally:
        X.relogio, X.ouvinte = relogio_antes, ouvinte_antes
    rs = [f["R"] for f in e["fechadas"]]
    resumo = {"inicio": inicio, "capital": capital, "final": quadros[-1]["pat"] if quadros else capital, "operacoes": len(rs),
              "acerto": sum(r > 0 for r in rs) / len(rs) if rs else None, "media_R": sum(rs) / len(rs) if rs else None,
              "maior_ganho_R": max(rs) if rs else None}
    saida = {"resumo": resumo, "quadros": quadros, "gerado": time.time()}
    ARQUIVO.write_text(json.dumps(saida))
    return saida


if __name__ == "__main__":
    r = rodar()
    print(json.dumps(r["resumo"], ensure_ascii=False))
    print("dias:", len(r["quadros"]), "| exemplos de eventos:")
    for q in r["quadros"]:
        for t in q["ev"][:1]:
            print(" ", q["d"], t[:140])
        if sum(len(x["ev"]) for x in r["quadros"][: r["quadros"].index(q) + 1]) > 8:
            break
