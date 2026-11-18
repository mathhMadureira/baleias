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
from executor import tamanho as TM

ORCAMENTO, ALAV, CUSTO_LADO = 25.0, 10.0, 0.0006
STOP_SEG = float(os.environ.get("V4P_STOP", "0.01"))
REALIZAR = float(os.environ.get("V4P_REALIZAR", "0.50"))      # US$ por posição de 25 (0,50 = +2%; o Scalper usa 0,125 = +0,5%)
CAPITAL, PISO, MAX_MESMO_LADO = 10.0, 5.0, 6
LIMIAR = float(os.environ.get("V4P_LIMIAR", "0.03"))            # 0,03 = todas as apostas (agressivo, pedido do dono); 0,12 = só as mais confiantes (H37)
MODO = os.environ.get("V4P_MODO", "limiar")                     # "limiar": entra nas apostas acima de LIMIAR; "ranking" (Caçador): a cada vela as K moedas
K = int(os.environ.get("V4P_K", "2"))                           #   com maior chance de subir (compra) e as K com maior chance de cair (venda) — sempre posicionado
VELA_MS = 900_000
ROTA = os.environ.get("V4P_ROTA", "vela")                       # "vela": sai no fim da vela de 15 min (antigo); "r6": H52 — segura até stop móvel,
MAX_HORAS_ROTA = 24                                             #   stop de segurança, tendência de 24 h virar contra ou 24 h (aprovada no juiz da H52)
FOCO = os.environ.get("V4P_FOCO", "")                           # Scalper D (H51): arquivo com os segmentos a evitar, escrito pelo torneio
ARQ = os.environ.get("V4P_ARQ", "robo_v4_perp.json")
NOME = os.environ.get("V4P_NOME", "Rápido nuvem")


def resolver(p, vela):
    """(preço de saída, motivo) da posição na vela seguinte à do sinal. vela = [t, o, h, l, c, ...] (strings da Binance)."""
    from executor import stop_movel as SM                  # H49: stop móvel e stop de segurança minuto a minuto, na ordem real dos preços
    r = SM.conferir(p, SM.MINUTOS.get(p["moeda"]), STOP_SEG, int(vela[0]) + VELA_MS, int(p["entrada_t"] * 1000), alvo_pct=REALIZAR / ORCAMENTO)
    if r:
        return r[0], r[1]
    o, h, l, c = (float(vela[k]) for k in (1, 2, 3, 4))
    venda = p["lado"] == "venda"
    stop = p["entrada"] * (1 + STOP_SEG if venda else 1 - STOP_SEG)
    alvo = p["entrada"] * (1 - REALIZAR / ORCAMENTO if venda else 1 + REALIZAR / ORCAMENTO)
    if (h >= stop) if venda else (l <= stop):
        return (max(o, stop) if venda else min(o, stop)), f"stop de segurança −{STOP_SEG:.1%}"
    if (l <= alvo) if venda else (h >= alvo):
        return alvo, f"lucro realizado +US$ {REALIZAR:.2f}"
    return c, "fim da vela do v4"


def segmento(lado, prob, t):
    """Os segmentos de uma entrada que o torneio mede (mesmas chaves de executor.torneio.segmentos)."""
    h = time.gmtime(t).tm_hour
    c = abs(prob - 0.5)
    return {f"lado:{lado}", f"horario_utc:{h // 6 * 6:02d}-{h // 6 * 6 + 6:02d}", "confianca:" + ("≥0,08" if c >= 0.08 else "<0,08")}


def evitar(lado, prob, t):
    try:
        excluir = set(json.loads((config.RAIZ / FOCO).read_text()).get("excluir", []))
    except (OSError, ValueError):
        return False
    return bool(segmento(lado, prob, t) & excluir)


def _fechar(e, par, saida, motivo, saida_t):
    p = e["abertas"].pop(par)
    sinal = -1 if p["lado"] == "venda" else 1
    noc = p.get("nocional", ORCAMENTO)
    resultado = noc * sinal * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * noc
    e["caixa"] += p["gasto"] + resultado
    e["fechadas"].append({**p, "saida": saida, "saida_t": saida_t, "motivo": motivo, "resultado_usd": resultado, "R": resultado / (noc * STOP_SEG)})
    return f"🌲 {NOME} SAIU da {'VENDA' if sinal < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT"


def _rota_r6(e, velas, agora_ms, permitido, regime):
    """H52 (rota R6): a posição não sai no fim da vela. Sai pelo stop móvel ou de segurança (minuto a minuto; sem os minutos, nas velas de
    15 min), quando a tendência de 24 h vira contra o lado dela, ou depois de MAX_HORAS_ROTA."""
    from executor import stop_movel as SM
    textos = []
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        entrada_ms = int(p["entrada_t"] * 1000)
        r = SM.conferir(p, SM.MINUTOS.get(par), STOP_SEG, agora_ms, entrada_ms,
                        alvo_pct=REALIZAR / ORCAMENTO if "V4P_REALIZAR" in os.environ else None)   # Scalpers: o alvo deles vale sem fim de vela
        if r:
            textos.append(_fechar(e, par, r[0], r[1], r[2] / 1000))
            continue
        if not SM.MINUTOS.get(par):                          # sem minutos (rede): confere o stop de segurança nas velas de 15 min
            venda = p["lado"] == "venda"
            stop = p["entrada"] * (1 + STOP_SEG if venda else 1 - STOP_SEG)
            for x in velas.get(par, []):
                if x[0] < p.get("conferido_15m", entrada_ms):
                    continue
                if (float(x[2]) >= stop) if venda else (float(x[3]) <= stop):
                    textos.append(_fechar(e, par, stop, f"stop de segurança −{STOP_SEG:.1%}", (x[0] + VELA_MS) / 1000))
                    break
                p["conferido_15m"] = x[0] + VELA_MS
            if par not in e["abertas"]:
                continue
        k = velas.get(par, [])
        if not k:
            continue
        ultimo = float(k[-1][4])
        if permitido and permitido != p["lado"]:
            textos.append(_fechar(e, par, ultimo, f"tendência de 24 h virou para {regime}", (k[-1][0] + VELA_MS) / 1000))
        elif agora_ms / 1000 - p["entrada_t"] > MAX_HORAS_ROTA * 3600:
            textos.append(_fechar(e, par, ultimo, f"tempo máximo ({MAX_HORAS_ROTA} h)", (k[-1][0] + VELA_MS) / 1000))
    return textos


def pendentes_frescos(pendentes, velas):
    """P1 do Treinador (lab, 18/11): moeda que sai da previsão deixava a aposta velha em `pendentes` (atrasos de 2 a 100 h). Só vale a aposta cuja
    vela do sinal é a última vela de 15 min fechada."""
    ultima = max((k[-1][0] for k in velas.values() if k), default=None)
    return {par: p for par, p in pendentes.items() if ultima is not None and p.get("t") == ultima}


def passo(e, pendentes, velas, agora_ms, regime=None, pausado=False, lado_ordem=None, vivos=None):
    """e: estado; pendentes: apostas do v4 {par: {t, px, prob, aposta}}; velas: {par: velas fechadas}. Devolve os textos.
    regime ("baixa"/"alta"/None, executor.regime): regra do dono — na baixa só vende, na alta só compra, e SEGURA a posição de uma vela
    para a seguinte enquanto o regime continuar e o v4 apostar no mesmo lado (sem pagar saída e entrada de novo)."""
    from executor.regime import lado_permitido
    permitido = lado_ordem or lado_permitido(regime)       # ordem do chefe da mesa (baleias.equipe) manda sobre a regra da tendência
    textos = []
    if ROTA == "r6":
        textos += _rota_r6(e, velas, agora_ms, permitido, regime)
    for par in (list(e["abertas"]) if ROTA != "r6" else []):
        p = e["abertas"][par]
        k = velas.get(par, [])
        vela = next((x for x in k if x[0] == p["vela_saida"]), None)
        if vela is None:
            vela = next((x for x in k if x[0] > p["vela_saida"]), None)     # rodada atrasada: usa a primeira vela depois da esperada
            if vela is None:
                continue
        saida, motivo = resolver(p, vela)
        nova = pendentes.get(par)
        mesmo_lado = nova and ((nova["prob"] > 0.5) == (p["lado"] == "compra")) and nova["t"] == vela[0]
        if motivo == "fim da vela do v4" and permitido == p["lado"] and mesmo_lado:
            p["vela_saida"] = vela[0] + VELA_MS                         # segura: a tendência continua e o v4 concorda
            p["rolagens"] = p.get("rolagens", 0) + 1
            e["ultimo_sinal"][par] = nova["t"]
            res_aberto = p.get("nocional", ORCAMENTO) * (1 if p["lado"] == "compra" else -1) * (float(vela[4]) / p["entrada"] - 1)
            textos.append(f"🌲 {NOME} SEGUROU a {'VENDA' if p['lado'] == 'venda' else 'COMPRA'} em {par[:-4]} ({p['rolagens']}ª vela; tendência de {regime}; "
                          f"{res_aberto:+.3f} até agora)")
            continue
        saida, motivo = (saida, motivo) if not (permitido and permitido != p["lado"] and motivo == "fim da vela do v4") else (saida, f"fim da vela (contra a tendência de {regime})")
        sinal = -1 if p["lado"] == "venda" else 1
        noc = p.get("nocional", ORCAMENTO)
        resultado = noc * sinal * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * noc
        e["caixa"] += p["gasto"] + resultado
        e["fechadas"].append({**p, "saida": saida, "saida_t": (vela[0] + VELA_MS) / 1000, "motivo": motivo,
                              "resultado_usd": resultado, "R": resultado / (noc * STOP_SEG)})
        del e["abertas"][par]
        textos.append(f"🌲 {NOME} SAIU da {'VENDA' if sinal < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT")
    e["fechadas"] = e["fechadas"][-3000:]
    if e["caixa"] + sum(p["gasto"] for p in e["abertas"].values()) < PISO:
        if not e.get("eliminado"):
            e["eliminado"] = True
            textos.append(f"⛔ {NOME} abaixo de US$ {PISO:.0f}: eliminado, sem novas entradas até o dono decidir")
        return textos
    if pausado:                                             # o chefe da mesa mandou pausar: segue cuidando das abertas, sem entradas novas
        return textos
    if MODO == "ranking":                                   # Caçador: caça a própria entrada a cada vela, nos dois lados (pedido do dono, 13/11)
        ordem = sorted(pendentes.items(), key=lambda kv: -kv[1]["prob"])
        compras = [(par, p) for par, p in ordem if p["prob"] > 0.51]
        vendas = [(par, p) for par, p in ordem[::-1] if p["prob"] < 0.49]
        if permitido == "venda":                            # na baixa: as 2K vendas mais confiantes, nenhuma compra
            candidatos = vendas[:2 * K]
        elif permitido == "compra":
            candidatos = compras[:2 * K]
        else:
            candidatos = compras[:K] + vendas[:K]
    else:
        candidatos = [(par, p) for par, p in sorted(pendentes.items(), key=lambda kv: -abs(kv[1]["prob"] - 0.5)) if abs(p["prob"] - 0.5) >= LIMIAR]
        if permitido:
            candidatos = [(par, p) for par, p in candidatos if (p["prob"] > 0.5) == (permitido == "compra")]
    for par, p in candidatos:
        if par in e["abertas"] or p["t"] == e["ultimo_sinal"].get(par):
            continue
        lado = "compra" if p["prob"] > 0.5 else "venda"
        if FOCO and evitar(lado, p["prob"], (p["t"] + VELA_MS) / 1000):
            continue
        noc = TM.nocional(e)                                   # H58: proporcional à carteira
        if sum(1 for q in e["abertas"].values() if q["lado"] == lado) >= MAX_MESMO_LADO or not noc:
            continue
        e["caixa"] -= noc / ALAV
        e["ultimo_sinal"][par] = p["t"]
        px_ent, t_ent = (vivos[par], agora_ms / 1000) if vivos and par in vivos else (p["px"], (p["t"] + VELA_MS) / 1000)   # P1 (18/11)
        e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": px_ent, "entrada_t": t_ent, "movel_ate": int(t_ent * 1000),
                             "vela_saida": p["t"] + VELA_MS, "prob": p["prob"], "gasto": noc / ALAV, "nocional": noc}
        textos.append(f"🌲 {NOME} ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {px_ent:.6g} "
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
    for par, p in list(e["abertas"].items()):                 # posição numa moeda que saiu do universo (sem velas no cache): busca as velas dela
        if velas.get(par):                                    # (13–14/11: SOXSB e RWUSD presas por isso travaram a margem dos dois robôs por 12 h)
            continue
        try:
            import urllib.request
            from lab import tartaruga as T
            with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={par}&interval=15m&startTime={p['vela_saida']}&limit=50", timeout=30) as r:
                velas[par] = [x[:7] for x in json.load(r) if x[6] < agora_ms]
        except (OSError, ValueError):
            velas[par] = []
        if not velas[par]:                                    # sem dados nenhum: fecha no preço de entrada e anota (não dá para inventar o preço)
            e["caixa"] += p["gasto"] - 2 * CUSTO_LADO * p.get("nocional", ORCAMENTO)
            e["fechadas"].append({**p, "saida": p["entrada"], "saida_t": time.time(), "motivo": "moeda saiu do universo (fechada no preço de entrada)",
                                  "resultado_usd": -2 * CUSTO_LADO * p.get("nocional", ORCAMENTO), "R": 0.0})
            del e["abertas"][par]
    from executor import regime as RG
    reg, s24, s4 = RG.de_velas(velas)
    e["regime"] = {"lado": reg, "subindo_24h": s24, "subindo_4h": s4, "t": int(time.time())}
    from executor import stop_movel as SM
    SM.preparar(e["abertas"], lambda q: int(q["entrada_t"] * 1000), agora_ms)
    from baleias import equipe
    agente = equipe.POR_ARQUIVO.get(ARQ, {}).get("id", ARQ)
    pausado, lado_ord = equipe.lado_da_ordem(agente, None)
    o = equipe.ordem_vigente(agente)
    e["ordem"] = o
    from executor import guarda_dia as GD                   # H54: dia que ficou positivo não é devolvido
    guarda, pre = GD.checar(e), []
    if guarda == "fechar":
        for par in list(e["abertas"]):
            k = velas.get(par) or []
            pre.append(_fechar(e, par, float(k[-1][4]) if k else e["abertas"][par]["entrada"], GD.motivo(e), time.time()))
        pre.append(GD.texto(NOME, e))
    pausado = pausado or guarda != "normal"
    pendentes = pendentes_frescos(pendentes, velas)                      # P1 (a): só a aposta da última vela de 15 min fechada
    textos = pre + passo(e, pendentes, velas, agora_ms, regime=reg, pausado=pausado, lado_ordem=lado_ord,
                         vivos=SM.precos_da_rodada(sorted(pendentes), agora_ms))
    if o:
        textos.insert(0, f"📣 {NOME} cumprindo ordem do chefe: {equipe.ACOES[o['acao']]} ({o.get('motivo', '')[:80]})")
    if reg:
        textos.insert(0, f"🧭 {NOME}: mercado em tendência de {reg} ({s24}% das moedas subindo em 24 h, {s4}% em 4 h) → só {'vendas' if reg == 'baixa' else 'compras'}")
    e["eventos"] = ([{"t": time.time(), "texto": x} for x in textos] + e["eventos"])[:100]
    ultimo = {par: float(k[-1][4]) for par, k in velas.items() if k}        # revisão 15/11: a carteira inclui o resultado das posições abertas
    e["patrimonio"] = e["caixa"] + sum(p["gasto"] + p.get("nocional", ORCAMENTO) * (1 if p["lado"] == "compra" else -1) * (ultimo.get(par, p["entrada"]) / p["entrada"] - 1)
                                       for par, p in e["abertas"].items())
    arq.write_text(json.dumps(e))
    equipe.postar_eventos(agente, [x for x in textos if not x.startswith(("🧭", "📣"))])
    print(f"🌲 {NOME} (v4): patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
