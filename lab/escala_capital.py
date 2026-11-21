"""H72 — escala: capital × alavancagem (regra e critério pré-registrados em lab/PROTOCOLO_LAB.md antes de rodar).

Mede, nas operações fechadas reais do ramo `estado`, o fio por operação (% do nocional) e o que muda em US$ quando se aumenta
(a) a carteira por agente com a regra de tamanho da H64, e (b) a alavancagem fixa. Monte Carlo de 10.000 ordens por braço.
Só biblioteca padrão. Uso: python3 -m lab.escala_capital
"""
import json
import math
import random
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REF = "origin/estado"
AGENTES = {"chefe": "robo_claude.json", "laboratorio": "agente_laboratorio.json",
           "treinador": "agente_treinador.json", "guardiao": "agente_guardiao.json"}
TESTNET = "robo_openbot_testnet.json"
CAPITAL, PISO_FRAC = 10.0, 0.5
CARTEIRAS = (10.0, 50.0, 100.0, 500.0, 1000.0)
ALAVANCAS = (10, 20, 50)
MONTE = 10_000
SAIDA = REPO / "dados" / "lab" / "escala_capital_resultado.json"


def ler(arq):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{REF}:dados/{arq}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def ops_de(doc):
    """[(saida_t, pct do nocional)] das fechadas, em ordem de fechamento."""
    out = []
    for x in doc.get("fechadas", []):
        noc, res = x.get("nocional"), x.get("resultado_usd")
        if noc and res is not None:
            t = float(x.get("saida_t") or 0)
            if 0 < t < 1e11:                                # alguns agentes gravam segundos, outros milissegundos
                t *= 1000
            out.append((t, float(res) / float(noc)))
    return sorted(out)


def fator_h64(carteira):
    return min(5.0, max(1.25, 2.5 * carteira / CAPITAL))


def simular(ops, carteira0, alav_fixa=None):
    """Sequência real de fechamento. Devolve (final, minima, queda_frac, liquidacoes)."""
    c, minima, liq = carteira0, carteira0, 0
    piso = carteira0 * PISO_FRAC
    for _, pct in ops:
        if c < piso:
            break
        f = fator_h64(c)
        if alav_fixa:
            noc, a = f * c, alav_fixa
            if pct < -1.0 / a:                              # perda para na margem
                pct, liq = -1.0 / a, liq + 1
        else:
            noc, a = f * c, (10 if f <= 2.5 else 20)
        c += noc * pct
        minima = min(minima, c)
    queda = (carteira0 - minima) / carteira0
    return c, minima, queda, liq


def monte(ops, carteira0, alav_fixa=None, semente=7):
    rnd = random.Random(semente)
    n, finais, dobrou = len(ops), [], 0
    for _ in range(MONTE):
        c, piso, alvo = carteira0, carteira0 * PISO_FRAC, carteira0 * 2
        ok = False
        for _, pct in (ops[rnd.randrange(n)] for _ in range(n)):
            if c < piso:
                break
            f = fator_h64(c)
            if alav_fixa:
                p, a = pct, alav_fixa
                if p < -1.0 / a:
                    p = -1.0 / a
                c += f * c * p
            else:
                c += f * c * pct
            if c >= alvo:
                ok = True
                break
        finais.append(c)
        dobrou += ok
    finais.sort()
    return {"mediana": round(finais[len(finais) // 2], 2), "p10": round(finais[int(0.10 * len(finais))], 2),
            "p90": round(finais[int(0.90 * len(finais))], 2), "dobrou_antes_do_piso": round(dobrou / MONTE, 4)}


def fio(ops):
    p = [x[1] for x in ops]
    n = len(p)
    m = sum(p) / n
    s = math.sqrt(sum((x - m) ** 2 for x in p) / (n - 1)) if n > 1 else 0.0
    return {"n": n, "media_pct": round(100 * m, 4), "desvio_pct": round(100 * s, 3),
            "t": round(m / (s / math.sqrt(n)), 2) if s else None,
            "media_usd_nocional_10": round(m * fator_h64(CAPITAL) * CAPITAL, 4)}


def por_dia(ops):
    if len(ops) < 2:
        return None
    dias = (ops[-1][0] - ops[0][0]) / 86_400_000
    return round(len(ops) / dias, 1) if dias > 0 else None


def rodar():
    sim = []
    for a, arq in AGENTES.items():
        d = ler(arq)
        if d:
            sim += ops_de(d)
    sim.sort()
    tst = ops_de(ler(TESTNET) or {})
    conjuntos = {"simulada 4 agentes": sim, "conta de teste (chefe)": tst}
    res = {"referencia": REF, "conjuntos": {}}
    for nome, ops in conjuntos.items():
        f = fio(ops)
        braços = {}
        for c0 in CARTEIRAS:
            fin, mini, queda, liq = simular(ops, c0)
            braços[f"capital {c0:.0f}"] = {"final": round(fin, 2), "queda_max_pct": round(100 * queda, 1),
                                          "lucro_usd": round(fin - c0, 2), **monte(ops, c0)}
        for a in ALAVANCAS:
            fin, mini, queda, liq = simular(ops, CAPITAL, a)
            braços[f"US$ 10 a {a}x"] = {"final": round(fin, 2), "queda_max_pct": round(100 * queda, 1),
                                        "liquidacoes": liq, **monte(ops, CAPITAL, a)}
        res["conjuntos"][nome] = {"fio": f, "operacoes_por_dia": por_dia(ops), "bracos": braços}
    # capital necessário com o fio de hoje (regra H64: nocional = fator × carteira)
    f = res["conjuntos"]["simulada 4 agentes"]["fio"]
    if f["media_pct"] and f["media_pct"] > 0:
        por_dia_n = res["conjuntos"]["simulada 4 agentes"]["operacoes_por_dia"] or 0
        m = f["media_pct"] / 100
        res["capital_necessario"] = {
            "usd_1_por_operacao": round(1 / (m * 2.5), 0),
            "usd_10_por_dia": round(10 / (m * 2.5 * por_dia_n), 0) if por_dia_n else None,
            "usd_100_por_dia": round(100 / (m * 2.5 * por_dia_n), 0) if por_dia_n else None,
            "operacoes_para_100usd_no_capital_10": round(100 / (m * 2.5 * 10), 0),
        }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    r = rodar()
    for nome, c in r["conjuntos"].items():
        f = c["fio"]
        print(f"\n{nome}: {f['n']} operações, fio {f['media_pct']:+.4f}% do nocional (t {f['t']}), {c['operacoes_por_dia']}/dia")
        for b, v in c["bracos"].items():
            print(f"  {b:14s} final {v['final']:8.2f}  queda {v['queda_max_pct']:5.1f}%  MC mediana {v['mediana']:8.2f}  p10 {v['p10']:7.2f}  dobra {100*v['dobrou_antes_do_piso']:5.1f}%" + (f"  liq {v['liquidacoes']}" if v.get("liquidacoes") else ""))
    print("\ncapital necessário:", r.get("capital_necessario"))
    print("resultado em", SAIDA)
