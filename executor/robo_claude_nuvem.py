"""Robô Claude (H43): executa, no perpétuo simulado da nuvem, as decisões que o Claude toma de hora em hora lendo o retrato do mercado
(dados/mercado_agora.json) e a cartilha (docs/CARTILHA_ROBO_CLAUDE.md). O Claude escreve dados/decisao_claude.json; este módulo só executa:
  - abre as posições pedidas (compra ou venda), US$ 25 a 10×, até MAX_POS ao mesmo tempo, ao fechamento da última vela de 15 min;
  - fecha as que o Claude mandar fechar; fecha no stop de segurança (STOP_SEG, conferido na mínima/máxima das velas desde a entrada);
  - fecha por tempo máximo (MAX_HORAS) se o Claude não disser nada;
  - guarda o motivo do Claude em cada operação e as lições que ele escreve, para ele reler na próxima hora.
Carteira de US$ 10, 0,06% por lado, eliminado abaixo de US$ 5. Estado: dados/robo_claude.json (ramo estado).
Uma decisão vale por VALIDADE_S; sem decisão nova, as posições abertas continuam até stop ou tempo máximo.

Uso: BALEIAS_DADOS=.../estado/dados CEREBROS_MOEDAS=... python -m executor.robo_claude_nuvem
"""
import json
import os
import time
from pathlib import Path

from baleias import config

ORCAMENTO, ALAV, CUSTO_LADO = 25.0, 10.0, 0.0006
STOP_SEG = float(os.environ.get("RC_STOP", "0.015"))
MAX_POS, CAPITAL, PISO = 4, 10.0, 5.0
MAX_HORAS = 24
VALIDADE_S = 75 * 60
VELA_MS = 900_000
ARQ = "robo_claude.json"


def ler(nome):
    arq = config.RAIZ / nome
    try:
        return json.loads(arq.read_text()) if arq.exists() else {}
    except ValueError:
        return {}


def fechar(e, par, p, saida, motivo, agora):
    sinal = -1 if p["lado"] == "venda" else 1
    resultado = ORCAMENTO * sinal * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * ORCAMENTO
    e["caixa"] += p["gasto"] + resultado
    e["fechadas"].append({**p, "saida": saida, "saida_t": agora, "motivo_saida": motivo, "resultado_usd": resultado, "R": resultado / (ORCAMENTO * STOP_SEG)})
    e["fechadas"] = e["fechadas"][-3000:]
    del e["abertas"][par]
    return f"🤖 Robô Claude SAIU da {'VENDA' if sinal < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT"


def passo(e, decisao, velas, agora):
    """e: estado; decisao: dados/decisao_claude.json (ou {}); velas: {par: velas fechadas de 15 min}. Devolve os textos."""
    textos = []
    ultimo = {par: k[-1] for par, k in velas.items() if k}
    preco = {par: float(v[4]) for par, v in ultimo.items()}
    # 1) stop de segurança e tempo máximo, nas velas fechadas desde a última conferência
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        k = [x for x in velas.get(par, []) if x[0] >= p.get("conferido_ate", p["entrada_t"] * 1000)]
        venda = p["lado"] == "venda"
        stop = p["entrada"] * (1 + STOP_SEG if venda else 1 - STOP_SEG)
        saiu = None
        for x in k:
            o, h, l = float(x[1]), float(x[2]), float(x[3])
            if (h >= stop) if venda else (l <= stop):
                saiu = (max(o, stop) if venda else min(o, stop))
                break
            p["conferido_ate"] = x[0] + VELA_MS
        if saiu is not None:
            textos.append(fechar(e, par, p, saiu, f"stop de segurança −{STOP_SEG:.1%}", agora))
        elif agora - p["entrada_t"] > MAX_HORAS * 3600 and par in preco:
            textos.append(fechar(e, par, p, preco[par], f"tempo máximo ({MAX_HORAS} h) sem nova decisão", agora))
    # 2) decisão do Claude (se recente)
    fresca = decisao and agora - decisao.get("t", 0) <= VALIDADE_S
    if fresca and decisao.get("t") != e.get("ultima_decisao_t"):
        e["ultima_decisao_t"] = decisao["t"]
        if decisao.get("licao"):
            e["licoes"] = (e.get("licoes", []) + [{"t": decisao["t"], "texto": str(decisao["licao"])[:400]}])[-50:]
            textos.append(f"🤖 Robô Claude anotou uma lição: {str(decisao['licao'])[:160]}")
        for par in decisao.get("fechar", []) or []:
            par = par if par.endswith("USDT") else par + "USDT"
            if par in e["abertas"] and par in preco:
                textos.append(fechar(e, par, e["abertas"][par], preco[par], "o Claude mandou fechar: " + str(decisao.get("motivos_fechar", {}).get(par[:-4], ""))[:80], agora))
        for pos in decisao.get("posicoes", []) or []:
            par = str(pos.get("moeda", "")).upper()
            par = par if par.endswith("USDT") else par + "USDT"
            lado = "venda" if str(pos.get("lado", "")).lower().startswith(("v", "s")) else "compra"
            if par in e["abertas"]:
                if e["abertas"][par]["lado"] != lado and par in preco:                      # inverteu o lado: fecha e reabre
                    textos.append(fechar(e, par, e["abertas"][par], preco[par], "o Claude inverteu o lado", agora))
                else:
                    continue
            if par not in preco or len(e["abertas"]) >= MAX_POS or e["caixa"] < ORCAMENTO / ALAV:
                continue
            if e["caixa"] + sum(q["gasto"] for q in e["abertas"].values()) < PISO:
                break
            e["caixa"] -= ORCAMENTO / ALAV
            e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": preco[par], "entrada_t": agora, "gasto": ORCAMENTO / ALAV,
                                 "motivo": str(pos.get("motivo", ""))[:300], "decisao_t": decisao["t"], "conferido_ate": ultimo[par][0] + VELA_MS}
            textos.append(f"🤖 Robô Claude ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {preco[par]:.6g}: {str(pos.get('motivo', ''))[:140]}")
    e["patrimonio"] = e["caixa"] + sum(q["gasto"] + (1 if q["lado"] == "compra" else -1) * ORCAMENTO * (preco.get(q["moeda"], q["entrada"]) / q["entrada"] - 1)
                                       for q in e["abertas"].values())
    if e["patrimonio"] < PISO and not e.get("eliminado"):
        e["eliminado"] = True
        textos.append(f"⛔ Robô Claude abaixo de US$ {PISO:.0f}: eliminado, sem novas entradas até o dono decidir")
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "licoes": [], "inicio": time.strftime("%Y-%m-%d"), "eventos": []}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    agora = time.time()
    velas = {par: [x for x in k if x[6] < agora * 1000] for par, k in velas.items()}
    textos = passo(e, ler("decisao_claude.json"), velas, agora)
    e["eventos"] = ([{"t": agora, "texto": x} for x in textos] + e["eventos"])[:100]
    arq.write_text(json.dumps(e, ensure_ascii=False))
    print(f"🤖 Robô Claude: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas · {len(e.get('licoes', []))} lições")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
