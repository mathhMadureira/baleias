"""Juízo da H59 (Chefe OpenBot no testnet) e da H62 (agentes livres, 30 operações por agente).

Critérios pré-registrados em lab/PROTOCOLO_LAB.md, sem ajuste:
- H59: as 30 primeiras operações fechadas (ordem de saída) de dados/robo_openbot_testnet.json; passa se a soma
  líquida (realizedPnl − commission, campo resultado_usd) > 0 e o fator de lucro > 1. ZEC e RENDER (abertas antes
  da emenda) relatadas à parte. Comparação (não decide): Robô Claude com decisao_t no mesmo período.
- H62: por agente, as 30 primeiras operações abertas a partir de 18/11/2026 20:37 UTC (ordem de entrada); passa se o
  fator de lucro > 1 e a carteira > US$ 10 (carteira = 10 + todas as fechadas até a saída da 30ª).
Uso: python3 -m lab.juizo_h59_h62 [ref]  (ref padrão origin/estado)
"""
import datetime as dt
import json
import math
import subprocess
import sys

H62_T = dt.datetime(2026, 11, 18, 20, 37, tzinfo=dt.timezone.utc).timestamp()
EMENDA_T = dt.datetime(2026, 11, 18, 1, 40, tzinfo=dt.timezone.utc).timestamp()
AGENTES = {"Baleias": "robo_claude.json", "Treinador": "agente_treinador.json",
           "Laboratório": "agente_laboratorio.json", "Guardião": "agente_guardiao.json"}


def ler(ref, nome):
    return json.loads(subprocess.check_output(["git", "show", f"{ref}:dados/{nome}"]))


def resumo(ops):
    r = [o["resultado_usd"] for o in ops]
    g, p = sum(x for x in r if x > 0), -sum(x for x in r if x < 0)
    n = len(r)
    m = sum(r) / n if n else 0
    dp = math.sqrt(sum((x - m) ** 2 for x in r) / (n - 1)) if n > 1 else 0
    return {"n": n, "soma": round(sum(r), 4), "fator": round(g / p, 3) if p else None,
            "acerto": round(sum(1 for x in r if x > 0) / n, 3) if n else None,
            "t_media": round(m / (dp / math.sqrt(n)), 2) if dp else None}


def hora(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%d/%m %H:%M UTC")


def h59(ref):
    e = ler(ref, "robo_openbot_testnet.json")
    fe = sorted(e["fechadas"], key=lambda o: o["saida_t"])
    ops = fe[:30]
    s = resumo(ops)
    s["passa"] = bool(s["n"] == 30 and s["soma"] > 0 and (s["fator"] or 0) > 1)
    s["janela"] = [hora(ops[0]["entrada_t"]), hora(ops[-1]["saida_t"])]
    s["antes_emenda"] = [{"moeda": o["moeda"], "res": round(o["resultado_usd"], 4)} for o in ops
                         if o["moeda"] in ("ZECUSDT", "RENDERUSDT") and o["entrada_t"] < EMENDA_T]
    t0, t1 = min(o["decisao_t"] for o in ops), max(o["decisao_t"] for o in ops)
    claude = [o for o in ler(ref, "robo_claude.json")["fechadas"] if t0 <= o.get("decisao_t", 0) <= t1]
    s["comparacao_robo_claude"] = resumo(claude)
    s["total_fechadas_hoje"] = resumo(fe)
    return s


def h62(ref):
    out = {}
    for ag, arq in AGENTES.items():
        fe = sorted(ler(ref, arq)["fechadas"], key=lambda o: o["saida_t"])
        novas = sorted([o for o in fe if o["entrada_t"] >= H62_T], key=lambda o: o["entrada_t"])
        if len(novas) < 30:
            out[ag] = {"n": len(novas), "julgavel": False}
            continue
        ops = novas[:30]
        fim = max(o["saida_t"] for o in ops)
        carteira = 10 + sum(o["resultado_usd"] for o in fe if o["saida_t"] <= fim)
        s = resumo(ops)
        s.update(julgavel=True, carteira=round(carteira, 3), fim=hora(fim),
                 passa=bool((s["fator"] or 0) > 1 and carteira > 10))
        out[ag] = s
    return out


if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "origin/estado"
    rev = subprocess.check_output(["git", "rev-parse", "--short=8", ref]).decode().strip()
    print(json.dumps({"estado": rev, "H59": h59(ref), "H62": h62(ref)}, ensure_ascii=False, indent=1))
