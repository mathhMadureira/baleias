"""Atraso de entrada dos robôs do v4 na nuvem (P1 do Treinador, julgada em 18/11/2026).

Para cada operação fechada: hora da rodada que abriu (evento "ENTROU ... em MOEDA a PREÇO", juntando os `eventos` de todas as
revisões do ramo `estado`) − `entrada_t` (fechamento da vela do sinal). Também conta as operações cuja saída aconteceu ANTES da
rodada que as abriu (a simulação conferiu stop/stop móvel em velas de 1 min que já tinham passado).

Uso: python3 -m lab.atraso_entrada [REF do ramo estado, padrão origin/estado] [desde (época s, rodada que abriu), padrão 0 = todas as fechadas do estado]
Só biblioteca padrão; lê o git, não grava nada no repositório (resultado em dados/lab/atraso_entrada.json, fora do git).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ROBOS = ["robo_v4_cacador", "robo_v4_perp", "robo_scalper_nuvem", "robo_scalper_b", "robo_scalper_c", "robo_scalper_d"]
LIMITE_H = 0.5                       # mais de 30 min entre a vela do sinal e a rodada = não executável no preço da vela
ENTROU = re.compile(r"ENTROU \w+ em (\S+) a ([0-9.e+-]+)")


def git(*a):
    return subprocess.run(["git", "-C", str(RAIZ), *a], capture_output=True, text=True).stdout


def eventos_de_entrada(ref, arq, desde_git):
    ev = {}
    for h in git("log", "--format=%H", f"--since={desde_git}", ref, "--", arq).splitlines():
        try:
            e = json.loads(git("show", f"{h}:{arq}"))
        except ValueError:
            continue
        for x in e.get("eventos", []):
            m = ENTROU.search(x.get("texto", ""))
            if m:
                ev[(round(x["t"], 3), m.group(1))] = float(m.group(2))
    return ev


def medir(ref="origin/estado", desde=0):
    desde_git = "2026-11-16 18:00"
    saida = {}
    for robo in ROBOS:
        arq = f"dados/{robo}.json"
        ev = eventos_de_entrada(ref, arq, desde_git)
        e = json.loads(git("show", f"{ref}:{arq}") or "{}")
        ops = []
        for o in e.get("fechadas", []):
            base = o["moeda"][:-4]
            ts = sorted(t for (t, mo), px in ev.items()
                        if mo == base and abs(px / o["entrada"] - 1) < 1e-3 and t >= o["entrada_t"] - 60)
            t_ab = ts[0] if ts else None
            if t_ab is not None and t_ab < desde:         # filtra pela rodada que abriu (a saída de uma velha pode cair antes do zero)
                continue
            ops.append({"moeda": o["moeda"], "entrada_t": o["entrada_t"], "saida_t": o["saida_t"], "t_abriu": t_ab,
                        "atraso_h": None if t_ab is None else (t_ab - o["entrada_t"]) / 3600,
                        "saiu_antes_de_abrir": t_ab is not None and o["saida_t"] < t_ab,
                        "res": o["resultado_usd"], "motivo": o.get("motivo", "")})
        saida[robo] = ops
    return saida


def resumo(g):
    s = sum(o["res"] for o in g)
    gp = sum(o["res"] for o in g if o["res"] > 0)
    gn = -sum(o["res"] for o in g if o["res"] < 0)
    return {"n": len(g), "soma": round(s, 3), "fator": round(gp / gn, 2) if gn else None}


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "origin/estado"
    desde = float(sys.argv[2]) if len(sys.argv) > 2 else 0   # padrão: todas as fechadas do estado (a lista recomeçou no zero de 16/11)
    d = medir(ref, desde)
    tab = {}
    for robo, ops in d.items():
        sem = [o for o in ops if o["atraso_h"] is None]
        limp = [o for o in ops if o["atraso_h"] is not None and o["atraso_h"] <= LIMITE_H]
        velh = [o for o in ops if o["atraso_h"] is not None and o["atraso_h"] > LIMITE_H]
        tab[robo] = {"todas": resumo(ops), "velhas": resumo(velh), "limpas": resumo(limp),
                     "limpas_saiu_antes_de_abrir": resumo([o for o in limp if o["saiu_antes_de_abrir"]]),
                     "limpas_saiu_depois": resumo([o for o in limp if not o["saiu_antes_de_abrir"]]),
                     "sem_evento": len(sem),
                     "atraso_limpas_min": sorted(round(o["atraso_h"] * 60, 1) for o in limp)}
        t = tab[robo]
        print(f"{robo:20s} todas {t['todas']} | velhas {t['velhas']} | limpas {t['limpas']} | "
              f"limpas que saíram antes de abrir {t['limpas_saiu_antes_de_abrir']} | sem evento {len(sem)}")
    out = RAIZ / "dados" / "lab" / "atraso_entrada.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ref": git("rev-parse", "--short", ref).strip(), "desde": desde, "tabela": tab, "ops": d}, ensure_ascii=False))


if __name__ == "__main__":
    main()
