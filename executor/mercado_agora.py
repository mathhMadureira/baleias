"""Retrato do mercado para o Robô Claude (H43): a cada rodada da nuvem escreve dados/mercado_agora.json com o que um operador olharia
antes de decidir — Bitcoin em 1 h / 4 h / 24 h, amplitude do mercado (quantas moedas sobem), maiores altas e quedas de 4 h, as apostas
mais confiantes do Cérebro v4 nos dois lados, e o estado do próprio Robô Claude (posições abertas, últimas operações, lições).
Só dados públicos da Binance (à vista) e arquivos do projeto. Nenhuma decisão aqui: quem decide é a rotina do Claude, de hora em hora.

Uso: BALEIAS_DADOS=.../estado/dados CEREBROS_MOEDAS=... python -m executor.mercado_agora
"""
import json
import os
import statistics
import time
import urllib.request
from pathlib import Path

from baleias import config
from lab import tartaruga as T


def ler(nome):
    arq = config.RAIZ / nome
    try:
        return json.loads(arq.read_text()) if arq.exists() else {}
    except ValueError:
        return {}


def main():
    agora = time.time()
    saida = {"t": int(agora), "hora_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(agora)), "fonte": "Binance à vista (data-api.binance.vision), velas de 15 min e 1 h"}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    retornos = {}
    for par, k in velas.items():
        k = [x for x in k if x[6] < agora * 1000]
        if len(k) < 100:
            continue
        c = [float(x[4]) for x in k]
        retornos[par] = {"1h": (c[-1] / c[-5] - 1) * 100, "4h": (c[-1] / c[-17] - 1) * 100, "24h": (c[-1] / c[-97] - 1) * 100, "preco": c[-1],
                         "vol_4h_vs_media": sum(float(x[5]) for x in k[-16:]) / (sum(float(x[5]) for x in k[-96:]) / 6 or 1e-9)}
    if retornos:
        for h in ("1h", "4h", "24h"):
            vals = [r[h] for r in retornos.values()]
            saida[f"mercado_{h}"] = {"moedas": len(vals), "subindo_pct": round(100 * sum(1 for v in vals if v > 0) / len(vals), 1), "mediana_pct": round(statistics.median(vals), 2)}
        btc = retornos.get("BTCUSDT")
        if btc:
            saida["btc"] = {k: round(v, 2) for k, v in btc.items()}
        ordem = sorted(retornos.items(), key=lambda kv: kv[1]["4h"])
        saida["maiores_quedas_4h"] = [{"moeda": p[:-4], "4h": round(r["4h"], 2), "24h": round(r["24h"], 2), "vol": round(r["vol_4h_vs_media"], 2)} for p, r in ordem[:10]]
        saida["maiores_altas_4h"] = [{"moeda": p[:-4], "4h": round(r["4h"], 2), "24h": round(r["24h"], 2), "vol": round(r["vol_4h_vs_media"], 2)} for p, r in ordem[-10:][::-1]]
    try:
        with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=24", timeout=30) as r:
            k1 = json.load(r)
        saida["btc_1h_ultimas_24"] = [round((float(x[4]) / float(x[1]) - 1) * 100, 2) for x in k1]
    except (OSError, ValueError):
        pass
    try:                                                                   # notícias, medo/ganância, funding, tendência diária, padrões gráficos
        from executor import contexto_mercado as CM
        por_volume = sorted(retornos, key=lambda p: -retornos[p]["vol_4h_vs_media"]) if retornos else []
        saida["contexto"] = CM.montar({p: [x for x in k if x[6] < agora * 1000] for p, k in velas.items()},
                                      ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"] + [p for p in por_volume if p not in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")])
        arq_evid = Path(__file__).resolve().parent.parent / "lab" / "resultados" / "padroes_graficos.json"   # H45 (vai no master, não no estado)
        if arq_evid.exists():
            saida["contexto"]["evidencia_padroes_h45"] = json.loads(arq_evid.read_text()).get("resumo")
    except Exception as ex:
        saida["contexto"] = {"falhas": [f"contexto: {type(ex).__name__}: {ex}"]}
    v4 = ler("cerebro_v4.json")
    pend = v4.get("pendentes", {})
    if pend:
        ordem = sorted(pend.items(), key=lambda kv: kv[1]["prob"])
        saida["v4"] = {"vela": time.strftime("%H:%M UTC", time.gmtime(ordem[0][1]["t"] / 1000 + 900)), "apostas": len(pend),
                       "compras": sum(1 for p in pend.values() if p["aposta"] > 0), "vendas": sum(1 for p in pend.values() if p["aposta"] < 0),
                       "mais_confiantes_venda": [{"moeda": p[:-4], "prob_subir": round(v["prob"], 3)} for p, v in ordem[:8]],
                       "mais_confiantes_compra": [{"moeda": p[:-4], "prob_subir": round(v["prob"], 3)} for p, v in ordem[-8:][::-1]],
                       "lembrete": "acerto do v4 ao vivo ≈ 54%; no perpétuo as apostas de 15 min não pagam o custo sozinhas (H30, H31, H36, H38, H40, H42)"}
    rc = ler("robo_claude.json")
    if rc:
        precos = {p: r["preco"] for p, r in retornos.items()}
        abertas = []
        for par, p in rc.get("abertas", {}).items():
            px = precos.get(par)
            lucro = (1 if p["lado"] == "compra" else -1) * (px / p["entrada"] - 1) * 100 if px else None
            abertas.append({"moeda": par[:-4], "lado": p["lado"], "entrada": p["entrada"], "agora": px, "resultado_pct": round(lucro, 2) if lucro is not None else None,
                            "horas_aberta": round((agora - p["entrada_t"]) / 3600, 1), "motivo_de_entrada": p.get("motivo", "")[:160]})
        fechadas = rc.get("fechadas", [])[-15:]
        saida["robo_claude"] = {"carteira": round(rc.get("patrimonio", 10.0), 2), "abertas": abertas,
                                "ultimas_fechadas": [{"moeda": f["moeda"][:-4], "lado": f["lado"], "resultado_usd": round(f["resultado_usd"], 3), "motivo_saida": f.get("motivo_saida", f.get("motivo", ""))[:80],
                                                      "motivo_de_entrada": f.get("motivo", "")[:120]} for f in fechadas],
                                "licoes_anteriores": rc.get("licoes", [])[-8:]}
    else:
        saida["robo_claude"] = {"carteira": 10.0, "abertas": [], "ultimas_fechadas": [], "licoes_anteriores": []}
    from baleias import equipe                                     # a mesa inteira (fusão com o OpenBot): o chefe vê a equipe e o que o dono pediu
    equipe.sincronizar_caixa()
    saida["equipe"] = equipe.retrato()
    tn = ler("torneio.json")                                        # placar campeão × desafiantes (executor/torneio.py)
    saida["torneio"] = {"campeao": tn.get("campeao"), "placar": tn.get("placar"), "vereditos": [{k: v[k] for k in ("desafiante", "veredito")} for v in tn.get("vereditos", [])]} if tn else None
    vg = ler("vigia_v4.json")                                       # monitoramento do v4 (executor/vigia_v4.py): acerto ao vivo × laboratório × modelo simples
    saida["vigia_v4"] = {k: vg.get(k) for k in ("resumo", "acerto_ao_vivo", "acerto_lab", "veredito", "z_contra_lab", "referencias", "referencia_ganha", "segmentos")} if vg else None
    saida["caixa_dono"] = equipe.pendentes_do_dono()
    saida["sala_recente"] = [{"hora_utc": time.strftime("%d/%m %H:%M", time.gmtime(x["t"])), "de": x["de"], "para": x["para"], "texto": x["texto"][:300]}
                             for x in equipe.sala() if x.get("tipo") != "evento"][-12:]
    (config.RAIZ / "mercado_agora.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))
    print(f"📷 Retrato do mercado: {saida.get('mercado_24h', {}).get('subindo_pct', '?')}% subindo em 24 h · BTC 24 h {saida.get('btc', {}).get('24h', '?')}% · v4 {saida.get('v4', {}).get('vendas', '?')} vendas / {saida.get('v4', {}).get('compras', '?')} compras")


if __name__ == "__main__":
    main()
