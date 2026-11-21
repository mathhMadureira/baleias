"""Juízo das hipóteses ao vivo das carteiras dos agentes (20/11/2026), pelos critérios pré-registrados em lab/PROTOCOLO_LAB.md.

- H61/H62 (por agente com 30 operações): fator de lucro > 1 e carteira > US$ 10 depois das 30 primeiras operações fechadas,
  abertas a partir de 18/11 20:18:18 UTC (H61, depois da P1) ou 20:37 UTC (H62). Carteira = US$ 10 + soma realizada até o fechamento da 30ª.
- H49 (stop móvel): soma das saídas reais (com o stop móvel) > soma com a saída antiga (a mesma regra sem o stop móvel), nas operações dos
  agentes abertas depois da P1. Só as operações fechadas pelo stop móvel mudam; nelas a saída antiga é refeita com o próprio
  executor/stop_movel.conferir (móvel desligado), nas velas de 1 min à vista (a fonte da nuvem), até stop, alvo ou prazo (max_min, teto 24 h).
- H69 (r9–r12 × r8, braço de controle): excesso = resultado real (% do nocional) − controle de lado sorteado (média dos dois lados, mesma moeda,
  instante, preço de entrada, stop, alvo, prazo e regra do móvel em vigor), custo 0,12%. Com menos de 30 r8 (r6/r8 juntas): passa com excesso
  médio > 0 e t ≥ 2 (erro-padrão agrupado pela rodada de decisão) e fator de lucro da r9 > 1. Nas 30 primeiras r9–r12 fechadas dos 3 agentes.

Uso: git fetch -q origin estado && python3 -m lab.juizo_agentes
"""
import json
import math
import random
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from executor import stop_movel as SM

U = timezone.utc
P1 = datetime(2026, 11, 18, 20, 18, 18, tzinfo=U).timestamp()
H62 = datetime(2026, 11, 18, 20, 37, tzinfo=U).timestamp()
ALVO_METADE = datetime(2026, 11, 19, 15, 44, 56, tzinfo=U).timestamp()   # commit 1de5b148: com alvo, o móvel arma em alvo/2
CUSTO = 0.0012
AGENTES = {"baleias": ("robo_claude", "decisao_claude"), "treinador": ("agente_treinador", "decisao_treinador"),
           "laboratorio": ("agente_laboratorio", "decisao_laboratorio"), "guardiao": ("agente_guardiao", "decisao_guardiao")}
ATIVA = {"r9", "r10", "r11", "r12"}          # registradas na H69 (adendos 1–4); r13/r14 sem adendo: relatadas à parte
CACHE = Path("/tmp/baleias_lab_1m")


def git(*a):
    return subprocess.check_output(["git", *a])


def estado(arq, rev="origin/estado"):
    return json.loads(git("show", f"{rev}:dados/{arq}"))


def minutos(par, desde_ms, ate_ms):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{par}_{desde_ms}_{ate_ms}.json"
    if f.exists():
        return [tuple(x) for x in json.loads(f.read_text())]
    m = SM.buscar(par, desde_ms, ate_ms)
    if m:
        f.write_text(json.dumps(m))
    time.sleep(0.05)
    return m


def simular(op, lado, movel=True, regra_metade=True):
    """Resultado (fração do nocional, já com custo) de uma posição com a regra de saída da nuvem. None sem velas."""
    t0 = int(op["entrada_t"] * 1000)
    prazo = min(op.get("max_min") or 1440, 1440) * 60_000
    fim = min(t0 + prazo, int(time.time() // 60 * 60_000))
    m = minutos(op["moeda"], t0 - t0 % 60_000, fim)
    if not m:
        return None
    p = {"entrada": op["entrada"], "lado": lado}
    orig = SM.armar_em
    SM.armar_em = (lambda a: 1e9) if not movel else (orig if regra_metade else (lambda a: SM.ARMA))
    try:
        r = SM.conferir(p, m, op["stop_pct"], fim, t0, alvo_pct=op.get("alvo_pct"))
    finally:
        SM.armar_em = orig
    saida = r[0] if r else [x for x in m if x[0] < fim][-1][3]
    s = -1 if lado in ("venda", "SELL") else 1
    return s * (saida / op["entrada"] - 1) - CUSTO


def fator(xs):
    g, l = sum(x for x in xs if x > 0), -sum(x for x in xs if x < 0)
    return g / l if l else float("inf")


def h61_h62(fech):
    print("\n== H61/H62: 30 operações por agente ==")
    for ag, ops in fech.items():
        todas = sorted(ops, key=lambda x: x["saida_t"])
        for nome, t0 in (("H61", P1), ("H62", H62)):
            el = [x for x in todas if x["entrada_t"] >= t0]
            if len(el) < 30:
                print(f"{nome} {ag}: {len(el)} operações (faltam {30 - len(el)})")
                continue
            trinta = el[:30]
            ate = trinta[-1]["saida_t"]
            cart = 10 + sum(x["resultado_usd"] for x in todas if x["saida_t"] <= ate)
            pf = fator([x["resultado_usd"] for x in trinta])
            soma = sum(x["resultado_usd"] for x in trinta)
            print(f"{nome} {ag}: 30ª fechou {datetime.fromtimestamp(ate, U):%d/%m %H:%M} UTC; soma das 30 {soma:+.3f}, fator {pf:.2f}, "
                  f"carteira realizada US$ {cart:.2f} → {'APROVADO' if pf > 1 and cart > 10 else 'REPROVADO'}")


def h49(fech):
    print("\n== H49: stop móvel × saída antiga (operações dos agentes depois da P1) ==")
    real = antiga = 0.0
    n = nm = sem = 0
    por = defaultdict(lambda: [0.0, 0.0, 0])
    linhas = []
    for ag, ops in fech.items():
        for x in ops:
            if x["entrada_t"] < P1:
                continue
            n += 1
            real += x["resultado_usd"]
            b = x["resultado_usd"]
            if x.get("motivo_saida", "").startswith("stop móvel"):
                nm += 1
                r = simular(x, x["lado"], movel=False)
                if r is None:
                    sem += 1
                else:
                    b = r * x["nocional"]
                    linhas.append((x["entrada_t"], x["resultado_usd"] - b))
            antiga += b
            era = "até 19/11 15:45" if x["entrada_t"] < ALVO_METADE else "móvel em alvo/2"
            por[era][0] += x["resultado_usd"]
            por[era][1] += b
            por[era][2] += 1
    print(f"{n} operações, {nm} fechadas pelo stop móvel ({sem} sem velas: ficam iguais). Soma real (com móvel) {real:+.3f} × "
          f"saída antiga {antiga:+.3f} → {'APROVADO' if real > antiga else 'REPROVADO'}")
    for era, (a, b, k) in por.items():
        print(f"  {era}: {k} operações, real {a:+.3f} × antiga {b:+.3f}")
    linhas.sort()
    k = len(linhas) // 3 or 1
    for i in range(3):
        bl = linhas[i * k:(i + 1) * k if i < 2 else None]
        print(f"  bloco {i + 1} (só as do móvel): {len(bl)} operações, real − antiga {sum(d for _, d in bl):+.3f}")


def versoes(dec):
    v = {}
    for r in git("log", "--format=%H", "origin/estado", "--", f"dados/{dec}.json").decode().split():
        try:
            d = estado(f"{dec}.json", r)
        except (subprocess.CalledProcessError, ValueError):
            continue
        v[d.get("t")] = d.get("versao_rotina", "antes da r8")
    return v


def h69(fech, vers):
    print("\n== H69: postura ativa (r9–r12) × r8, total de baleias, treinador e guardião (laboratório à parte) ==")
    grupos = defaultdict(list)
    for ag, ops in fech.items():
        for x in ops:
            v = vers[ag].get(x.get("decisao_t"), "?")
            g = "ativa" if v in ATIVA else ("r8" if v in ("r6", "r8") else ("r13/r14" if v in ("r13", "r14") else "outra"))
            grupos[(ag == "laboratorio", g)].append((ag, v, x))
    for k, v in sorted(grupos.items()):
        print(f"  {'laboratório' if k[0] else 'os 3'} {k[1]}: {len(v)}")
    ativa = sorted(grupos[(False, "ativa")], key=lambda z: z[2]["saida_t"])
    r8 = grupos[(False, "r8")]
    if len(ativa) < 30:
        print(f"faltam {30 - len(ativa)} operações r9–r12")
        return

    def excessos(lista):
        out = []
        for ag, v, x in lista:
            real = x["resultado_usd"] / x["nocional"]
            metade = x["entrada_t"] >= ALVO_METADE
            c = [simular(x, l, regra_metade=metade) for l in ("compra", "venda")]
            if None in c:
                continue
            out.append(((ag, x["decisao_t"]), real, real - sum(c) / 2, x["resultado_usd"], x["saida_t"]))
        return out

    def resumo(nome, ex):
        if not ex:
            print(f"  {nome}: sem operações com velas")
            return None
        m = sum(e[2] for e in ex) / len(ex)
        cl = defaultdict(float)
        for e in ex:
            cl[e[0]] += e[2] - m
        G = len(cl)
        ep = math.sqrt(sum(s * s for s in cl.values()) * G / (G - 1)) / len(ex) if G > 1 else float("nan")
        pf = fator([e[3] for e in ex])
        print(f"  {nome}: n {len(ex)}, rodadas {G}, real médio {sum(e[1] for e in ex) / len(ex):+.3%}, excesso médio {m:+.3%}, "
              f"erro-padrão {ep:.3%}, t {m / ep:+.2f}, fator de lucro {pf:.2f}, soma US$ {sum(e[3] for e in ex):+.3f}")
        return m, m / ep, pf

    ex30 = excessos(ativa[:30])
    print(f"30ª r9–r12 fechou {datetime.fromtimestamp(ativa[29][2]['saida_t'], U):%d/%m %H:%M} UTC; r6/r8: {len(r8)} operações (< 30 → juiz pelo controle)")
    res = resumo("r9–r12, 30 primeiras", ex30)
    if res:
        m, t, pf = res
        print(f"  → {'FICA (APROVADA)' if m > 0 and t >= 2 and pf > 1 else 'REPROVADA (o REVISOR volta à r8)'}"
              f" [excesso > 0 e t ≥ 2: {'sim' if m > 0 and t >= 2 else 'não'}; fator > 1: {'sim' if pf > 1 else 'não'}]")
    resumo("r9–r12, todas (relato)", excessos(ativa))
    resumo("r6/r8 (relato)", excessos(r8))
    resumo("r13/r14 (relato)", excessos(grupos[(False, "r13/r14")]))
    resumo("laboratório, método fixo (relato)", excessos(grupos[(True, "ativa")] + grupos[(True, "r13/r14")] + grupos[(True, "outra")]))


def main():
    random.seed(0)
    rev = git("rev-parse", "--short", "origin/estado").decode().strip()
    print(f"ramo estado {rev}, {datetime.now(U):%d/%m %H:%M} UTC")
    fech = {ag: estado(f"{a}.json")["fechadas"] for ag, (a, _) in AGENTES.items()}
    vers = {ag: versoes(d) for ag, (_, d) in AGENTES.items()}
    h61_h62(fech)
    h49(fech)
    h69(fech, vers)


if __name__ == "__main__":
    main()
