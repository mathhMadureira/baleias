"""Espelho local do robô que roda no GitHub Actions: puxa o estado do ramo `estado` e atualiza radar e patrimônio com preços ao vivo.

Não decide nem executa nada — a fonte de verdade é a nuvem. Assim não existem dois robôs com carteiras diferentes.
"""
import json
import subprocess
import time
from pathlib import Path

from lab import tartaruga as T

from . import tartaruga_exec as X

REPO = Path(__file__).resolve().parent.parent


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=60)


def puxar():
    """Copia o estado e os eventos da nuvem para dados/. Devolve o estado ou None."""
    if _git("fetch", "-q", "origin", "estado").returncode != 0:
        return None
    for nome, destino in (("dados/robo_tartaruga.json", X.ESTADO), ("dados/robo_eventos.jsonl", X.EVENTOS)):
        r = _git("show", f"origin/estado:{nome}")
        if r.returncode == 0 and r.stdout:
            tmp = destino.with_suffix(".nuvem")
            tmp.write_text(r.stdout)
            tmp.replace(destino)
    try:
        return json.loads(X.ESTADO.read_text())
    except (OSError, ValueError):
        return None


def rodar(cliente):
    dados, dia = None, None
    while True:
        try:
            e = puxar()
            if e is None:
                msg = "espelho: sem estado da nuvem ainda"
            else:
                hoje = time.strftime("%Y-%m-%d", time.gmtime())
                if dados is None or dia != hoje:
                    T.CACHE_VIVO.unlink(missing_ok=True)
                    dados, dia = T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO), hoje
                precos = cliente.precos(T.MOEDAS_ROBO)
                e["radar"] = X.radar(dados, precos)
                e["patrimonio"] = X.patrimonio(e, precos, X.Simulada(cliente, e))
                e["atualizado"] = time.time()
                e["fonte"] = "nuvem (GitHub Actions)"
                X.salvar(e)
                msg = f"espelho da nuvem: patrimônio US$ {e['patrimonio']:,.2f}, {len(e['abertas'])} abertas, última rodada {e.get('ultimo_dia')}"
        except Exception as ex:
            msg = f"espelho erro: {type(ex).__name__}: {str(ex)[:150]}"
        print(time.strftime("%F %T"), msg, flush=True)
        yield msg
        time.sleep(300)
