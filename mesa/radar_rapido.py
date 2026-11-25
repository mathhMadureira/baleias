"""Radar rápido da equipe (25/11, dono: "a equipe operando sem pausa"): lê a BingX inteira em segundos e devolve as melhores entradas A MERCADO.

1 chamada pega o ticker de todos os perpétuos; as TOP moedas por liquidez ganham velas de 5 min (em paralelo). Para cada uma:
  var 15 min, 1 h e 4 h · acima/abaixo da EMA20 de 5 min · volume da última vela ÷ média · amplitude média da vela de 5 min.
Pontuação (momento confirmado, sem perseguir esticada):
  lado = sinal do movimento de 1 h; exige 15 min e EMA20 do mesmo lado; |1 h| entre 0,4% e 4% (acima = "esticada");
  nota = |1 h| × (1 + mín(vol_rel, 3)/3) × (1,3 se 4 h a favor).
Stop = máx(0,6%, 3 × amplitude média de 5 min), até 2,5%; alvo = 2 × stop; prazo 45 min (scalper) ou 240 min (4 h a favor e |4 h| > 2%).
Grava a tabela também em Shared/baleias/equipe/radar.json para o operador e o painel. Só leitura de dados públicos; nenhuma ordem.
Uso: python3 -I radar_rapido.py [n=8]
"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://open-api-vst.bingx.com/openApi/swap"
SAIDA = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/equipe/radar.json")
MEMES = {"DOGE", "1000PEPE", "PEPE", "WIF", "BONK", "1000BONK", "SHIB", "1000SHIB", "FLOKI", "1000FLOKI", "PENGU", "TRUMP", "PNUT", "NEIRO",
         "POPCAT", "MOODENG", "SPX", "FARTCOIN", "BOME", "MEME", "MEW", "BRETT", "GOAT", "TURBO", "PUMP", "1000SATS", "MUBARAK", "BROCCOLI714"}
FORA = {"XAUT", "PAXG", "USDC", "FDUSD", "TUSD", "USDE", "DAI"}        # ouro e moedas estáveis: não são cripto que anda
LIQ_MIN = 5_000_000            # US$ de volume em 24 h
TOP = 45


def _get(url, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "baleias/1.0"}), timeout=timeout) as r:
        return json.load(r)["data"]


def velas(sym):
    try:
        k = _get(f"{BASE}/v3/quote/klines?symbol={sym}&interval=5m&limit=50")
        return sym, sorted(k, key=lambda x: x["time"])
    except Exception:
        return sym, None


def ema(xs, n=20):
    k, e = 2 / (n + 1), xs[0]
    for x in xs[1:]:
        e = x * k + e * (1 - k)
    return e


def avaliar(t, k):
    c = [float(x["close"]) for x in k]
    h = [float(x["high"]) for x in k]
    l = [float(x["low"]) for x in k]
    v = [float(x["volume"]) for x in k]
    if len(c) < 49 or c[-1] <= 0:
        return None
    px = c[-1]
    v15, v1h, v4h = (px / c[-4] - 1) * 100, (px / c[-13] - 1) * 100, (px / c[-49] - 1) * 100
    amp = sum((h[i] - l[i]) / c[i] for i in range(-12, 0)) / 12 * 100
    vol_rel = v[-2] / (sum(v[-22:-2]) / 20) if sum(v[-22:-2]) > 0 else 0    # última vela FECHADA
    acima = px > ema(c[-40:])
    lado = "compra" if v1h > 0 else "venda"
    s = 1 if lado == "compra" else -1
    motivo = None
    if abs(v1h) < 0.4:
        motivo = "parada"
    elif abs(v1h) > 4:
        motivo = "esticada"
    elif v15 * s < 0 or acima != (s > 0):
        motivo = "contra no 15 min"
    nota = abs(v1h) * (1 + min(vol_rel, 3) / 3) * (1.3 if v4h * s > 0 else 1.0)
    stop = round(min(2.5, max(0.6, 3 * amp)), 2)
    posicao = v4h * s > 2
    base = t["symbol"].replace("-USDT", "")
    return {"moeda": base + "USDT", "meme": base in MEMES, "lado": lado, "preco": px, "v15": round(v15, 2), "v1h": round(v1h, 2),
            "v4h": round(v4h, 2), "vol_rel": round(vol_rel, 2), "acima_ema20_5m": acima, "liq_24h": float(t["quoteVolume"]),
            "stop_pct": stop, "alvo_pct": round(2 * stop, 2), "max_min": 240 if posicao else 45, "estilo": "posição" if posicao else "scalper",
            "nota": round(nota, 2), "descarte": motivo}


def radar(n=8):
    t0 = time.time()
    tk = [t for t in _get(f"{BASE}/v2/quote/ticker") if t["symbol"].endswith("-USDT") and float(t.get("quoteVolume") or 0) >= LIQ_MIN
          and not t["symbol"].startswith("NC") and t["symbol"].split("-")[0] not in FORA]
    tk.sort(key=lambda t: -float(t["quoteVolume"]) * (1 + abs(float(t.get("priceChangePercent") or 0)) / 10))
    tk = tk[:TOP]
    por = {t["symbol"]: t for t in tk}
    with ThreadPoolExecutor(12) as ex:
        res = [avaliar(por[s], k) for s, k in ex.map(velas, por) if k]
    res = [r for r in res if r]
    boas = sorted((r for r in res if not r["descarte"]), key=lambda r: -r["nota"])[:n]
    fora = sorted((r for r in res if r["descarte"] in ("esticada", "contra no 15 min")), key=lambda r: -abs(r["v1h"]))[:6]
    out = {"t": time.time(), "segundos": round(time.time() - t0, 1), "lidas": len(res), "entradas": boas, "descartes": fora}
    try:
        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        SAIDA.write_text(json.dumps(out, ensure_ascii=False))
    except OSError:
        pass
    return out


def tabela(out):
    linhas = [f"RADAR {time.strftime('%H:%M:%S', time.gmtime(out['t']))} UTC · {out['lidas']} moedas líquidas lidas em {out['segundos']} s",
              "| # | moeda | meme | estilo | lado | preço | 15m | 1h | 4h | vol rel | stop_pct | alvo_pct | max_min | nota |", "|" + "---|" * 14]
    for i, r in enumerate(out["entradas"], 1):
        linhas.append(f"| {i} | {r['moeda']} | {'✓' if r['meme'] else ''} | {r['estilo']} | {r['lado']} | {r['preco']:.6g} | {r['v15']:+.2f}% | "
                      f"{r['v1h']:+.2f}% | {r['v4h']:+.2f}% | {r['vol_rel']:.1f}x | {r['stop_pct']} | {r['alvo_pct']} | {r['max_min']} | {r['nota']} |")
    linhas.append("DESCARTES: " + ("; ".join(f"{r['moeda']} ({r['descarte']}, 1h {r['v1h']:+.2f}%)" for r in out["descartes"]) or "nenhum"))
    return "\n".join(linhas)


if __name__ == "__main__":
    print(tabela(radar(int(sys.argv[1]) if len(sys.argv) > 1 else 8)))
