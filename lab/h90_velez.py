"""H90 (28/11/2026): mede os setups do método Oliver Velez (mesa/velez.py) com e sem o filtro de estado 20/200.
Critério e execução pré-registrados em lab/PROTOCOLO_LAB.md (H90). Mesmas moedas, velas e custo da H85.
Uso: python3 -m lab.h90_velez → dados/lab/h90_velez.json"""
import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "mesa"))
sys.path.insert(0, str(RAIZ))
import padroes as P  # noqa: E402
import velez as V  # noqa: E402
from lab.h85_padroes import velas, resumo, RADAR, PLANO  # noqa: E402

SAIDA = RAIZ / "dados" / "lab" / "h90_velez.json"


def main():
    r = json.loads(RADAR.read_text())
    moedas = sorted({x["moeda"][:-4] for x in (r.get("entradas") or []) + (r.get("descartes") or [])})
    g = defaultdict(list)
    for iv in PLANO:
        for m in moedas:
            try:
                v = velas(m, iv)
            except Exception as ex:
                print(m, iv, "sem velas", ex)
                continue
            for s in V.sinais(v):
                res = P.simular(v, s)
                if not res:
                    continue
                t = v[s["i"]][0]
                g[(s["setup"], s["lado"], "todos", iv)].append((t, res["liq"]))
                if s["filtro"]:
                    g[(s["setup"], s["lado"], "estado 20/200 a favor", iv)].append((t, res["liq"]))
    linhas = []
    for (setup, lado, filtro, iv), xs in sorted(g.items()):
        xs.sort()
        liq = [x[1] for x in xs]
        meio = len(liq) // 2
        rs, a, b = resumo(liq), resumo(liq[:meio]), resumo(liq[meio:])
        ok = rs["n"] >= 80 and rs.get("media_pct", 0) > 0 and rs.get("t", 0) >= 2 and a.get("media_pct", 0) > 0 and b.get("media_pct", 0) > 0
        linhas.append({"setup": setup, "lado": lado, "filtro": filtro, "tempo": iv, **rs,
                       "metade1": a.get("media_pct"), "metade2": b.get("media_pct"),
                       "acerto": round(sum(1 for x in liq if x > 0) / len(liq), 3) if liq else None, "passa": ok})
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"grupos": linhas, "moedas": moedas}, ensure_ascii=False, indent=1))
    for x in sorted(linhas, key=lambda x: -(x.get("t") or 0)):
        print(f"{'PASSA ' if x['passa'] else '      '}{x['setup']:28s} {x['lado']:6s} {x['filtro']:22s} {x['tempo']:4s} n {x['n']:5d} "
              f"média {x.get('media_pct', 0):+.3f}% t {x.get('t', 0):+.2f} metades {x['metade1']} / {x['metade2']} acerto {x['acerto']}")


if __name__ == "__main__":
    main()
