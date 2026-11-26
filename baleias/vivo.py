"""Painel da equipe (24/11, organização nova): a missão da carteira única, o foco, a rodada passando de agente em agente e a conta do operador.

Lê só arquivos locais (nada escreve, nada manda ordem, nenhuma chave):
- Shared/baleias/FOCO.json                      → onde a equipe opera
- Shared/baleias/equipe/quadro.jsonl            → a linha que cada agente registra ao terminar a sua parte da rodada
- Shared/baleias/operar/corretoras/laboratorio.json → a carteira única (patrimônio, posição, stop/alvo, fechadas, eventos)
"""
import json
import os
import time
import urllib.request
from pathlib import Path

RAIZ = Path(os.environ.get("BALEIAS_OPENBOT", "/home/servidor-de-producao/OpenBot"))
SHARED = RAIZ / "Shared" / "baleias"
OPERADOR = "laboratorio"
CAPITAL, META = 10.0, 20.0
RODADA_S = 10 * 60

FLUXO = [                                                     # 25/11: o MOTOR executa a cada 30 s; os agentes o comandam
    {"id": "laboratorio", "nome": "Operador", "avatar": "🎛", "cargo": "comanda o motor", "entrega": "lados, força mínima, bloqueios"},
    {"id": "cacador", "nome": "Radar", "avatar": "📡", "cargo": "moedas preferidas", "entrega": "o que priorizar e evitar"},
]
APOIO = [
    {"id": "guardiao", "nome": "Risco", "avatar": "🛡", "cargo": "manda sair quando a tese quebra"},
    {"id": "memecoins", "nome": "Memes", "avatar": "🐸", "cargo": "memecoins e risco de golpe"},
    {"id": "treinador", "nome": "Juiz", "avatar": "⚖", "cargo": "placar e lições"},
    {"id": "engenheiro", "nome": "Engenheiro", "avatar": "🛠", "cargo": "saúde do motor e do painel"},
    {"id": "minerador", "nome": "Tesouro", "avatar": "💰", "cargo": "ganhos grátis"},
    {"id": "baleias", "nome": "Baleias", "avatar": "🐋", "cargo": "chefe da equipe"},
]
NOMES = {a["id"]: a for a in FLUXO + APOIO}


def _json(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def _quadro(n=300):
    out = []
    try:
        for l in (SHARED / "equipe" / "quadro.jsonl").read_text().splitlines()[-n:]:
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


_PRECO = {}


def preco_bingx(par):
    """Preço público do perpétuo da BingX VST, com memória de 10 s (o painel lê a cada 4 s)."""
    t, v = _PRECO.get(par, (0, None))
    if time.time() - t < 10:
        return v
    try:
        with urllib.request.urlopen(f"https://open-api-vst.bingx.com/openApi/swap/v2/quote/price?symbol={par[:-4]}-USDT", timeout=4) as r:
            v = float(json.load(r)["data"]["price"])
    except (OSError, ValueError, KeyError, TypeError):
        v = None
    _PRECO[par] = (time.time(), v)
    return v


def causa_saida(x):
    """Quem fechou: o PLANO (alvo, stop, stop móvel, prazo) ou a EQUIPE (tese quebrada, Risco, pedido de agente, troca manual)."""
    m = str(x.get("motivo_saida") or "").lower()
    if "alvo" in m:
        return ("plano", "alvo")
    if "móvel" in m or "movel" in m:
        return ("plano", "stop móvel")
    if "prazo" in m or "tempo máximo" in m:
        return ("plano", "prazo")
    if "tese quebrou" in m:
        return ("equipe", "tese quebrou")
    if "risco" in m or "guardiao" in m:
        return ("equipe", "Risco")
    if "pedido de" in m:
        return ("equipe", "pedido de agente")
    if "fora da lista" in m or "inverteu" in m:
        return ("equipe", "troca manual")
    if "stop" in m:
        return ("plano", "stop")
    return ("equipe", m[:20] or "?")


def _carteira():
    e = _json(SHARED / "operar" / "corretoras" / f"{OPERADOR}.json")
    if not e:
        return {"existe": False, "corretora": None, "patrimonio": CAPITAL, "capital": CAPITAL, "abertas": [], "fechadas": [], "eventos": [],
                "atualizado": None}
    ab = []
    for par, p in (e.get("abertas") or {}).items():
        st, al = p.get("stop") if isinstance(p.get("stop"), dict) else {}, p.get("alvo") if isinstance(p.get("alvo"), dict) else {}
        ab.append({"moeda": par, "lado": p.get("lado"), "entrada": p.get("entrada"), "desde": p.get("entrada_t"), "stop": st.get("preco"),
                   "alvo": al.get("preco"), "nocional": p.get("nocional"), "alav": p.get("alav"), "max_min": p.get("max_min"),
                   "motivo": str(p.get("motivo") or "")[:240]})
        if isinstance(p.get("resultado_aberto"), (int, float)):     # 25/11: o resultado aberto é o da CORRETORA (o mesmo do patrimônio)
            ab[-1]["resultado"] = round(p["resultado_aberto"], 4)
            ab[-1]["agora"] = p.get("preco_corretora")
            continue
        agora_px = preco_bingx(par) if os.environ.get("BALEIAS_SEM_REDE") != "1" else None
        if agora_px and p.get("entrada") and p.get("nocional"):
            sinal = 1 if p.get("lado") == "compra" else -1
            ab[-1]["agora"] = agora_px
            ab[-1]["resultado"] = round(p["nocional"] * (agora_px / p["entrada"] - 1) * sinal, 4)
    fe = [{"moeda": x.get("moeda"), "lado": x.get("lado"), "entrada": x.get("entrada"), "saida": x.get("saida"), "t": x.get("saida_t"),
           "resultado": x.get("resultado_usd"), "taxas": x.get("taxas"), "motivo": str(x.get("motivo_saida") or "")[:120],
           "causa": causa_saida(x)} for x in e.get("fechadas") or []]
    ev = sorted((x for x in e.get("eventos") or [] if isinstance(x, dict) and x.get("t")), key=lambda x: -x["t"])[:30]
    realizado = sum(x["resultado"] for x in fe if isinstance(x["resultado"], (int, float)))
    aberto = sum(a.get("resultado") or 0 for a in ab)
    cap = e.get("capital_inicial") or CAPITAL
    conta = {"capital": cap, "realizado": round(realizado, 4), "aberto": round(aberto, 4),
             "taxas_entrada_abertas": round(-sum((p.get("taxa_entrada") or 0) for p in (e.get("abertas") or {}).values()), 4),
             "patrimonio": e.get("patrimonio")}
    conta["diferenca"] = round((conta["patrimonio"] or 0) - (cap + realizado + aberto), 4)   # taxa de entrada é descontada no fechamento
    return {"existe": True, "conta": conta, "corretora": e.get("corretora"), "patrimonio": e.get("patrimonio", CAPITAL), "capital": e.get("capital_inicial") or CAPITAL,
            "caixa": e.get("caixa"), "abertas": ab, "fechadas": fe, "eventos": ev, "atualizado": e.get("atualizado")}


def vivo(agora=None):
    agora = agora or time.time()
    foco = _json(SHARED / "FOCO.json") or {"foco": "parado", "descricao": "FOCO.json ausente: parado"}
    q = _quadro()
    ult = {}
    for x in q:
        ult[x.get("agente")] = x
    inicio = None                                         # a rodada atual começa na última linha do Caçador
    for x in reversed(q):
        if x.get("agente") == "cacador":
            inicio = x["t"]
            break
    fluxo = []
    for a in FLUXO:
        u = ult.get(a["id"])
        feita = bool(u and inicio and u["t"] >= inicio and agora - inicio < RODADA_S)
        fluxo.append({**a, "ultimo": u, "nesta_rodada": feita})
    pendente = next((i for i, a in enumerate(fluxo) if not a["nesta_rodada"]), None)
    if inicio and agora - inicio < RODADA_S and pendente is not None:
        fluxo[pendente]["trabalhando"] = True
    c = _carteira()
    rs = [x["resultado"] for x in c["fechadas"] if isinstance(x["resultado"], (int, float))]
    feed = [{"t": x["t"], "agente": x.get("agente"), "texto": x.get("texto"), "tipo": "equipe", "conf": x.get("conf")} for x in q[-60:]]
    feed += [{"t": x["t"], "agente": "laboratorio", "texto": x["texto"], "tipo": "corretora"} for x in c["eventos"]]
    canal = []
    try:
        for l in (SHARED / "equipe" / "canal.jsonl").read_text().splitlines()[-60:]:
            m = json.loads(l)
            de, para = NOMES.get(m["de"], {}), NOMES.get(m["para"], {})
            canal.append({**m, "de_nome": de.get("nome", "Motor" if m["de"] == "motor" else m["de"]), "de_avatar": de.get("avatar", "⚙"),
                          "para_nome": "todos" if m["para"] == "todos" else para.get("nome", m["para"])})
    except (OSError, ValueError, KeyError):
        pass
    feed.sort(key=lambda x: -x["t"])
    for f in feed:
        a = NOMES.get(f["agente"], {})
        f["avatar"], f["nome"] = a.get("avatar", "•"), a.get("nome", f["agente"])
    hoje0 = agora - (agora % 86400)
    cont = {}
    for x in q:
        a = x.get("agente")
        cont.setdefault(a, {"total": 0, "hoje": 0})
        cont[a]["total"] += 1
        cont[a]["hoje"] += x["t"] >= hoje0
    curva, eq = [], c["capital"]
    for x in sorted((f for f in c["fechadas"] if isinstance(f["resultado"], (int, float)) and f["t"]), key=lambda f: f["t"]):
        eq += x["resultado"]
        curva.append([x["t"], round(eq, 4)])
    curva.append([agora, round(c["patrimonio"], 4)])
    risco = _json(SHARED / "equipe" / "risco.json")
    desc, ult_desc = {}, []
    try:
        for l in (SHARED / "equipe" / "descartes.jsonl").read_text().splitlines()[-2000:]:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            r = x.get("regra") or "?"
            d = desc.setdefault(r, {"regra": r, "total": 0, "hoje": 0, "ultimo": None})
            d["total"] += 1
            d["hoje"] += x.get("t", 0) >= agora - (agora % 86400)
            d["ultimo"] = x.get("moeda")
            ult_desc.append(x)
    except OSError:
        pass
    for e_ in c["eventos"]:                                  # recusas da própria corretora
        if "não entra" in e_["texto"] or "recusou" in e_["texto"]:
            d = desc.setdefault("corretora recusou", {"regra": "corretora recusou", "total": 0, "hoje": 0, "ultimo": None})
            d["total"] += 1
            d["hoje"] += e_["t"] >= agora - (agora % 86400)
            d["ultimo"] = e_["texto"].split(":")[0][:20]
    desk = []
    for a in FLUXO + APOIO:
        u = ult.get(a["id"])
        desk.append({**a, "ultimo": u, "contagem": cont.get(a["id"], {"total": 0, "hoje": 0}),
                     "ativo": bool(u and agora - u["t"] < 600)})
    motor = {"estado": _json(SHARED / "equipe" / "motor_estado.json"), "comando": _json(SHARED / "equipe" / "motor.json")}
    return {"t": agora, "foco": foco, "curva": curva, "desk": desk, "risco": risco, "motor": motor, "canal": canal[::-1],
            "descartes": sorted(desc.values(), key=lambda d: -d["total"]), "descartes_recentes": ult_desc[-8:][::-1], "missao": {"capital": c["capital"], "meta": META, "patrimonio": c["patrimonio"],
            "progresso": (c["patrimonio"] - c["capital"]) / (META - c["capital"]), "operacoes": len(rs),
            "ganhos": sum(1 for r in rs if r > 0), "resultado": sum(rs), "melhor": max(rs) if rs else None, "pior": min(rs) if rs else None},
            "fluxo": fluxo, "rodada_inicio": inicio, "apoio": [{**a, "ultimo": ult.get(a["id"])} for a in APOIO], "carteira": c, "feed": feed[:60]}
