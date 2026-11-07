"""H10b ao vivo: Tartarugas só compra, spot, sem alavancagem, carteira simulada. Gera eventos de entrada, stop e saída.

Uma vez por dia (depois do fechamento das 00:00 UTC) decide entradas e saídas pelo canal; a cada minuto confere os stops com o preço ao vivo.
"""
import json
import os
import time

from baleias import config

from . import tartaruga as T

ESTADO = config.RAIZ / "tartaruga_vivo.json"
CAPITAL_INICIAL = float(os.environ.get("TARTARUGA_CAPITAL", "700"))
RISCO = float(os.environ.get("TARTARUGA_RISCO", "0.01"))


def novo_estado():
    return {"capital": CAPITAL_INICIAL, "abertas": {}, "fechadas": [], "ultimo_dia": None, "inicio": time.strftime("%Y-%m-%d")}


def carregar():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return novo_estado()


def salvar(e):
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, indent=1))
    tmp.replace(ESTADO)


def _fechar(e, m, px, motivo, agora):
    p = e["abertas"].pop(m)
    bruto = p["qtd"] * px - p["qtd"] * p["entrada"]
    custo = p["qtd"] * px * T.CUSTO_LADO
    resultado = bruto - custo
    e["capital"] += p["qtd"] * px - custo
    R = (resultado - p["custo_entrada"]) / p["risco_usd"] if p["risco_usd"] else 0.0
    e["fechadas"].append({**p, "saida": px, "saida_t": agora, "motivo": motivo, "resultado_usd": resultado - p["custo_entrada"], "R": R})
    return {"tipo": "tartaruga", "notificar": True,
            "texto": f"🐢 SAÍDA {m[:-4]} ({motivo}) a {px:,.6g}: {resultado - p['custo_entrada']:+,.2f} USDT ({R:+.1f}R) | capital simulado US$ {e['capital'] + _exposto(e):,.2f}"}


def _exposto(e):
    return sum(p["qtd"] * p["entrada"] for p in e["abertas"].values())


def passo_diario(e, dados, precos, agora=None):
    """`dados`: velas diárias fechadas por moeda (formato de tartaruga.baixar); `precos`: preço atual por moeda. Devolve eventos."""
    agora = agora or time.time()
    eventos = []
    for m in list(e["abertas"]):
        vs = dados.get(m)
        if vs and len(vs) > T.SAIDA and T.saida_canal(vs, len(vs) - 1, "compra") and m in precos:
            eventos.append(_fechar(e, m, precos[m], "fechou abaixo da mínima de 20 dias", agora))
    for m, vs in dados.items():
        if m in e["abertas"] or m not in precos or len(vs) <= T.ENTRADA:
            continue
        k = len(vs) - 1
        if not T.sinais(vs, k, "compra"):
            continue
        n = T.atr(vs)[k]
        if not n:
            continue
        px = precos[m]
        total = e["capital"] + _exposto(e)
        risco_usd = RISCO * total
        nocional = min(risco_usd / (T.STOP_N * n) * px, e["capital"] * 0.999)   # spot: sem alavancagem
        if nocional < 5:                                                          # mínimo da Binance
            continue
        qtd = nocional / px
        custo = nocional * T.CUSTO_LADO
        e["capital"] -= nocional + custo
        stop = px - T.STOP_N * n
        e["abertas"][m] = {"moeda": m, "entrada": px, "qtd": qtd, "stop": stop, "entrada_t": agora, "risco_usd": qtd * (px - stop),
                           "custo_entrada": custo, "N": n}
        eventos.append({"tipo": "tartaruga", "notificar": True,
                        "texto": f"🐢 ENTRADA COMPRA {m[:-4]} a {px:,.6g} — rompeu a máxima de 55 dias. Stop {stop:,.6g} ({(stop / px - 1) * 100:.1f}%), "
                                 f"posição US$ {nocional:,.2f}, risco US$ {qtd * (px - stop):,.2f} (1R). Saída: fechar abaixo da mínima de 20 dias."})
    e["ultimo_dia"] = time.strftime("%Y-%m-%d", time.gmtime(agora))
    return eventos


def checar_stops(e, precos, agora=None):
    eventos = []
    for m in list(e["abertas"]):
        px = precos.get(m)
        if px is not None and px <= e["abertas"][m]["stop"]:
            eventos.append(_fechar(e, m, px, "stop 2N", agora or time.time()))
    return eventos


def resumo(e, precos):
    aberto = sum(p["qtd"] * precos.get(m, p["entrada"]) for m, p in e["abertas"].items())
    rs = [f["R"] for f in e["fechadas"]]
    return {"capital_total": e["capital"] + aberto, "inicial": CAPITAL_INICIAL, "abertas": len(e["abertas"]), "fechadas": len(rs),
            "expectativa_R": sum(rs) / len(rs) if rs else None, "desde": e["inicio"]}
