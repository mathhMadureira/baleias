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


def stop_da_moeda(k):
    """Stop pela volatilidade da moeda: 2 × a amplitude média de 1 h (blocos de 4 velas de 15 min, últimas 24 h), entre 1,5% e 4%.
    (15/11: as 7 primeiras operações pararam todas no stop fixo de 1,5%, a maioria em 15 min, em moedas que caíam 14% no dia.)"""
    if len(k) < 96:
        return STOP_SEG
    blocos = [k[i:i + 4] for i in range(len(k) - 96, len(k), 4)]
    amp = [(max(float(x[2]) for x in b) - min(float(x[3]) for x in b)) / float(b[-1][4]) for b in blocos if len(b) == 4]
    return min(0.04, max(STOP_SEG, 2 * sum(amp) / len(amp))) if amp else STOP_SEG


def fechar(e, par, p, saida, motivo, agora):
    sinal = -1 if p["lado"] == "venda" else 1
    noc = p.get("nocional", ORCAMENTO)
    resultado = noc * sinal * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * noc
    e["caixa"] += p["gasto"] + resultado
    e["fechadas"].append({**p, "saida": saida, "saida_t": agora, "motivo_saida": motivo, "resultado_usd": resultado,
                          "R": resultado / (noc * p.get("stop_pct", STOP_SEG))})
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
        sp = p.get("stop_pct", STOP_SEG)
        stop = p["entrada"] * (1 + sp if venda else 1 - sp)
        saiu = None
        motivo_saida = f"stop de segurança −{sp:.1%}"
        from executor import stop_movel as SM                  # H49 (substitui a trava fixa da H48): stop móvel minuto a minuto
        r = SM.conferir(p, SM.MINUTOS.get(par), sp, int(agora * 1000), int(p["entrada_t"] * 1000))
        if r:
            saiu, motivo_saida = r[0], r[1]
            k = []
        for x in k:
            o, h, l = float(x[1]), float(x[2]), float(x[3])
            if (h >= stop) if venda else (l <= stop):
                saiu = (max(o, stop) if venda else min(o, stop))
                break
            p["conferido_ate"] = x[0] + VELA_MS
        if saiu is not None:
            textos.append(fechar(e, par, p, saiu, motivo_saida, agora))
        elif agora - p["entrada_t"] > MAX_HORAS * 3600 and par in preco:
            textos.append(fechar(e, par, p, preco[par], f"tempo máximo ({MAX_HORAS} h) sem nova decisão", agora))
    # 2) decisão do Claude (se recente)
    fresca = decisao and agora - decisao.get("t", 0) <= VALIDADE_S
    if fresca and decisao.get("t") != e.get("ultima_decisao_t"):
        e["ultima_decisao_t"] = decisao["t"]
        e["historico_decisoes"] = (e.get("historico_decisoes", []) + [{                # histórico de execuções da rotina (como o routine-results do OpenBot)
            "t": decisao["t"], "leitura": str(decisao.get("leitura", ""))[:300],
            "posicoes": [[str(x.get("moeda", "")), str(x.get("lado", ""))] for x in decisao.get("posicoes", []) or []],
            "fechar": list(decisao.get("fechar", []) or []), "licao": str(decisao.get("licao", ""))[:300]}])[-300:]
        if decisao.get("licao"):
            e["licoes"] = (e.get("licoes", []) + [{"t": decisao["t"], "texto": str(decisao["licao"])[:400]}])[-50:]
            textos.append(f"🤖 Robô Claude anotou uma lição: {str(decisao['licao'])[:160]}")
        for par in decisao.get("fechar", []) or []:
            par = par if par.endswith("USDT") else par + "USDT"
            if par in e["abertas"] and par in preco:
                textos.append(fechar(e, par, e["abertas"][par], preco[par], "o Claude mandou fechar: " + str(decisao.get("motivos_fechar", {}).get(par[:-4], ""))[:80], agora))
        if isinstance(decisao.get("posicoes"), list):              # revisão 15/11: "posicoes" é o que deve ficar aberto; o resto fecha
            querer = {(str(x.get("moeda", "")).upper() if str(x.get("moeda", "")).upper().endswith("USDT") else str(x.get("moeda", "")).upper() + "USDT")
                      for x in decisao["posicoes"] if isinstance(x, dict)}
            for par in [q for q in e["abertas"] if q not in querer and q in preco]:
                textos.append(fechar(e, par, e["abertas"][par], preco[par], "fora da lista de posições do Claude", agora))
        for pos in decisao.get("posicoes", []) or []:
            par = str(pos.get("moeda", "")).upper()
            par = par if par.endswith("USDT") else par + "USDT"
            lado = "venda" if str(pos.get("lado", "")).lower().startswith(("v", "s")) else "compra"
            if par in e["abertas"]:
                if e["abertas"][par]["lado"] != lado and par in preco:                      # inverteu o lado: fecha e reabre
                    textos.append(fechar(e, par, e["abertas"][par], preco[par], "o Claude inverteu o lado", agora))
                else:
                    continue
            patrimonio = e["caixa"] + sum(q["gasto"] for q in e["abertas"].values())
            if patrimonio < PISO:
                break
            noc = min(ORCAMENTO, patrimonio * ALAV / MAX_POS)          # as 4 posições sempre cabem na carteira (15/11: ERA e KAVA não couberam)
            if par not in preco or len(e["abertas"]) >= MAX_POS or e["caixa"] < noc / ALAV - 1e-9:
                continue
            from executor.sem_perseguir import persegue
            if persegue(lado, velas.get(par), preco[par]):     # H55: não persegue o movimento de 15 min
                textos.append(f"🤖 Robô Claude NÃO entrou {'vendido' if lado == 'venda' else 'comprado'} em {par[:-4]}: perseguiria o movimento de 15 min (H55)")
                continue
            sp = stop_da_moeda(velas.get(par, []))
            e["caixa"] -= noc / ALAV
            e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": preco[par], "entrada_t": agora, "gasto": noc / ALAV, "nocional": noc, "stop_pct": sp,
                                 "motivo": str(pos.get("motivo", ""))[:300], "decisao_t": decisao["t"], "conferido_ate": ultimo[par][0] + VELA_MS}
            textos.append(f"🤖 Robô Claude ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {preco[par]:.6g} (US$ {noc:.0f}, stop {sp:.1%}): {str(pos.get('motivo', ''))[:120]}")
    e["patrimonio"] = e["caixa"] + sum(q["gasto"] + (1 if q["lado"] == "compra" else -1) * q.get("nocional", ORCAMENTO) * (preco.get(q["moeda"], q["entrada"]) / q["entrada"] - 1)
                                       for q in e["abertas"].values())
    if e["patrimonio"] < PISO and not e.get("eliminado"):
        e["eliminado"] = True
        textos.append(f"⛔ Robô Claude abaixo de US$ {PISO:.0f}: eliminado, sem novas entradas até o dono decidir")
    return textos


def falar_e_ordenar(decisao, agora):
    """Parte 'chefe da mesa' da decisão (fusão com o OpenBot, baleias.equipe): respostas ao dono, recados na sala e ordens aos robôs.
    Formato (cartilha, seção 6): "respostas": [{"ref": id, "texto"}], "mensagens": [{"para", "texto"}], "ordens": [{"agente", "acao", "horas", "motivo"}]."""
    from baleias import equipe
    ids_dono = {x["id"] for x in equipe.sala() if x["de"] == "dono"}
    for i, r in enumerate(decisao.get("respostas", []) or []):
        if isinstance(r, dict) and r.get("ref") in ids_dono and str(r.get("texto", "")).strip():
            equipe.postar("claude", r["texto"], para="dono", tipo="resposta", t=agora + i / 1000, ref=r["ref"])
    for i, m in enumerate(decisao.get("mensagens", []) or []):
        if isinstance(m, dict) and str(m.get("texto", "")).strip():
            para = str(m.get("para", "sala")).lower()
            equipe.postar("claude", m["texto"], para=para if para in equipe.POR_ID or para == "dono" else "sala", t=agora + 0.1 + i / 1000)
    if decisao.get("leitura"):
        equipe.postar("claude", "🧭 Leitura: " + str(decisao["leitura"])[:400], tipo="evento", t=agora + 0.2)
    return equipe.aplicar_ordens(decisao.get("ordens"), agora=agora)


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "licoes": [], "inicio": time.strftime("%Y-%m-%d"), "eventos": []}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    agora = time.time()
    velas = {par: [x for x in k if x[6] < agora * 1000] for par, k in velas.items()}
    decisao = ler("decisao_claude.json")
    from baleias import equipe
    equipe.sincronizar_caixa()                                               # mensagens novas do dono (painel → dados/caixa/) entram na sala
    antes = e.get("ultima_decisao_t")
    from executor import stop_movel as SM
    SM.preparar(e["abertas"], lambda q: int(q["entrada_t"] * 1000), agora * 1000)
    from executor import guarda_dia as GD                   # H54: dia que ficou positivo não é devolvido
    guarda, textos = GD.checar(e, agora), []
    if guarda == "fechar":
        for par in list(e["abertas"]):
            k = velas.get(par) or []
            textos.append(fechar(e, par, e["abertas"][par], float(k[-1][4]) if k else e["abertas"][par]["entrada"], GD.motivo(e), agora))
        textos.append(GD.texto("Robô Claude", e))
    if guarda == "normal":
        textos += passo(e, decisao, velas, agora)
    else:                                                   # travado: sem posições e sem entradas; a decisão desta hora não vale depois
        e["patrimonio"] = e["caixa"] + sum(q["gasto"] for q in e["abertas"].values())
        if decisao:
            e["ultima_decisao_t"] = decisao.get("t")
    if decisao and e.get("ultima_decisao_t") != antes:                       # decisão nova: o chefe da mesa fala e dá ordens
        textos += falar_e_ordenar(decisao, agora)
    idade_h = (agora - decisao.get("t", 0)) / 3600 if decisao else 99.0      # saúde da rotina: sem decisão nova há mais de 2 h = alarme
    if idade_h > 2:                                                           # (15/11: a rotina ficou morta das 03:10 às 09:08 por limite de modelo)
        if not e.get("alerta_rotina"):
            textos.append(f"⚠️ Robô Claude: a rotina do Claude não decide há {idade_h:.1f} h (limite de uso, erro ou rotina parada). As posições seguem só com stop e tempo máximo.")
        e["alerta_rotina"] = f"sem decisão há {idade_h:.1f} h"
    else:
        if e.get("alerta_rotina"):
            textos.append("✅ Robô Claude: a rotina voltou a decidir.")
        e["alerta_rotina"] = None
    e["eventos"] = ([{"t": agora, "texto": x} for x in textos] + e["eventos"])[:100]
    arq.write_text(json.dumps(e, ensure_ascii=False))
    equipe.postar_eventos("claude", [x for x in textos if not x.startswith("📣")])
    print(f"🤖 Robô Claude: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas · {len(e.get('licoes', []))} lições")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
