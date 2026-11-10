"""H15 (força relativa entre moedas), H16 (sazonalidade hora/dia) e H17 (funding extremo contrário). Ver lab/PROTOCOLO_LAB.md."""
import json
import math
import statistics as st
import time

from baleias import config

from . import tartaruga as T

CUSTO_LADO = 0.001


def _t(xs):
    if len(xs) < 3:
        return 0.0
    dp = st.stdev(xs)
    return st.fmean(xs) / (dp / math.sqrt(len(xs))) if dp else 0.0


def _metricas(curva):
    dias = sorted(curva)
    v = [curva[d] for d in dias]
    anos = len(v) / 365
    pico, queda = v[0], 0.0
    for x in v:
        pico = max(pico, x)
        queda = min(queda, x / pico - 1)
    return {"ao_ano": (v[-1] / v[0]) ** (1 / anos) - 1 if anos else 0, "total": v[-1] / v[0] - 1, "maior_queda": queda}


# ---------------- H15 ----------------
def forca_relativa(dados, inicio, fim, top=5, olhar=28, a_cada=7, media_btc=100):
    fech = {m: {v[0]: v[4] for v in vs} for m, vs in dados.items()}
    btc = fech["BTCUSDT"]
    dias = sorted(d for d in btc if inicio <= d < fim)
    todos_btc = sorted(btc)
    pos_btc = {d: i for i, d in enumerate(todos_btc)}
    capital, pesos, curva, ultima = 1.0, {}, {}, None
    for k, d in enumerate(dias):
        # marca a mercado do dia (retorno de ontem para hoje das moedas em carteira)
        if k:
            ontem = dias[k - 1]
            r = sum(w * (fech[m].get(d, fech[m].get(ontem)) / fech[m][ontem] - 1) for m, w in pesos.items() if ontem in fech[m])
            capital *= 1 + r
        if ultima is None or k - ultima >= a_cada:
            i = pos_btc[d]
            regime_ok = i >= media_btc and btc[d] > st.fmean(btc[x] for x in todos_btc[i - media_btc:i])
            novos = {}
            if regime_ok:
                ranking = []
                for m, f in fech.items():
                    hist = [x for x in sorted(f) if x <= d]
                    if len(hist) < olhar + 2:
                        continue
                    ranking.append((f[hist[-2]] / f[hist[-olhar - 2]] - 1, m))   # pula o último dia
                novos = {m: 1 / top for _, m in sorted(ranking, reverse=True)[:top]}
            giro = sum(abs(novos.get(m, 0) - pesos.get(m, 0)) for m in set(novos) | set(pesos))
            capital *= 1 - giro * CUSTO_LADO
            pesos, ultima = novos, k
        curva[d] = capital
    return curva


def comprar_segurar_btc(dados, inicio, fim):
    btc = {v[0]: v[4] for v in dados["BTCUSDT"]}
    dias = sorted(d for d in btc if inicio <= d < fim)
    return {d: btc[d] / btc[dias[0]] for d in dias}


# ---------------- H16 ----------------
def sazonalidade(horas, corte):
    """horas: {moeda: [[ 'AAAA-MM-DD HH:MM', o, h, l, c ], ...]} em 1 h. Retorno médio por hora UTC e por dia da semana."""
    por = {"hora": {}, "dia": {}}
    for vs in horas.values():
        for a, b in zip(vs, vs[1:]):
            r = b[4] / a[4] - 1
            if abs(r) > 0.5:
                continue
            per = "treino" if b[0] < corte else "teste"
            hora = int(b[0][11:13])
            dia = time.strptime(b[0][:10], "%Y-%m-%d").tm_wday
            por["hora"].setdefault((hora, per), []).append(r)
            por["dia"].setdefault((dia, per), []).append(r)
    return por


# ---------------- H17 ----------------
def funding_contrario(funding, diarios, corte="2025-01-01", horizonte=3, quantil=0.10):
    resultados = {"treino": [], "teste": []}
    for moeda, serie in funding.items():
        par = moeda + "USDT"
        if par not in diarios:
            continue
        fech = {v[0]: v[4] for v in diarios[par]}
        dias = sorted(fech)
        media_dia = {}
        for t, f in serie:
            media_dia.setdefault(time.strftime("%Y-%m-%d", time.gmtime(t / 1000)), []).append(f)
        media_dia = {d: st.fmean(x) for d, x in media_dia.items() if len(x) >= 12}
        treino = sorted(v for d, v in media_dia.items() if d < corte)
        if len(treino) < 50:
            continue
        limite = treino[int(len(treino) * quantil)]
        livre = ""
        for d in sorted(media_dia):
            if d < livre or media_dia[d] > limite or d not in fech:
                continue
            i = dias.index(d)
            if i + horizonte >= len(dias):
                continue
            r = fech[dias[i + horizonte]] / fech[d] - 1 - 2 * CUSTO_LADO
            resultados["treino" if d < corte else "teste"].append((moeda, d, r))
            livre = dias[i + horizonte]
    return resultados


if __name__ == "__main__":
    hoje = time.strftime("%Y-%m-%d")
    dados = T.baixar(T.MOEDAS_ROBO, T.CACHE_ROBO)
    print("== H15 força relativa (top 5 de 28 dias, a cada 7 dias, filtro BTC > média de 100 dias)")
    grupo3 = json.load(open(config.RAIZ / "lab" / "cripto_grupo3.json"))
    grupo3["BTCUSDT"] = dados["BTCUSDT"]
    for nome, d, a, b in (("33 moedas treino 2018-23", dados, "2018-01-01", "2024-01-01"), ("33 moedas teste 2024-hoje", dados, "2024-01-01", hoje),
                          ("grupo 3 2024-hoje", grupo3, "2024-01-01", hoje)):
        fr, bh = _metricas(forca_relativa(d, a, b)), _metricas(comprar_segurar_btc(d, a, b))
        print(f"  {nome:26}: força relativa {fr['ao_ano']:+6.1%}/ano, queda {fr['maior_queda']:6.1%} | BTC parado {bh['ao_ano']:+6.1%}/ano, queda {bh['maior_queda']:6.1%}")
    print("\n== H16 sazonalidade (velas de 1 h das 33 moedas; treino 2024, teste 2025-hoje)")
    from .tartaruga_intradia import baixar as baixar_intradia
    horas = baixar_intradia("1h")
    s = sazonalidade(horas, "2025-01-01")
    nomes_dia = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    for tipo, chaves, rot in (("hora", range(24), lambda k: f"{k:02d}h UTC"), ("dia", range(7), lambda k: nomes_dia[k])):
        for k in chaves:
            a, b = s[tipo].get((k, "treino"), []), s[tipo].get((k, "teste"), [])
            ta, tb = _t(a), _t(b)
            marca = "  ← candidato" if ta * tb > 0 and abs(ta) > 3 and abs(tb) > 2 else ""
            print(f"  {rot(k):8} treino {st.fmean(a) * 100:+.4f}% (t {ta:+.1f}) | teste {st.fmean(b) * 100:+.4f}% (t {tb:+.1f}){marca}")
    print("\n== H17 funding extremo negativo → compra por 3 dias (líquido de 0,2%)")
    fund = json.load(open(config.RAIZ / "lab" / "funding_e_velas.json"))["funding"]
    r = funding_contrario(fund, dados)
    for per, xs in r.items():
        rs = [x[2] for x in xs]
        if rs:
            print(f"  {per}: {len(rs)} sinais | média {st.fmean(rs) * 100:+.2f}% | t {_t(rs):+.2f} | acerto {sum(x > 0 for x in rs) / len(rs):.0%}")
