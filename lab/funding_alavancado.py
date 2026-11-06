"""Hipótese 3b: funding com alavancagem (lab/PROTOCOLO_LAB.md). Usa o histórico de funding e as velas de 1 h da Hyperliquid."""
import json
import statistics as st
import time
import urllib.error
import urllib.request

from baleias import config
from . import funding as F

NIVEIS = (1, 2, 3, 5, 10)
MANUTENCAO = 0.0125
CUSTO_REEQUILIBRIO = 0.0007
CACHE = config.RAIZ / "lab"


def _post(corpo):
    for tentativa in range(8):
        req = urllib.request.Request(F.API, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(15 * (tentativa + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(20 * (tentativa + 1))
    raise RuntimeError("Hyperliquid indisponível")


def velas_1h(moeda, inicio_ms):
    saida, t = {}, inicio_ms
    fim = int(time.time() * 1000)
    while t < fim:
        lote = _post({"type": "candleSnapshot", "req": {"coin": moeda, "interval": "1h", "startTime": t, "endTime": fim}})
        if not lote:
            break
        for v in lote:
            saida[v["t"]] = (float(v["o"]), float(v["h"]), float(v["c"]))
        if len(lote) < 2:
            break
        t = lote[-1]["t"] + 3_600_000
        time.sleep(4)
    return saida


def dados(inicio_ms=1_683_000_000_000):
    """Cache em disco: buscar tudo de novo estoura a cota de pedidos."""
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / "funding_e_velas.json"
    if arq.exists():
        d = json.loads(arq.read_text())
        return {m: [tuple(x) for x in v] for m, v in d["funding"].items()}, {m: {int(k): tuple(v) for k, v in x.items()} for m, x in d["velas"].items()}
    funding, velas = {}, {}
    for m in F.MOEDAS:
        funding[m] = F.historico(m, inicio_ms, _post)
        velas[m] = velas_1h(m, inicio_ms)
        print(f"  {m}: {len(funding[m])} h de funding, {len(velas[m])} velas", flush=True)
    arq.write_text(json.dumps({"funding": funding, "velas": {m: {str(k): v for k, v in x.items()} for m, x in velas.items()}}))
    return funding, velas


def simular(funding, velas, L):
    """Resultado diário sobre o capital total, com liquidação e reequilíbrio pelo preço máximo de cada hora."""
    capital_por_exp = 1 + 1 / L
    dist_liq = 1 / L - MANUTENCAO          # alta do preço (relativa ao último reequilíbrio) que liquida o vendido
    gatilho = dist_liq / 2
    dia = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t / 1000))
    por_dia, eventos = {}, {"liquidacoes": 0, "reequilibrios": 0}
    for m, serie in funding.items():
        v = velas.get(m, {})
        dentro, taxas, ref = False, [], None
        for t, f in serie:
            d = dia(t)
            por_dia.setdefault(d, 0.0)
            hora = v.get(t - t % 3_600_000)
            if dentro and hora:
                o, h, c = hora
                if ref is None:
                    ref = o
                if dist_liq > 0 and h >= ref * (1 + dist_liq):
                    por_dia[d] -= F.PESO * (MANUTENCAO + F.CUSTO_IDA_VOLTA) / capital_por_exp
                    eventos["liquidacoes"] += 1
                    ref = c
                elif c >= ref * (1 + gatilho):
                    movido = (c / ref - 1)          # fração da exposição levada da perna à vista para a margem
                    por_dia[d] -= F.PESO * movido * CUSTO_REEQUILIBRIO / capital_por_exp
                    eventos["reequilibrios"] += 1
                    ref = c
            if dentro:
                por_dia[d] += F.PESO * f / capital_por_exp
            taxas.append(f)
            novo = F.decidir(taxas, dentro)
            if novo != dentro:
                por_dia[d] -= F.PESO * (F.CUSTO_IDA_VOLTA / 2) / capital_por_exp
                dentro = novo
                ref = hora[2] if hora else None
    return dict(sorted(por_dia.items())), eventos


if __name__ == "__main__":
    funding, velas = dados()
    print("\nAlavancagem do perpétuo | ao ano | dias positivos | maior queda | liquidações | reequilíbrios | média/dia")
    for L in NIVEIS:
        pd, ev = simular(funding, velas, L)
        r = F.resumo(pd)
        print(f"  {L:>2}x  {r['ao_ano']:+7.2%}  {r['dias_positivos']:5.0%}  {r['maior_queda']:+7.2%}  {ev['liquidacoes']:>4}  {ev['reequilibrios']:>5}  {r['media_dia'] * 100:+.4f}%")
        vals = list(pd.values())
        if L == 1:
            m, v = st.fmean(vals), st.pvariance(vals)
            print(f"      (referência: Kelly ~ média/variância diária = {m / v:,.0f}x — só vale se não houver eventos extremos fora do histórico)")
