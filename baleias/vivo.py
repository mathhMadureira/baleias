"""Painel da equipe (24/11, organização nova): a missão da carteira única, o foco, a rodada passando de agente em agente e a conta do operador.

Lê só arquivos locais (nada escreve, nada manda ordem, nenhuma chave):
- Shared/baleias/FOCO.json                      → onde a equipe opera
- Shared/baleias/equipe/quadro.jsonl            → a linha que cada agente registra ao terminar a sua parte da rodada
- Shared/baleias/operar/corretoras/laboratorio.json → a carteira única (patrimônio, posição, stop/alvo, fechadas, eventos)
"""
import json
import os
import time
from pathlib import Path

RAIZ = Path(os.environ.get("BALEIAS_OPENBOT", "/home/servidor-de-producao/OpenBot"))
SHARED = RAIZ / "Shared" / "baleias"
OPERADOR = "laboratorio"
CAPITAL, META = 10.0, 20.0
RODADA_S = 10 * 60

FLUXO = [                                                     # 24/11 (dono: "modelo mais rápido"): olheiro → operador
    {"id": "cacador", "nome": "Caçador", "avatar": "🔭", "cargo": "olheiro", "entrega": "3 entradas a mercado (criptos e memecoins)"},
    {"id": "laboratorio", "nome": "Laboratório", "avatar": "🔬", "cargo": "operador", "entrega": "entra a mercado e executa"},
]
APOIO = [
    {"id": "baleias", "nome": "Baleias", "avatar": "⚓", "cargo": "chefe: coordena e fala com o dono"},
    {"id": "guardiao", "nome": "Guardião", "avatar": "🛡", "cargo": "risco: revisa a posição aberta"},
    {"id": "treinador", "nome": "Treinador", "avatar": "🎯", "cargo": "juiz: revisa as operações fechadas"},
    {"id": "memecoins", "nome": "Memecoins", "avatar": "🐸", "cargo": "pesquisa de memecoins"},
    {"id": "engenheiro", "nome": "Engenheiro", "avatar": "🛠", "cargo": "infraestrutura e corretora"},
    {"id": "minerador", "nome": "Minerador", "avatar": "⛏", "cargo": "tesouraria: ganhos grátis"},
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
    fe = [{"moeda": x.get("moeda"), "lado": x.get("lado"), "entrada": x.get("entrada"), "saida": x.get("saida"), "t": x.get("saida_t"),
           "resultado": x.get("resultado_usd"), "motivo": str(x.get("motivo_saida") or "")[:120]} for x in e.get("fechadas") or []]
    ev = sorted((x for x in e.get("eventos") or [] if isinstance(x, dict) and x.get("t")), key=lambda x: -x["t"])[:30]
    return {"existe": True, "corretora": e.get("corretora"), "patrimonio": e.get("patrimonio", CAPITAL), "capital": e.get("capital_inicial") or CAPITAL,
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
    feed = [{"t": x["t"], "agente": x.get("agente"), "texto": x.get("texto"), "tipo": "equipe"} for x in q[-60:]]
    feed += [{"t": x["t"], "agente": "laboratorio", "texto": x["texto"], "tipo": "corretora"} for x in c["eventos"]]
    feed.sort(key=lambda x: -x["t"])
    for f in feed:
        a = NOMES.get(f["agente"], {})
        f["avatar"], f["nome"] = a.get("avatar", "•"), a.get("nome", f["agente"])
    return {"t": agora, "foco": foco, "missao": {"capital": c["capital"], "meta": META, "patrimonio": c["patrimonio"],
            "progresso": (c["patrimonio"] - c["capital"]) / (META - c["capital"]), "operacoes": len(rs),
            "ganhos": sum(1 for r in rs if r > 0), "resultado": sum(rs), "melhor": max(rs) if rs else None, "pior": min(rs) if rs else None},
            "fluxo": fluxo, "rodada_inicio": inicio, "apoio": [{**a, "ultimo": ult.get(a["id"])} for a in APOIO], "carteira": c, "feed": feed[:60]}
