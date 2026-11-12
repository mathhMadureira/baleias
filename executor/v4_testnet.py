"""Robô v4 no testnet de futuros da Binance: segue as apostas do Cérebro v4 (LightGBM, nuvem) com confiança ≥ LIMIAR, entrando com
ordem limitada SÓ MAKER (taxa 0,02% em vez de 0,05%) no melhor preço do livro; segura até o fim da vela de 15 min apostada; sai
primeiro com ordem maker e, se não executar em ESPERA_SAIDA s, a mercado. Registra quantas ordens executam de verdade.
Dinheiro de teste. Serviço: baleias-v4testnet. Estado: dados/robo_v4_testnet.json.
"""
import json
import os
import time

from baleias import config, mesa
from executor.binance_futuros import ErroFuturos, Futuros

LIMIAR = float(os.environ.get("V4_LIMIAR", "0.10"))         # |p − 0,5| mínimo (H31: só as apostas mais confiantes chegam perto de pagar)
NOCIONAL = float(os.environ.get("V4_NOCIONAL", "25"))       # US$ por posição (sobe ao mínimo da moeda: BTC 50, ETH 20)
MAX_POS = 6
ESPERA_ENTRADA, ESPERA_SAIDA, VELA = 90, 45, 900
TAXA_MAKER, TAXA_TAKER = 0.0002, 0.0005
ARQ = config.RAIZ / "robo_v4_testnet.json"


def carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text())
    return {"inicio": time.strftime("%Y-%m-%d"), "capital_inicial": 10.0, "abertas": {}, "ordens": {}, "fechadas": [], "tentadas": [],
            "nao_executadas": 0, "eventos": []}


def salvar(e):
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text(json.dumps(e))
    tmp.replace(ARQ)


def anotar(e, texto):
    e["eventos"] = ([{"t": time.time(), "texto": "🧪 " + texto}] + e["eventos"])[:100]
    print(time.strftime("%H:%M:%S"), texto, flush=True)


def fechar(e, par, p, px_saida, maker):
    sinal = 1 if p["lado"] == "BUY" else -1
    bruto = sinal * (px_saida / p["entrada"] - 1) * p["qtd"] * p["entrada"]
    taxas = p["qtd"] * (p["entrada"] * TAXA_MAKER + px_saida * (TAXA_MAKER if maker else TAXA_TAKER))
    res = bruto - taxas
    e["fechadas"].append({"moeda": par, "lado": "venda" if p["lado"] == "SELL" else "compra", "entrada": p["entrada"], "saida": px_saida,
                          "entrada_t": p["t"], "saida_t": time.time(), "qtd": p["qtd"], "resultado_usd": res, "saida_maker": maker, "prob": p["prob"],
                          "motivo": "fim da vela do v4" + ("" if maker else " (saída a mercado)")})
    del e["abertas"][par]
    anotar(e, f"{'✅' if res > 0 else '❌'} {par} fechou {'maker' if maker else 'a mercado'} a {px_saida}: {res:+.3f} USDT")


def main():
    f = Futuros.do_env()
    e = carregar()
    livre, total = f.saldo_usdt()
    anotar(e, f"ligado no testnet: saldo de teste {total:.0f} USDT · confiança ≥ {LIMIAR:.0%} · US$ {NOCIONAL:.0f} por posição (ou o mínimo da moeda)")
    while True:
        agora = time.time()
        try:
            mesa._buscar_estado()
            v4 = mesa._git_json("dados/cerebro_v4.json") or {}
        except Exception:
            v4 = {}
        for par, p in v4.get("pendentes", {}).items():
            inicio, fim = p["t"] / 1000 + VELA, p["t"] / 1000 + 2 * VELA
            chave = f"{par}@{p['t']}"
            if abs(p["prob"] - 0.5) < LIMIAR or chave in e["tentadas"] or not (inicio <= agora <= fim - 180):
                continue
            if par in e["abertas"] or par in e["ordens"] or len(e["abertas"]) + len(e["ordens"]) >= MAX_POS:
                continue
            lado = "BUY" if p["aposta"] > 0 else "SELL"
            e["tentadas"] = (e["tentadas"] + [chave])[-500:]
            try:
                bid, ask = f.livro(par)
                px = f.preco_redondo(par, bid if lado == "BUY" else ask, lado)
                qtd = f.quantidade(par, NOCIONAL, px)
                o = f.ordem_limit(par, lado, qtd, px, so_maker=True)
            except ErroFuturos as ex:
                e["nao_executadas"] += 1
                anotar(e, f"✗ {par} ordem maker recusada ({str(ex)[:80]})")
                continue
            e["ordens"][par] = {"id": o["orderId"], "lado": lado, "qtd": qtd, "px": px, "t": agora, "fim": fim, "prob": p["prob"]}
            anotar(e, f"📝 {par} ordem maker {lado} {qtd} a {px} (v4 {max(p['prob'], 1 - p['prob']):.0%}, nocional {qtd * px:.0f})")
        for par, o in list(e["ordens"].items()):
            try:
                st = f.consultar(par, o["id"])
            except ErroFuturos:
                continue
            if st["status"] == "FILLED":
                e["abertas"][par] = {"lado": o["lado"], "qtd": st["executada"], "entrada": st["preco_medio"], "t": agora, "fim": o["fim"], "prob": o["prob"]}
                del e["ordens"][par]
                anotar(e, f"✅ {par} EXECUTOU {o['lado']} {st['executada']} a {st['preco_medio']} (maker)")
            elif st["status"] in ("CANCELED", "EXPIRED", "REJECTED") or agora - o["t"] > ESPERA_ENTRADA:
                if st["status"] == "NEW" or st["status"] == "PARTIALLY_FILLED":
                    try:
                        f.cancelar(par, o["id"])
                    except ErroFuturos:
                        pass
                if st["executada"] > 0:
                    e["abertas"][par] = {"lado": o["lado"], "qtd": st["executada"], "entrada": st["preco_medio"], "t": agora, "fim": o["fim"], "prob": o["prob"]}
                    anotar(e, f"◐ {par} executou só {st['executada']} a {st['preco_medio']}; o resto foi cancelado")
                else:
                    e["nao_executadas"] += 1
                    anotar(e, f"⌛ {par} não executou em {ESPERA_ENTRADA}s ({st['status']}): cancelada")
                del e["ordens"][par]
        for par, p in list(e["abertas"].items()):
            if agora < p["fim"] and not p.get("saida_id"):
                continue
            lado_saida = "SELL" if p["lado"] == "BUY" else "BUY"
            try:
                if not p.get("saida_id"):
                    bid, ask = f.livro(par)
                    px = f.preco_redondo(par, ask if lado_saida == "SELL" else bid, lado_saida)
                    try:
                        o = f.ordem_limit(par, lado_saida, p["qtd"], px, so_maker=True, reduce_only=True)
                        p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=False)
                    except ErroFuturos:
                        o = f.ordem_mercado(par, lado_saida, p["qtd"], reduce_only=True)
                        p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=True)
                    continue
                st = f.consultar(par, p["saida_id"])
                if st["status"] == "FILLED":
                    fechar(e, par, p, st["preco_medio"], maker=not p.get("saida_mercado"))
                elif agora - p["saida_t"] > ESPERA_SAIDA and not p.get("saida_mercado"):
                    try:
                        f.cancelar(par, p["saida_id"])
                    except ErroFuturos:
                        pass
                    o = f.ordem_mercado(par, lado_saida, p["qtd"], reduce_only=True)
                    p.update(saida_id=o["orderId"], saida_t=agora, saida_mercado=True)
            except ErroFuturos as ex:
                anotar(e, f"✗ {par} saída falhou ({str(ex)[:80]})")
        n = len(e["fechadas"])
        e["resumo"] = {"fechadas": n, "ganhos": sum(1 for x in e["fechadas"] if x["resultado_usd"] > 0),
                       "resultado": sum(x["resultado_usd"] for x in e["fechadas"]), "nao_executadas": e["nao_executadas"],
                       "saidas_maker": sum(1 for x in e["fechadas"] if x["saida_maker"])}
        salvar(e)
        time.sleep(10)


if __name__ == "__main__":
    main()
