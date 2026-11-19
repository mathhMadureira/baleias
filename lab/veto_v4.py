"""O veto do v4 ajuda ou atrapalha? (pedido do dono, 19/11: "o v4 está barrando todas as entradas do Caçador"). Medição descritiva, não regra.

Eventos (ramo `estado`, desde DESDE):
  descarte  — cada moeda em "descartadas" das decisões dos 4 agentes (lado lido no motivo; "cita o v4" se o motivo fala do v4/confiança/p subir);
  cacador   — cada sinal da varredura da nuvem (H68, dados/oportunidades.json, histórico de commits) e cada aviso confirmado pelo agente Caçador.
O mesmo (fonte, moeda, lado) conta uma vez a cada 30 min. Entrada = fechamento do último minuto fechado na hora do evento; resultado = fechamento
15 e 60 min depois, no lado do evento, − 0,12%. O v4 da hora do evento vem do `ultima` do commit de dados/cerebro_v4.json mais novo antes dele:
  a favor / contra = confiança |p − 0,5| ≥ 0,12 do mesmo lado / do lado oposto; fraco a favor / fraco contra = confiança < 0,12; fora = moeda sem v4.
Controle: para cada evento, uma moeda sorteada do v4 daquela hora e um lado sorteado, no mesmo instante (tem de dar ≈ −0,12%).
Erro-padrão agrupado pela hora do evento. Uso: python3 -m lab.veto_v4 [desde] → dados/lab/veto_v4_resultado.json
"""
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = "https://data-api.binance.vision/api/v3/klines"
CUSTO, CONF, REPETE_S = 0.0012, 0.12, 1800
AGENTES = ("claude", "treinador", "laboratorio", "guardiao")
CITA_V4 = re.compile(r"v4|p subir|confian|conf\.|prob", re.I)
CACADOR_JSONL = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/oportunidades_cacador.jsonl")


def git(*a):
    return subprocess.run(["git", "-C", str(RAIZ), *a], capture_output=True, text=True).stdout


def historico(arq, desde):
    """[(t_commit, conteúdo)] do arquivo no ramo estado, do mais antigo ao mais novo."""
    out = []
    for linha in git("log", "--reverse", f"--since=@{desde}", "--format=%h %ct", "origin/estado", "--", f"dados/{arq}").splitlines():
        h, ct = linha.split()
        try:
            out.append((int(ct), json.loads(git("show", f"{h}:dados/{arq}") or "null")))
        except ValueError:
            continue
    return out


def lado_do_motivo(m):
    m = m.lower()
    i, j = m.find("compra"), m.find("venda")
    if i < 0 and j < 0:
        return None
    return "compra" if j < 0 or (0 <= i < j) else "venda"


def grupo_v4(prob, lado):
    if prob is None:
        return "fora do v4"
    conf = abs(prob - 0.5)
    a_favor = (prob > 0.5) == (lado == "compra")
    if conf >= CONF:
        return "v4 a favor (≥ 0,12)" if a_favor else "v4 contra (≥ 0,12)"
    return "fraco a favor (< 0,12)" if a_favor else "fraco contra (< 0,12)"


def resultados(k, t_ms):
    """Velas de 1 min [t, o, h, l, c, ...]; entrada = fechamento do último minuto fechado até t_ms. Devolve (entrada, {15: px, 60: px})."""
    ent = [x for x in k if int(x[6]) < t_ms]
    if not ent:
        return None
    t0 = int(ent[-1][0])
    por = {int(x[0]): float(x[4]) for x in k}
    return float(ent[-1][4]), {h: por.get(t0 + h * 60_000) for h in (15, 60)}


def velas(par, t_ms):
    try:
        with urllib.request.urlopen(f"{DADOS}?symbol={par}&interval=1m&startTime={t_ms - 180_000}&limit=70", timeout=25) as r:
            return json.load(r)
    except (OSError, ValueError):
        return []


def resumo(vals):
    """vals: [(t_ms, r)] → n, média %, ep % agrupado por hora, t, acerto."""
    if not vals:
        return {"n": 0}
    n = len(vals)
    media = sum(r for _, r in vals) / n
    g = defaultdict(lambda: [0, 0.0])
    for t, r in vals:
        g[t // 3_600_000][0] += 1
        g[t // 3_600_000][1] += r
    G = len(g)
    ep = ((G / (G - 1)) * sum((s - c * media) ** 2 for c, s in g.values()) / n ** 2) ** 0.5 if G > 1 else None
    return {"n": n, "media_pct": round(100 * media, 3), "ep_pct": round(100 * ep, 3) if ep else None,
            "t": round(media / ep, 2) if ep else None, "acerto": round(sum(r > 0 for _, r in vals) / n, 3)}


def main(desde):
    agora = time.time()
    v4 = [(ct, (d or {}).get("ultima") or {}) for ct, d in historico("cerebro_v4.json", desde - 3600)]
    v4 = [(ct, u) for ct, u in v4 if len(u) >= 30]

    def prob_em(par, t):
        u = next((u for ct, u in reversed(v4) if ct <= t), None)
        return (float(u[par]["prob"]) if u and par in u else None), (sorted(u) if u else [])

    ev = []
    for ag in AGENTES:
        for ct, d in historico(f"decisao_{ag}.json", desde):
            for x in (d or {}).get("descartadas") or []:
                par = str(x.get("moeda", "")).upper()
                par = par if par.endswith("USDT") else par + "USDT"
                lado = lado_do_motivo(str(x.get("motivo", "")))
                if lado:
                    ev.append({"fonte": "descarte", "agente": ag, "par": par, "lado": lado, "t": float(d.get("t", ct)),
                               "cita_v4": bool(CITA_V4.search(str(x.get("motivo", ""))))})
    for ct, d in historico("oportunidades.json", desde):
        for o in (d or {}).get("oportunidades") or []:
            if o.get("t", 0) >= desde:
                ev.append({"fonte": "caçador (nuvem)", "par": o["par"], "lado": o["lado"], "t": float(o["t"]), "sinal": o.get("tipo")})
    if CACADOR_JSONL.exists():
        for l in CACADOR_JSONL.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x.get("t", 0) >= desde:
                ev.append({"fonte": "caçador (aviso)", "par": x["moeda"], "lado": x["lado"], "t": float(x["t"]), "sinal": x.get("sinal")})
    ev.sort(key=lambda e: e["t"])
    ultimo, unicos = {}, []
    for e in ev:
        k = (e["fonte"], e.get("agente"), e["par"], e["lado"])
        if e["t"] - ultimo.get(k, -1e18) >= REPETE_S and e["t"] <= agora - 16 * 60:
            ultimo[k] = e["t"]
            unicos.append(e)
    rnd = random.Random(19112026)
    for e in unicos:
        e["prob"], lista = prob_em(e["par"], e["t"])
        e["grupo"] = grupo_v4(e["prob"], e["lado"])
        e["controle_par"], e["controle_lado"] = (rnd.choice(lista), rnd.choice(("compra", "venda"))) if lista else (None, None)
    pedidos = sorted({(e["par"], int(e["t"] * 1000)) for e in unicos} | {(e["controle_par"], int(e["t"] * 1000)) for e in unicos if e["controle_par"]})
    with ThreadPoolExecutor(10) as ex:
        k = dict(zip(pedidos, ex.map(lambda p: velas(*p), pedidos)))

    def r(par, lado, t_ms, h):
        x = resultados(k.get((par, t_ms)) or [], t_ms)
        if not x or x[1].get(h) is None:
            return None
        return (x[1][h] / x[0] - 1) * (1 if lado == "compra" else -1) - CUSTO

    tabela = defaultdict(lambda: defaultdict(list))
    for e in unicos:
        tm = int(e["t"] * 1000)
        for h in (15, 60):
            v = r(e["par"], e["lado"], tm, h)
            c = r(e["controle_par"], e["controle_lado"], tm, h) if e["controle_par"] else None
            fonte = "descarte (cita o v4)" if e["fonte"] == "descarte" and e["cita_v4"] else "descarte (outro motivo)" if e["fonte"] == "descarte" else "caçador"
            if v is not None:
                tabela[(fonte, e["grupo"])][h].append((tm, v))
                tabela[(fonte, "todos")][h].append((tm, v))
                tabela[("todos os eventos", e["grupo"])][h].append((tm, v))
            if c is not None:
                tabela[("controle aleatório", "—")][h].append((tm, c))
    out = {"desde_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(desde)), "ate_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(agora)),
           "eventos": len(unicos), "por_fonte": {f: sum(1 for e in unicos if e["fonte"] == f) for f in {e["fonte"] for e in unicos}},
           "tabela": [{"fonte": f, "grupo": g, "15 min": resumo(hs.get(15, [])), "60 min": resumo(hs.get(60, []))}
                      for (f, g), hs in sorted(tabela.items())]}
    dest = RAIZ / "dados" / "lab" / "veto_v4_resultado.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{out['eventos']} eventos {out['por_fonte']} de {out['desde_utc']} a {out['ate_utc']} UTC")
    print("| fonte | v4 na hora | 15 min: n / média / t | 60 min: n / média / t |\n|---|---|---|---|")
    for x in out["tabela"]:
        a, b = x["15 min"], x["60 min"]
        f = lambda s: f"{s['n']} / {s.get('media_pct', 0):+.3f}% / {s.get('t')}" if s["n"] else "0"
        print(f"| {x['fonte']} | {x['grupo']} | {f(a)} | {f(b)} |")


def replay(dias=2):
    """Explosões de vela da H68 (executor/cacador_nuvem.sinais_1m, mesma regra) reproduzidas minuto a minuto nas moedas do v4 nos últimos `dias`,
    com o v4 da hora (commit de dados/cerebro_v4.json mais novo antes do minuto). Mesmo (moeda, sinal, lado) uma vez a cada 30 min."""
    from executor import cacador_nuvem as C
    agora = time.time()
    desde = agora - dias * 86400
    v4 = []
    for linha in git("log", "--reverse", f"--since=@{int(desde - 3600)}", "--format=%h %ct", "origin/estado", "--", "dados/cerebro_v4.json").splitlines():
        h, ct = linha.split()
        if v4 and int(ct) - v4[-1][0] < 840:                      # o v4 muda a cada vela de 15 min
            continue
        try:
            u = (json.loads(git("show", f"{h}:dados/cerebro_v4.json") or "null") or {}).get("ultima") or {}
        except ValueError:
            continue
        if len(u) >= 30:
            v4.append((int(ct), u))
    pares = sorted({p for _, u in v4 for p in u})

    cache = Path("/tmp/veto_v4_cache")
    cache.mkdir(exist_ok=True)

    def minutos(par):
        arq = cache / f"{par}-{int(desde // 3600)}.json"
        if arq.exists():
            return par, json.loads(arq.read_text())
        out, t = [], int((desde - 3 * 3600) * 1000)
        while t < agora * 1000:
            for tentativa in range(4):                                # rede lenta: tenta de novo antes de desistir da moeda
                try:
                    with urllib.request.urlopen(f"{DADOS}?symbol={par}&interval=1m&startTime={t}&limit=1000", timeout=40) as r:
                        k = json.load(r)
                    break
                except (OSError, ValueError):
                    time.sleep(2 + 3 * tentativa)
            else:
                return par, []
            if not k:
                break
            out += [x[:7] for x in k if int(x[6]) < agora * 1000]
            t = int(k[-1][0]) + 60_000
            if len(k) < 1000:
                break
        arq.write_text(json.dumps(out))
        return par, out
    with ThreadPoolExecutor(6) as ex:
        ks = {p: k for p, k in ex.map(minutos, pares) if k}
    # o cache guarda 7 campos; o volume em US$ (campo 8) é reconstruído como volume × fechamento (a razão de volume da regra fica igual)
    ks = {p: [list(x[:7]) + [float(x[5]) * float(x[4])] if len(x) < 8 else x for x in k] for p, k in ks.items()}
    por_t = {p: {int(x[0]): i for i, x in enumerate(k)} for p, k in ks.items()}
    rnd = random.Random(7)
    tab = defaultdict(lambda: defaultdict(list))
    n_ev = 0
    janela = C.BASE + max(C.JANELAS) + 1
    for par, k in ks.items():
        ult = {}
        for L in range(janela, len(k) - 61):
            t_ms = int(k[L][6]) + 1
            if t_ms < desde * 1000:
                continue
            sinais, _, _ = C.sinais_1m(k[L - janela + 1:L + 1])
            for s in sinais:
                chave = (s["tipo"], s["lado"])
                if t_ms / 1000 - ult.get(chave, -1e18) < REPETE_S:
                    continue
                ult[chave] = t_ms / 1000
                u = next((u for ct, u in reversed(v4) if ct <= t_ms / 1000), None)
                if not u:
                    continue
                prob = float(u[par]["prob"]) if par in u else None
                g = grupo_v4(prob, s["lado"])
                n_ev += 1
                t0 = int(k[L][0])
                com_dado = [p for p in sorted(u) if p in por_t and t0 in por_t[p] and por_t[p][t0] + 60 < len(ks[p])]
                controles = [(rnd.choice(com_dado), rnd.choice(("compra", "venda"))) for _ in range(2)] if com_dado else []
                for h in (15, 60):
                    v = (float(k[L + h][4]) / float(k[L][4]) - 1) * (1 if s["lado"] == "compra" else -1) - CUSTO
                    tab[(s["tipo"], g)][h].append((t_ms, v))
                    tab[("todas as explosões", g)][h].append((t_ms, v))
                    tab[("todas as explosões", "todos")][h].append((t_ms, v))
                    for cp, cl in controles:
                        kc, ic = ks[cp], por_t[cp][t0]
                        tab[("controle aleatório", "—")][h].append((t_ms, (float(kc[ic + h][4]) / float(kc[ic][4]) - 1) * (1 if cl == "compra" else -1) - CUSTO))
    out = {"desde_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(desde)), "ate_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(agora)),
           "moedas": len(ks), "eventos": n_ev, "versoes_do_v4": len(v4),
           "tabela": [{"sinal": f, "grupo": g, "15 min": resumo(hs.get(15, [])), "60 min": resumo(hs.get(60, []))} for (f, g), hs in sorted(tab.items())]}
    dest = RAIZ / "dados" / "lab" / "veto_v4_replay.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"replay: {n_ev} explosões em {len(ks)} moedas, {out['desde_utc']} → {out['ate_utc']} UTC, {len(v4)} versões do v4")
    print("| sinal | v4 na hora | 15 min: n / média / t | 60 min: n / média / t |\n|---|---|---|---|")
    for x in out["tabela"]:
        f = lambda s: f"{s['n']} / {s.get('media_pct', 0):+.3f}% / {s.get('t')}" if s["n"] else "0"
        print(f"| {x['sinal']} | {x['grupo']} | {f(x['15 min'])} | {f(x['60 min'])} |")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--replay"]:
        replay(float(sys.argv[2]) if len(sys.argv) > 2 else 2)
        raise SystemExit(0)
    d = sys.argv[1] if len(sys.argv) > 1 else "2026-11-19 12:51 UTC"
    main(int(subprocess.run(["date", "-d", d, "+%s"], capture_output=True, text=True).stdout))
