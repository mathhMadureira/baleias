"""Quadro da rodada da equipe (24/11): cada agente registra 1 linha ao terminar a sua parte; o painel mostra a rodada ao vivo.

Uso: python3 -I quadro.py <agente> "<resumo de 1 linha com números>" [--conf alta|média|baixa]
     python3 -I quadro.py descarte <agente> <MOEDA> "<regra>"   → entrada que NÃO foi feita e por qual regra (painel: "Descartadas por regra")
     regras: esticada | contra no 15 min | liquidez baixa | spread largo | risco de golpe | sem dado | vaga ocupada | stop pequeno | manual: evitar | corretora recusou | nota baixa
     agente = cacador | memecoins | treinador | guardiao | laboratorio | baleias | engenheiro | minerador
Arquivo: Shared/baleias/equipe/quadro.jsonl (só as últimas 500 linhas). Nunca escreva chave, senha ou token no resumo.
"""
import json
import os
import sys
import time
from pathlib import Path

ARQ = Path(os.environ.get("BALEIAS_QUADRO", "/home/servidor-de-producao/OpenBot/Shared/baleias/equipe/quadro.jsonl"))
REGRAS = ("esticada", "contra no 15 min", "liquidez baixa", "spread largo", "risco de golpe", "sem dado", "vaga ocupada", "stop pequeno",
          "manual: evitar", "corretora recusou", "nota baixa")
DESCARTES = ARQ.with_name("descartes.jsonl")
AGENTES = ("cacador", "memecoins", "treinador", "guardiao", "laboratorio", "baleias", "engenheiro", "minerador")


CONFIANCAS = ("alta", "média", "baixa")


def registrar(agente, texto, agora=None, conf=None):
    """conf (alta | média | baixa): quanto confiar nesta linha — o próximo agente não herda certeza que não existe (blackboard)."""
    if agente not in AGENTES:
        raise SystemExit(f"agente inválido: {agente!r}; use um de {', '.join(AGENTES)}")
    linha = {"t": agora or time.time(), "agente": agente, "texto": " ".join(str(texto).split())[:400]}
    if conf:
        c = str(conf).lower().replace("media", "média")
        if c not in CONFIANCAS:
            raise SystemExit(f"confiança inválida: {conf!r}; use alta, média ou baixa")
        linha["conf"] = c
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    linhas = ARQ.read_text().splitlines()[-499:] if ARQ.exists() else []
    linhas.append(json.dumps(linha, ensure_ascii=False))
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text("\n".join(linhas) + "\n")
    tmp.replace(ARQ)
    return linha


def descarte(agente, moeda, regra, agora=None):
    if agente not in AGENTES:
        raise SystemExit(f"agente inválido: {agente!r}")
    r = " ".join(str(regra).split()).lower()[:60]
    r = next((x for x in REGRAS if r.startswith(x) or x in r), r)
    linha = {"t": agora or time.time(), "agente": agente, "moeda": str(moeda).upper()[:20], "regra": r}
    DESCARTES.parent.mkdir(parents=True, exist_ok=True)
    linhas = DESCARTES.read_text().splitlines()[-1999:] if DESCARTES.exists() else []
    linhas.append(json.dumps(linha, ensure_ascii=False))
    tmp = DESCARTES.with_suffix(".tmp")
    tmp.write_text("\n".join(linhas) + "\n")
    tmp.replace(DESCARTES)
    return linha


def ler(n=100):
    try:
        out = []
        for l in ARQ.read_text().splitlines()[-n:]:
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
        return out
    except OSError:
        return []


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "descarte":
        print(json.dumps(descarte(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:])), ensure_ascii=False))
        sys.exit(0)
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    a = sys.argv[1:]
    conf = None
    if "--conf" in a:
        i = a.index("--conf")
        conf = a[i + 1] if i + 1 < len(a) else None
        a = a[:i] + a[i + 2:]
    print(json.dumps(registrar(a[0], " ".join(a[1:]), conf=conf), ensure_ascii=False))
