"""Acordar um agente por EVENTO (27/11, dono: rever se as rotinas de relógio são necessárias → "por evento").

Só quem decide fica no relógio (Operador e Memes). Os outros são acordados pelo código quando algo acontece:
  Juiz       — uma operação fechou (BingX ou pump.fun)
  Risco      — uma posição está perdendo ou o stop sumiu
  Radar      — apareceu uma oportunidade rara no radar
  Engenheiro — o motor deu erro, parou ou o briefing envelheceu

acordar(agente, motivo, chave, intervalo_s): roda a rotina do agente pela API local do OpenBot com o motivo no payload.
Não repete a mesma chave e respeita um intervalo mínimo por agente. Lê a URL e o cabeçalho de autorização de arquivos locais
em tempo de execução (nada de segredo no repositório; nunca imprima o cabeçalho). Registro: equipe/acordar.jsonl.
Uso manual: python3 -I acordar.py <agente> "<motivo>"
"""
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

EQUIPE = Path(os.environ.get("BALEIAS_EQUIPE", "/home/servidor-de-producao/OpenBot/Shared/baleias/equipe"))
AUTO = Path("/home/servidor-de-producao/.config/OpenBot/automation")
ROTINAS = {   # agente → (id do agente no OpenBot, id da rotina pausada que o evento roda)
    "treinador": ("agent-fde8e0b0-c814-4442-86b4-c153a4e2d2ea", "19123ac3-a195-4dab-afce-e1b86cb3eab5"),
    "guardiao": ("agent-a4cdc32a-f297-4607-b8e0-6b74f1a1572c", "411d7997-39f4-4099-9e4e-e1759778c7b5"),
    "cacador": ("agent-22ccc4a1-4c77-41c3-b01b-c5b37542dc2b", "a70b66bb-4013-4d42-a53c-cf6b9048d5bc"),
    "engenheiro": ("agent-506330b0-6f64-431b-9fbe-9b2232c739d8", "9d48087d-13cd-4bb5-a0f9-30668b7f1f6b"),
}
INTERVALO = {"treinador": 120, "guardiao": 300, "cacador": 900, "engenheiro": 1800}   # mínimo entre dois despertares do mesmo agente


def _estado_rw(f):
    arq = EQUIPE / "acordar_estado.json"
    EQUIPE.mkdir(parents=True, exist_ok=True)
    with open(EQUIPE / "acordar.lock", "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        try:
            est = json.loads(arq.read_text())
        except (OSError, ValueError):
            est = {}
        out = f(est)
        arq.write_text(json.dumps(est, ensure_ascii=False))
    return out


def acordar(agente, motivo, chave=None, intervalo_s=None, agora=None, enviar=None):
    """True se acordou. enviar (para testes) substitui a chamada HTTP."""
    if agente not in ROTINAS:
        return False
    agora = agora or time.time()
    intervalo_s = INTERVALO[agente] if intervalo_s is None else intervalo_s
    chave = chave or motivo[:60]

    def decidir(est):
        a = est.setdefault(agente, {"ultimo": 0, "chaves": {}})
        a["chaves"] = {k: t for k, t in a["chaves"].items() if agora - t < 86400}
        if chave in a["chaves"] or agora - a["ultimo"] < intervalo_s:
            return False
        a["ultimo"], a["chaves"][chave] = agora, agora
        return True

    if not _estado_rw(decidir):
        return False
    ok, info = (enviar or _enviar)(agente, motivo)
    with open(EQUIPE / "acordar.jsonl", "a") as f:
        f.write(json.dumps({"t": agora, "agente": agente, "motivo": motivo[:300], "ok": ok, "info": str(info)[:200]}, ensure_ascii=False) + "\n")
    return ok


def _enviar(agente, motivo):
    agente_id, rotina = ROTINAS[agente]
    try:
        url = (AUTO / "url").read_text().strip()
    except OSError as ex:
        return False, f"sem url de automação: {ex}"
    corpo = json.dumps({"payload": f"EVENTO: {motivo[:500]}"}, ensure_ascii=False)
    try:
        r = subprocess.run(["curl", "-sS", "-m", "20", "-o", "/dev/stdout", "-w", "\n%{http_code}", "-X", "POST",
                            f"{url}/v1/agents/{agente_id}/routines/{rotina}/run", "-H", f"@{AUTO / 'headers'}",
                            "-H", "Content-Type: application/json", "--data-binary", corpo], capture_output=True, text=True, timeout=30)
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"
    codigo = (r.stdout.strip().splitlines() or ["0"])[-1]
    return codigo.startswith("2"), f"HTTP {codigo} {r.stdout[:120]}"


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        print(acordar(sys.argv[1], " ".join(sys.argv[2:]), chave=f"manual {time.time()}", intervalo_s=0))
    else:
        print(__doc__)
