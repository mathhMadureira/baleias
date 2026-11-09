"""A mesma Tartaruga (55/20, stop 2N, 1% de risco) em velas de 4 h e 1 h, para operar todo dia. Mede no histórico 2024–hoje."""
import json
import time
import urllib.request

from baleias import config

from . import tartaruga as T

INTERVALOS = {"4h": 6, "1h": 24, "15m": 96}          # velas por dia


def baixar(intervalo, inicio_ms=1_704_067_200_000):
    arq = config.RAIZ / "lab" / f"cripto_{intervalo}.json"
    if arq.exists() and time.time() - arq.stat().st_mtime < 6 * 3600:
        return json.loads(arq.read_text())
    saida = {}
    for m in T.MOEDAS_ROBO:
        velas, t = [], inicio_ms
        while True:
            for tentativa in range(6):
                try:
                    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={m}&interval={intervalo}&startTime={t}&limit=1000", timeout=30) as r:
                        lote = json.load(r)
                    break
                except OSError:                    # conexão caída ou lenta: espera e tenta de novo
                    time.sleep(5 * (tentativa + 1))
            else:
                raise RuntimeError(f"Binance não respondeu ({m} {intervalo})")
            if not lote:
                break
            velas += [[time.strftime("%Y-%m-%d %H:%M", time.gmtime(x[0] / 1000)), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in lote]
            if len(lote) < 1000:
                break
            t = lote[-1][0] + 1
            time.sleep(0.1)
        saida[m] = velas[:-1]
    arq.write_text(json.dumps(saida))
    return saida


def medir(intervalo, inicio="2024-01-01", fim="2099"):
    dados = baixar(intervalo)
    custo_dia = T.CUSTO_DIA
    T.CUSTO_DIA = custo_dia / INTERVALOS[intervalo]     # financiamento por vela, não por dia
    try:
        curva, ops = T.simular(dados, inicio, fim, ("compra",), alav_max=1.0)
    finally:
        T.CUSTO_DIA = custo_dia
    rs = [o["R"] for o in ops]
    ganhos, perdas = [r for r in rs if r > 0], [r for r in rs if r <= 0]
    v = [curva[k] for k in sorted(curva)]
    pico, queda = v[0], 0.0
    for x in v:
        pico = max(pico, x)
        queda = min(queda, x / pico - 1)
    dias = len(v) / INTERVALOS[intervalo]
    return {"operacoes": len(rs), "por_dia": len(rs) / dias, "total": v[-1] - 1, "maior_queda": queda,
            "acerto": len(ganhos) / len(rs), "ganho_R": sum(ganhos) / len(ganhos), "perda_R": sum(perdas) / len(perdas),
            "expectativa_R": sum(rs) / len(rs), "pf": sum(ganhos) / -sum(perdas)}


if __name__ == "__main__":
    import sys
    for iv in sys.argv[1:] or ("4h", "1h", "15m"):
        for nome, a, b in (("2024", "2024-01-01", "2025-01-01"), ("2025-hoje", "2025-01-01", "2099")):
            m = medir(iv, a, b)
            print(f"{iv} {nome:9}: {m['operacoes']:4} op ({m['por_dia']:.1f}/dia) | total {m['total']:+.1%} | queda {m['maior_queda']:.1%} | acerto {m['acerto']:.0%} | "
                  f"ganho {m['ganho_R']:+.2f}R perda {m['perda_R']:+.2f}R | {m['expectativa_R']:+.2f}R/op | PF {m['pf']:.2f}", flush=True)
