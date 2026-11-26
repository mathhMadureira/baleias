"""Canal da equipe (25/11, dono: "uma rede onde todos os agentes conversem enquanto trabalham, sem conflitos").

Conversa sem conflito = cada DECISÃO tem um único dono; os outros conversam, propõem e pedem ao dono.
Tipos de mensagem:
  info      — aviso, sem pedir nada
  proposta  — "sugiro X porque <números>" ao dono do tema; o dono responde aceito/recusado
  pedido    — "preciso de X" a um agente; ele responde
  resposta  — fecha uma proposta/pedido (--ref <id>): aceito | recusado | feito, com o motivo
Ninguém muda o que é de outro: o motor recusa o comando de quem não é dono do tema (motor.DONOS).

Uso: python3 -I canal.py falar <de> <para|todos> <info|proposta|pedido|resposta> "<texto>" [--ref <id>]
     python3 -I canal.py ler <agente>            → mensagens novas para você (ou para todos) desde a sua última leitura
     python3 -I canal.py pendentes <agente>      → propostas e pedidos dirigidos a você ainda sem resposta (responda TODOS)
Arquivo: Shared/baleias/equipe/canal.jsonl (últimas 1000). Nunca escreva chave, senha ou token.
"""
import fcntl
import json
import os
import sys
import time
import uuid
from pathlib import Path

ARQ = Path(os.environ.get("BALEIAS_CANAL", "/home/servidor-de-producao/OpenBot/Shared/baleias/equipe/canal.jsonl"))
AGENTES = ("cacador", "memecoins", "treinador", "guardiao", "laboratorio", "baleias", "engenheiro", "minerador")
TIPOS = ("info", "proposta", "pedido", "resposta")
TEMAS_DONO = {"lados e força mínima do motor": "laboratorio", "preferidas e bloqueios": "cacador", "sair de uma posição": "guardiao",
              "placar e lições": "treinador", "motor, painel e corretora": "engenheiro", "memecoins": "memecoins",
              "tamanho, alavancagem, alvo mínimo, foco": "baleias (só com o dono)"}


def _ler():
    try:
        return [json.loads(l) for l in ARQ.read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def falar(de, para, tipo, texto, ref=None, agora=None):
    if de not in AGENTES:
        raise SystemExit(f"remetente inválido: {de!r}")
    if para != "todos" and para not in AGENTES:
        raise SystemExit(f"destino inválido: {para!r}; use um agente ou 'todos'")
    if tipo not in TIPOS:
        raise SystemExit(f"tipo inválido: {tipo!r}; use {', '.join(TIPOS)}")
    if tipo == "resposta" and not ref:
        raise SystemExit("resposta precisa de --ref <id da proposta ou pedido>")
    if tipo in ("proposta", "pedido") and para == "todos":
        raise SystemExit("proposta e pedido vão ao DONO do tema, não a todos (veja TEMAS_DONO)")
    m = {"id": uuid.uuid4().hex[:8], "t": agora or time.time(), "de": de, "para": para, "tipo": tipo,
         "texto": " ".join(str(texto).split())[:500], "ref": ref}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQ.with_suffix(".lock"), "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        linhas = ARQ.read_text().splitlines()[-999:] if ARQ.exists() else []
        linhas.append(json.dumps(m, ensure_ascii=False))
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text("\n".join(linhas) + "\n")
        tmp.replace(ARQ)
    return m


def ler(agente):
    cursor = ARQ.with_name(f"canal_lido_{agente}.txt")
    try:
        desde = float(cursor.read_text())
    except (OSError, ValueError):
        desde = time.time() - 3600
    novas = [m for m in _ler() if m["t"] > desde and m["de"] != agente and m["para"] in (agente, "todos")]
    cursor.write_text(str(time.time()))
    return novas


def pendentes(agente):
    msgs = _ler()
    respondidas = {m.get("ref") for m in msgs if m["tipo"] == "resposta"}
    return [m for m in msgs if m["para"] == agente and m["tipo"] in ("proposta", "pedido") and m["id"] not in respondidas]


def _fmt(m):
    return f"[{m['id']}] {time.strftime('%H:%M', time.gmtime(m['t']))} UTC {m['de']} → {m['para']} ({m['tipo']}{' a ' + m['ref'] if m.get('ref') else ''}): {m['texto']}"


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["falar"] and len(a) >= 5:
        ref = None
        if "--ref" in a:
            i = a.index("--ref")
            ref = a[i + 1] if i + 1 < len(a) else None
            a = a[:i] + a[i + 2:]
        print(_fmt(falar(a[1], a[2], a[3], " ".join(a[4:]), ref)))
    elif a[:1] in (["ler"], ["pendentes"]) and len(a) == 2:
        ms = ler(a[1]) if a[0] == "ler" else pendentes(a[1])
        print("\n".join(_fmt(m) for m in ms) or "nada novo")
    else:
        print(__doc__)
        print("Donos dos temas:", json.dumps(TEMAS_DONO, ensure_ascii=False))
