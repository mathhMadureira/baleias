"""Vigia de saúde SEM IA (27/11, "por evento"): a cada 2 min confere motor, pump.fun e painel; só acorda o Engenheiro se algo parou.
Roda pelo timer de usuário baleias-vigia.timer. Nada de segredo aqui."""
import importlib.util
import json
import subprocess
import time
from pathlib import Path

S = Path("/home/servidor-de-producao/OpenBot/Shared/baleias")


def _idade(p, campo):
    try:
        return time.time() - float(json.loads(Path(p).read_text()).get(campo) or 0)
    except (OSError, ValueError):
        return 1e9


def main():
    spec = importlib.util.spec_from_file_location("acordar_m", S / "acordar.py")
    k = importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
    problemas = []
    for svc in ("baleias-motor", "baleias-pump", "baleias-painel"):
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", svc]).returncode != 0:
            problemas.append(f"serviço {svc} parado")
    if (i := _idade(S / "equipe" / "briefing.json", "t")) > 300:
        problemas.append(f"briefing da BingX há {i:.0f} s")
    if (i := _idade(S / "pump" / "estado.json", "atualizado")) > 120:
        problemas.append(f"estado da pump.fun há {i:.0f} s")
    if problemas:
        print("; ".join(problemas))
        k.acordar("engenheiro", "vigia de saúde: " + "; ".join(problemas), chave="saude " + ",".join(sorted(p.split(" há")[0] for p in problemas)) + f" {int(time.time() // 1800)}")


if __name__ == "__main__":
    main()
