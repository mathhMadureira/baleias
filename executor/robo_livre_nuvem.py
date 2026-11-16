"""Robô Livre (H47, pedido do dono em 15/11: "um robô livre dessas regras, vamos ver se ele avança mais rápido").

Sem aprovação do laboratório, sem stop, sem tempo máximo, sem trava de perda, sem ordens do chefe. Só o que a corretora impõe de verdade:
  - custo de 0,06% por lado (a conta mostra também o resultado SEM custo, para o dono ver o peso dele);
  - liquidação: com 20×, um movimento contra de LIQ (4,5%) desde a entrada leva a margem inteira da posição.

Regra (a referência que ganhou do v4 ao vivo no vigia de 15/11: "segue a maioria do mercado nas últimas 24 h"):
  - lado = o da maioria das moedas em 24 h (mais da metade subindo → compra; senão → venda);
  - entra nas K moedas que mais andaram nesse lado em 24 h, carteira inteira dividida em K, 20×, lucro reinvestido;
  - segura enquanto a moeda estiver entre as 2K líderes do lado; sai quando cai fora delas ou quando a maioria vira de lado.
Carteira de US$ 10; abaixo de US$ 1 fica sem margem (quebrou). Estado: dados/robo_livre.json.
"""
import json
import os
import time
from pathlib import Path

from baleias import config

CAPITAL, ALAV, K, LIQ, CUSTO_LADO, QUEBROU = 10.0, 20.0, 4, 0.045, 0.0006, 1.0
VELA_MS, H24 = 900_000, 96
ARQ, NOME = "robo_livre.json", "Robô Livre"


def ranking(velas):
    """(lado, [pares em ordem de força no lado]) pela variação de 24 h, ou (None, [])."""
    var = {}
    for par, k in velas.items():
        if len(k) > H24:
            a, b = float(k[-1 - H24][4]), float(k[-1][4])
            if a > 0:
                var[par] = b / a - 1
    if len(var) < 20:
        return None, []
    lado = "compra" if sum(v > 0 for v in var.values()) > len(var) / 2 else "venda"
    ordem = sorted(var, key=lambda p: -var[p] if lado == "compra" else var[p])
    return lado, ordem


def _fechar(e, par, saida, motivo, agora):
    p = e["abertas"].pop(par)
    s = 1 if p["lado"] == "compra" else -1
    bruto = p["nocional"] * s * (saida / p["entrada"] - 1)
    custo = 2 * CUSTO_LADO * p["nocional"]
    resultado = -p["margem"] if motivo.startswith("LIQUIDADO") else max(-p["margem"], bruto - custo)   # liquidado: a corretora leva a margem toda
    e["caixa"] += p["margem"] + resultado
    e["sem_custo"] += -p["margem"] if motivo.startswith("LIQUIDADO") else max(-p["margem"], bruto)
    e["custo_pago"] += custo if resultado > -p["margem"] else 0.0
    e["fechadas"].append({**p, "saida": saida, "saida_t": agora, "motivo_saida": motivo, "resultado_usd": resultado, "bruto_usd": bruto})
    e["fechadas"] = e["fechadas"][-3000:]
    return f"🦅 {NOME} SAIU da {'COMPRA' if s > 0 else 'VENDA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT (sem custo {bruto:+.3f})"


def passo(e, velas, agora):
    textos = []
    preco = {par: float(k[-1][4]) for par, k in velas.items() if k}
    # 1) liquidação, conferida na máxima/mínima das velas desde a entrada
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        venda = p["lado"] == "venda"
        liq = p["entrada"] * (1 + LIQ if venda else 1 - LIQ)
        for x in velas.get(par, []):
            if x[0] < p.get("conferido_ate", 0):
                continue
            if (float(x[2]) >= liq) if venda else (float(x[3]) <= liq):
                textos.append(_fechar(e, par, liq, f"LIQUIDADO (−{LIQ:.1%} a {ALAV:.0f}×)", agora))
                break
            p["conferido_ate"] = x[0] + VELA_MS
    lado, ordem = ranking(velas)
    if not lado:
        return textos
    lideres = set(ordem[:2 * K])
    # 2) saída: a maioria virou de lado ou a moeda saiu das líderes
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        if par not in preco:
            continue
        if p["lado"] != lado:
            textos.append(_fechar(e, par, preco[par], f"a maioria do mercado virou para {lado}", agora))
        elif par not in lideres:
            textos.append(_fechar(e, par, preco[par], "saiu das líderes do movimento", agora))
    # 3) entrada: carteira inteira dividida em K, reinvestindo o lucro
    patrimonio = e["caixa"] + sum(q["margem"] for q in e["abertas"].values())
    if patrimonio < QUEBROU:
        if not e.get("quebrou"):
            e["quebrou"] = True
            textos.append(f"💥 {NOME} quebrou: patrimônio US$ {patrimonio:.2f}")
        return textos
    for par in ordem[:K]:
        if par in e["abertas"] or len(e["abertas"]) >= K or par not in preco:
            continue
        margem = min(e["caixa"], patrimonio / K)
        if margem < 0.05:
            break
        e["caixa"] -= margem
        e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": preco[par], "entrada_t": agora, "margem": margem,
                             "nocional": margem * ALAV, "conferido_ate": velas[par][-1][0] + VELA_MS}
        textos.append(f"🦅 {NOME} ENTROU {'COMPRADO' if lado == 'compra' else 'VENDIDO'} em {par[:-4]} a {preco[par]:.6g} "
                      f"(US$ {margem * ALAV:.0f} a {ALAV:.0f}×; líder do mercado em 24 h)")
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "eventos": [], "sem_custo": 0.0,
                                                           "custo_pago": 0.0, "inicio": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    agora = time.time()
    velas = {par: [x for x in k if x[6] < agora * 1000] for par, k in velas.items()}
    from executor import guarda_dia as GD                   # H54: dia que ficou positivo não é devolvido
    guarda, textos = GD.checar(e, agora), []
    if guarda == "fechar":
        for par in list(e["abertas"]):
            k = velas.get(par) or []
            textos.append(_fechar(e, par, float(k[-1][4]) if k else e["abertas"][par]["entrada"], GD.motivo(e), agora))
        textos.append(GD.texto(NOME, e))
    if guarda == "normal":
        textos += passo(e, velas, agora)
    preco = {par: float(k[-1][4]) for par, k in velas.items() if k}
    e["patrimonio"] = e["caixa"] + sum(q["margem"] + max(-q["margem"], (1 if q["lado"] == "compra" else -1) * q["nocional"] * (preco.get(q["moeda"], q["entrada"]) / q["entrada"] - 1))
                                       for q in e["abertas"].values())
    e["patrimonio_sem_custo"] = CAPITAL + e["sem_custo"] + (e["patrimonio"] - e["caixa"] - sum(q["margem"] for q in e["abertas"].values()))
    e["eventos"] = ([{"t": agora, "texto": x} for x in textos] + e["eventos"])[:100]
    arq.write_text(json.dumps(e, ensure_ascii=False))
    from baleias import equipe
    equipe.postar_eventos("livre", textos)
    print(f"🦅 {NOME}: patrimônio US$ {e['patrimonio']:.2f} (sem custo US$ {e['patrimonio_sem_custo']:.2f}) · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
