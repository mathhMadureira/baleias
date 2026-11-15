"""H45 — os padrões gráficos clássicos pagam o custo em 1 h? (pré-registrada em lab/PROTOCOLO_LAB.md antes de rodar)

Evento = padrão CONFIRMADO no fechamento de uma vela de 1 h (lab.padroes_graficos.detectar só com as velas até ali).
Resultado no sentido do padrão em 4 h e 12 h, menos 0,12% de custo. Juiz por família e horizonte: média > 0, t ≥ 2 agrupado por dia,
> 0 em 2 dos 3 blocos, ≥ 200 eventos. Escreve lab/resultados/padroes_graficos.json (vai para o retrato do Robô Claude).

Uso: .venv-ml/bin/python -m lab.padroes_teste
"""
import json
import math
import statistics as st
import time
from pathlib import Path

from lab import minerador as M
from lab import padroes_graficos as PG

CUSTO = 0.0012
JANELA = 120
SAIDA = Path(__file__).resolve().parent / "resultados" / "padroes_graficos.json"


def familia(nome):
    if nome.startswith("triângulo"):
        return "triângulo"
    if nome.startswith("bandeira"):
        return "bandeira"
    if nome.startswith("estrutura"):
        return "virada de estrutura"
    return nome


def main():
    t0 = time.time()
    t, moedas, ohlcv = M.baixar()
    eventos = []
    for im, par in enumerate(moedas):
        o15, h15, l15, c15 = (ohlcv[im, :, k] for k in range(4))
        o, h, l, c, tt = [], [], [], [], []
        for j in range(0, len(t) - 3, 4):
            if int(t[j]) % 3_600_000:
                continue
            b = slice(j, j + 4)
            if any(math.isnan(x) for x in c15[b]) or any(math.isnan(x) for x in o15[b]):
                o.append(float("nan")); h.append(float("nan")); l.append(float("nan")); c.append(float("nan")); tt.append(int(t[j]))
                continue
            o.append(float(o15[j])); h.append(float(max(h15[b]))); l.append(float(min(l15[b]))); c.append(float(c15[j + 3])); tt.append(int(t[j]))
        n = len(c)
        for i in range(JANELA, n - 12):
            jan = slice(i - JANELA + 1, i + 1)
            cj = c[jan]
            if any(math.isnan(x) for x in cj) or math.isnan(c[i + 12]) or math.isnan(c[i + 4]):
                continue
            for p in PG.detectar(o[jan], h[jan], l[jan], cj):
                if not p["confirmado"] or p["sentido"] not in ("alta", "baixa"):
                    continue
                s = 1 if p["sentido"] == "alta" else -1
                eventos.append({"familia": familia(p["padrao"]), "moeda": par, "t": tt[i],
                                "r4": s * (c[i + 4] / c[i] - 1) - CUSTO, "r12": s * (c[i + 12] / c[i] - 1) - CUSTO})
        print(f"  {par}: {sum(1 for e in eventos if e['moeda'] == par)} eventos ({time.time() - t0:.0f} s)", flush=True)
    t_ini, t_fim = int(t[0]), int(t[-1])
    cortes = [t_ini + (t_fim - t_ini) * k // 3 for k in range(4)]
    resultado = {"quando": time.strftime("%Y-%m-%d %H:%M"), "custo": CUSTO, "familias": {}, "resumo": {}}
    for fam in sorted({e["familia"] for e in eventos}):
        ev = [e for e in eventos if e["familia"] == fam]
        for hz in ("r4", "r12"):
            por_dia = {}
            for e in ev:
                por_dia.setdefault(e["t"] // 86_400_000, []).append(e[hz])
            medias = [st.fmean(v) for v in por_dia.values()]
            tstat = st.fmean(medias) / (st.stdev(medias) / math.sqrt(len(medias))) if len(medias) > 1 and st.stdev(medias) > 0 else 0.0
            blocos = [st.fmean([e[hz] for e in ev if cortes[k] <= e["t"] < cortes[k + 1]] or [0.0]) * 100 for k in range(3)]
            media = st.fmean(e[hz] for e in ev) * 100
            acerto = sum(1 for e in ev if e[hz] + CUSTO > 0) / len(ev)
            passa = media > 0 and tstat >= 2 and sum(1 for b in blocos if b > 0) >= 2 and len(ev) >= 200
            chave = f"{fam} · {'4 h' if hz == 'r4' else '12 h'}"
            resultado["familias"][chave] = {"eventos": len(ev), "media_liquida_pct": round(media, 4), "t": round(tstat, 2), "acerto_direcao": round(acerto, 3),
                                            "blocos_pct": [round(b, 4) for b in blocos], "passa": passa}
            resultado["resumo"][chave] = f"{'APROVADO' if passa else 'reprovado'}: {len(ev)} eventos, direção certa {acerto:.0%}, {media:+.3f}%/op depois do custo (t {tstat:+.1f})"
            print(f"{chave:32s} {len(ev):6d} ev · direção certa {acerto:.1%} · líquido {media:+.4f}%/op (t {tstat:+.1f}) · blocos {[round(b, 3) for b in blocos]} → {'PASSA' if passa else 'não passa'}")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    print(f"fim ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
