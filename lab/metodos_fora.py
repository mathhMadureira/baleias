"""H65 — métodos de fora com evidência publicada (regra e juiz pré-registrados em lab/PROTOCOLO_LAB.md antes de baixar os dados).

F: fluxo agressor de 15 min (F1 segue, F2 contra), |z| >= 2,5, sai 1 h depois.
M: momento semanal comprado e vendido (21 dias, 20% de cima × 20% de baixo, 7 dias).
L: alavancagem pela volatilidade da estratégia (só se F ou M passar).
Só biblioteca padrão. Uso: python3 -m lab.metodos_fora
"""
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "dados" / "lab" / "h65_cache.json"
SAIDA = REPO / "dados" / "lab" / "metodos_fora_resultado.json"
BASE = "https://fapi.binance.com/fapi/v1"
CUSTO, Z_MIN, N_MOEDAS = 0.0012, 2.13, 60
M15, DIA = 900_000, 86_400_000


def pedir(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except (OSError, ValueError):
            time.sleep(2 + 3 * k)
    raise OSError("sem resposta: " + url[:80])


def universo():
    t = pedir(f"{BASE}/ticker/24hr")
    info = pedir(f"{BASE}/exchangeInfo")
    perp = {s["symbol"] for s in info["symbols"] if s.get("contractType") == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"}
    t = [x for x in t if x["symbol"] in perp]
    return [x["symbol"] for x in sorted(t, key=lambda x: -float(x["quoteVolume"]))[:N_MOEDAS]]


def velas(par, intervalo, ini, fim, passo):
    out, t = [], ini
    while t < fim:
        k = pedir(f"{BASE}/klines?symbol={par}&interval={intervalo}&startTime={t}&endTime={fim}&limit=1500")
        if not k:
            break
        out += [[int(x[0]), float(x[4]), float(x[7]), float(x[10])] for x in k if int(x[6]) < fim]   # abre, fecho, volume US$, comprador US$
        t = int(k[-1][0]) + passo
        time.sleep(0.2)
        if len(k) < 1500:
            break
    return out


def estat(rs, chave):
    """rs: [(grupo, retorno)]. Média, t com erro-padrão agrupado por grupo, 3 blocos."""
    n = len(rs)
    if n < 30:
        return {"n": n}
    m = sum(r for _, r in rs) / n
    g = {}
    for k, r in rs:
        g.setdefault(k, []).append(r)
    var = sum((sum(v) - len(v) * m) ** 2 for v in g.values())
    t = m / (math.sqrt(var) / n) if var > 0 else 0.0
    ks = sorted(g)
    tercos = [ks[: len(ks) // 3], ks[len(ks) // 3: 2 * len(ks) // 3], ks[2 * len(ks) // 3:]]
    blocos = []
    for tc in tercos:
        x = [r for k in tc for r in g[k]]
        blocos.append(sum(x) / len(x) if x else 0.0)
    ok = m > 0 and t >= Z_MIN and all(b > 0 for b in blocos)
    return {"n": n, "grupos": len(g), "media": m, "t": t, "blocos": blocos, "acerto": sum(r > 0 for _, r in rs) / n, "passa": ok, "chave": chave}


def parte_f(dados):
    rs1, rs2 = [], []
    for par, v in dados.items():
        for i in range(96, len(v) - 4):
            vol = v[i][2]
            if vol <= 0:
                continue
            serie = [2 * x[3] / x[2] - 1 for x in v[i - 96:i] if x[2] > 0]
            if len(serie) < 80:
                continue
            mu = sum(serie) / len(serie)
            sd = math.sqrt(sum((s - mu) ** 2 for s in serie) / len(serie))
            if sd <= 0:
                continue
            z = ((2 * v[i][3] / vol - 1) - mu) / sd
            if abs(z) < 2.5 or v[i + 4][0] != v[i][0] + 4 * M15:
                continue
            ret = v[i + 4][1] / v[i][1] - 1
            lado = 1 if z > 0 else -1
            rs1.append((v[i][0], lado * ret - CUSTO))
            rs2.append((v[i][0], -lado * ret - CUSTO))
    return estat(rs1, "F1 segue o fluxo"), estat(rs2, "F2 contra o fluxo"), rs1, rs2


def parte_m(diarias):
    por_dia = {p: {x[0]: x[1] for x in v} for p, v in diarias.items()}
    dias = sorted({d for v in por_dia.values() for d in v})
    segundas = [d for d in dias if time.gmtime(d / 1000).tm_wday == 0]
    semanas = []
    for s in segundas:
        ant, fim = s - DIA, s + 7 * DIA - DIA          # fechamento de domingo; fechamento do domingo seguinte
        rank = []
        for p, c in por_dia.items():
            if ant in c and ant - 21 * DIA in c and fim in c:
                rank.append((c[ant] / c[ant - 21 * DIA] - 1, c[fim] / c[ant] - 1))
        if len(rank) < 20:
            continue
        rank.sort()
        q = max(1, len(rank) // 5)
        longo = sum(r for _, r in rank[-q:]) / q
        curto = sum(r for _, r in rank[:q]) / q
        semanas.append((s, 0.5 * (longo - curto) - CUSTO))   # metade do capital em cada perna; custo das duas pernas
    return estat(semanas, "M momento semanal"), semanas


def parte_l(serie, por_semana):
    """serie: [(t, ret)] por período. Exposição = alvo / vol das 4 últimas (por_semana) ou 16 últimas (fluxo agregado por hora)."""
    j = 4 if por_semana else 96
    rets = [r for _, r in serie]
    meio = len(rets) // 2
    alvo = math.sqrt(sum(r * r for r in rets[:meio]) / meio)
    fixa, var = [], []
    for i in range(max(j, meio), len(rets)):
        vol = math.sqrt(sum(r * r for r in rets[i - j:i]) / j) or alvo
        e = min(3.0, alvo / vol)
        fixa.append(rets[i])
        var.append(e * rets[i])

    def sharpe(x):
        m = sum(x) / len(x)
        s = math.sqrt(sum((y - m) ** 2 for y in x) / len(x))
        return m / s if s else 0.0

    def queda(x):
        p, pico, q = 1.0, 1.0, 0.0
        for y in x:
            p *= 1 + y
            pico = max(pico, p)
            q = min(q, p / pico - 1)
        return q

    m = sum(rets) / len(rets)
    v2 = sum((r - m) ** 2 for r in rets) / len(rets)
    kelly = m / v2 if v2 else 0.0
    r = {"fixa": {"sharpe": sharpe(fixa), "queda": queda(fixa)}, "vol_alvo": {"sharpe": sharpe(var), "queda": queda(var)}, "kelly": kelly,
         "meio_kelly": kelly / 2}
    r["passa"] = r["vol_alvo"]["sharpe"] > r["fixa"]["sharpe"] and r["vol_alvo"]["queda"] > r["fixa"]["queda"]
    return r


def main():
    agora = int(time.time() * 1000) // M15 * M15
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if not cache.get("moedas"):
        cache = {"moedas": universo(), "m15": {}, "d1": {}, "fim": agora}
    moedas, fim = cache["moedas"], cache["fim"]
    for k, p in enumerate(moedas):
        try:
            if p not in cache["m15"]:
                cache["m15"][p] = velas(p, "15m", fim - 60 * DIA, fim, M15)
            if p not in cache["d1"]:
                cache["d1"][p] = velas(p, "1d", fim - 730 * DIA, fim // DIA * DIA, DIA)
        except (OSError, urllib.error.HTTPError) as ex:
            print(f"  {p}: {str(ex)[:60]}")
        if k % 10 == 0:
            print(f"  {k}/{len(moedas)} moedas")
            CACHE.write_text(json.dumps(cache))
    CACHE.write_text(json.dumps(cache))
    f1, f2, rs1, rs2 = parte_f(cache["m15"])
    m, sem = parte_m(cache["d1"])
    res = {"moedas": moedas, "F1": f1, "F2": f2, "M": m}
    print("| tentativa | n | média | t | blocos | acerto | passa |\n|---|---|---|---|---|---|---|")
    for x in (f1, f2, m):
        if x["n"] < 30:
            print(f"| {x.get('chave')} | {x['n']} | — |")
            continue
        print(f"| {x['chave']} | {x['n']} | {x['media']:+.3%} | {x['t']:+.2f} | {' '.join(f'{b:+.3%}' for b in x['blocos'])} | {x['acerto']:.1%} | "
              f"{'SIM' if x['passa'] else 'não'} |")
    for nome, x, serie, ps in (("F1", f1, rs1, False), ("F2", f2, rs2, False), ("M", m, sem, True)):
        if x.get("passa"):
            if not ps:                                   # fluxo: agrega por hora para a série da estratégia
                h = {}
                for t, r in serie:
                    h.setdefault(t // 3_600_000, []).append(r)
                serie = [(k, sum(v) / len(v)) for k, v in sorted(h.items())]
            res["L_" + nome] = parte_l(serie, ps)
            print(f"L ({nome}):", json.dumps(res["L_" + nome]))
    m_info = parte_l(sem, True) if len(sem) > 20 else None
    res["M_info_alavancagem"] = m_info
    print("M (informação, não decide):", json.dumps(m_info))
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
