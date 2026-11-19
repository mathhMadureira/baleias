"""H64 — "perder de colher e ganhar de balde" (regra e critério pré-registrados em lab/PROTOCOLO_LAB.md antes de rodar).

Parte T: tamanho que cresce com o ganho (fator = 2,5 × carteira ÷ 10, em [1,25; 5]), contrafactual igual ao da H60.
Parte S: 4 rotas de saída com stop pequeno e lucro grande nas apostas do v4 a favor do regime de 24 h, velas de 15 min da Binance.
Só biblioteca padrão. Uso: python3 -m lab.colher_balde
"""
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

from lab.alavancagem import CAPITAL, PISO, ler, nocional

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "dados" / "lab" / "h64_velas15.json"
SAIDA = REPO / "dados" / "lab" / "colher_balde_resultado.json"
PASSO, CUSTO, MAX_VELAS, ARMA, GUARDA = 900_000, 0.0012, 96, 0.005, 0.70
ROBOS_T = {"rapido": "robo_v4_perp.json", "cacador": "robo_v4_cacador.json", "scalper": "robo_scalper_nuvem.json", "scalper_b": "robo_scalper_b.json",
           "scalper_c": "robo_scalper_c.json", "scalper_d": "robo_scalper_d.json", "minerador": "robo_minerador.json", "claude": "robo_claude.json",
           "lbank": "robo_lbank.json", "radar": "robo_radar.json",
           "treinador": "agente_treinador.json", "laboratorio": "agente_laboratorio.json", "guardiao": "agente_guardiao.json"}
CONJ_T = {"antes do zero (etiqueta)": "estado-antes-do-zero-2026-11-16", "desde o zero (agora)": "origin/estado"}
ROTAS = {"S1 stop 0,5% alvo 1,5%": (0.005, 0.015, False), "S2 stop 0,5% + móvel": (0.005, None, True),
         "S3 stop 1% + móvel": (0.01, None, True), "S4 stop 1% alvo 3%": (0.01, 0.03, False)}
REFERENCIA = {"R6 (referência) stop 2% + móvel": (0.02, None, True)}
Z_MIN = 2.24
CORRIGIDO = True


# ---------- Parte T ----------
def fator_h64(realizado):
    return min(5.0, max(1.25, 2.5 * realizado / CAPITAL))


def simular_t(ops, regra):
    """ops: [(entrada_t, saida_t, pct do nocional)]. regra 'atual' (2,5× a 10×) ou 'h64'. Devolve (final, mínimo, feitas)."""
    ev = sorted([(e, 0, i) for i, (e, s, p) in enumerate(ops)] + [(s, 1, i) for i, (e, s, p) in enumerate(ops)], key=lambda x: (x[0], -x[1]))
    realizado, minimo, aberto, feitas = CAPITAL, CAPITAL, {}, 0
    for t, tipo, i in ev:
        if tipo == 0:
            if realizado < PISO:
                continue
            f = 2.5 if regra == "atual" else fator_h64(realizado)
            aberto[i] = (f * realizado, 10 if f <= 2.5 else 20)
        elif i in aberto:
            noc, a = aberto.pop(i)
            pct = max(ops[i][2], -1.0 / a)                     # liquidação: perde no máximo a margem
            realizado += noc * pct
            feitas += 1
            minimo = min(minimo, realizado)
    return realizado, minimo, feitas


def parte_t():
    saida = {}
    for nome, ref in CONJ_T.items():
        tab = {}
        for rid, arq in ROBOS_T.items():
            e = ler(ref, arq)
            if not e or not e.get("fechadas"):
                continue
            ops = [(float(x.get("entrada_t") or x["saida_t"]), float(x["saida_t"]), float(x["resultado_usd"]) / nocional(x))
                   for x in e["fechadas"] if x.get("saida_t") and x.get("resultado_usd") is not None]
            tab[rid] = {r: dict(zip(("final", "minimo", "ops"), simular_t(ops, r))) for r in ("atual", "h64")}
        saida[nome] = tab
    ok = True
    for nome, tab in saida.items():
        sa, sh = (sum(v[r]["final"] for v in tab.values()) for r in ("atual", "h64"))
        piso = all(not (v["h64"]["final"] < PISO and v["atual"]["final"] >= PISO) for v in tab.values())
        ok = ok and sh > sa and piso
        print(f"\n### Parte T — {nome}: soma atual {sa:.2f} × H64 {sh:.2f}; abaixo do piso só na H64: "
              f"{[r for r, v in tab.items() if v['h64']['final'] < PISO and v['atual']['final'] >= PISO] or '—'}")
        print("| robô | ops | atual | H64 |\n|---|---|---|---|")
        for r, v in tab.items():
            print(f"| {r} | {v['atual']['ops']} | {v['atual']['final']:.2f} | {v['h64']['final']:.2f} |")
    print("Parte T:", "PASSOU" if ok else "não passou")
    return {"conjuntos": saida, "veredito": "PASSOU" if ok else "não passou"}


# ---------- Parte S ----------
def velas(pares, ini, fim):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for k, par in enumerate(pares):
        if par in cache and cache[par] and cache[par][-1][0] >= fim - PASSO:
            continue
        lst, t = [], ini
        try:
            while t < fim:
                kk = None
                for base in ("https://fapi.binance.com/fapi/v1", "https://data-api.binance.vision/api/v3"):   # perpétuo; senão o à vista (o v4 lê o à vista)
                    for _ in range(3):
                        try:
                            with urllib.request.urlopen(f"{base}/klines?symbol={par}&interval=15m&startTime={t}&endTime={fim}&limit=1000", timeout=20) as r:
                                kk = json.load(r)
                            break
                        except urllib.error.HTTPError:
                            break
                        except (OSError, ValueError):
                            time.sleep(2)
                    if kk is not None:
                        break
                if kk is None:
                    raise OSError("nenhuma fonte respondeu")
                if not kk:
                    break
                lst += [[int(x[0]), float(x[2]), float(x[3]), float(x[4])] for x in kk]
                t = int(kk[-1][0]) + PASSO
                time.sleep(0.45)
                if len(kk) < 1000:
                    break
        except (OSError, ValueError) as ex:
            print(f"  {par}: sem velas ({str(ex)[:60]})")
        cache[par] = lst
        if k % 40 == 0:
            print(f"  velas {k}/{len(pares)}")
            CACHE.write_text(json.dumps(cache))
    CACHE.write_text(json.dumps(cache))
    return {p: {x[0]: x[1:] for x in v} for p, v in cache.items() if v}


def regime(vs, tempos):
    """% das moedas com fechamento acima do de 24 h antes, por vela."""
    out = {}
    for t in tempos:
        sob = tot = 0
        for d in vs.values():
            a, b = d.get(t), d.get(t - 96 * PASSO)
            if a and b:
                tot += 1
                sob += a[2] > b[2]
        out[t] = 100.0 * sob / tot if tot >= 30 else None
    return out


def sair(d, t0, venda, stop, alvo, movel):
    """Entrada no fechamento da vela t0; percorre as velas seguintes como stop_movel.conferir. Devolve retorno bruto ou None."""
    c0 = d.get(t0)
    if not c0:
        return None
    e, pico, ant = c0[2], 0.0, 0.0
    for j in range(1, MAX_VELAS + 1):
        v = d.get(t0 + j * PASSO)
        if not v:
            return None
        h, l, c = v
        fav = (1 - l / e) if venda else (h / e - 1)
        adv = (1 - h / e) if venda else (l / e - 1)
        if movel and pico >= ARMA and adv <= GUARDA * pico:
            return min(GUARDA * pico, ant) if CORRIGIDO else GUARDA * pico      # 19/11 (H66): não sair num preço que já passou
        if adv <= -stop:
            return -stop
        if alvo and fav >= alvo:
            return alvo
        pico = max(pico, fav)
        ant = (1 - c / e) if venda else (c / e - 1)
        if j == MAX_VELAS:
            return (1 - c / e) if venda else (c / e - 1)
    return None


def estat(rs):
    """rs: [(t_entrada, líquido)]. Média, z com erro-padrão por vela de entrada, blocos, acerto, G, L."""
    n = len(rs)
    if n < 30:
        return {"n": n}
    m = sum(r for _, r in rs) / n
    grupos = {}
    for t, r in rs:
        grupos.setdefault(t, []).append(r)
    var = sum((sum(g) - len(g) * m) ** 2 for g in grupos.values())
    z = m / (math.sqrt(var) / n) if var > 0 else 0.0
    ts = sorted(t for t, _ in rs)
    cortes = [ts[0], ts[n // 3], ts[2 * n // 3], ts[-1] + 1]
    blocos = []
    for a, b in zip(cortes, cortes[1:]):
        x = [r for t, r in rs if a <= t < b]
        blocos.append(sum(x) / len(x) if x else 0.0)
    g = [r for _, r in rs if r > 0]
    p = [-r for _, r in rs if r <= 0]
    G, L = (sum(g) / len(g) if g else 0.0), (sum(p) / len(p) if p else 0.0)
    return {"n": n, "media": m, "z": z, "blocos": blocos, "acerto": len(g) / n, "G": G, "L": L}


def parte_s():
    r = __import__("subprocess").run(["git", "-C", str(REPO), "show", "origin/estado:dados/cerebro_v4.json"], capture_output=True, text=True)
    ops = json.loads(r.stdout)["ops"]
    apostas = [(par, int(o[0]), int(o[2])) for par, lst in ops.items() for o in lst]
    ini = min(t for _, t, _ in apostas) - 97 * PASSO
    fim = max(t for _, t, _ in apostas) + (MAX_VELAS + 2) * PASSO
    fim = min(fim, int(time.time() * 1000) // PASSO * PASSO)
    vs = velas(sorted(ops), ini, fim)
    reg = regime(vs, sorted({t for _, t, _ in apostas}))
    favor = [(par, t, a) for par, t, a in apostas if reg.get(t) is not None and ((reg[t] <= 30 and a < 0) or (reg[t] >= 70 and a > 0))]
    print(f"\n### Parte S — {len(apostas)} apostas do v4, {len(favor)} a favor do regime de 24 h, {len(vs)} moedas com velas")
    res, ok = {}, {}
    print("| rota | apostas | média/aposta | z | blocos | acerto | G | L | G ÷ L |\n|---|---|---|---|---|---|---|---|---|")
    for nome, (stop, alvo, movel) in {**ROTAS, **REFERENCIA}.items():
        rs = []
        for par, t, a in favor:
            d = vs.get(par)
            x = sair(d, t, a < 0, stop, alvo, movel) if d else None
            if x is not None:
                rs.append((t, x - CUSTO))
        s = estat(rs)
        res[nome] = s
        if s["n"] < 30:
            print(f"| {nome} | {s['n']} | — |")
            continue
        gl = s["G"] / s["L"] if s["L"] else float("inf")
        if nome in ROTAS:
            ok[nome] = s["media"] > 0 and s["z"] >= Z_MIN and all(b > 0 for b in s["blocos"]) and s["G"] >= 2 * s["L"]
        print(f"| {nome} | {s['n']} | {s['media']:+.3%} | {s['z']:+.2f} | {' '.join(f'{b:+.3%}' for b in s['blocos'])} | {s['acerto']:.1%} | "
              f"{s['G']:.2%} | {s['L']:.2%} | {gl:.2f} |")
    aprov = [n for n, v in ok.items() if v]
    melhor = max(aprov, key=lambda n: res[n]["media"]) if aprov else None
    print("Parte S:", f"APROVADA {melhor}" if melhor else "nenhuma rota passou")
    return {"rotas": res, "aprovadas": aprov, "vale": melhor, "apostas": len(apostas), "a_favor": len(favor)}


def main():
    import sys
    if "--so-s" in sys.argv:
        parte_s()
        return
    t = parte_t()
    s = parte_s()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"parte_t": t, "parte_s": s}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
