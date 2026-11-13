"""Rápido na NUVEM com o Cérebro v4 (decisão do dono, 2026-11-13: todos os robôs com o cérebro de mais lucro, operando na nuvem).

A cada vela de 15 min (logo depois de executor.cerebro_v4_nuvem publicar as apostas):
  1) fecha as posições da vela que acabou de fechar: stop de segurança de 1%, lucro realizado de +US$ 0,50 (= +2% em US$ 25) ou
     fim da vela, conferidos na mínima/máxima da vela (se o stop e o alvo caberiam na mesma vela, conta o stop: conservador);
  2) abre as apostas novas do v4 (|p − 0,5| ≥ 0,03) ao preço de fechamento da vela do sinal, nos dois lados.
Perpétuo simulado com o tamanho do dono: US$ 25 a 10× (margem US$ 2,50), 0,06% por lado, até 6 posições por lado, carteira de US$ 10,
sem trava de perda do dia ("tirar"), eliminado abaixo de US$ 5. Estado: dados/robo_v4_perp.json (ramo estado).

Uso: BALEIAS_DADOS=... CEREBROS_MOEDAS=... python -m executor.v4_perp_nuvem
"""
import json
import os
import time
from pathlib import Path

from baleias import config

ORCAMENTO, ALAV, CUSTO_LADO, STOP_SEG, REALIZAR = 25.0, 10.0, 0.0006, 0.01, 0.50
CAPITAL, PISO, MAX_MESMO_LADO = 10.0, 5.0, 6
LIMIAR = float(os.environ.get("V4P_LIMIAR", "0.03"))            # 0,03 = todas as apostas (agressivo, pedido do dono); 0,12 = só as mais confiantes (H37)
MODO = os.environ.get("V4P_MODO", "limiar")                     # "limiar": entra nas apostas acima de LIMIAR; "ranking" (Caçador): a cada vela as K moedas
K = int(os.environ.get("V4P_K", "2"))                           #   com maior chance de subir (compra) e as K com maior chance de cair (venda) — sempre posicionado
VELA_MS = 900_000
ARQ = os.environ.get("V4P_ARQ", "robo_v4_perp.json")
NOME = os.environ.get("V4P_NOME", "Rápido nuvem")


def resolver(p, vela):
    """(preço de saída, motivo) da posição na vela seguinte à do sinal. vela = [t, o, h, l, c, ...] (strings da Binance)."""
    o, h, l, c = (float(vela[k]) for k in (1, 2, 3, 4))
    venda = p["lado"] == "venda"
    stop = p["entrada"] * (1 + STOP_SEG if venda else 1 - STOP_SEG)
    alvo = p["entrada"] * (1 - REALIZAR / ORCAMENTO if venda else 1 + REALIZAR / ORCAMENTO)
    if (h >= stop) if venda else (l <= stop):
        return (max(o, stop) if venda else min(o, stop)), f"stop de segurança −{STOP_SEG:.0%}"
    if (l <= alvo) if venda else (h >= alvo):
        return alvo, f"lucro realizado +US$ {REALIZAR:.2f}"
    return c, "fim da vela do v4"


def passo(e, pendentes, velas, agora_ms):
    """e: estado; pendentes: apostas do v4 {par: {t, px, prob, aposta}}; velas: {par: velas fechadas}. Devolve os textos."""
    textos = []
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        k = velas.get(par, [])
        vela = next((x for x in k if x[0] == p["vela_saida"]), None)
        if vela is None:
            vela = next((x for x in k if x[0] > p["vela_saida"]), None)     # rodada atrasada: usa a primeira vela depois da esperada
            if vela is None:
                continue
        saida, motivo = resolver(p, vela)
        sinal = -1 if p["lado"] == "venda" else 1
        resultado = ORCAMENTO * sinal * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * ORCAMENTO
        e["caixa"] += ORCAMENTO / ALAV + resultado
        e["fechadas"].append({**p, "saida": saida, "saida_t": (vela[0] + VELA_MS) / 1000, "motivo": motivo,
                              "resultado_usd": resultado, "R": resultado / (ORCAMENTO * STOP_SEG)})
        del e["abertas"][par]
        textos.append(f"🌲 {NOME} SAIU da {'VENDA' if sinal < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT")
    e["fechadas"] = e["fechadas"][-3000:]
    if e["caixa"] + sum(p["gasto"] for p in e["abertas"].values()) < PISO:
        if not e.get("eliminado"):
            e["eliminado"] = True
            textos.append(f"⛔ {NOME} abaixo de US$ {PISO:.0f}: eliminado, sem novas entradas até o dono decidir")
        return textos
    if MODO == "ranking":                                   # Caçador: caça a própria entrada a cada vela, nos dois lados (pedido do dono, 13/11)
        ordem = sorted(pendentes.items(), key=lambda kv: -kv[1]["prob"])
        candidatos = [(par, p) for par, p in ordem if p["prob"] > 0.51][:K] + [(par, p) for par, p in ordem[::-1] if p["prob"] < 0.49][:K]
    else:
        candidatos = [(par, p) for par, p in sorted(pendentes.items(), key=lambda kv: -abs(kv[1]["prob"] - 0.5)) if abs(p["prob"] - 0.5) >= LIMIAR]
    for par, p in candidatos:
        if par in e["abertas"] or p["t"] == e["ultimo_sinal"].get(par):
            continue
        lado = "compra" if p["prob"] > 0.5 else "venda"
        if sum(1 for q in e["abertas"].values() if q["lado"] == lado) >= MAX_MESMO_LADO or e["caixa"] < ORCAMENTO / ALAV:
            continue
        e["caixa"] -= ORCAMENTO / ALAV
        e["ultimo_sinal"][par] = p["t"]
        e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": p["px"], "entrada_t": (p["t"] + VELA_MS) / 1000,
                             "vela_saida": p["t"] + VELA_MS, "prob": p["prob"], "gasto": ORCAMENTO / ALAV}
        textos.append(f"🌲 {NOME} ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {p['px']:.6g} "
                      f"(v4 {max(p['prob'], 1 - p['prob']):.0%} até o fim da vela)")
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "ultimo_sinal": {},
                                                           "inicio": time.strftime("%Y-%m-%d"), "eventos": []}
    arq_v4 = config.RAIZ / "cerebro_v4.json"
    pendentes = (json.loads(arq_v4.read_text()).get("pendentes") or {}) if arq_v4.exists() else {}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    agora_ms = time.time() * 1000
    velas = {par: [x for x in k if x[6] < agora_ms] for par, k in velas.items()}       # só velas fechadas
    textos = passo(e, pendentes, velas, agora_ms)
    e["eventos"] = ([{"t": time.time(), "texto": x} for x in textos] + e["eventos"])[:100]
    e["patrimonio"] = e["caixa"] + sum(p["gasto"] for p in e["abertas"].values())
    arq.write_text(json.dumps(e))
    print(f"🌲 {NOME} (v4): patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
