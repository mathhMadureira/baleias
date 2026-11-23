"""H75: o maestro (R1 sem duplicar, R2 exposição ≤ 6 por lado, R3 perda do dia −US$ 1) melhora as carteiras dos agentes?

Uso: python3 lab/juizo_h75.py <pasta dados do ramo estado> [saida.json]
Regras e juiz fixados em lab/PROTOCOLO_LAB.md (Hipótese 75) antes de rodar.
"""
import json
import random
import sys
import time
from pathlib import Path

CARTEIRAS = ["robo_claude", "agente_guardiao", "agente_laboratorio", "agente_treinador"]
MAX_LADO, PERDA_DIA, SORTEIOS = 6, -1.00, 2000


def operacoes(pasta):
    ops = []
    for c in CARTEIRAS:
        for x in json.load(open(Path(pasta) / f"{c}.json")).get("fechadas", []):
            if all(isinstance(x.get(k), (int, float)) for k in ("entrada_t", "saida_t", "resultado_usd")) and x.get("lado") in ("compra", "venda"):
                ops.append({"carteira": c, "moeda": x["moeda"], "lado": x["lado"], "t0": float(x["entrada_t"]),
                            "t1": float(x["saida_t"]), "r": float(x["resultado_usd"])})
    return sorted(ops, key=lambda o: o["t0"])


def maestro(ops):
    """Devolve (mantidas, recusadas com o motivo)."""
    mant, rec = [], []
    for o in ops:
        abertas = [m for m in mant if m["t0"] <= o["t0"] < m["t1"]]
        dia = time.strftime("%Y-%m-%d", time.gmtime(o["t0"]))
        feito_dia = sum(m["r"] for m in mant if m["t1"] <= o["t0"] and time.strftime("%Y-%m-%d", time.gmtime(m["t1"])) == dia)
        if any(m["moeda"] == o["moeda"] and m["lado"] == o["lado"] and m["carteira"] != o["carteira"] for m in abertas):
            rec.append({**o, "regra": "R1"})
        elif sum(m["lado"] == o["lado"] for m in abertas) >= MAX_LADO:
            rec.append({**o, "regra": "R2"})
        elif feito_dia <= PERDA_DIA:
            rec.append({**o, "regra": "R3"})
        else:
            mant.append(o)
    return mant, rec


def media(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    pasta = sys.argv[1]
    ops = operacoes(pasta)
    mant, rec = maestro(ops)
    base = [o["r"] for o in ops]
    m_mant, m_rec = media([o["r"] for o in mant]), media([o["r"] for o in rec])
    rnd = random.Random(75)
    k = len(rec)
    acima = 0
    for _ in range(SORTEIOS):
        fora = set(rnd.sample(range(len(ops)), k))
        if m_mant > media([o["r"] for i, o in enumerate(ops) if i not in fora]):
            acima += 1
    pct = acima / SORTEIOS
    t_ini, t_fim = ops[0]["t0"], ops[-1]["t0"] + 1
    blocos = []
    for b in range(3):
        a, z = t_ini + (t_fim - t_ini) * b / 3, t_ini + (t_fim - t_ini) * (b + 1) / 3
        blocos.append({"base": media([o["r"] for o in ops if a <= o["t0"] < z]), "mantidas": media([o["r"] for o in mant if a <= o["t0"] < z]),
                       "n": sum(a <= o["t0"] < z for o in ops)})
    juiz = {"a_placebo": pct > 0.975, "b_recusadas_negativas": bool(rec) and m_rec < 0,
            "c_blocos": sum(bl["mantidas"] >= bl["base"] for bl in blocos) >= 2}
    out = {"n": len(ops), "mantidas": len(mant), "recusadas": k,
           "por_regra": {r: sum(o["regra"] == r for o in rec) for r in ("R1", "R2", "R3")},
           "soma_base": sum(base), "soma_mantidas": sum(o["r"] for o in mant), "soma_recusadas": sum(o["r"] for o in rec),
           "media_base": media(base), "media_mantidas": m_mant, "media_recusadas": m_rec,
           "percentil_placebo": pct, "blocos": blocos, "juiz": juiz, "passou": all(juiz.values()),
           "de": time.strftime("%Y-%m-%d %H:%M", time.gmtime(t_ini)), "ate": time.strftime("%Y-%m-%d %H:%M", time.gmtime(ops[-1]["t0"]))}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
