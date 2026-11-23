"""Juízo da H70 (saída com alvo: o stop móvel não pode fechar antes do alvo), pelo critério pré-registrado (3e5ea591, adendo de 19/11).

Entradas: apostas do v4 conferidas ao vivo (estado:dados/cerebro_v4.json, ops [t, líquido, aposta, prob]) com |prob − 0,5| ≥ 0,08,
de 16/11 21:53 UTC até agora; entrada no fechamento da vela de 1 min que fecha 5 min depois do fim da vela de 15 min do sinal.
Velas de 1 min do perpétuo da Binance (à vista quando o perpétuo não tem o símbolo). Custo 0,12%.
Saídas pelo próprio executor/stop_movel.conferir: G1 (stop 0,6%, alvo 1,2%, 120 min) e G2 (1%, 3%, 24 h) × A0 (móvel a +0,5%),
A1 (sem móvel), A2 (móvel em alvo/2). Entradas cujo prazo ainda não terminou ficam de fora (não conferidas).
Controle: mesmas moedas e instantes, lado sorteado; cada uma das 6 combinações tem de dar −0,12% ± 3 erros-padrão, senão a rodada é inválida.
Juiz (4 tentativas: A1 e A2 em G1 e G2): diferença pareada Ax − A0 com média > 0, z ≥ 2,24 (erro-padrão agrupado pela vela de 15 min
do sinal) e > 0 nos 3 blocos de tempo iguais.

Uso: git fetch -q origin estado && python3 -m lab.juizo_h70
"""
import json
import math
import random
import subprocess
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from executor import stop_movel as SM

U = timezone.utc
INICIO = int(datetime(2026, 11, 16, 21, 53, tzinfo=U).timestamp() * 1000)
CONF, CUSTO, Z = 0.08, 0.0012, 2.24
GEOM = {"G1": (0.006, 0.012, 120), "G2": (0.01, 0.03, 1440)}
FORMAS = {"A0": lambda a: SM.ARMA, "A1": lambda a: 1e9, "A2": lambda a: max(SM.ARMA, 0.5 * a)}
CACHE = Path("/tmp/baleias_lab_1m_h70")
FAPI, SPOT = "https://fapi.binance.com/fapi/v1/klines", "https://data-api.binance.vision/api/v3/klines"


def baixar(par, desde, ate):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{par}_{desde}_{ate}.json"
    if f.exists():
        d = json.loads(f.read_text())
        return d["fonte"], [tuple(x) for x in d["m"]]
    for fonte, url in (("perp", FAPI), ("spot", SPOT)):
        out, t, falhou, tentativas = [], desde, False, 0
        while t < ate:
            try:
                with urllib.request.urlopen(f"{url}?symbol={par}&interval=1m&startTime={t}&endTime={ate - 1}&limit=1000", timeout=20) as r:
                    k = json.load(r)
            except urllib.error.HTTPError:
                falhou = True
                break
            except (OSError, ValueError):
                tentativas += 1
                if tentativas > 3:                          # rede teimosa: desiste desta fonte (antes: laço infinito)
                    falhou = True
                    break
                time.sleep(2)
                continue
            tentativas = 0
            time.sleep(0.15)
            if not k:
                break
            out += [(int(x[0]), float(x[2]), float(x[3]), float(x[4])) for x in k if int(x[6]) < ate]
            t = int(k[-1][0]) + 60_000
        if out and not falhou:
            f.write_text(json.dumps({"fonte": fonte, "m": out}))
            return fonte, out
    return None, []


def resultado(entrada, lado, caminho, stop, alvo, fim, forma):
    p = {"entrada": entrada, "lado": lado}
    orig = SM.armar_em
    SM.armar_em = FORMAS[forma]
    try:
        r = SM.conferir(p, caminho, stop, fim, caminho[0][0], alvo_pct=alvo)
    finally:
        SM.armar_em = orig
    saida = r[0] if r else caminho[-1][3]
    s = -1 if lado == "venda" else 1
    return s * (saida / entrada - 1) - CUSTO


def media_ep(vals, grupos):
    n = len(vals)
    m = sum(vals) / n
    cl = defaultdict(float)
    for v, g in zip(vals, grupos):
        cl[g] += v - m
    G = len(cl)
    ep = math.sqrt(sum(s * s for s in cl.values()) * G / (G - 1)) / n
    return m, ep


def main():
    random.seed(70)
    rev = subprocess.check_output(["git", "rev-parse", "--short", "origin/estado"], text=True).strip()
    v4 = json.loads(subprocess.check_output(["git", "show", "origin/estado:dados/cerebro_v4.json"]))
    agora = int(time.time() // 60 * 60_000)
    apostas = [(par, o[0], "compra" if o[2] > 0 else "venda") for par, ops in v4["ops"].items() for o in ops
               if len(o) >= 4 and o[0] >= INICIO and abs(o[3] - 0.5) >= CONF]
    pares = sorted({a[0] for a in apostas})
    print(f"ramo estado {rev}; {len(apostas)} apostas com confiança ≥ {CONF} desde 16/11 21:53 UTC em {len(pares)} moedas")
    velas, fontes = {}, defaultdict(int)
    for par in pares:
        fonte, m = baixar(par, INICIO, agora)
        fontes[fonte] += 1
        velas[par] = m
    print("fonte das velas:", dict(fontes))
    idx = {par: {x[0]: i for i, x in enumerate(m)} for par, m in velas.items()}
    res = {}
    for g, (stop, alvo, prazo) in GEOM.items():
        linhas, faltou = [], 0
        for par, t, lado in apostas:
            t_ent = t + 19 * 60_000                   # vela de 1 min que fecha 5 min depois do fim da vela de 15 min
            fim = t_ent + 60_000 + prazo * 60_000
            i = idx.get(par, {}).get(t_ent)
            if i is None or fim > agora:
                faltou += 1
                continue
            m = velas[par]
            caminho = [x for x in m[i + 1:i + 1 + prazo + 5] if x[0] < fim]
            if len(caminho) < prazo * 0.9:
                faltou += 1
                continue
            e = m[i][3]
            sorteado = random.choice(("compra", "venda"))
            linhas.append({"t": t, "real": {f: resultado(e, lado, caminho, stop, alvo, fim, f) for f in FORMAS},
                           "ctl": {f: resultado(e, sorteado, caminho, stop, alvo, fim, f) for f in FORMAS}})
        res[g] = linhas
        print(f"\n{g} (stop {stop:.1%}, alvo {alvo:.1%}, {prazo} min): {len(linhas)} entradas conferidas, {faltou} fora (prazo aberto ou sem velas)")
    valido = True
    print("\nControle (lado sorteado): média, erro-padrão, dentro de −0,12% ± 3 EP?")
    for g, L in res.items():
        for f in FORMAS:
            m, ep = media_ep([x["ctl"][f] for x in L], [x["t"] for x in L])
            ok = abs(m + CUSTO) <= 3 * ep
            valido &= ok
            print(f"  {g} {f}: {m:+.3%} ± {ep:.3%} → {'ok' if ok else 'FORA'}")
    print(f"Rodada {'VÁLIDA' if valido else 'INVÁLIDA (simulador suspeito; nada é julgado)'}")
    print("\nMédia absoluta das entradas reais (relato, não decide):")
    for g, L in res.items():
        print("  " + g + ": " + ", ".join(f"{f} {sum(x['real'][f] for x in L) / len(L):+.3%}" for f in FORMAS))
    print("\nJuiz (diferença pareada contra A0):")
    for g, L in res.items():
        L = sorted(L, key=lambda x: x["t"])
        for f in ("A1", "A2"):
            d = [x["real"][f] - x["real"]["A0"] for x in L]
            m, ep = media_ep(d, [x["t"] for x in L])
            k = len(d) // 3
            blocos = [sum(d[:k]) / k, sum(d[k:2 * k]) / k, sum(d[2 * k:]) / len(d[2 * k:])]
            passa = valido and m > 0 and m / ep >= Z and all(b > 0 for b in blocos)
            print(f"  {g} {f} − A0: média {m:+.3%}, EP {ep:.3%}, z {m / ep:+.2f}, blocos " + " / ".join(f"{b:+.3%}" for b in blocos)
                  + f" → {'APROVADA' if passa else 'REPROVADA'}")


if __name__ == "__main__":
    main()
