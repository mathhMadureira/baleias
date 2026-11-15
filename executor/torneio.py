"""Torneio dos robôs — campeão × desafiantes ao vivo ("Machine Learning for High-Risk Applications", cap. 3: A/B e champion-challenger).

Missão do dono (15/11): "ver qual robô performa melhor e aperfeiçoá-lo, inclusive suas habilidades".
A cada rodada da nuvem: placar de todos os robôs com as mesmas medidas (carteira, operações, acerto, ganho e perda médios, fator de lucro =
soma dos ganhos ÷ soma das perdas). Campeão = maior fator de lucro entre os que têm pelo menos MIN_OPS operações (com menos, "não sei").
Os desafiantes do campeão (clones com UMA mudança, H50) são julgados contra ele nas operações do mesmo período: o desafiante que tiver
fator de lucro maior E carteira maior depois de MIN_OPS operações é anunciado na sala para virar a nova versão do campeão.
Escreve dados/torneio.json e vai no retrato do chefe da mesa.
"""
import json
import time

from baleias import config, equipe

MIN_OPS = 30
DESAFIANTES = {"scalper": ["scalper_b", "scalper_c", "scalper_d"]}     # H50/H51: clones do Scalper
FOCO_MIN_OPS, FOCO_Z = 50, -2.0                           # H51: segmento a evitar só com ≥ 50 operações e perda de 2 erros-padrão


def medir(e, desde=0):
    f = [x for x in (e.get("fechadas") or []) if (x.get("entrada_t") or 0) >= desde]
    res = [float(x.get("resultado_usd") or 0) for x in f]
    g, p = [x for x in res if x > 0], [x for x in res if x < 0]
    return {"ops": len(f), "acerto": round(len(g) / len(f), 3) if f else None, "soma": round(sum(res), 3),
            "ganho_medio": round(sum(g) / len(g), 3) if g else None, "perda_media": round(sum(p) / len(p), 3) if p else None,
            "fator_lucro": round(sum(g) / -sum(p), 2) if p else (None if not g else 99.0),
            "carteira": round(float(e.get("patrimonio", e.get("carteira", 10.0)) or 0), 2)}


def segmentos(fechadas):
    """Soma, n e z (média ÷ erro-padrão) do resultado por segmento de ENTRADA (lado, faixa de horário UTC, confiança do v4)."""
    import math
    from executor.v4_perp_nuvem import segmento
    seg = {}
    for x in fechadas:
        if x.get("prob") is None or not x.get("entrada_t"):
            continue
        for k in segmento(x["lado"], x["prob"], x["entrada_t"]):
            seg.setdefault(k, []).append(float(x.get("resultado_usd") or 0))
    out = {}
    for k, v in seg.items():
        n, m = len(v), sum(v) / len(v)
        dp = math.sqrt(sum((a - m) ** 2 for a in v) / (n - 1)) if n > 1 else 0.0
        out[k] = {"n": n, "soma": round(sum(v), 3), "z": round(m / (dp / math.sqrt(n)), 2) if dp else 0.0}
    return out


def foco(fechadas):
    """Segmentos que o Scalper D deve evitar: os que perdem com ≥ FOCO_MIN_OPS operações e z ≤ FOCO_Z. Nunca exclui os dois lados."""
    seg = segmentos(fechadas)
    ruins = sorted((k for k, v in seg.items() if v["n"] >= FOCO_MIN_OPS and v["z"] <= FOCO_Z and v["soma"] < 0), key=lambda k: seg[k]["z"])
    if {"lado:compra", "lado:venda"} <= set(ruins):
        ruins.remove("lado:compra" if seg["lado:compra"]["z"] > seg["lado:venda"]["z"] else "lado:venda")
    return ruins, seg


def avaliar(estados):
    """estados: {id do agente: estado}. Devolve o placar, o campeão e os vereditos dos desafiantes."""
    placar = {ag: medir(e) for ag, e in estados.items() if e}
    validos = {ag: m for ag, m in placar.items() if m["ops"] >= MIN_OPS and m["fator_lucro"] is not None and ag not in sum(DESAFIANTES.values(), [])}
    campeao = max(validos, key=lambda a: (validos[a]["fator_lucro"], validos[a]["carteira"])) if validos else None
    vereditos = []
    for camp, desafs in DESAFIANTES.items():
        for d in desafs:
            ed, ec = estados.get(d), estados.get(camp)
            if not ed or not ec:
                continue
            desde = min((x.get("entrada_t") or 0) for x in ed.get("fechadas") or [{"entrada_t": time.time()}])
            md, mc = medir(ed, desde), medir(ec, desde)          # mesmo período
            if md["ops"] < MIN_OPS:
                v = f"não sei ainda ({md['ops']} de {MIN_OPS} operações)"
            elif (md["fator_lucro"] or 0) > (mc["fator_lucro"] or 0) and md["soma"] > mc["soma"]:
                v = "GANHOU do campeão: candidato a nova versão"
            else:
                v = "não ganhou do campeão"
            vereditos.append({"desafiante": d, "campeao": camp, "desafiante_mede": md, "campeao_mede": mc, "veredito": v})
    return {"t": int(time.time()), "placar": placar, "campeao": campeao, "vereditos": vereditos, "min_ops": MIN_OPS}


def main():
    estados = {}
    for a in equipe.EQUIPE:
        arq = config.RAIZ / a["arquivo"]
        try:
            estados[a["id"]] = json.loads(arq.read_text()) if arq.exists() else None
        except ValueError:
            estados[a["id"]] = None
    r = avaliar(estados)
    if estados.get("scalper"):                                 # H51: o foco do Scalper D vem dos segmentos do Scalper original
        ruins, seg = foco(estados["scalper"].get("fechadas") or [])
        r["segmentos_scalper"] = seg
        arq_foco = config.RAIZ / "foco_scalper.json"
        antes_foco = json.loads(arq_foco.read_text()).get("excluir", []) if arq_foco.exists() else []
        arq_foco.write_text(json.dumps({"t": int(time.time()), "excluir": ruins, "segmentos": seg}, ensure_ascii=False))
        if ruins != antes_foco:
            equipe.postar("torneio", "🎯 Scalper D (foco) " + (f"passa a evitar: {', '.join(ruins)} (perdem com ≥ {FOCO_MIN_OPS} operações e z ≤ {FOCO_Z})" if ruins else "sem segmentos a evitar"), tipo="evento")
    arq = config.RAIZ / "torneio.json"
    antes = json.loads(arq.read_text()) if arq.exists() else {}
    arq.write_text(json.dumps(r, ensure_ascii=False))
    nome = lambda ag: f"{equipe.POR_ID[ag]['avatar']} {equipe.POR_ID[ag]['nome']}" if ag in equipe.POR_ID else str(ag)
    if r["campeao"] and r["campeao"] != antes.get("campeao"):
        m = r["placar"][r["campeao"]]
        equipe.postar("torneio", f"🏆 Novo campeão da mesa: {nome(r['campeao'])} — fator de lucro {m['fator_lucro']}, {m['ops']} operações, carteira US$ {m['carteira']:.2f}", tipo="evento")
    vel = {v["desafiante"]: v["veredito"] for v in antes.get("vereditos", [])}
    for v in r["vereditos"]:
        if v["veredito"].startswith("GANHOU") and not vel.get(v["desafiante"], "").startswith("GANHOU"):
            equipe.postar("torneio", f"🥊 {nome(v['desafiante'])} ganhou de {nome(v['campeao'])} no mesmo período: fator {v['desafiante_mede']['fator_lucro']} × {v['campeao_mede']['fator_lucro']}, "
                          f"soma {v['desafiante_mede']['soma']:+.2f} × {v['campeao_mede']['soma']:+.2f}", tipo="evento")
    print("🏆 Torneio: campeão", nome(r["campeao"]) if r["campeao"] else "não sei (ninguém com 30 operações)", "·",
          " · ".join(f"{nome(a)} FL {m['fator_lucro']} ({m['ops']})" for a, m in sorted(r["placar"].items(), key=lambda kv: -(kv[1]["fator_lucro"] or 0))))


if __name__ == "__main__":
    main()
