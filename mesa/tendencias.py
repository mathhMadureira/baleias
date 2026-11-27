"""EM ALTA — o "analista de notícias e do X" das mesas do Grok Bot, com fontes públicas (H89, 27/11/2026).

Sem login no X pelo código. Junta três fontes e cruza com os perpétuos da BingX (onde a carteira opera):
  BingX       — maiores altas/baixas de 24 h com volume (quoteVolume) relevante
  CoinGecko   — moedas em tendência nas buscas (o "burburinho")
  DexScreener — tokens com mais impulso pago (boosts) e o volume de 24 h deles na DEX
Só INFORMAÇÃO para o Radar e o Operador: não abre ordem e não é regra.
Uso: python3 -I tendencias.py   (grava equipe/tendencias.json e imprime)
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

EQUIPE = Path(os.environ.get("BALEIAS_EQUIPE", "/home/servidor-de-producao/OpenBot/Shared/baleias/equipe"))
ARQ = EQUIPE / "tendencias.json"
VOL_MIN = 5e6          # US$ de volume em 24 h na BingX para entrar na lista de altas/baixas


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def montar(tickers, contratos, gecko, boosts, dex_info):
    """Funções puras (testáveis): recebe as respostas das APIs e devolve o feed."""
    perps = {c["symbol"].split("-")[0].upper() for c in contratos if str(c.get("status")) == "1" and c.get("symbol", "").endswith("-USDT")}
    out = {"bingx": [], "gecko": [], "dex": []}
    for t in tickers:
        s = t.get("symbol", "")
        if not s.endswith("-USDT") or (s.startswith("NC") and "2USD" in s):     # NCSK…2USD, NCCO…2USD = ações e metais tokenizados
            continue
        try:
            v, qv = float(t.get("priceChangePercent") or 0), float(t.get("quoteVolume") or 0)
        except ValueError:
            continue
        if qv >= VOL_MIN:
            out["bingx"].append({"moeda": s.split("-")[0], "v24h": round(v, 2), "vol_musd": round(qv / 1e6, 1)})
    out["bingx"].sort(key=lambda x: -abs(x["v24h"]))
    out["bingx"] = out["bingx"][:12]
    for c in (gecko.get("coins") or [])[:15]:
        it = c.get("item") or {}
        sym = str(it.get("symbol") or "").upper()
        d = (it.get("data") or {})
        v = (d.get("price_change_percentage_24h") or {}).get("usd")
        out["gecko"].append({"moeda": sym, "nome": it.get("name"), "rank": it.get("market_cap_rank"),
                             "v24h": round(v, 2) if isinstance(v, (int, float)) else None, "na_bingx": sym in perps})
    vistos = set()
    for b in boosts[:30]:
        info = dex_info.get(b.get("tokenAddress")) or {}
        sym = str(((info.get("baseToken") or {}).get("symbol")) or "").upper()
        if not sym or sym in vistos:
            continue
        vistos.add(sym)
        out["dex"].append({"moeda": sym, "rede": b.get("chainId"), "boost": b.get("totalAmount"),
                           "vol24h_kusd": round(float((info.get("volume") or {}).get("h24") or 0) / 1e3, 1),
                           "v24h": (info.get("priceChange") or {}).get("h24"), "mcap_kusd": round(float(info.get("marketCap") or 0) / 1e3, 1),
                           "na_bingx": sym in perps})
    out["dex"] = out["dex"][:12]
    out["acionaveis"] = sorted({x["moeda"] for x in out["gecko"] + out["dex"] if x.get("na_bingx")})
    return out


def coletar():
    erros, r = [], {}
    for k, u in (("tickers", "https://open-api.bingx.com/openApi/swap/v2/quote/ticker"),
                 ("contratos", "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"),
                 ("gecko", "https://api.coingecko.com/api/v3/search/trending"),
                 ("boosts", "https://api.dexscreener.com/token-boosts/top/v1")):
        try:
            j = _get(u)
            r[k] = j.get("data", j) if k in ("tickers", "contratos") else j
        except Exception as ex:
            erros.append(f"{k}: {type(ex).__name__}")
            r[k] = [] if k != "gecko" else {}
    dex_info = {}
    por_rede = {}
    for b in (r["boosts"] or [])[:30]:
        por_rede.setdefault(b.get("chainId"), []).append(b.get("tokenAddress"))
    for rede, ends in por_rede.items():
        try:
            for p in _get(f"https://api.dexscreener.com/tokens/v1/{rede}/{','.join(ends[:30])}"):
                a = (p.get("baseToken") or {}).get("address")
                if a and float((p.get("volume") or {}).get("h24") or 0) >= float((dex_info.get(a, {}).get("volume") or {}).get("h24") or 0):
                    dex_info[a] = p
        except Exception as ex:
            erros.append(f"dex {rede}: {type(ex).__name__}")
    f = montar(r["tickers"] or [], r["contratos"] or [], r["gecko"] or {}, r["boosts"] or [], dex_info)
    f["t"], f["erros"] = time.time(), erros
    EQUIPE.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(f, ensure_ascii=False))
    return f


def ler(max_idade=300):
    """Feed com no máximo max_idade s; recolhe se estiver velho (o ver chama isto)."""
    try:
        f = json.loads(ARQ.read_text())
        if time.time() - float(f.get("t") or 0) < max_idade:
            return f
    except (OSError, ValueError):
        pass
    return coletar()


def texto(f):
    ls = [f"EM ALTA (burburinho, fontes públicas; há {time.time() - float(f.get('t') or 0):.0f} s"
          + (f"; falhou: {', '.join(f['erros'])}" if f.get("erros") else "") + "). Informação, não regra:"]
    if f.get("bingx"):
        ls.append("  BingX 24 h (maiores movimentos com volume ≥ US$ 5 mi): "
                  + ", ".join(f"{x['moeda']} {x['v24h']:+.1f}% ({x['vol_musd']} mi)" for x in f["bingx"]))
    if f.get("gecko"):
        ls.append("  CoinGecko em tendência: " + ", ".join(
            f"{x['moeda']}{'*' if x['na_bingx'] else ''}" + (f" {x['v24h']:+.1f}%" if x.get("v24h") is not None else "") for x in f["gecko"]))
    if f.get("dex"):
        ls.append("  DexScreener com mais impulso: " + ", ".join(
            f"{x['moeda']}{'*' if x['na_bingx'] else ''} ({x['rede']}, vol {x['vol24h_kusd']} mil)" for x in f["dex"]))
    ls.append(f"  * = tem perpétuo na BingX. Acionáveis agora: {', '.join(f.get('acionaveis') or []) or 'nenhuma'}")
    return "\n".join(ls)


if __name__ == "__main__":
    print(texto(coletar()))
    sys.exit(0)
