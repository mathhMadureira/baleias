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
MAX_POS, CAPITAL, PISO = 8, 10.0, 5.0          # R2 (dono, 23/11: "mude todas"): 8 posições; cada uma com 4/8 do tamanho (exposição total igual)
POR_POS = 4 / MAX_POS
MAX_HORAS = 24


FATOR_H73 = 5.0      # dono (22/11): "pode aumentar o tamanho da perda também" — carteiras simuladas a 5 × a carteira, 20×


def tamanho(carteira, fator_fixo=None):
    """H64 (dono, 18/11: "com os ganhos, aumentar a porcentagem de entrada"; aprovada no lab/colher_balde.py): nocional = fator × carteira
    realizada, fator = 2,5 × carteira ÷ US$ 10 em [1,25; 5] — cresce no ganho, encolhe na perda. Alavancagem 10× até 2,5× e 20× acima
    (as 4 margens cabem). Devolve (nocional, alavancagem).
    H73 (dono, 22/11; juiz em lab/escala_capital.py): fator_fixo=5 (20×) dobra a posição e a perda por operação nas carteiras simuladas — passou
    (queda 35,7%, sem liquidação na sequência real, 14,3% de chance de bater no piso). Fator 10 a 50× reprovou (termina abaixo do piso). A conta
    de teste continua sem fator_fixo: com o fio negativo dela, o braço maior bateria no piso em 30,1% das ordens."""
    fator = min(5.0, max(1.25, 2.5 * carteira / CAPITAL)) if not fator_fixo else float(fator_fixo)
    return fator * carteira, (10 if fator <= 2.5 else 20)

VALIDADE_S = 75 * 60
VELA_MS = 900_000
# 18/11 (dono: "quem opera são vocês, os agentes do OpenBot, no lugar dos robôs"): o mesmo executor serve a cada agente operador.
# Cada agente escreve SÓ a própria decisão (DECISAO) e este módulo executa na carteira dele (ARQ). Só o chefe (claude) fala com o dono e dá ordens.
AGENTE = os.environ.get("RC_AGENTE", "claude")
ARQ = os.environ.get("RC_ARQ", "robo_claude.json")
DECISAO = os.environ.get("RC_DECISAO", "decisao_claude.json")
NOME = os.environ.get("RC_NOME", "Baleias (chefe da mesa)")


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
    if p.get("alav", ALAV) > ALAV:
        resultado = max(resultado, -p["gasto"])                  # H64: a 20× a perda de uma posição para na margem (liquidação)
    e["caixa"] += p["gasto"] + resultado
    e["fechadas"].append({**p, "saida": saida, "saida_t": agora, "motivo_saida": motivo, "resultado_usd": resultado,
                          "R": resultado / (noc * p.get("stop_pct", STOP_SEG))})
    e["fechadas"] = e["fechadas"][-3000:]
    del e["abertas"][par]
    return f"🤖 {NOME} SAIU da {'VENDA' if sinal < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT"


ALVO_X_STOP, ALVO_MIN = None, None                       # R2 (dono, 23/11): o alvo é do agente; nada de 3 × stop nem mínimo de 1%
LIMITES = {"stop_pct": (0.003, 0.04), "alvo_pct": (0.002, 0.50), "max_min": (5, MAX_HORAS * 60)}


def parametros(pos):
    """H62 (18/11, dono: "operar livremente e tomar suas próprias decisões de entrada e stop; scalper, operações rápidas"): o agente pode
    escolher, por posição, stop_pct, alvo_pct (realiza o lucro) e max_min (prazo). Fora dos limites, o valor é encostado no limite."""
    out = {}
    for k, (lo, hi) in LIMITES.items():
        try:
            v = float(pos.get(k))
        except (TypeError, ValueError):
            continue
        out[k] = min(hi, max(lo, v))
    if pos.get("movel") is False:                            # R2: o agente pode desligar o stop móvel da posição (padrão: ligado, H49)
        out["movel"] = False
    return out


MAX_GATILHOS, GATILHO_MIN = 6, (5, 240)


def validar_gatilhos(gs):
    """H67 (dono, 19/11: "operações constantes, varredura contínua"): o agente deixa níveis armados entre as rodadas dele.
    Cada gatilho: moeda, lado (compra/venda), "acima" OU "abaixo" (preço > 0), motivo; opcionais stop_pct, alvo_pct, max_min, validade_min (5–240).
    Devolve a lista de erros (vazia = válido)."""
    erros = []
    if gs is None:
        return erros
    if not isinstance(gs, list) or len(gs) > MAX_GATILHOS:
        return [f"gatilhos: lista de 0 a {MAX_GATILHOS}"]
    for g in gs:
        m = str((g or {}).get("moeda", "")).upper()
        if not isinstance(g, dict) or not m.endswith("USDT") or g.get("lado") not in ("compra", "venda") or not str(g.get("motivo", "")).strip():
            erros.append(f"gatilho inválido (moeda, lado, motivo): {g}")
            continue
        niveis = [k for k in ("acima", "abaixo") if k in g]
        if len(niveis) != 1 or not isinstance(g[niveis[0]], (int, float)) or g[niveis[0]] <= 0:
            erros.append(f"{m}: o gatilho precisa de UM nível, 'acima' ou 'abaixo', com preço > 0")
        for k, (lo, hi) in {**LIMITES, "validade_min": GATILHO_MIN}.items():
            if k in g and not (isinstance(g[k], (int, float)) and lo <= g[k] <= hi):
                erros.append(f"{m}: {k} = {g[k]!r} fora de {lo}–{hi}")
    return erros


def armar(e, decisao, preco):
    """Decisão nova: os gatilhos dela substituem os anteriores. Nível que o preço já passou não é armado."""
    textos, armados = [], []
    for g in (decisao.get("gatilhos") or []) if not validar_gatilhos(decisao.get("gatilhos")) else []:
        par = str(g["moeda"]).upper()
        par = par if par.endswith("USDT") else par + "USDT"
        tipo = "acima" if "acima" in g else "abaixo"
        nivel, px = float(g[tipo]), preco.get(par)
        if px is not None and ((px >= nivel) if tipo == "acima" else (px <= nivel)):
            textos.append(f"🎯 {NOME}: gatilho de {par[:-4]} {tipo} de {nivel:.6g} não armado — o preço ({px:.6g}) já passou")
            continue
        armados.append({"moeda": par, "lado": g["lado"], "tipo": tipo, "nivel": nivel, "motivo": str(g.get("motivo", ""))[:300],
                        "desde_ms": int(decisao["t"] * 1000), "ate": decisao["t"] + 60 * float(g.get("validade_min", 120)), "decisao_t": decisao["t"],
                        **parametros(g)})
    e["gatilhos"] = armados
    if armados:
        textos.append(f"🎯 {NOME} armou {len(armados)} gatilho(s): " + "; ".join(
            f"{'compra' if a['lado'] == 'compra' else 'venda'} {a['moeda'][:-4]} {a['tipo']} de {a['nivel']:.6g}" for a in armados))
    return textos


def disparou(g, minutos):
    """Primeiro minuto (desde g['desde_ms']) em que o preço cruzou o nível. Devolve (preço de entrada, t_ms) ou None.
    Sem olhar o futuro: se o fechamento do minuto anterior já tinha passado do nível, entra nesse fechamento (a abertura), não no nível."""
    ant = None
    for m in minutos or []:
        t, h, l = m[0], m[1], m[2]
        if t < g["desde_ms"]:
            if len(m) > 3:
                ant = m[3]
            continue
        if (h >= g["nivel"]) if g["tipo"] == "acima" else (l <= g["nivel"]):
            px = g["nivel"]
            if ant is not None and ((ant > px) if g["tipo"] == "acima" else (ant < px)):
                px = ant
            return px, t
        if len(m) > 3:
            ant = m[3]
    return None


def abrir(e, par, lado, entrada, entrada_t, prm, velas, motivo, decisao_t):
    """Abre a posição se couber (piso, 4 posições, caixa). Devolve o texto ou None."""
    patrimonio = e["caixa"] + sum(q["gasto"] for q in e["abertas"].values())
    if patrimonio < PISO or par in e["abertas"] or len(e["abertas"]) >= MAX_POS:
        return None
    noc, alav = tamanho(patrimonio, FATOR_H73)                   # H73 (22/11): 5 × a carteira a 20× — o dobro da H64, por decisão do dono
    noc *= POR_POS                                               # R2: até 8 posições, cada uma com metade; a exposição total não muda
    if 0.95 * noc / alav <= e["caixa"] < noc / alav:             # a 4ª posição: centavos de menos pelo arredondamento
        noc = e["caixa"] * alav
    if e["caixa"] < noc / alav - 1e-9:
        return None
    prm = dict(prm)
    sp = prm.pop("stop_pct", None) or stop_da_moeda(velas.get(par, []))
    e["caixa"] -= noc / alav
    e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": entrada, "entrada_t": entrada_t, "gasto": noc / alav, "nocional": noc, "alav": alav, "stop_pct": sp,
                         "motivo": str(motivo)[:300], "decisao_t": decisao_t,
                         "conferido_ate": -(-int(entrada_t * 1000) // VELA_MS) * VELA_MS, **prm}   # P1: só velas de 15 min depois da entrada
    return (f"🤖 {NOME} ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {entrada:.6g} (US$ {noc:.0f}, stop {sp:.2%}"
            + (f", alvo {prm['alvo_pct']:.2%}" if prm.get("alvo_pct") else "") + (f", prazo {prm['max_min']:.0f} min" if prm.get("max_min") else "")
            + f"): {str(motivo)[:120]}")


def conferir_gatilhos(e, velas, agora, minutos):
    """A cada rodada da nuvem (~3 min): cada gatilho armado é conferido nas velas de 1 min desde que foi armado."""
    textos, ficam = [], []
    for g in e.get("gatilhos", []):
        if agora > g["ate"]:
            textos.append(f"⌛ {NOME}: gatilho de {g['moeda'][:-4]} {g['tipo']} de {g['nivel']:.6g} venceu sem disparar")
            continue
        r = disparou(g, minutos.get(g["moeda"]))
        if not r:
            ficam.append(g)
            continue
        px, t = r
        prm = {k: g[k] for k in LIMITES if k in g}
        txt = abrir(e, g["moeda"], g["lado"], px, (t + 60_000) / 1000, prm, velas,
                    f"🎯 gatilho {g['tipo']} de {g['nivel']:.6g}: {g['motivo']}", g["decisao_t"])
        textos.append(txt or f"🎯 {NOME}: gatilho de {g['moeda'][:-4]} disparou a {px:.6g}, mas não coube (4 posições, caixa ou moeda já aberta)")
    e["gatilhos"] = ficam
    return textos


def passo(e, decisao, velas, agora, vivos=None, minutos_gatilho=None):
    """e: estado; decisao: dados/decisao_claude.json (ou {}); velas: {par: velas fechadas de 15 min}. Devolve os textos."""
    textos = []
    ultimo = {par: k[-1] for par, k in velas.items() if k}
    preco = {par: float(v[4]) for par, v in ultimo.items()}
    preco.update(vivos or {})       # P1 (18/11): preço da rodada (vela de 1 min); H68 (19/11): também moeda fora das velas do v4 (oportunidade do Caçador)
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
        r = SM.conferir(p, SM.MINUTOS.get(par), sp, int(agora * 1000), int(p["entrada_t"] * 1000), alvo_pct=p.get("alvo_pct"), movel=p.get("movel", True))   # H62: alvo do agente
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
        elif agora - p["entrada_t"] > p.get("max_min", MAX_HORAS * 60) * 60 and par in preco:
            textos.append(fechar(e, par, p, preco[par], f"prazo da operação ({p['max_min']:.0f} min)" if p.get("max_min") else
                                 f"tempo máximo ({MAX_HORAS} h) sem nova decisão", agora))
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
            textos.append(f"🤖 {NOME} anotou uma lição: {str(decisao['licao'])[:160]}")
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
                    e["abertas"][par].update(parametros(pos))                         # H62: o agente pode apertar stop, alvo e prazo
                    continue
            if e["caixa"] + sum(q["gasto"] for q in e["abertas"].values()) < PISO:
                break
            if par not in preco or (vivos is not None and par not in vivos):
                # auditoria 19/11: sem o preço da rodada (vela de 1 min) a entrada sairia no fechamento de uma vela de 15 min que já
                # passou (até 15 min atrás: preço conhecido depois do fato). Não entra e avisa, em vez de pular calado.
                textos.append(f"⚠️ {NOME}: {par[:-4]} não entrou — sem o preço da rodada" + ("" if par in preco else " (moeda fora das velas da nuvem)"))
                continue
            txt = abrir(e, par, lado, preco[par], agora, parametros(pos), velas, pos.get("motivo", ""), decisao["t"])
            if txt:
                textos.append(txt)
        textos += armar(e, decisao, preco)                                          # H67: níveis armados até a próxima rodada do agente
    # 3) H67: gatilhos armados, conferidos minuto a minuto desde que foram armados
    if e.get("gatilhos") and not e.get("eliminado"):
        textos += conferir_gatilhos(e, velas, agora, minutos_gatilho or {})
    e["patrimonio"] = e["caixa"] + sum(q["gasto"] + (1 if q["lado"] == "compra" else -1) * q.get("nocional", ORCAMENTO) * (preco.get(q["moeda"], q["entrada"]) / q["entrada"] - 1)
                                       for q in e["abertas"].values())
    if e["patrimonio"] < PISO and not e.get("eliminado"):
        e["eliminado"] = True
        textos.append(f"⛔ {NOME} abaixo de US$ {PISO:.0f}: eliminado, sem novas entradas até o dono decidir")
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
    decisao = ler(DECISAO)
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
        textos.append(GD.texto(NOME, e))
    if guarda == "normal":
        pares = set(e["abertas"]) | {(str(x.get("moeda", "")).upper() if str(x.get("moeda", "")).upper().endswith("USDT") else str(x.get("moeda", "")).upper() + "USDT")
                                     for x in (decisao.get("posicoes") or []) if isinstance(x, dict)} if decisao else set(e["abertas"])
        pg = {str(g.get("moeda", "")).upper() for g in e.get("gatilhos", [])}
        if decisao and decisao.get("t") != e.get("ultima_decisao_t"):
            pg |= {str(g.get("moeda", "")).upper() for g in (decisao.get("gatilhos") or []) if isinstance(g, dict)}
        pg = {p if p.endswith("USDT") else p + "USDT" for p in pg if p}
        desde = min([int(g["desde_ms"]) for g in e.get("gatilhos", [])] + [int((decisao or {}).get("t", agora) * 1000)]) - 120_000
        mins_g = {p: SM.buscar(p, max(desde, int(agora * 1000) - 6 * 3_600_000), int(agora * 1000)) for p in sorted(pg)}
        textos += passo(e, decisao, velas, agora, vivos=SM.precos_da_rodada(sorted(pares | pg), agora * 1000), minutos_gatilho=mins_g)
    else:                                                   # travado: sem posições e sem entradas; a decisão desta hora não vale depois
        e["patrimonio"] = e["caixa"] + sum(q["gasto"] for q in e["abertas"].values())
        if decisao:
            e["ultima_decisao_t"] = decisao.get("t")
    if decisao and e.get("ultima_decisao_t") != antes:                       # decisão nova: o chefe da mesa fala e dá ordens
        if AGENTE == "claude":
            textos += falar_e_ordenar(decisao, agora)
        else:                                                                 # os outros agentes só falam na sala (sem ordens, sem respostas)
            from baleias import equipe as EQ
            for i, m in enumerate(decisao.get("mensagens", []) or []):
                if isinstance(m, dict) and str(m.get("texto", "")).strip():
                    EQ.postar(AGENTE, m["texto"], t=agora + 0.1 + i / 1000)
    idade_h = (agora - decisao.get("t", 0)) / 3600 if decisao else 99.0      # saúde da rotina: sem decisão nova há mais de 2 h = alarme
    if idade_h > 2:                                                           # (15/11: a rotina ficou morta das 03:10 às 09:08 por limite de modelo)
        if not e.get("alerta_rotina"):
            textos.append(f"⚠️ {NOME}: a rotina não decide há {idade_h:.1f} h (limite de uso, erro ou rotina parada). As posições seguem só com stop e tempo máximo.")
        e["alerta_rotina"] = f"sem decisão há {idade_h:.1f} h"
    else:
        if e.get("alerta_rotina"):
            textos.append(f"✅ {NOME}: a rotina voltou a decidir.")
        e["alerta_rotina"] = None
    e["eventos"] = ([{"t": agora, "texto": x} for x in textos] + e["eventos"])[:100]
    arq.write_text(json.dumps(e, ensure_ascii=False))
    equipe.postar_eventos(AGENTE, [x for x in textos if not x.startswith("📣")])
    print(f"🤖 {NOME}: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas · {len(e.get('licoes', []))} lições")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
