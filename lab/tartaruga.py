"""Hipótese 10: Tartarugas (Sistema 2) em cripto diário — perder pouco (stop 2N) e ganhar muito (saída só no canal de 20 dias)."""
import json
import math
import os
import statistics as st
import time
import urllib.request

from baleias import config

MOEDAS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "SOLUSDT"]
CACHE = config.RAIZ / "lab" / "cripto_ohlc_diario.json"
# Dados públicos: em nuvem dos EUA a api.binance.com bloqueia; data-api.binance.vision serve os mesmos dados de mercado.
DADOS = os.environ.get("BINANCE_DADOS", "https://api.binance.com")
# H10c: as mesmas regras confirmadas em 23 moedas que nunca tinham sido testadas (2026-11-07); o robô opera as 33.
MOEDAS_ROBO = MOEDAS + ["AAVEUSDT", "ARBUSDT", "AVAXUSDT", "BCHUSDT", "CELOUSDT", "CYBERUSDT", "ENAUSDT", "FETUSDT", "GTCUSDT",
                        "HBARUSDT", "INJUSDT", "LSKUSDT", "NEARUSDT", "NFPUSDT", "ONEUSDT", "PEPEUSDT", "QNTUSDT", "SUIUSDT",
                        "TAOUSDT", "UNIUSDT", "WLDUSDT", "XLMUSDT", "ZECUSDT"]
CACHE_ROBO = config.RAIZ / "lab" / "cripto_ohlc_robo.json"      # histórico completo (curva do teste)
CACHE_VIVO = config.RAIZ / "lab" / "cripto_ohlc_vivo.json"      # últimos 320 dias (decisão diária e gráfico)
DIAS_VIVO = 320
ENTRADA, SAIDA, N_DIAS = 55, 20, 20
STOP_N = 2.0
RISCO = 0.01
ALAV_MAX = 3.0
CUSTO_LADO = 0.001
CUSTO_DIA = 0.0002
INICIO_TREINO, INICIO_TESTE = "2018-01-01", "2024-01-01"


def baixar(moedas=None, cache=None, dias=None):
    """`dias`: só os últimos N dias (a decisão diária precisa de ~80; baixar desde 2017 leva ~24 s por moeda)."""
    moedas, cache = moedas or MOEDAS, cache or CACHE
    if cache.exists():
        return json.loads(cache.read_text())
    saida = {}
    for m in moedas:
        velas, t = [], (int(time.time() * 1000) - dias * 86_400_000) if dias else 1_500_000_000_000
        while True:
            with urllib.request.urlopen(f"{DADOS}/api/v3/klines?symbol={m}&interval=1d&startTime={t}&limit=1000", timeout=30) as r:
                lote = json.load(r)
            if not lote:
                break
            velas += [[time.strftime("%Y-%m-%d", time.gmtime(x[0] / 1000)), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in lote]
            if len(lote) < 1000:
                break
            t = lote[-1][0] + 86_400_000
            time.sleep(0.2)
        saida[m] = velas[:-1]          # o dia de hoje ainda está aberto
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(saida))
    return saida


def atr(velas, n=N_DIAS):
    """ATR de Wilder; posição i usa só velas até i."""
    saida, a = [None] * len(velas), None
    for i in range(1, len(velas)):
        _, _, h, l, _ = velas[i]
        c0 = velas[i - 1][4]
        tr = max(h - l, abs(h - c0), abs(l - c0))
        a = tr if a is None else (a * (n - 1) + tr) / n
        if i >= n:
            saida[i] = a
    return saida


def sinais(velas, i, lado):
    """Sinal no fechamento do dia i (sem olhar o futuro)."""
    if i < ENTRADA:
        return None
    c = velas[i][4]
    if lado == "compra":
        return c > max(v[2] for v in velas[i - ENTRADA:i])
    return c < min(v[3] for v in velas[i - ENTRADA:i])


def saida_canal(velas, i, lado):
    c = velas[i][4]
    if lado == "compra":
        return c < min(v[3] for v in velas[i - SAIDA:i])
    return c > max(v[2] for v in velas[i - SAIDA:i])


def simular(dados, inicio, fim, lados=("compra", "venda"), alav_max=ALAV_MAX, alvo_vol=None, stop_min=0.0):
    """`stop_min` (H12): só entra se 2N/preço ≥ stop_min — o custo fixo de ida e volta vira uma fração pequena do risco."""
    """Carteira diária. Devolve (curva por dia, lista de operações com resultado em R e em % do capital)."""
    dias = sorted({v[0] for vs in dados.values() for v in vs if inicio <= v[0] < fim})
    idx = {m: {v[0]: k for k, v in enumerate(vs)} for m, vs in dados.items()}
    atrs = {m: atr(vs) for m, vs in dados.items()}
    capital, abertas, ops, curva = 1.0, {}, [], {}
    var_ewma, anterior = None, None      # H11: volatilidade da própria carteira (EWMA λ=0,94)
    pendentes = []                      # ordens decididas no fechamento, executadas na abertura seguinte
    for d in dias:
        # 1) executa ordens pendentes na abertura
        for tipo, m, lado in pendentes:
            k = idx[m].get(d)
            if k is None:
                continue
            aberto = dados[m][k][1]
            if tipo == "sai" and m in abertas:
                p = abertas.pop(m)
                ops.append(_fechar(p, aberto, d))
                capital += ops[-1]["resultado"]
            elif tipo == "entra" and m not in abertas:
                n = atrs[m][k - 1]
                if not n or STOP_N * n / aberto < stop_min:
                    continue
                escala = 1.0
                if alvo_vol and var_ewma:
                    escala = min(1.0, alvo_vol / math.sqrt(var_ewma * 365))
                nocional = RISCO * escala * capital / (STOP_N * n) * aberto
                exposto = sum(p["nocional"] for p in abertas.values())
                nocional = min(nocional, max(0.0, alav_max * capital - exposto))
                if nocional <= 0:
                    continue
                stop = aberto - STOP_N * n if lado == "compra" else aberto + STOP_N * n
                capital -= nocional * CUSTO_LADO
                abertas[m] = {"moeda": m, "lado": lado, "entrada": aberto, "stop": stop, "nocional": nocional, "dia": d,
                              "risco": nocional * STOP_N * n / aberto, "custos": nocional * CUSTO_LADO}
        pendentes = []
        # 2) stops durante o dia e marcação a mercado no fechamento
        for m in list(abertas):
            k = idx[m].get(d)
            if k is None:
                continue
            _, o, h, l, c = dados[m][k]
            p = abertas[m]
            furou = l <= p["stop"] if p["lado"] == "compra" else h >= p["stop"]
            if furou:
                px = min(o, p["stop"]) if p["lado"] == "compra" else max(o, p["stop"])
                abertas.pop(m)
                ops.append(_fechar(p, px, d))
                capital += ops[-1]["resultado"]
                continue
            custo_dia = p["nocional"] * CUSTO_DIA
            p["custos"] += custo_dia
            capital -= custo_dia
            if saida_canal(dados[m], k, p["lado"]):
                pendentes.append(("sai", m, p["lado"]))
        # 3) novas entradas decididas no fechamento
        for m, vs in dados.items():
            k = idx[m].get(d)
            if k is None or m in abertas:
                continue
            for lado in lados:
                if sinais(vs, k, lado):
                    pendentes.append(("entra", m, lado))
                    break
        aberto_mtm = 0.0
        for m, p in abertas.items():
            k = idx[m].get(d)
            if k is not None:
                c = dados[m][k][4]
                aberto_mtm += p["nocional"] * ((c / p["entrada"] - 1) if p["lado"] == "compra" else (1 - c / p["entrada"]))
        curva[d] = capital + aberto_mtm
        if anterior:
            r = curva[d] / anterior - 1
            var_ewma = r * r if var_ewma is None else 0.94 * var_ewma + 0.06 * r * r
        anterior = curva[d]
    return curva, ops


def _fechar(p, px, d):
    bruto = p["nocional"] * ((px / p["entrada"] - 1) if p["lado"] == "compra" else (1 - px / p["entrada"]))
    custo_saida = p["nocional"] * CUSTO_LADO
    resultado = bruto - custo_saida            # custos de entrada e diários já saíram do capital
    liquido = resultado - p["custos"]
    return {"moeda": p["moeda"], "lado": p["lado"], "entrada_dia": p["dia"], "saida_dia": d, "entrada": p["entrada"], "saida": px,
            "resultado": resultado, "R": liquido / p["risco"] if p["risco"] else 0.0}


def metricas(curva, ops):
    dias = sorted(curva)
    if len(dias) < 2:
        return {}
    v = [curva[d] for d in dias]
    anos = len(dias) / 365
    pico, queda = v[0], 0.0
    for x in v:
        pico = max(pico, x)
        queda = min(queda, x / pico - 1)
    meses = {}
    for d in dias:
        meses[d[:7]] = curva[d]
    mv = list(meses.values())
    ret_mes = [mv[k] / mv[k - 1] - 1 for k in range(1, len(mv))]
    rs = [o["R"] for o in ops]
    ganhos, perdas = [r for r in rs if r > 0], [r for r in rs if r <= 0]
    return {"operacoes": len(ops), "ao_ano": (v[-1] / v[0]) ** (1 / anos) - 1 if anos > 0 else 0, "total": v[-1] / v[0] - 1,
            "maior_queda": queda, "acerto": len(ganhos) / len(rs) if rs else 0, "ganho_medio_R": st.fmean(ganhos) if ganhos else 0,
            "perda_media_R": st.fmean(perdas) if perdas else 0, "expectativa_R": st.fmean(rs) if rs else 0,
            "profit_factor": sum(ganhos) / -sum(perdas) if perdas and sum(perdas) else float("inf"),
            "maior_ganho_R": max(rs) if rs else 0, "meses_positivos": sum(r > 0 for r in ret_mes) / len(ret_mes) if ret_mes else 0,
            "pior_mes": min(ret_mes) if ret_mes else 0, "melhor_mes": max(ret_mes) if ret_mes else 0}


def passou(treino, teste):
    return (teste.get("expectativa_R", 0) > 0.2 and teste.get("profit_factor", 0) > 1.3 and teste.get("operacoes", 0) >= 30
            and teste.get("maior_queda", -1) > -0.35 and treino.get("expectativa_R", 0) > 0)


if __name__ == "__main__":
    dados = baixar()
    hoje = time.strftime("%Y-%m-%d")
    linhas = {}
    for nome, lados in (("compra e venda", ("compra", "venda")), ("só compra", ("compra",))):
        tr = metricas(*simular(dados, INICIO_TREINO, INICIO_TESTE, lados))
        te = metricas(*simular(dados, INICIO_TESTE, hoje, lados))
        linhas[nome] = {"treino": tr, "teste": te, "passou": passou(tr, te)}
        for periodo, m in (("treino 2018-23", tr), ("teste 2024-hoje", te)):
            print(f"[{nome}] {periodo}: {m['operacoes']} op. | {m['ao_ano']:+.1%}/ano | queda máx {m['maior_queda']:.1%} | acerto {m['acerto']:.0%} | "
                  f"ganho médio {m['ganho_medio_R']:+.2f}R, perda média {m['perda_media_R']:+.2f}R, maior ganho {m['maior_ganho_R']:+.1f}R | "
                  f"expectativa {m['expectativa_R']:+.2f}R | PF {m['profit_factor']:.2f} | meses + {m['meses_positivos']:.0%} | pior mês {m['pior_mes']:+.1%}")
        print(f"[{nome}] {'PASSOU' if linhas[nome]['passou'] else 'não passou'}\n")
    (config.RAIZ / "lab" / "tartaruga_resultado.json").write_text(json.dumps(linhas, indent=1))
