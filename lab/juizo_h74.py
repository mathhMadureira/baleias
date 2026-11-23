"""Juízo da H74 (P2 do Treinador): alertas explosao_* de COMPRA do Caçador, fora da amostra, pelo critério pré-registrado (c0fb0353).

Alertas remontados do histórico de estado:dados/oportunidades.json (cada commit); mesmo (moeda, sinal, lado) dentro de 30 min conta uma vez.
Entrada: fechamento da vela de 1 min que fecha depois da hora do alerta. Saída: stop/alvo/prazo do alerta pelo executor/stop_movel.conferir
(regra em vigor). Custo 0,12%. Controle: mesmas moedas e instantes, lado sorteado (−0,12% ± 3 EP, senão inválida). Vendas relatadas.
Juiz (a): média > 0, z ≥ 2 (EP agrupado pela hora do alerta) e > 0 em 3 blocos de tempo iguais.

Uso: git fetch -q origin estado && .venv-ml/bin/python -m lab.juizo_h74
"""
import json
import random
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from executor import stop_movel as SM
from lab.juizo_h70 import baixar, media_ep

CUSTO, Z, REPETE = 0.0012, 2.0, 30 * 60


def alertas():
    shas = subprocess.check_output(["git", "log", "--format=%H", "origin/estado", "--", "dados/oportunidades.json"], text=True).split()
    entrada = "".join(f"{s}:dados/oportunidades.json\n" for s in shas).encode()
    data = subprocess.run(["git", "cat-file", "--batch"], input=entrada, capture_output=True, check=True).stdout
    vistos, i = {}, 0
    while i < len(data):
        nl = data.index(b"\n", i)
        tam = int(data[i:nl].split()[2])
        corpo, i = data[nl + 1:nl + 1 + tam], nl + 2 + tam
        try:
            d = json.loads(corpo)
        except ValueError:
            continue
        for o in d.get("oportunidades") or []:
            if str(o.get("tipo", "")).startswith("explosao_") and o.get("sugestao"):
                vistos[(o["par"], o["tipo"], o["lado"], int(o["t"]))] = o
    ult, out = {}, []
    for o in sorted(vistos.values(), key=lambda o: o["t"]):
        k = (o["par"], o["tipo"], o["lado"])
        if k in ult and o["t"] - ult[k] < REPETE:
            continue
        ult[k] = o["t"]
        out.append(o)
    return out, len(shas)


def resultado(entrada, lado, caminho, stop, alvo, fim):
    r = SM.conferir({"entrada": entrada, "lado": lado}, caminho, stop, fim, caminho[0][0], alvo_pct=alvo)
    saida = r[0] if r else caminho[-1][3]
    return (-1 if lado == "venda" else 1) * (saida / entrada - 1) - CUSTO


def julgar(nome, L, decide):
    L = sorted(L, key=lambda x: x["t"])
    v = [x["r"] for x in L]
    m, ep = media_ep(v, [x["t"] // 3600 for x in L])
    t0, t1 = L[0]["t"], L[-1]["t"] + 1
    blocos = []
    for b in range(3):
        a, z = t0 + b * (t1 - t0) / 3, t0 + (b + 1) * (t1 - t0) / 3
        s = [x["r"] for x in L if a <= x["t"] < z]
        blocos.append((sum(s) / len(s) if s else float("nan"), len(s)))
    g, p = sum(x for x in v if x > 0), -sum(x for x in v if x < 0)
    passa = m > 0 and m / ep >= Z and all(b[0] > 0 for b in blocos)
    print(f"{nome}: n {len(v)}, média {m:+.3%}, EP {ep:.3%}, z {m / ep:+.2f}, acerto {sum(x > 0 for x in v) / len(v):.1%}, fator {g / p:.2f}; blocos "
          + " / ".join(f"{b:+.3%} (n {n})" for b, n in blocos) + (f" → {'APROVADA' if passa else 'REPROVADA'}" if decide else ""))
    return m, ep, passa


def main():
    random.seed(74)
    rev = subprocess.check_output(["git", "rev-parse", "--short", "origin/estado"], text=True).strip()
    al, ncommits = alertas()
    agora = int(time.time() // 60 * 60_000)
    print(f"ramo estado {rev}; {ncommits} commits de oportunidades.json; {len(al)} alertas explosao_* depois da regra de 30 min "
          f"({sum(o['lado'] == 'compra' for o in al)} compra, {sum(o['lado'] == 'venda' for o in al)} venda)")
    faixa = defaultdict(lambda: [10**15, 0])
    for o in al:
        t = int(o["t"] * 1000)
        f = faixa[o["par"]]
        f[0], f[1] = min(f[0], t // 60_000 * 60_000), max(f[1], t + (o["sugestao"]["max_min"] + 3) * 60_000)
    pares = sorted(faixa)
    with ThreadPoolExecutor(8) as ex:
        velas = dict(zip(pares, ex.map(lambda p: baixar(p, faixa[p][0], min(agora, faixa[p][1])), pares)))
    fontes = defaultdict(int)
    for f, _ in velas.values():
        fontes[f] += 1
    print("fonte das velas:", dict(fontes))
    idx = {p: {x[0]: i for i, x in enumerate(m)} for p, (_, m) in velas.items()}
    linhas, faltou = defaultdict(list), 0
    for o in al:
        sg = o["sugestao"]
        ab = int(o["t"] * 1000) // 60_000 * 60_000              # vela que fecha logo depois do alerta
        fim = ab + 60_000 + sg["max_min"] * 60_000
        m = velas[o["par"]][1]
        i = idx[o["par"]].get(ab)
        if i is None or fim > agora:
            faltou += 1
            continue
        caminho = [x for x in m[i + 1:i + 1 + sg["max_min"] + 5] if x[0] < fim]
        if len(caminho) < sg["max_min"] * 0.9:
            faltou += 1
            continue
        e = m[i][3]
        linhas[o["lado"]].append({"t": o["t"], "r": resultado(e, o["lado"], caminho, sg["stop_pct"], sg["alvo_pct"], fim)})
        linhas["controle"].append({"t": o["t"], "r": resultado(e, random.choice(("compra", "venda")), caminho, sg["stop_pct"], sg["alvo_pct"], fim)})
    print(f"{faltou} alertas fora (prazo aberto ou sem velas)\n")
    mc, epc, _ = julgar("controle (lado sorteado)", linhas["controle"], False)
    valido = abs(mc + CUSTO) <= 3 * epc
    print(f"controle dentro de −0,12% ± 3 EP: {'sim → rodada VÁLIDA' if valido else 'NÃO → rodada INVÁLIDA, nada é julgado'}")
    julgar("venda (relato)", linhas["venda"], False)
    _, _, passa = julgar("COMPRA (juiz a)", linhas["compra"], True)
    print("Veredito H74:", "APROVADA em (a)" if valido and passa else "REPROVADA" if valido else "INVÁLIDA")


if __name__ == "__main__":
    main()
