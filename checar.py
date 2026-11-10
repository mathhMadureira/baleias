"""Checagem ponta a ponta do projeto (ritual de início de cada sessão/rodada do laço). Uso: python3 checar.py

Confere serviços, fontes ao vivo do painel, nuvem (últimas rodadas e frescor do estado), cérebro, testes. Imprime ✅/❌ por item.
"""
import json
import subprocess
import sys
import time
import urllib.request

RESULTADOS = []


def item(nome, ok, detalhe=""):
    RESULTADOS.append(ok)
    print(f"{'✅' if ok else '❌'} {nome}" + (f" — {detalhe}" if detalhe else ""))


def sh(*cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def main():
    for s in ("baleias", "baleias-robo", "baleias-painel", "baleias-pesquisa"):
        r = sh("systemctl", "--user", "is-active", s)
        item(f"serviço {s}", r.stdout.strip() == "active", r.stdout.strip())
    try:
        d = json.load(urllib.request.urlopen("http://127.0.0.1:8787/api/ao-vivo?desde=999999999&calor=999999999", timeout=10))
        limites = {"liquidacoes": 900, "leitura": 420, "mapa": 2400, "cerebro": 300, "tartaruga": 120, "b3": 300}
        for k, v in d["fontes"].items():
            idade = d["agora"] - v["t"]
            item(f"fonte ao vivo {k}", v["ok"] and idade < limites.get(k, 120), f"{idade:.0f}s" + (f" erro {v['erro']}" if v.get("erro") else ""))
    except OSError as e:
        item("painel responde", False, type(e).__name__)
    for wf in ("robo-diario", "cerebro"):
        r = sh("gh", "run", "list", "-R", "mathhMadureira/baleias", "--workflow", wf, "--limit", "1", "--json", "conclusion,createdAt")
        try:
            u = json.loads(r.stdout)[0]
            item(f"nuvem: última rodada {wf}", u["conclusion"] == "success", f"{u['createdAt']} {u['conclusion']}")
        except (ValueError, IndexError):
            item(f"nuvem: última rodada {wf}", False, "sem resposta do GitHub")
    sh("git", "fetch", "-q", "origin", "estado")
    r = sh("git", "show", "origin/estado:dados/cerebro.json")
    try:
        c = json.loads(r.stdout)
        idade = time.time() - c["ultima_t"] / 1000
        item("cérebro na nuvem atualizado", idade < 3600, f"última vela há {idade / 60:.0f} min, {c['passos']} passos, capital US$ {c['capital']:,.2f}")
    except (ValueError, KeyError, TypeError):
        item("cérebro na nuvem atualizado", False, "estado ilegível")
    r = sh("python3", "-m", "unittest", "tests.test_baleias", timeout=300)
    ultima = (r.stderr.strip().splitlines() or ["?"])[-1]
    item("testes", r.returncode == 0, ultima)
    print(f"\n{sum(RESULTADOS)}/{len(RESULTADOS)} ok")
    return 0 if all(RESULTADOS) else 1


if __name__ == "__main__":
    sys.exit(main())
