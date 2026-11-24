"""Mesa ao vivo: o que cada agente do OpenBot está fazendo agora, lido dos rastros locais (só leitura).

Fontes (pastas do OpenBot nesta máquina; mudam por BALEIAS_OPENBOT):
- operar/rodadas/<data>-<agente>-varredura.json / -escolha.json e proposta_<agente>.json  → etapa e "pensamento" dos operadores
- chefe/rodadas/<data>-leitura.json / -chefe-varredura.json / -decisao.json               → etapa e pensamento do chefe
- operar/corretoras/<agente>.json e chefe/robo_openbot_testnet.json                       → conta de demonstração: patrimônio, abertas, ordens
- oportunidades_cacador.jsonl e cacador/rodadas                                           → avisos do Caçador
Nada aqui escreve, manda ordem ou lê chave.
"""
import json
import os
import re
import time
from pathlib import Path

RAIZ = Path(os.environ.get("BALEIAS_OPENBOT", "/home/servidor-de-producao/OpenBot"))
SHARED = RAIZ / "Shared" / "baleias"
OPERAR = SHARED / "operar"
CHEFE = RAIZ / "Agents" / "agent-85eaa35b-7f9b-407c-839d-fed207b6b72d" / "chefe"
ATIVO_S = 240          # arquivo gravado há menos de 4 min = o agente está trabalhando agora

AGENTES = [
    {"id": "claude", "nome": "Chefe da mesa", "avatar": "⚓", "papel": "decide e opera a conta de teste da Binance", "corretora": "Binance testnet"},
    {"id": "guardiao", "nome": "Guardião", "avatar": "🛡", "papel": "tendência + memecoins · vigia", "corretora": "BingX VST"},
    {"id": "treinador", "nome": "Treinador", "avatar": "🎯", "papel": "método do Caçador", "corretora": "Bybit Demo"},
    {"id": "laboratorio", "nome": "Laboratório", "avatar": "🔬", "papel": "só o que passou no lab", "corretora": "Gate TestNet"},
    {"id": "cacador", "nome": "Caçador", "avatar": "🔭", "papel": "procura oportunidades; não opera", "corretora": None},
    {"id": "memecoins", "nome": "Memecoins", "avatar": "🐸", "papel": "lançamentos de memecoins (simulado)", "corretora": None},
]
ETAPAS = ["raspagem", "leitura", "decisão", "corretora"]


def _json(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def _mtime(p):
    try:
        return Path(p).stat().st_mtime
    except OSError:
        return None


def _ultimo(pasta, padrao):
    """(caminho, mtime) do arquivo mais novo da pasta cujo nome casa com o padrão."""
    melhor = (None, None)
    try:
        for f in Path(pasta).iterdir():
            if re.search(padrao, f.name):
                t = _mtime(f)
                if t and (melhor[1] is None or t > melhor[1]):
                    melhor = (f, t)
    except OSError:
        pass
    return melhor


def _curto(x, n=240):
    x = " ".join(str(x or "").split())
    return x if len(x) <= n else x[: n - 1] + "…"


def _posicoes(d):
    return [{"moeda": p.get("moeda"), "lado": p.get("lado"), "motivo": _curto(p.get("motivo"), 160)}
            for p in (d or {}).get("posicoes") or [] if isinstance(p, dict)]


def _conta(arq, nome):
    e = _json(arq)
    if not e:
        return None
    ab = []
    for par, p in (e.get("abertas") or {}).items():
        ab.append({"moeda": par, "lado": p.get("lado"), "entrada": p.get("entrada"), "desde": p.get("entrada_t"),
                   "stop": (p.get("stop") or {}).get("preco") if isinstance(p.get("stop"), dict) else None,
                   "alvo": (p.get("alvo") or {}).get("preco") if isinstance(p.get("alvo"), dict) else None,
                   "resultado": p.get("resultado_aberto")})
    fe = e.get("fechadas") or []
    ev = sorted((x for x in e.get("eventos") or [] if isinstance(x, dict) and x.get("t")), key=lambda x: -x["t"])[:8]
    return {"nome": nome, "patrimonio": e.get("patrimonio"), "capital": e.get("capital_inicial") or 10.0, "abertas": ab,
            "fechadas": len(fe), "atualizado": e.get("atualizado"), "eventos": [{"t": x["t"], "texto": _curto(x["texto"], 200)} for x in ev]}


def _operador(a, agora):
    ag = a["id"]
    v = _ultimo(OPERAR / "rodadas", rf"-{ag}-varredura\.json$")
    es = _ultimo(OPERAR / "rodadas", rf"-{ag}-escolha\.json$")
    pr = OPERAR / "rodadas" / f"proposta_{ag}.json"
    conta = _conta(OPERAR / "corretoras" / f"{ag}.json", a["corretora"])
    tempos = {"raspagem": v[1], "leitura": es[1], "decisão": _mtime(pr), "corretora": (conta or {}).get("atualizado")}
    d = _json(pr) or {}
    return tempos, d, conta


def _chefe(a, agora):
    r = CHEFE / "rodadas"
    v = _ultimo(r, r"-chefe-varredura\.json$")
    le = _ultimo(r, r"-leitura\.json$")
    de = _ultimo(r, r"-decisao\.json$")
    conta = _conta(CHEFE / "robo_openbot_testnet.json", a["corretora"])
    tempos = {"raspagem": v[1], "leitura": le[1], "decisão": de[1], "corretora": (conta or {}).get("atualizado")}
    d = _json(de[0]) if de[0] else {}
    return tempos, d or {}, conta


def _avisos(agora, n=8):
    out = []
    try:
        linhas = (SHARED / "oportunidades_cacador.jsonl").read_text().splitlines()[-200:]
    except OSError:
        linhas = []
    for l in reversed(linhas):
        try:
            x = json.loads(l)
        except ValueError:
            continue
        out.append({"t": x.get("t"), "moeda": x.get("moeda"), "lado": x.get("lado"), "sinal": x.get("sinal"), "forca": x.get("forca"),
                    "entrada": x.get("entrada"), "valido": (x.get("valida_ate") or 0) > agora, "motivo": _curto(x.get("motivo"), 160)})
        if len(out) >= n:
            break
    return out


def vivo(agora=None):
    agora = agora or time.time()
    mesa, feed = [], []
    avisos = _avisos(agora)
    for a in AGENTES:
        item = {**a, "etapas": {}, "pensamento": None, "mensagem": None, "posicoes": [], "conta": None, "ultimo": None}
        if a["id"] == "claude":
            tempos, d, conta = _chefe(a, agora)
        elif a["id"] in ("guardiao", "treinador", "laboratorio"):
            tempos, d, conta = _operador(a, agora)
        elif a["id"] == "cacador":
            _, t = _ultimo(SHARED / "cacador" / "rodadas", r"\.json$")
            tempos, d, conta = {"raspagem": t, "leitura": t, "decisão": avisos[0]["t"] if avisos else None}, {}, None
            if avisos:
                item["pensamento"] = f"Último aviso: {avisos[0]['moeda']} {avisos[0]['lado']} ({avisos[0]['sinal']}, força {avisos[0]['forca']}). {avisos[0]['motivo']}"
        else:
            tempos, d, conta = {}, {}, None
        item["etapas"] = {k: tempos.get(k) for k in ETAPAS if k in tempos}
        ts = [t for t in tempos.values() if t]
        item["ultimo"] = max(ts) if ts else None
        item["trabalhando"] = bool(item["ultimo"] and agora - item["ultimo"] < ATIVO_S)
        if ts:
            item["etapa_atual"] = max(((k, t) for k, t in tempos.items() if t), key=lambda kt: kt[1])[0]
        if d:
            item["pensamento"] = _curto(d.get("leitura"), 320) or item["pensamento"]
            ms = d.get("mensagens") or []
            m = ms[0] if ms else None
            item["mensagem"] = _curto(m.get("texto") if isinstance(m, dict) else m, 220) if m else None
            item["posicoes"] = _posicoes(d)
        item["conta"] = conta
        mesa.append(item)
        for e in (conta or {}).get("eventos", []):
            feed.append({"t": e["t"], "agente": a["id"], "avatar": a["avatar"], "nome": a["nome"], "tipo": "ordem", "texto": e["texto"]})
        if d and item["etapas"].get("decisão"):
            feed.append({"t": item["etapas"]["decisão"], "agente": a["id"], "avatar": a["avatar"], "nome": a["nome"], "tipo": "decisão",
                         "texto": "decidiu: " + (", ".join(f"{p['moeda'].replace('USDT', '')} {p['lado']}" for p in item["posicoes"]) or "ficar de fora")})
    for x in avisos:
        if x.get("t"):
            feed.append({"t": x["t"], "agente": "cacador", "avatar": "🔭", "nome": "Caçador", "tipo": "aviso",
                         "texto": f"aviso: {str(x['moeda']).replace('USDT', '')} {x['lado']} · {x['sinal']} · força {x['forca']}"})
    feed.sort(key=lambda x: -x["t"])
    return {"t": agora, "mesa": mesa, "feed": feed[:40], "avisos": avisos}
