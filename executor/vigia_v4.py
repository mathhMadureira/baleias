"""Vigia do Cérebro v4 — monitoramento de modelo como manda "Machine Learning for High-Risk Applications" (Hall, Curtis e Pandey,
O'Reilly, 2023, cap. 3: "Model Monitoring", "Benchmark Models", "Residual Analysis"), aplicado às apostas conferidas ao vivo.

Responde, a cada rodada da nuvem, três perguntas que nenhum robô fazia:
  1. **O v4 acerta ao vivo o que acertou no laboratório?** Acerto das últimas apostas contra o do teste que o aprovou (H41: 53,46%), com
     limite de controle. O erro-padrão é calculado POR VELA (as moedas de uma mesma vela andam juntas; contar cada aposta como
     independente inflava o t — lição da H16).
  2. **Ganha de um modelo simples?** Referências triviais nas mesmas velas e moedas: "segue as últimas 24 h da moeda" e "segue a maioria
     do mercado nas últimas 24 h". Livro: "se o modelo simples ganha, use o modelo simples".
  3. **Onde ele erra?** Acerto por segmento (lado, faixa de horário UTC, faixa de confiança quando o v4 grava a probabilidade).

Não decide nada: escreve dados/vigia_v4.json, vai no retrato do chefe da mesa e avisa na sala quando o estado muda.
Uso: BALEIAS_DADOS=.../estado/dados CEREBROS_MOEDAS=... python -m executor.vigia_v4
"""
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

from baleias import config

ACERTO_LAB = 0.5346          # H41 (14/11): v4.1 no holdout de 30 dias, lab/PROTOCOLO_LAB.md
JANELA_DIAS = 7              # apostas dos últimos 7 dias (2000 apostas cobriam só 10 h = 40 velas)
MIN_VELAS = 30               # menos que isso: "não sei"
VELA_MS = 900_000


def _sinal(x):
    return 1 if x > 0 else -1 if x < 0 else 0


def avaliar(ops_por_par, velas=None, agora=None):
    """ops_por_par: {par: [[t, liquido, aposta, prob?], ...]}; velas: {par: [[t, o, h, l, c, ...], ...]} (para as referências).
    Devolve o relatório (dict)."""
    agora = agora or time.time()
    ops = sorted(((o[0], par, o[1] > 0, o[2], o[3] if len(o) > 3 else None) for par, lst in ops_por_par.items() for o in lst), key=lambda x: x[0])
    ops = [o for o in ops if o[0] >= (agora - JANELA_DIAS * 86400) * 1000]
    rel = {"t": int(agora), "acerto_lab": ACERTO_LAB, "n_apostas": len(ops)}
    if not ops:
        rel["veredito"] = "não sei (sem apostas conferidas)"
        return rel
    # 1) acerto ao vivo, com erro-padrão por vela
    por_vela = defaultdict(list)
    for t, _, ganhou, _, _ in ops:
        por_vela[t].append(ganhou)
    medias = [sum(v) / len(v) for v in por_vela.values()]
    n_v = len(medias)
    acerto = sum(g for _, _, g, _, _ in ops) / len(ops)
    if n_v >= 2:
        m = sum(medias) / n_v
        dp = math.sqrt(sum((x - m) ** 2 for x in medias) / (n_v - 1))
        ep = dp / math.sqrt(n_v) if dp else 0.0
    else:
        ep = 0.0
    rel.update({"acerto_ao_vivo": round(acerto, 4), "n_velas": n_v, "erro_padrao": round(ep, 4),
                "de": time.strftime("%d/%m %H:%M", time.gmtime(ops[0][0] / 1000)), "ate": time.strftime("%d/%m %H:%M", time.gmtime(ops[-1][0] / 1000))})
    if n_v < MIN_VELAS or not ep:
        rel["veredito"] = f"não sei (só {n_v} velas)"
    else:
        z_lab = (acerto - ACERTO_LAB) / ep
        z_moeda = (acerto - 0.5) / ep
        rel.update({"z_contra_lab": round(z_lab, 2), "z_contra_moeda": round(z_moeda, 2)})
        if z_lab <= -3:
            rel["veredito"] = "ALARME: ao vivo está abaixo do limite de controle do laboratório (3 erros-padrão)"
        elif z_lab <= -2:
            rel["veredito"] = "atenção: ao vivo abaixo do laboratório (2 erros-padrão)"
        else:
            rel["veredito"] = "dentro do esperado pelo laboratório"
        rel["melhor_que_moeda"] = z_moeda >= 2
    # 3) segmentos (análise de resíduos: onde o modelo erra)
    seg = defaultdict(lambda: [0, 0])
    for t, _, ganhou, aposta, prob in ops:
        h = time.gmtime(t / 1000).tm_hour
        for chave in (("lado", "compra" if aposta > 0 else "venda"), ("horario_utc", f"{h // 6 * 6:02d}–{h // 6 * 6 + 6:02d} h")):
            seg[chave][0] += ganhou
            seg[chave][1] += 1
        if prob is not None:
            c = abs(prob - 0.5)
            faixa = "≥0,12" if c >= 0.12 else "0,08–0,12" if c >= 0.08 else "0,05–0,08" if c >= 0.05 else "<0,05"
            seg[("confianca", faixa)][0] += ganhou
            seg[("confianca", faixa)][1] += 1
    rel["segmentos"] = {f"{a}:{b}": {"acerto": round(g / n, 4), "n": n} for (a, b), (g, n) in sorted(seg.items())}
    # 2) referências triviais nas mesmas apostas
    if velas:
        fech = {par: {x[0]: float(x[4]) for x in k} for par, k in velas.items()}
        mom, maioria = [0, 0], [0, 0]
        maioria_cache = {}
        for t, par, ganhou, aposta, _ in ops:
            f = fech.get(par, {})
            antes, ha24 = f.get(t - VELA_MS), f.get(t - 97 * VELA_MS)
            direcao_real = aposta if ganhou else -aposta          # a vela andou para o lado da aposta se ganhou
            if antes and ha24:
                d = _sinal(antes / ha24 - 1)
                if d:
                    mom[0] += d == direcao_real
                    mom[1] += 1
            if t not in maioria_cache:
                sobe = [_sinal(fech[p].get(t - VELA_MS, 0) / fech[p][t - 97 * VELA_MS] - 1) for p in fech
                        if fech[p].get(t - 97 * VELA_MS) and fech[p].get(t - VELA_MS)]
                maioria_cache[t] = _sinal(sum(sobe)) if len(sobe) >= 20 else 0
            d = maioria_cache[t]
            if d:
                maioria[0] += d == direcao_real
                maioria[1] += 1
        rel["referencias"] = {
            "segue_24h_da_moeda": {"acerto": round(mom[0] / mom[1], 4), "n": mom[1]} if mom[1] else None,
            "segue_maioria_24h": {"acerto": round(maioria[0] / maioria[1], 4), "n": maioria[1]} if maioria[1] else None}
        melhores = [k for k, v in rel["referencias"].items() if v and v["n"] >= 200 and v["acerto"] >= acerto]
        rel["referencia_ganha"] = melhores
    return rel


def resumo(rel):
    if "acerto_ao_vivo" not in rel:
        return f"🔬 Vigia do v4: {rel['veredito']}"
    txt = (f"🔬 Vigia do v4: acerto ao vivo {rel['acerto_ao_vivo']:.1%} em {rel['n_apostas']} apostas ({rel['n_velas']} velas, {rel['de']}–{rel['ate']} UTC) "
           f"contra {ACERTO_LAB:.1%} no laboratório → {rel['veredito']}")
    if rel.get("referencia_ganha"):
        txt += f". Modelo simples ganhou do v4: {', '.join(rel['referencia_ganha'])}"
    return txt


def main():
    arq_v4 = config.RAIZ / "cerebro_v4.json"
    e = json.loads(arq_v4.read_text()) if arq_v4.exists() else {}
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    rel = avaliar(e.get("ops") or {}, velas)
    arq = config.RAIZ / "vigia_v4.json"
    antes = json.loads(arq.read_text()) if arq.exists() else {}
    rel["resumo"] = resumo(rel)
    arq.write_text(json.dumps(rel, ensure_ascii=False))
    mudou = (antes.get("veredito", "")[:8] != rel.get("veredito", "")[:8]) or (bool(antes.get("referencia_ganha")) != bool(rel.get("referencia_ganha")))
    if mudou or time.gmtime().tm_hour != time.gmtime(antes.get("t", 0)).tm_hour and time.gmtime().tm_hour % 6 == 0:
        from baleias import equipe
        equipe.postar("vigia", rel["resumo"], tipo="evento")
    print(rel["resumo"])


if __name__ == "__main__":
    main()
