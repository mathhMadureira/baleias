"""Robô Minerador (H28) na nuvem do GitHub, a cada vela de 15 min, 24 h por dia (pedido do dono: não depender da máquina ligada).

Regra aprovada pelo minerador de oportunidades (H26): movimento forte (r1 na cauda de 10%) com volume muito baixo (vol96 nos 10%
menores) tende a reverter. Entra contra o movimento (compra depois de queda, vende depois de alta) e sai uma vela depois.
Perpétuo simulado: US$ 5 por posição, margem 5×, 0,05% por lado (como registrado na H28). Conta de US$ 10 na mesa.

Uso: BALEIAS_DADOS=... BINANCE_DADOS=https://data-api.binance.vision python -m executor.minerador_nuvem
"""
import json
import math
import statistics
import time
import urllib.request

from baleias import config
from lab import tartaruga as T
from lab import universo as U

# limiares fixos do treino da H26 (dados/lab/minerador_resultado.json): não mudam depois de ver o resultado ao vivo
R1_BAIXO, R1_ALTO, VOL_BAIXO = -1.1734489877988534, 1.1757000900702275, 0.25682599216387464
VOL_HORA_BAIXO = 0.20471780701561856     # 2ª família aprovada na H26: volume ≤ 20% do mesmo horário nos 20 dias anteriores (+0,05–0,06%/op)
ORCAMENTO, ALAV, CUSTO_LADO, STOP_SEG = 25.0, 10.0, 0.0006, 0.02     # tamanho do dono (2026-11-12): US$ 25 a 10×, margem US$ 2,50
CAPITAL, PERDA_DIA, MAX_MESMO_LADO = 10.0, 1.0, 6
DIA = 96
VELA_MS = 900_000
ARQ = "robo_minerador.json"


def velas(par, limite=100):
    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={par}&interval=15m&limit={limite}", timeout=30) as r:
        return [x for x in json.load(r) if x[6] < time.time() * 1000]          # só velas fechadas


def sinal(k):
    """(lado, r1, vol) se a última vela fechada dispara uma das duas regras aprovadas na H26, senão None.
    Regra 1: volume ≤ 26% da média de 96 velas. Regra 2 (precisa de 20 dias de velas): volume ≤ 32% do mesmo horário dos 20 dias anteriores."""
    if len(k) < 98:
        return None
    c = [float(x[4]) for x in k]
    v = [float(x[5]) for x in k]
    lr = [math.log(c[i] / c[i - 1]) for i in range(len(c) - 96, len(c))]
    sig, media_v = statistics.pstdev(lr), sum(v[-96:]) / 96
    if sig <= 0 or media_v <= 0:
        return None
    r1, vol96 = lr[-1] / sig, v[-1] / media_v
    forte = "compra" if r1 <= R1_BAIXO else "venda" if r1 >= R1_ALTO else None
    if not forte:
        return None
    if vol96 <= VOL_BAIXO:
        return forte, r1, vol96
    mesmo = [v[-1 - DIA * j] for j in range(1, 21) if len(v) > DIA * j]
    if len(mesmo) == 20 and sum(mesmo) > 0 and v[-1] / (sum(mesmo) / 20) <= VOL_HORA_BAIXO:
        return forte, r1, v[-1] / (sum(mesmo) / 20)
    return None


def resolver(p, k):
    """Fecha a posição na vela seguinte à do sinal: no stop de segurança se a vela tocou −2%, senão no fechamento dela."""
    vela = next((x for x in k if x[0] == p["vela_saida"]), None)
    if vela is None:
        return None
    h, l, c = float(vela[2]), float(vela[3]), float(vela[4])
    venda = p["lado"] == "venda"
    stop = p["entrada"] * (1 + STOP_SEG if venda else 1 - STOP_SEG)
    if (h >= stop) if venda else (l <= stop):
        return stop, "stop de segurança −2%"
    return c, "fim da vela seguinte"


def passo(e, todas, agora_ms):
    """e: estado do robô; todas: {par: velas fechadas}. Resolve as posições vencidas e abre as novas. Devolve os textos."""
    textos = []
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        r = resolver(p, todas.get(par, []))
        if r is None:
            continue
        saida, motivo = r
        sinal_lado = -1 if p["lado"] == "venda" else 1
        resultado = ORCAMENTO * sinal_lado * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * ORCAMENTO   # lucro líquido da posição de US$ 25
        e["caixa"] += ORCAMENTO / ALAV + resultado
        e["fechadas"].append({**p, "saida": saida, "saida_t": (p["vela_saida"] + VELA_MS) / 1000, "motivo": motivo,
                              "resultado_usd": resultado, "R": resultado / (ORCAMENTO * STOP_SEG)})
        del e["abertas"][par]
        textos.append(f"⛏ Minerador SAIU da {'VENDA' if sinal_lado < 0 else 'COMPRA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT")
    hoje = time.strftime("%Y-%m-%d", time.gmtime(agora_ms / 1000))
    dia = sum(f["resultado_usd"] for f in e["fechadas"] if time.strftime("%Y-%m-%d", time.gmtime(f["saida_t"])) == hoje)
    if dia <= -PERDA_DIA or e["caixa"] < CAPITAL / 2:
        return textos + [f"⛏ Minerador sem novas entradas hoje (resultado do dia {dia:+.2f}, caixa {e['caixa']:.2f})"]
    candidatos = []
    for par, k in todas.items():
        s = sinal(k) if k else None
        if s and par not in e["abertas"] and k[-1][0] != e["ultimo_sinal"].get(par):
            candidatos.append((abs(s[1]), par, k[-1], s))
    for _, par, vela, (lado, r1, vol96) in sorted(candidatos, reverse=True):
        if sum(1 for p in e["abertas"].values() if p["lado"] == lado) >= MAX_MESMO_LADO or e["caixa"] < ORCAMENTO / ALAV:
            continue
        entrada = float(vela[4])
        e["caixa"] -= ORCAMENTO / ALAV
        e["ultimo_sinal"][par] = vela[0]
        e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": entrada, "entrada_t": (vela[0] + VELA_MS) / 1000,
                             "vela_saida": vela[0] + VELA_MS, "r1": r1, "vol96": vol96, "gasto": ORCAMENTO / ALAV}
        textos.append(f"⛏ Minerador ENTROU {'VENDIDO' if lado == 'venda' else 'COMPRADO'} em {par[:-4]} a {entrada:.6g}: "
                      f"movimento de {r1:+.1f}σ com volume de só {vol96:.0%} da média (aposta na reversão)")
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "ultimo_sinal": {},
                                                           "inicio": time.strftime("%Y-%m-%d"), "eventos": []}
    import os
    from pathlib import Path
    cache_v4 = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"   # 2200 velas por moeda, do cérebro v4
    historico = json.loads(cache_v4.read_text()) if cache_v4.exists() else {}
    todas = {}
    for par in U.moedas():                                # todas as moedas da Binance com volume (decisão do dono, 13/11)
        try:
            novas = velas(par)
        except (OSError, ValueError):
            novas = []
        junto = {x[0]: x for x in historico.get(par, []) + novas}
        todas[par] = [junto[t] for t in sorted(junto)][-2200:]
        time.sleep(0.05)
    textos = passo(e, todas, time.time() * 1000)
    e["eventos"] = ([{"t": time.time(), "texto": x} for x in textos] + e["eventos"])[:100]
    e["patrimonio"] = e["caixa"] + sum(p["gasto"] for p in e["abertas"].values())
    arq.write_text(json.dumps(e))
    print(f"⛏ Minerador: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
