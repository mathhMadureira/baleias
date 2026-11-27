"""Leitor de estrutura e padrões, SEM IA (27/11). A cada 2 min (timer baleias-padroes) lê velas de 15 min e 1 h das moedas do radar
e das abertas na BingX (dado público) e grava equipe/padroes.json com, por moeda:
  estrutura (15 min): resistência/suporte mais próximos, quanto o movimento já andou, posição no range
  linhas: LTA/LTB atuais (15 min e 1 h)
  sinais na última vela fechada (15 min e 1 h), cada um com o resultado MEDIDO na H85 (n, média líquida, t)
O Operador e o Radar leem isto no `ordem_bingx.py ver`; a ordem avisa quando a entrada repete o erro da BOME (resistência, movimento passado)."""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import padroes as P  # noqa: E402

EQUIPE = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/equipe")
H85 = Path("/home/servidor-de-producao/baleias/dados/lab/h85_padroes.json")
URL = "https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={s}-USDT&interval={i}&limit=300"


def velas(moeda, iv):
    d = json.load(urllib.request.urlopen(urllib.request.Request(URL.format(s=moeda, i=iv), headers={"User-Agent": "Mozilla/5.0"}), timeout=15)).get("data") or []
    v = sorted([[int(x["time"]) // 1000, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]), float(x["volume"])] for x in d])
    return v[:-1]                                            # só velas fechadas


def medido():
    try:
        t = json.loads(H85.read_text())["tabela"]
    except (OSError, ValueError, KeyError):
        return {}
    return {(x["padrao"], x["lado"], x["contexto"], x["tempo"]): {k: x.get(k) for k in ("n", "media_pct", "t", "acerto_pct", "funciona")} for x in t}


def ler(moeda, med):
    out = {"moeda": moeda + "USDT"}
    for iv in ("15m", "1h"):
        try:
            v = velas(moeda, iv)
        except Exception as ex:
            out[f"erro_{iv}"] = str(ex)[:80]
            continue
        if iv == "15m":
            out["estrutura"] = P.estrutura(v)
        out[f"linhas_{iv}"] = P.linhas_agora(v)
        out[f"sinais_{iv}"] = [{**{k: s[k] for k in ("padrao", "lado", "gatilho", "stop", "contexto", "nota")},
                               "medido": med.get((s["padrao"], s["lado"], s["contexto"], iv))} for s in P.sinais(v, so_ultima=True)]
    return out


def main():
    r = json.loads((EQUIPE / "radar.json").read_text())
    moedas = {x["moeda"][:-4] for x in (r.get("entradas") or []) + (r.get("descartes") or [])}
    try:
        conta = json.loads((AQUI / "operar" / "corretoras" / "laboratorio.json").read_text())
    except (OSError, ValueError):
        conta = {}
    if not (AQUI / "operar" / "corretoras").exists():
        try:
            conta = json.loads(Path("/home/servidor-de-producao/OpenBot/Shared/baleias/operar/corretoras/laboratorio.json").read_text())
        except (OSError, ValueError):
            conta = {}
    moedas |= {m[:-4] for m in (conta.get("abertas") or {})}
    moedas.add("BTC")
    med = medido()
    with ThreadPoolExecutor(8) as ex:
        lidas = list(ex.map(lambda m: ler(m, med), sorted(moedas)))
    tmp = EQUIPE / "padroes.tmp"
    tmp.write_text(json.dumps({"t": time.time(), "moedas": {x["moeda"]: x for x in lidas}}, ensure_ascii=False))
    tmp.replace(EQUIPE / "padroes.json")
    print(f"{len(lidas)} moedas lidas")


if __name__ == "__main__":
    main()
