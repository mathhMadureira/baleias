"""H35 — swing trade nas 33 moedas, velas diárias (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar).

Três regras com a melhor evidência aberta em cripto (relatório "Ensinamentos práticos para robôs", seção 11), testadas como
estão escritas, sem ajuste depois de ver o resultado:
  A) Momentum semanal (Liu & Tsyvinski 2021): R7 = C[t]/C[t−7] − 1. R7 > 0 ⇒ compra na abertura seguinte e segura 7 dias; R7 < 0 ⇒ vende.
  B) Média móvel variável de 20 dias com banda de 1% (Grobys, Ahmed & Sapkota 2020): C > MM20×1,01 ⇒ comprado; C < MM20×0,99 ⇒ vendido;
     entre as bandas, fora. A posição muda na abertura seguinte ao sinal.
  C) Tartaruga curta 20/10 (Sistema 1 sem filtro): compra no rompimento da máxima de 20 dias, sai na mínima de 10; vendido simétrico.
Todas com stop de 2×ATR20 conferido na mínima/máxima do dia (sai no stop, ou na abertura se o dia abriu além dele).
Custo: 0,06% por lado (tomador da Binance Futures), 0,12% ida e volta. Uma unidade por moeda (sem alavancagem no teste; o tamanho
ao vivo é só uma escala). Juiz: média do retorno líquido por dia da carteira > 0, t ≥ 2 (agrupado por dia) e média > 0 em 2 dos
3 blocos de tempo iguais. Três tentativas contadas (A, B, C). "Só compra" é informado como leitura, não conta para aprovar.

Uso: python -m lab.swing   (baixa 2200 dias das 33 moedas uma vez para dados/lab/cripto_ohlc_swing.json)
"""
import json
import math
import statistics as st
import time

from baleias import config
from lab import tartaruga as T

CACHE = config.RAIZ / "lab" / "cripto_ohlc_swing.json"
SAIDA = config.RAIZ / "lab" / "swing_resultado.json"
CUSTO_LADO = 0.0006
INICIO = "2020-01-01"
STOP_N = 2.0


def sma(c, i, n):
    return sum(c[i - n + 1:i + 1]) / n if i >= n - 1 else None


def atr20(vs):
    """ATR de 20 dias (média simples do true range), alinhado por índice; None nos primeiros 20 dias."""
    tr = [vs[0][2] - vs[0][3]] + [max(vs[i][2], vs[i - 1][4]) - min(vs[i][3], vs[i - 1][4]) for i in range(1, len(vs))]
    return [sum(tr[i - 19:i + 1]) / 20 if i >= 19 else None for i in range(len(tr))]


def posicao_desejada(regra, vs, i, atual):
    """Posição que a regra quer ao FECHAR o dia i: +1 comprado, −1 vendido, 0 fora. `atual` é a posição que está aberta."""
    c = [v[4] for v in vs]
    if regra == "A":
        if i < 7:
            return 0
        r7 = c[i] / c[i - 7] - 1
        return 1 if r7 > 0 else -1 if r7 < 0 else 0
    if regra == "B":
        m = sma(c, i, 20)
        if m is None:
            return 0
        return 1 if c[i] > m * 1.01 else -1 if c[i] < m * 0.99 else 0
    if regra == "C":
        if i < 20:
            return 0
        hi20, lo20 = max(v[2] for v in vs[i - 20:i]), min(v[3] for v in vs[i - 20:i])
        hi10, lo10 = max(v[2] for v in vs[i - 10:i]), min(v[3] for v in vs[i - 10:i])
        if atual == 1:
            return 0 if c[i] < lo10 else 1
        if atual == -1:
            return 0 if c[i] > hi10 else -1
        return 1 if c[i] > hi20 else -1 if c[i] < lo20 else 0
    raise ValueError(regra)


def simular(regra, dados, lados=(1, -1)):
    """Devolve (retorno líquido por dia da carteira {dia: r}, operações). Uma unidade por moeda; a carteira é a média das moedas vivas."""
    por_dia, ops = {}, []
    for m, vs in dados.items():
        if len(vs) < 60:
            continue
        atr = atr20(vs)
        pos, entrada, stop, dias_seg, pend = 0, None, None, 0, None
        for i in range(1, len(vs)):
            d, o, h, l, c = vs[i]
            if d < INICIO:
                continue
            r = 0.0
            # 1) ordem pendente (decidida no fechamento de ontem) executa na abertura de hoje
            if pend is not None and pend != pos:
                if pos != 0:                                             # fecha a posição atual na abertura (retorno só desde o fechamento de ontem)
                    r += pos * (o / vs[i - 1][4] - 1) - CUSTO_LADO
                    ops.append({"moeda": m, "lado": pos, "entrada": entrada, "saida": o, "ret": pos * (o / entrada - 1) - 2 * CUSTO_LADO, "motivo": "sinal"})
                    pos, entrada = 0, None
                if pend != 0 and pend in lados and atr[i - 1]:
                    pos, entrada, dias_seg = pend, o, 0
                    stop = o - STOP_N * atr[i - 1] if pos == 1 else o + STOP_N * atr[i - 1]
                    r -= CUSTO_LADO
                    base = o
                else:
                    base = None
                pend = None
            else:
                base = vs[i - 1][4] if pos != 0 else None
            # 2) stop dentro do dia
            if pos != 0:
                tocou = (l <= stop) if pos == 1 else (h >= stop)
                if tocou:
                    px = (min(o, stop) if pos == 1 else max(o, stop))
                    r += pos * (px / base - 1) - CUSTO_LADO
                    ops.append({"moeda": m, "lado": pos, "entrada": entrada, "saida": px, "ret": pos * (px / entrada - 1) - 2 * CUSTO_LADO, "motivo": "stop 2×ATR20"})
                    pos, entrada = 0, None
                else:
                    r += pos * (c / base - 1)
                    dias_seg += 1
            # 3) decisão no fechamento
            if regra == "A":
                if pos != 0 and dias_seg < 7:
                    quer = pos                                           # segura os 7 dias
                else:
                    quer = posicao_desejada("A", vs, i, pos)
            else:
                quer = posicao_desejada(regra, vs, i, pos)
            if quer not in lados:
                quer = 0
            if quer != pos:
                pend = quer
            por_dia.setdefault(d, []).append(r)
    curva = {d: st.fmean(rs) for d, rs in sorted(por_dia.items())}
    return curva, ops


def juiz(curva):
    dias = sorted(curva)
    rs = [curva[d] for d in dias]
    n = len(rs)
    media = st.fmean(rs)
    t = media / (st.pstdev(rs) / math.sqrt(n)) if n > 1 and st.pstdev(rs) > 0 else 0.0
    blocos = [st.fmean(rs[k * n // 3:(k + 1) * n // 3]) for k in range(3)]
    total = 1.0
    for x in rs:
        total *= 1 + x
    return {"dias": n, "media_dia_pct": media * 100, "t": t, "blocos_pct": [b * 100 for b in blocos], "ao_ano_pct": (total ** (365 / n) - 1) * 100,
            "passa": media > 0 and t >= 2 and sum(b > 0 for b in blocos) >= 2}


def main():
    t0 = time.time()
    dados = T.baixar(T.MOEDAS_ROBO, cache=CACHE, dias=2200)
    print(f"{len(dados)} moedas, {sum(len(v) for v in dados.values())} dias de velas ({time.time() - t0:.0f} s)")
    saida = {}
    # referência: "mercado" = sempre comprado em todas as moedas (mesmo universo, mesma média por dia). As 33 moedas são as que
    # sobreviveram até hoje, então esta referência carrega o viés de sobrevivência que também infla as versões "só compra".
    por_dia = {}
    for vs in dados.values():
        for i in range(1, len(vs)):
            if vs[i][0] >= INICIO:
                por_dia.setdefault(vs[i][0], []).append(vs[i][4] / vs[i - 1][4] - 1)
    ref = juiz({d: st.fmean(rs) for d, rs in por_dia.items()})
    saida["mercado sempre comprado"] = ref
    print(f"[ref] mercado sempre comprado (viés de sobrevivência incluso): média {ref['media_dia_pct']:+.3f}%/dia (t {ref['t']:+.1f}), "
          f"blocos {[round(b, 3) for b in ref['blocos_pct']]}, ≈{ref['ao_ano_pct']:+.0f}%/ano")
    for regra, nome in (("A", "momentum semanal 7d"), ("B", "MM20 ±1% (variável)"), ("C", "Tartaruga 20/10")):
        for lados, rotulo in (((1, -1), "compra e venda"), ((1,), "só compra")):
            curva, ops = simular(regra, dados, lados)
            j = juiz(curva)
            ganhos = sum(1 for o in ops if o["ret"] > 0)
            j.update({"operacoes": len(ops), "acerto_pct": ganhos / len(ops) * 100 if ops else 0, "ret_medio_op_pct": st.fmean(o["ret"] for o in ops) * 100 if ops else 0,
                      "stops": sum(1 for o in ops if "stop" in o["motivo"]), "conta": rotulo == "compra e venda"})
            saida[f"{regra} {rotulo}"] = j
            print(f"[{regra}] {nome} — {rotulo}: {j['dias']} dias, {j['operacoes']} op. ({j['acerto_pct']:.0f}% certas, {j['ret_medio_op_pct']:+.2f}%/op), "
                  f"média {j['media_dia_pct']:+.3f}%/dia (t {j['t']:+.1f}), blocos {[round(b, 3) for b in j['blocos_pct']]}, "
                  f"≈{j['ao_ano_pct']:+.0f}%/ano → {'PASSA' if j['passa'] else 'não passa'}{'' if j['conta'] else ' (leitura, não conta)'}")
    SAIDA.write_text(json.dumps(saida, indent=1))


if __name__ == "__main__":
    main()
