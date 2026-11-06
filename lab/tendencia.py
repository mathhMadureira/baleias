"""Hipótese 1: seguir tendência (momentum de série temporal), conforme lab/PROTOCOLO_LAB.md."""
import json
import math
import statistics as st
import sys
import time
from pathlib import Path

from . import dados as D

COFRE = "2024-11-06"
REGISTRO_COFRE = Path(__file__).with_name("cofre_aberto.json")
CRIPTO = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "SOLUSDT"]
FUNDOS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "DBC", "VNQ"]
CUSTO = {"cripto": 0.0010, "fundos": 0.0005}
LS = (20, 60, 120, 250)
MODOS = ("comprado_fora", "comprado_vendido")
DIAS_ANO = {"cripto": 365, "fundos": 252}


def retornos_estrategia(serie, L, modo, custo):
    """{dia: retorno do dia} da estratégia num ativo. Posição decidida no fechamento de t vale para t→t+1."""
    dias = sorted(serie)
    saida, pos_ant = {}, 0
    for i in range(L, len(dias) - 1):
        hoje, amanha = dias[i], dias[i + 1]
        sinal = serie[hoje] / serie[dias[i - L]] - 1
        pos = 1 if sinal > 0 else (-1 if modo == "comprado_vendido" else 0)
        r = serie[amanha] / serie[hoje] - 1
        saida[amanha] = pos * r - abs(pos - pos_ant) * custo
        pos_ant = pos
    return saida


def retornos_comprar_segurar(serie, L):
    dias = sorted(serie)
    return {dias[i + 1]: serie[dias[i + 1]] / serie[dias[i]] - 1 for i in range(L, len(dias) - 1)}


def carteira(por_ativo, inicio, fim):
    """Peso igual entre os ativos com retorno no dia, dentro de [inicio, fim)."""
    dias = sorted({d for r in por_ativo.values() for d in r if inicio <= d < fim})
    return [st.fmean(r[d] for r in por_ativo.values() if d in r) for d in dias]


def metricas(ret, dias_ano):
    if len(ret) < 30:
        return None
    m, dp = st.fmean(ret), st.pstdev(ret)
    capital, pico, queda = 1.0, 1.0, 0.0
    for r in ret:
        capital *= 1 + r
        pico = max(pico, capital)
        queda = min(queda, capital / pico - 1)
    anos = len(ret) / dias_ano
    return {"dias": len(ret), "retorno_anual": capital ** (1 / anos) - 1, "vol_anual": dp * math.sqrt(dias_ano),
            "sharpe": (m / dp) * math.sqrt(dias_ano) if dp else 0.0, "sharpe_diario": m / dp if dp else 0.0,
            "maior_queda": queda, "assimetria": _momento(ret, 3), "curtose": _momento(ret, 4)}


def _momento(x, k):
    m, dp = st.fmean(x), st.pstdev(x)
    return st.fmean(((v - m) / dp) ** k for v in x) if dp else 0.0


def sharpe_deflacionado(sr, T, assimetria, curtose, sharpes_tentativas):
    """Probabilidade de o Sharpe (diário) ser real dado o número de tentativas (Bailey e López de Prado, 2014)."""
    N = len(sharpes_tentativas)
    if N < 2 or T < 3:
        return None
    nd, gama = st.NormalDist(), 0.5772156649
    var = st.pvariance(sharpes_tentativas)
    sr0 = math.sqrt(var) * ((1 - gama) * nd.inv_cdf(1 - 1 / N) + gama * nd.inv_cdf(1 - 1 / (N * math.e)))
    den = 1 - assimetria * sr + (curtose - 1) / 4 * sr * sr
    return nd.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(den, 1e-9)))


def avaliar(universos, inicio, fim):
    tabela = {}
    for nome, series in universos.items():
        for L in LS:
            for modo in MODOS:
                por = {a: retornos_estrategia(s, L, modo, CUSTO[nome]) for a, s in series.items() if len(s) > L + 60}
                tabela[(nome, L, modo)] = carteira(por, inicio, fim)
        base = {a: retornos_comprar_segurar(s, max(LS)) for a, s in series.items() if len(s) > max(LS) + 60}
        tabela[(nome, "comprar_e_segurar", "")] = carteira(base, inicio, fim)
    return tabela


def main(abrir_cofre=False):
    print("baixando/lendo dados…", flush=True)
    universos = {"cripto": D.carregar("cripto", CRIPTO, D.binance), "fundos": D.carregar("fundos", FUNDOS, D.yahoo)}
    dev = avaliar(universos, "2000-01-01", COFRE)
    print("\n== DESENVOLVIMENTO (até 2024-11-05) ==")
    m = {k: metricas(v, DIAS_ANO[k[0]]) for k, v in dev.items()}
    for k, x in sorted(m.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        if x:
            print(f"{k[0]:6s} L={str(k[1]):17s} {k[2]:16s} ret/ano {x['retorno_anual']:+7.1%}  vol {x['vol_anual']:6.1%}  Sharpe {x['sharpe']:+.2f}  maior queda {x['maior_queda']:+.0%}")
    medias = {(L, modo): st.fmean(m[(u, L, modo)]["sharpe"] for u in universos) for L in LS for modo in MODOS}
    L_esc, modo_esc = max(medias, key=medias.get)
    print(f"\nescolhida (maior Sharpe médio nos dois universos): L={L_esc}, {modo_esc}")
    passou_dsr = False
    for u in universos:
        trials = [m[(u, L, modo)]["sharpe_diario"] for L in LS for modo in MODOS]
        x = m[(u, L_esc, modo_esc)]
        dsr = sharpe_deflacionado(x["sharpe_diario"], x["dias"], x["assimetria"], x["curtose"], trials)
        print(f"Sharpe Deflacionado em {u}: {dsr:.3f} (precisa ≥ 0,95)")
        passou_dsr |= dsr is not None and dsr >= 0.95
    if not passou_dsr:
        print("\nRESULTADO: não passou no Sharpe Deflacionado. Pelo protocolo, a hipótese cai sem abrir o cofre.")
        return
    if not abrir_cofre:
        print("\nPassou no desenvolvimento. O cofre só abre com --abrir-cofre (uma única vez).")
        return
    if REGISTRO_COFRE.exists():
        raise SystemExit(f"cofre já foi aberto: {REGISTRO_COFRE.read_text()}")
    REGISTRO_COFRE.write_text(json.dumps({"aberto_em": time.strftime("%F %T"), "L": L_esc, "modo": modo_esc}))
    cofre = avaliar(universos, COFRE, "2100-01-01")
    print("\n== COFRE (de 2024-11-06 até hoje, avaliado uma única vez) ==")
    aprovado = True
    for u in universos:
        e, b = metricas(cofre[(u, L_esc, modo_esc)], DIAS_ANO[u]), metricas(cofre[(u, "comprar_e_segurar", "")], DIAS_ANO[u])
        ok = e["retorno_anual"] > 0 and e["sharpe"] > b["sharpe"] and e["maior_queda"] > b["maior_queda"]
        aprovado &= ok
        print(f"{u}: estratégia ret/ano {e['retorno_anual']:+.1%} Sharpe {e['sharpe']:+.2f} queda {e['maior_queda']:+.0%} | "
              f"comprar e segurar ret/ano {b['retorno_anual']:+.1%} Sharpe {b['sharpe']:+.2f} queda {b['maior_queda']:+.0%} → {'passa' if ok else 'falha'}")
    print("\nRESULTADO NO COFRE:", "APROVADA (vai para o simulado ao vivo)" if aprovado else "REPROVADA (descartada)")


if __name__ == "__main__":
    main("--abrir-cofre" in sys.argv)
