"""Diário de lições dos robôs: a cada rodada da nuvem, lê o estado de todos os robôs e escreve dados/LICOES.md — o que cada um fez,
onde ganhou e onde perdeu (por horário, lado, confiança e moeda), o que os cérebros aprenderam (promoções e podas de sinapses) e os
últimos vereditos do laboratório. É a parte "visível" do aprendizado (pedido do dono, 14/11): o painel mostra este arquivo.
Só descreve; nenhuma regra muda por causa dele (mudança de regra passa pelo protocolo).

Uso: BALEIAS_DADOS=.../estado/dados python -m executor.licoes
"""
import collections
import json
import time
from pathlib import Path

from baleias import config

PROTOCOLO = Path(__file__).resolve().parent.parent / "lab" / "PROTOCOLO_LAB.md"
ROBOS = (("robo_v4_perp.json", "🌲 Rápido nuvem (v4, todas as apostas)"), ("robo_v4_cacador.json", "🎯 Caçador (2 compras + 2 vendas por vela)"),
         ("robo_minerador.json", "⛏ Minerador (reversão sem volume)"), ("robo_v4_testnet.json", "🧪 v4 Testnet (ordens reais na conta de teste)"),
         ("robo_claude.json", "🤖 Robô Claude (decide de hora em hora lendo o mercado)"))


def ler(nome):
    arq = config.RAIZ / nome
    try:
        return json.loads(arq.read_text()) if arq.exists() else {}
    except ValueError:
        return {}


def faixa_hora(ts):
    h = (time.gmtime(ts).tm_hour // 6) * 6
    return f"{h:02d}–{h + 5:02d} UTC"


def grupo(ops, chave):
    g = collections.defaultdict(lambda: [0, 0, 0.0])
    for o in ops:
        k = chave(o)
        g[k][0] += 1
        g[k][1] += o["resultado_usd"] > 0
        g[k][2] += o["resultado_usd"]
    return g


def linha_grupo(nome, g, minimo=1):
    itens = [(k, v) for k, v in g.items() if v[0] >= minimo]
    if not itens:
        return ""
    itens.sort(key=lambda kv: kv[1][2])
    return f"- **{nome}:** " + " · ".join(f"{k}: {v[0]} op, {v[1] / v[0]:.0%} certas, {v[2]:+.2f}" for k, v in itens) + "\n"


def secao_robo(titulo, e):
    f = e.get("fechadas", [])
    hist = e.get("historico_eliminado", [])
    s = f"## {titulo}\n\n"
    carteira = e.get("patrimonio", e.get("carteira"))
    s += f"Carteira **US$ {carteira:.2f}**" if isinstance(carteira, (int, float)) else "Carteira: ?"
    s += f" · {len(f)} operações fechadas · {len(e.get('abertas', {}))} abertas"
    if hist:
        s += f" · carteiras anteriores zeradas: {len(hist)} (última terminou em {hist[-1].get('carteira_final', 0):.2f} com {len(hist[-1].get('fechadas', []))} op.)"
    s += "\n\n"
    if not f:
        return s + "Sem operações fechadas ainda.\n\n"
    g = sum(1 for x in f if x["resultado_usd"] > 0)
    tot = sum(x["resultado_usd"] for x in f)
    s += f"- **Total:** {g}/{len(f)} com lucro ({g / len(f):.0%}), resultado {tot:+.2f}, média {tot / len(f):+.3f} por operação.\n"
    agora = time.time()
    rec = [x for x in f if x["saida_t"] >= agora - 86400]
    if rec:
        gr = sum(1 for x in rec if x["resultado_usd"] > 0)
        s += f"- **Últimas 24 h:** {gr}/{len(rec)} com lucro, {sum(x['resultado_usd'] for x in rec):+.2f}.\n"
    s += linha_grupo("Por horário", grupo(f, lambda o: faixa_hora(o["saida_t"])))
    s += linha_grupo("Por lado", grupo(f, lambda o: o.get("lado", "?")))
    if any("prob" in x for x in f):
        def faixa(o):
            c = abs(o.get("prob", 0.5) - 0.5)
            return "confiança baixa (<0,05)" if c < 0.05 else "média (0,05–0,08)" if c < 0.08 else "alta (0,08–0,12)" if c < 0.12 else "muito alta (≥0,12)"
        s += linha_grupo("Por confiança do v4", grupo(f, faixa))
    s += linha_grupo("Por motivo de saída", grupo(f, lambda o: o.get("motivo", "?")[:30]))
    gm = grupo(f, lambda o: o["moeda"].replace("USDT", ""))
    piores = sorted((kv for kv in gm.items() if kv[1][0] >= 3), key=lambda kv: kv[1][2])[:5]
    melhores = sorted((kv for kv in gm.items() if kv[1][0] >= 3), key=lambda kv: -kv[1][2])[:5]
    if piores:
        s += "- **Moedas que mais perderam (≥ 3 op):** " + " · ".join(f"{k} {v[2]:+.2f} ({v[0]} op)" for k, v in piores) + "\n"
    if melhores:
        s += "- **Moedas que mais ganharam (≥ 3 op):** " + " · ".join(f"{k} {v[2]:+.2f} ({v[0]} op)" for k, v in melhores) + "\n"
    s += "- Lembrete do laboratório (H36): o ranking de moedas não se repete no tempo; serve para olhar, não para filtrar.\n\n"
    return s


def secao_cerebros():
    s = "## 🧠 O que os cérebros aprenderam (sinapses promovidas e podadas)\n\n"
    achou = False
    for arq, nome in (("cerebro_v3.json", "v3"), ("cerebro_v2.json", "v2"), ("cerebro.json", "v1")):
        e = ler(arq)
        diario = e.get("diario", [])[-6:]
        if diario:
            achou = True
            s += f"**{nome}:**\n"
            for d in diario:
                texto = d.get("texto", str(d)) if isinstance(d, dict) else str(d)
                s += f"- {texto[:220]}\n"
        sin = e.get("sinapses", [])
        obs = [x for x in sin if x.get("status") == "observacao"]
        ativas = [x for x in sin if x.get("status") == "ativa"]
        if sin:
            s += f"  ({nome}: {len(ativas)} sinapses votando, {len(obs)} em observação, {sum(1 for x in sin if x.get('status') == 'podada')} podadas)\n"
    if not achou:
        s += "Sem anotações dos cérebros nesta pasta.\n"
    v4 = ler("cerebro_v4.json")
    ops = [o for x in v4.get("ops", {}).values() for o in x]
    if ops:
        g = sum(1 for o in ops if o[1] > 0)
        s += f"\n**v4 (o cérebro de todos):** {len(ops)} apostas conferidas ao vivo, acerto {g / len(ops):.1%}; prevê {len(v4.get('ultima', {}))} moedas por vela. "
        s += "Retreino semanal automático com juiz (H41): só troca o modelo se acertar mais nos últimos 30 dias.\n"
    return s + "\n"


def secao_laboratorio():
    s = "## 🔬 Últimos vereditos do laboratório\n\n"
    try:
        linhas = [l.strip() for l in PROTOCOLO.read_text(encoding="utf-8").splitlines() if l.startswith("### Resultado") or l.startswith("### Retreino")]
        for l in linhas[-6:]:
            s += f"- {l.replace('### ', '')}\n"
    except OSError:
        s += "Protocolo não encontrado.\n"
    return s + "\n"


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    texto = f"# 📓 Diário de lições dos robôs\n\nAtualizado em {time.strftime('%d/%m/%Y %H:%M')} UTC. Gerado a cada rodada da nuvem a partir do estado real dos robôs. " \
            "Descreve; não muda regra (toda mudança passa pelo protocolo do laboratório).\n\n"
    for arq, titulo in ROBOS:
        e = ler(arq)
        if e:
            texto += secao_robo(titulo, e)
    texto += secao_cerebros() + secao_laboratorio()
    (config.RAIZ / "LICOES.md").write_text(texto, encoding="utf-8")
    print(f"📓 Lições: {len(texto)} caracteres em {config.RAIZ / 'LICOES.md'}")


if __name__ == "__main__":
    main()
