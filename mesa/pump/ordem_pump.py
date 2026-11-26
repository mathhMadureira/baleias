"""Ordens do agente Memes para o motor do pump.fun NO PAPEL (v4, H82). Só o Memes usa; o motor executa a cada 5 s.

  python3 -I ordem_pump.py ver
      pacote de dados (candidatos.json), abertas, últimas ordens e placar — leia antes de decidir
  python3 -I ordem_pump.py comprar <MINT> --conf <alta|média|baixa> --tese "<por quê, com números do pacote>"
          [--usd 2] [--gatilho 0.00] [--teto 0.06] [--validade 4] [--stop 0.08] [--alvo 0.20] [--arma 0.10] [--guarda 0.60] [--prazo 15]
      compra quando o preço ficar entre preço_da_ordem×(1+gatilho) e ×(1+teto) dentro de `validade` min; acima do teto, cancela
      (não persegue topo). gatilho > 0 = só compra se continuar subindo (confirmação); gatilho < 0 = compra num recuo.
  python3 -I ordem_pump.py sair <MINT> "<motivo>"
Limites (código recusa fora deles): usd 0,5–3; stop 4–20%; alvo ≥ stop + 6% (custo de 4% ida e volta); prazo 2–60 min;
validade 1–15 min; teto −10% a +15%; o pacote precisa ter menos de 3 min e a moeda estar nele.
"""
import argparse
import fcntl
import json
import sys
import time
import uuid
from pathlib import Path

PASTA = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/pump")
ORDENS, CANDIDATOS, EST = PASTA / "ordens.jsonl", PASTA / "candidatos.json", PASTA / "estado.json"


def _json(p):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def gravar(o):
    with open(ORDENS.with_suffix(".lock"), "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        linhas = ORDENS.read_text().splitlines()[-300:] if ORDENS.exists() else []
        linhas.append(json.dumps(o, ensure_ascii=False))
        ORDENS.write_text("\n".join(linhas) + "\n")
    return o


def validar(a, pacote, agora):
    erros = []
    if agora - float(pacote.get("t") or 0) > 180:
        erros.append("pacote de dados velho (> 3 min): o motor está parado? avise o baleias")
    c = next((c for c in pacote.get("candidatas") or [] if c["mint"] == a.mint), None)
    if not c:
        erros.append("moeda fora do pacote de candidatas: só opere o que tem dado")
    for nome, v, lo, hi in (("usd", a.usd, 0.5, 3), ("stop", a.stop, 0.04, 0.20), ("prazo", a.prazo, 2, 60), ("validade", a.validade, 1, 15),
                            ("teto", a.teto, -0.10, 0.15), ("gatilho", a.gatilho, -0.10, 0.10), ("guarda", a.guarda, 0.3, 0.9), ("arma", a.arma, 0.03, 0.5)):
        if not lo <= v <= hi:
            erros.append(f"{nome} {v} fora de {lo}–{hi}")
    if a.alvo < a.stop + 0.06:
        erros.append(f"alvo {a.alvo:.0%} < stop + 6% ({a.stop + 0.06:.0%}): não paga o custo de 4% ida e volta")
    if a.gatilho > a.teto:
        erros.append("gatilho acima do teto")
    if not a.tese or len(a.tese) < 25:
        erros.append("tese curta demais: diga o porquê com números do pacote")
    return c, erros


def main(argv):
    if argv[:1] == ["ver"]:
        p, e = _json(CANDIDATOS), _json(EST)
        print(f"pacote há {time.time() - float(p.get('t') or 0):.0f} s | caixa US$ {e.get('caixa', 0):.2f} | patrimônio US$ {e.get('patrimonio', 0):.2f} | vagas {p.get('vagas')}")
        for c in p.get("candidatas") or []:
            f = lambda k: "—" if c.get(k) is None else f"{c[k]:+.0%}"
            print(f"- {c['simbolo']} {c['mint']} | idade {c['idade_min']} min | mercado US$ {c['mercado_usd']:,} | 1m {f('var_1m')} 5m {f('var_5m')} 15m {f('var_15m')}"
                  f" pico {c['queda_do_pico_15m']:+.0%} | 5m compras/vendas {c.get('compras_5m')}/{c.get('vendas_5m')} vol US$ {c.get('volume_5m_usd')}"
                  f" | 1h {c.get('compras_1h')}/{c.get('vendas_1h')} | redes {','.join(c.get('redes') or []) or 'nenhuma'}"
                  f"{' | ⚠ ' + '; '.join(c['alertas']) if c.get('alertas') else ''}")
        print("ABERTAS:", json.dumps({p_["simbolo"]: {"entrada_ha_min": round((time.time() - p_["t"]) / 60, 1), "pico": round(p_.get("pico", 0), 3),
                                                     "motivo": p_.get("motivo")} for p_ in (e.get("abertas") or {}).values()}, ensure_ascii=False))
        print("PENDENTES:", [f"{o['simbolo']} até {o['validade_min']} min" for o in (e.get("ordens_pendentes") or {}).values()])
        for o in (e.get("ordens_log") or [])[-6:]:
            print(f"ordem {o['id']} {o['simbolo']}: {o['estado']} — {o['texto']}")
        fech = [f for f in e.get("fechadas") or [] if str(f.get("versao", "")).startswith("v4")]
        if fech:
            g = sum(1 for f in fech if f["resultado"] > 0)
            print(f"PLACAR do Memes: {len(fech)} operações, {g} ganhas, resultado US$ {sum(f['resultado'] for f in fech):+.2f}")
            for f in fech[-5:]:
                print(f"  {f['simbolo']}: {f['resultado']:+.3f} ({f['motivo_saida']}) — tese: {f.get('motivo')}")
        return
    if argv[:1] == ["sair"] and len(argv) >= 3:
        o = gravar({"id": uuid.uuid4().hex[:8], "t": time.time(), "tipo": "sair", "mint": argv[1], "tese": " ".join(argv[2:])[:300],
                    "simbolo": ((_json(EST).get("abertas") or {}).get(argv[1]) or {}).get("simbolo")})
        print(f"ordem {o['id']} de saída gravada; o motor executa em até 5 s")
        return
    ap = argparse.ArgumentParser(prog="ordem_pump.py comprar")
    ap.add_argument("mint")
    ap.add_argument("--conf", required=True, choices=["alta", "média", "baixa"])
    ap.add_argument("--tese", required=True)
    for k, d in (("usd", 2.0), ("gatilho", 0.0), ("teto", 0.06), ("validade", 4), ("stop", 0.08), ("alvo", 0.20), ("arma", 0.10), ("guarda", 0.60), ("prazo", 15)):
        ap.add_argument(f"--{k}", type=float, default=d)
    if argv[:1] != ["comprar"]:
        print(__doc__)
        return
    a = ap.parse_args(argv[1:])
    agora = time.time()
    c, erros = validar(a, _json(CANDIDATOS), agora)
    if erros:
        print("RECUSADA:", "; ".join(erros))
        sys.exit(2)
    o = gravar({"id": uuid.uuid4().hex[:8], "t": agora, "tipo": "comprar", "mint": a.mint, "simbolo": c["simbolo"], "preco_ref": c["preco_sol"],
                "usd": a.usd, "gatilho": a.gatilho, "teto": a.teto, "validade_min": a.validade, "stop": a.stop, "alvo": a.alvo, "arma": a.arma,
                "guarda": a.guarda, "prazo_min": int(a.prazo), "conf": a.conf, "tese": " ".join(a.tese.split())[:300]})
    print(f"ordem {o['id']} gravada: {c['simbolo']} US$ {a.usd:.2f}, compra entre {a.gatilho:+.0%} e {a.teto:+.0%} do preço atual em até "
          f"{a.validade:.0f} min; stop −{a.stop:.0%}, alvo +{a.alvo:.0%}, prazo {a.prazo:.0f} min. Confira com: ordem_pump.py ver")


if __name__ == "__main__":
    main(sys.argv[1:])
