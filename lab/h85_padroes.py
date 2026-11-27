"""H85 (27/11/2026): mede cada padrão de day trade (mesa/padroes.py) nas 45 moedas do radar da BingX, 15 min e 1 h.
Critério e execução pré-registrados em lab/PROTOCOLO_LAB.md (H85). Uso: python3 -m lab.h85_padroes
Saída: dados/lab/h85_padroes.json (tabela por padrão × lado × contexto × tempo gráfico)."""
import json
import math
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mesa"))
import padroes as P  # noqa: E402

RADAR = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/equipe/radar.json")
SAIDA = RAIZ / "dados" / "lab" / "h85_padroes.json"
CACHE = Path("/tmp/h85_velas")
URL = "https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={s}-USDT&interval={i}&limit=1000"
PLANO = {"15m": 3, "1h": 1}                                  # páginas de 1.000 velas


def velas(moeda, iv):
    CACHE.mkdir(exist_ok=True)
    arq = CACHE / f"{moeda}_{iv}.json"
    if arq.exists() and time.time() - arq.stat().st_mtime < 6 * 3600:
        return json.loads(arq.read_text())
    out, fim = {}, None
    for _ in range(PLANO[iv]):
        u = URL.format(s=moeda, i=iv) + (f"&endTime={fim}" if fim else "")
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)).get("data") or []
        if not d:
            break
        for x in d:
            out[int(x["time"]) // 1000] = [int(x["time"]) // 1000, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]), float(x["volume"])]
        fim = min(int(x["time"]) for x in d) - 1
        time.sleep(0.15)
    v = [out[t] for t in sorted(out)][:-1]                   # sem a vela em formação
    arq.write_text(json.dumps(v))
    return v


def resumo(xs):
    n = len(xs)
    if n < 2:
        return {"n": n}
    m = sum(xs) / n
    dp = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return {"n": n, "media_pct": round(m * 100, 4), "t": round(m / (dp / math.sqrt(n)), 2) if dp else 0.0}


def main():
    r = json.loads(RADAR.read_text())
    moedas = sorted({x["moeda"][:-4] for x in (r.get("entradas") or []) + (r.get("descartes") or [])})
    grupos = defaultdict(list)                                # chave → [(t, liq, r)]
    for iv in PLANO:
        for m in moedas:
            try:
                v = velas(m, iv)
            except Exception as ex:
                print(f"{m} {iv}: sem velas ({ex})", flush=True)
                continue
            for s in P.sinais(v):
                res = P.simular(v, s)
                if res:
                    grupos[(s["padrao"], s["lado"], s["contexto"], iv)].append((s["t"], res["liq"], res["r"]))
        print(f"{iv}: {len(moedas)} moedas lidas", flush=True)
    tabela = []
    for (pad, lado, ctx, iv), xs in grupos.items():
        xs.sort()
        meio = xs[len(xs) // 2][0] if xs else 0
        liq = [x[1] for x in xs]
        a, b = [x[1] for x in xs if x[0] < meio], [x[1] for x in xs if x[0] >= meio]
        s_ = resumo(liq)
        ganhas = sum(1 for x in liq if x > 0)
        linha = {"padrao": pad, "lado": lado, "contexto": ctx, "tempo": iv, **s_, "acerto_pct": round(100 * ganhas / max(1, len(liq)), 1),
                 "r_medio": round(sum(x[2] for x in xs) / max(1, len(xs)), 3),
                 "metade1_pct": resumo(a).get("media_pct"), "metade2_pct": resumo(b).get("media_pct")}
        linha["funciona"] = bool(s_.get("n", 0) >= 80 and s_.get("media_pct", -1) > 0 and s_.get("t", 0) >= 2
                                 and (linha["metade1_pct"] or -1) > 0 and (linha["metade2_pct"] or -1) > 0)
        tabela.append(linha)
    tabela.sort(key=lambda x: (-x["funciona"], -(x.get("t") or -99)))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"t": time.time(), "moedas": moedas, "criterio": "n>=80, media>0, t>=2, as duas metades >0; custo 0,12%",
                                 "tabela": tabela}, ensure_ascii=False, indent=1))
    print(f"{'padrão':16s} {'lado':6s} {'contexto':8s} {'tf':3s} {'n':>5s} {'média%':>8s} {'t':>6s} {'acerto':>6s} {'R':>6s} {'met1':>7s} {'met2':>7s}")
    for x in tabela:
        print(f"{x['padrao']:16s} {x['lado']:6s} {x['contexto']:8s} {x['tempo']:3s} {x.get('n', 0):5d} {x.get('media_pct', 0):+8.3f} {x.get('t', 0):+6.2f} "
              f"{x['acerto_pct']:6.1f} {x['r_medio']:+6.2f} {x['metade1_pct'] or 0:+7.3f} {x['metade2_pct'] or 0:+7.3f} {'FUNCIONA' if x['funciona'] else ''}")


if __name__ == "__main__":
    main()
