"""H60 — alavancagem na carteira (regra e critério pré-registrados em lab/PROTOCOLO_LAB.md antes de rodar).

Contrafactual nas operações fechadas reais: o resultado de cada operação em % do nocional (já com o custo) é preservado; muda só o tamanho da
posição, calculado na entrada com a carteira realizada daquele momento. Dois conjuntos: etiqueta estado-antes-do-zero-2026-11-16 e o ramo
estado de agora (desde o zero de 16/11). Só biblioteca padrão.

Uso: python3 -m lab.alavancagem
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROBOS = {"rapido": "robo_v4_perp.json", "cacador": "robo_v4_cacador.json", "scalper": "robo_scalper_nuvem.json", "scalper_b": "robo_scalper_b.json",
         "scalper_c": "robo_scalper_c.json", "scalper_d": "robo_scalper_d.json", "minerador": "robo_minerador.json", "claude": "robo_claude.json",
         "lbank": "robo_lbank.json", "radar": "robo_radar.json"}
CONJUNTOS = {"antes do zero (etiqueta)": "estado-antes-do-zero-2026-11-16", "desde o zero (agora)": "origin/estado"}
CAPITAL, PISO = 10.0, 5.0
BRACOS = {"atual 2,5× a 10×": (2.5, 10, False), "A 3,75× a 20×": (3.75, 20, False), "B 5× a 20×": (5.0, 20, False),
          "C 5× só no lucro com prova, a 20×": (5.0, 20, True)}


def ler(ref, arq):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:dados/{arq}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None


def nocional(x):
    if x.get("nocional"):
        return float(x["nocional"])
    g = float(x.get("gasto") or 0)
    return g * 10 if g >= 2 else (5.0 if g else 25.0)       # US$ 25 a 10× (margem 2,50); Minerador antigo da H28: US$ 5


def simular(ops, fator, alav, so_lucro):
    """ops: [(entrada_t, saida_t, pct)]. Devolve (carteira final, mínima, operações feitas)."""
    eventos = sorted([(e, 0, i) for i, (e, s, p) in enumerate(ops)] + [(s, 1, i) for i, (e, s, p) in enumerate(ops)], key=lambda x: (x[0], -x[1]))
    realizado, minimo, aberto, feitas, fechadas = CAPITAL, CAPITAL, {}, 0, []
    for t, tipo, i in eventos:
        if tipo == 0:
            if realizado < PISO:
                continue
            f = fator
            if so_lucro:
                g = sum(r for r in fechadas if r > 0)
                p = -sum(r for r in fechadas if r < 0)
                prova = len(fechadas) >= 30 and realizado > CAPITAL and p > 0 and g / p > 1
                f, a = (fator, alav) if prova else (2.5, 10)
            aberto[i] = (f * realizado, alav if not so_lucro else a)
        elif i in aberto:
            noc, a = aberto.pop(i)
            pct = ops[i][2]
            if a > 10:
                pct = max(pct, -1.0 / a)                       # liquidação: perde no máximo a margem da posição
            r = noc * pct
            realizado += r
            fechadas.append(r)
            feitas += 1
            minimo = min(minimo, realizado)
    return realizado, minimo, feitas


def main():
    saida = {}
    for nome_c, ref in CONJUNTOS.items():
        print(f"\n### {nome_c} ({ref})")
        tab = {b: {} for b in BRACOS}
        for rid, arq in ROBOS.items():
            e = ler(ref, arq)
            if not e or not e.get("fechadas"):
                continue
            ops = [(float(x.get("entrada_t") or x["saida_t"]), float(x["saida_t"]), float(x["resultado_usd"]) / nocional(x))
                   for x in e["fechadas"] if x.get("saida_t") and x.get("resultado_usd") is not None]
            for b, (f, a, so) in BRACOS.items():
                tab[b][rid] = simular(ops, f, a, so)
        robos = sorted(tab["atual 2,5× a 10×"])
        print("| braço | soma das carteiras | robôs < US$ 5 | " + " | ".join(robos) + " |")
        print("|---|---|---|" + "---|" * len(robos))
        for b in BRACOS:
            soma = sum(tab[b][r][0] for r in robos)
            abaixo = [r for r in robos if tab[b][r][0] < PISO]
            print(f"| {b} | {soma:.2f} | {', '.join(abaixo) or '—'} | " + " | ".join(f"{tab[b][r][0]:.2f}" for r in robos) + " |")
        saida[nome_c] = {b: {r: {"final": round(v[0], 4), "minimo": round(v[1], 4), "ops": v[2]} for r, v in tab[b].items()} for b in BRACOS}
    veredito = {}
    for b in list(BRACOS)[1:]:
        ok = True
        for c in CONJUNTOS:
            base, br = saida[c]["atual 2,5× a 10×"], saida[c][b]
            soma_ok = sum(v["final"] for v in br.values()) > sum(v["final"] for v in base.values())
            piso_ok = all(not (br[r]["final"] < PISO and base[r]["final"] >= PISO) for r in br)
            ok = ok and soma_ok and piso_ok
        veredito[b] = "PASSOU" if ok else "não passou"
    print("\nVeredito (critério pré-registrado):", json.dumps(veredito, ensure_ascii=False))
    arq = REPO / "dados" / "lab" / "alavancagem_resultado.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps({"conjuntos": saida, "veredito": veredito}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
