"""Quadro da rodada da equipe (24/11): cada agente registra 1 linha ao terminar a sua parte; o painel mostra a rodada ao vivo.

Uso: python3 -I quadro.py <agente> "<resumo de 1 linha com números>"
     agente = cacador | memecoins | treinador | guardiao | laboratorio | baleias | engenheiro | minerador
Arquivo: Shared/baleias/equipe/quadro.jsonl (só as últimas 500 linhas). Nunca escreva chave, senha ou token no resumo.
"""
import json
import os
import sys
import time
from pathlib import Path

ARQ = Path(os.environ.get("BALEIAS_QUADRO", "/home/servidor-de-producao/OpenBot/Shared/baleias/equipe/quadro.jsonl"))
AGENTES = ("cacador", "memecoins", "treinador", "guardiao", "laboratorio", "baleias", "engenheiro", "minerador")


def registrar(agente, texto, agora=None):
    if agente not in AGENTES:
        raise SystemExit(f"agente inválido: {agente!r}; use um de {', '.join(AGENTES)}")
    linha = {"t": agora or time.time(), "agente": agente, "texto": " ".join(str(texto).split())[:400]}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    linhas = ARQ.read_text().splitlines()[-499:] if ARQ.exists() else []
    linhas.append(json.dumps(linha, ensure_ascii=False))
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text("\n".join(linhas) + "\n")
    tmp.replace(ARQ)
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
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(json.dumps(registrar(sys.argv[1], " ".join(sys.argv[2:])), ensure_ascii=False))
