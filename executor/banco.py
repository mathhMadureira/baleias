"""Banco da mesa (pedido do dono, 16/11) — o TESOUREIRO do dinheiro real.

Regras do dono: tudo é feito para operar com dinheiro real; o banco NÃO dá crédito e NÃO empresta (cada robô opera só o próprio dinheiro);
não existe campeão no prejuízo; nenhum robô é pausado no prejuízo ou com operações abertas (baleias.equipe.pausa_proibida).

Por que o banco não move dinheiro dos perdedores para os ganhadores: medido em 16/11 nas 112 janelas de 30 operações dos robôs da mesa,
quem estava no lucro nas 30 anteriores fez em média −0,56 nas 30 seguintes, e quem estava no prejuízo fez −0,44 (correlação −0,14).
Lucro recente não se repetiu, então dar mais dinheiro a quem ganhou teria piorado a mesa. Se essa medida mudar, o banco mostra.

O que o banco faz a cada rodada da nuvem (dados/banco.json, aba Mesa do painel):
  1. tesouro: soma das carteiras, quanto entrou, resultado da mesa, quanto está em margem e quanto está livre;
  2. exposição consolidada: por moeda, o líquido comprado/vendido de toda a mesa. Numa conta real só, um robô comprado e outro vendido na
     mesma moeda se ANULAM: a exposição real é zero e só se paga taxa. O banco lista esses conflitos e quanto custam em taxa;
  3. persistência: refaz a medida acima com os dados de hoje (lucro das 30 anteriores × das 30 seguintes).
"""
import json
import statistics
import time

from baleias import equipe

CAPITAL, JANELA, CUSTO_LADO = 10.0, 30, 0.0006
FORA = {"testnet"}                    # conta de teste da Binance em outro fluxo: aparece no placar, não no tesouro da mesa simulada


def _nocional(p):
    return float(p.get("nocional") or 25.0)


def _margem(p):
    return float(p.get("gasto", p.get("margem", 0)) or 0)


def persistencia(estados):
    """Lucro das JANELA operações anteriores × das JANELA seguintes, em todos os robôs (passo de 10)."""
    pares = []
    for e in estados.values():
        res = [float(x.get("resultado_usd") or 0) for x in sorted(e.get("fechadas") or [], key=lambda x: x.get("saida_t") or 0)]
        pares += [(sum(res[i - JANELA:i]), sum(res[i:i + JANELA])) for i in range(JANELA, len(res) - JANELA + 1, 10)]
    if len(pares) < 10:
        return {"janelas": len(pares)}
    g = [d for a, d in pares if a > 0]
    p = [d for a, d in pares if a <= 0]
    try:
        corr = round(statistics.correlation([a for a, _ in pares], [d for _, d in pares]), 3)
    except statistics.StatisticsError:
        corr = None
    return {"janelas": len(pares), "correlacao": corr,
            "depois_do_lucro": round(statistics.mean(g), 3) if g else None, "n_lucro": len(g),
            "depois_do_prejuizo": round(statistics.mean(p), 3) if p else None, "n_prejuizo": len(p)}


def rodar(estados):
    """estados: {id: estado}. Devolve o retrato do banco (não altera nenhum robô)."""
    est = {ag: e for ag, e in estados.items() if e and ag not in FORA}
    carteiras = {ag: round(float(e.get("patrimonio", e.get("carteira", CAPITAL)) or 0), 2) for ag, e in est.items()}
    margem = sum(_margem(p) for e in est.values() for p in (e.get("abertas") or {}).values())
    moedas = {}
    for ag, e in est.items():
        for par, p in (e.get("abertas") or {}).items():
            m = moedas.setdefault(str(p.get("moeda", par)), {"compra": 0.0, "venda": 0.0, "robos": []})
            m["compra" if p.get("lado") == "compra" else "venda"] += _nocional(p)
            m["robos"].append(f"{ag}:{p.get('lado')}")
    conflitos = []
    for par, m in moedas.items():
        m["liquido"] = round(m["compra"] - m["venda"], 2)
        anulado = min(m["compra"], m["venda"])
        if anulado > 0:
            conflitos.append({"moeda": par, "anulado_usd": round(anulado, 2), "taxa_perdida": round(2 * 2 * CUSTO_LADO * anulado, 3), "robos": m["robos"]})
    bruto = sum(m["compra"] + m["venda"] for m in moedas.values())
    liquido = sum(abs(m["liquido"]) for m in moedas.values())
    total = sum(carteiras.values())
    return {"t": int(time.time()),
            "tesouro": {"robos": len(carteiras), "inicial": CAPITAL * len(carteiras), "carteiras": round(total, 2),
                        "resultado": round(total - CAPITAL * len(carteiras), 2), "em_margem": round(margem, 2), "livre": round(total - margem, 2),
                        "no_lucro": sorted(ag for ag, c in carteiras.items() if c > CAPITAL)},
            "exposicao": {"bruta": round(bruto, 2), "liquida": round(liquido, 2), "moedas": len(moedas),
                          "conflitos": sorted(conflitos, key=lambda c: -c["anulado_usd"])},
            "persistencia": persistencia(est)}


def main():
    estados = {a["id"]: equipe._ler(a["arquivo"], None) for a in equipe.EQUIPE}
    b = rodar(estados)
    antes = equipe._ler("banco.json", {})
    equipe._gravar("banco.json", b)
    t, x = b["tesouro"], b["exposicao"]
    linha = (f"🏦 Banco: {t['robos']} robôs, carteiras US$ {t['carteiras']:.2f} de {t['inicial']:.0f} ({t['resultado']:+.2f}); "
             f"em margem {t['em_margem']:.2f}; exposição bruta US$ {x['bruta']:.0f}, líquida US$ {x['liquida']:.0f}; "
             f"{len(x['conflitos'])} moeda(s) com robôs em lados opostos")
    print(linha)
    novos = {c["moeda"] for c in x["conflitos"]} - {c["moeda"] for c in (antes.get("exposicao") or {}).get("conflitos", [])}
    for c in x["conflitos"]:
        if c["moeda"] in novos:
            equipe.postar("banco", f"🏦 Banco: conflito em {c['moeda'].replace('USDT', '')} — {', '.join(c['robos'])}. Numa conta real US$ {c['anulado_usd']:.0f} "
                                   f"se anulam e custam US$ {c['taxa_perdida']:.3f} em taxa sem exposição nenhuma", tipo="evento")


if __name__ == "__main__":
    main()
