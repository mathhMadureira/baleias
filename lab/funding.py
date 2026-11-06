"""Hipótese 3: carregar funding na Hyperliquid (lab/PROTOCOLO_LAB.md). Backtest no histórico e acompanhamento ao vivo."""
import json
import statistics as st
import sys
import time
import urllib.request

API = "https://api.hyperliquid.xyz/info"
MOEDAS = ("BTC", "ETH", "HYPE", "SOL")
CUSTO_IDA_VOLTA = 2 * (0.00070 + 0.00045)
JANELA_H = 72
RECUPERAR_H = 14 * 24
PESO = 1 / len(MOEDAS)
CAPITAL_POR_EXPOSICAO = 2.0


def historico(moeda, inicio_ms, post=None):
    """[(t_ms, taxa por hora)] desde inicio_ms, em ordem."""
    def _post(corpo):
        req = urllib.request.Request(API, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    post = post or _post
    saida, t = [], inicio_ms
    while True:
        lote = post({"type": "fundingHistory", "coin": moeda, "startTime": t})
        if not lote:
            break
        saida += [(x["time"], float(x["fundingRate"])) for x in lote]
        if len(lote) < 500:
            break
        t = lote[-1]["time"] + 1
        time.sleep(0.3)
    return saida


def decidir(janela, dentro):
    """Regra pura: True = ficar com a posição na próxima hora."""
    if len(janela) < JANELA_H:
        return False
    media = st.fmean(janela[-JANELA_H:])
    if dentro:
        return media >= 0
    return media > 0 and media * RECUPERAR_H > CUSTO_IDA_VOLTA


def simular(series):
    """series: {moeda: [(t_ms, taxa)]}. Devolve {dia UTC: resultado sobre o capital} (funding recebido − custos)."""
    dia = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t / 1000))
    por_dia = {}
    for moeda, s in series.items():
        dentro, taxas = False, []
        for t, f in s:
            d = dia(t)
            por_dia.setdefault(d, 0.0)
            if dentro:  # quem está vendido recebe f (ou paga, se f < 0) sobre a exposição
                por_dia[d] += PESO * f / CAPITAL_POR_EXPOSICAO
            taxas.append(f)
            novo = decidir(taxas, dentro)
            if novo != dentro:
                por_dia[d] -= PESO * (CUSTO_IDA_VOLTA / 2) / CAPITAL_POR_EXPOSICAO
                dentro = novo
    return dict(sorted(por_dia.items()))


def resumo(por_dia):
    vals = list(por_dia.values())
    if not vals:
        return None
    capital, pico, queda = 1.0, 1.0, 0.0
    for v in vals:
        capital *= 1 + v
        pico = max(pico, capital)
        queda = min(queda, capital / pico - 1)
    anos = len(vals) / 365
    return {"dias": len(vals), "acumulado": capital - 1, "ao_ano": capital ** (1 / anos) - 1 if anos > 0 else None,
            "dias_positivos": sum(v > 0 for v in vals) / len(vals), "dias_negativos": sum(v < 0 for v in vals) / len(vals),
            "maior_queda": queda, "media_dia": st.fmean(vals)}


if __name__ == "__main__":
    series = {}
    for m in MOEDAS:
        series[m] = historico(m, 1_683_000_000_000)
        print(f"{m}: {len(series[m])} horas, desde {time.strftime('%Y-%m-%d', time.gmtime(series[m][0][0] / 1000))}", flush=True)
    por_dia = simular(series)
    r = resumo(por_dia)
    print(f"\nCarteira (4 moedas, capital 2x a exposição): {r['dias']} dias")
    print(f"  acumulado {r['acumulado']:+.2%} | ao ano {r['ao_ano']:+.2%} | dias positivos {r['dias_positivos']:.0%} | dias negativos {r['dias_negativos']:.0%} | maior queda {r['maior_queda']:+.2%}")
    print(f"  média por dia {r['media_dia']*100:+.4f}% do capital  →  com US$ 10: US$ {r['media_dia']*10:+.5f} por dia")
    por_ano = {}
    for d, v in por_dia.items():
        por_ano.setdefault(d[:4], []).append(v)
    for a, vs in por_ano.items():
        cap = 1.0
        for v in vs:
            cap *= 1 + v
        print(f"  {a}: {cap - 1:+.2%} em {len(vs)} dias")
    for m in MOEDAS:
        s = simular({m: series[m]})
        rr = resumo({d: v / PESO for d, v in s.items()})
        print(f"  só {m:4s}: ao ano {rr['ao_ano']:+.2%} | dias positivos {rr['dias_positivos']:.0%} | maior queda {rr['maior_queda']:+.2%}")
