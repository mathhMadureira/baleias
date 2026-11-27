"""Ordens do agente OPERADOR para o motor da BingX VST (demonstração), modo "agente" (27/11, dono: "o foco tem que ser nos agentes").

O agente decide cada operação; o motor executa em até 30 s, põe o stop (e o alvo, se houver) NA CORRETORA e segue o plano do agente.
Não há entrada automática, garantia, trava nem "tese quebrada": só o que o agente pediu.

  python3 -I ordem_bingx.py ver
      carteira, abertas (resultado, pico, plano, tese), o radar inteiro (45 moedas mais líquidas, com descartes),
      BTC, ordens recentes, PLACAR do Operador por confiança e as lições do Juiz — leia antes de decidir
  python3 -I ordem_bingx.py abrir <MOEDA> <compra|venda> --conf <alta|média> --tese "<por quê, com números do ver>"
          --stop 0.02 [--alvo 0.06] [--prazo 240] [--movel-arma 0.03 --movel-guarda 0.6] [--risco 0.05] [--teto 0.01] [--validade 10]
      stop/alvo em fração do preço; prazo em min; movel-arma = a partir de que ganho o stop passa a seguir o preço (guarda × pico);
      risco = fração da carteira que o stop custa (o tamanho sai disso); teto = quanto o preço pode andar a favor antes de entrar
  python3 -I ordem_bingx.py sair <MOEDA> "<motivo com números>"
Limites (o código recusa fora deles): stop 0,5–4%; alvo ≥ stop; prazo 15–1440 min; risco 1–10%; teto 0,2–3%; validade 2–30 min;
moeda no radar (≤ 3 min); tese com 25+ caracteres.
"""
import argparse
import fcntl
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EQUIPE = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/equipe")
ORDENS, ORDENS_EST = EQUIPE / "ordens_bingx.jsonl", EQUIPE / "ordens_bingx_estado.json"
CONTA = AQUI / "corretoras" / "laboratorio.json"
LICOES = EQUIPE / "licoes_operador.md"


def _json(p, d=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return d


def gravar(o):
    with open(ORDENS.with_suffix(".lock"), "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        linhas = ORDENS.read_text().splitlines()[-300:] if ORDENS.exists() else []
        linhas.append(json.dumps(o, ensure_ascii=False))
        ORDENS.write_text("\n".join(linhas) + "\n")
    return o


def _par(m):
    m = str(m).upper()
    return m if m.endswith("USDT") else m + "USDT"


def ver():
    agora = time.time()
    e, r, b = _json(CONTA, {}) or {}, _json(EQUIPE / "radar.json", {}) or {}, _json(EQUIPE / "briefing.json", {}) or {}
    cmd = {**(_json(EQUIPE / "motor.json", {}) or {})}
    print(f"CARTEIRA US$ {e.get('patrimonio', 0):.2f} (capital {e.get('capital_inicial', 10)}) | caixa {float(e.get('caixa') or 0):.2f} | "
          f"motor {'LIGADO' if cmd.get('ligado', True) else 'DESLIGADO'}, modo {cmd.get('modo', 'agente')}, vagas {int(cmd.get('max_pos') or 2) - len(e.get('abertas') or {})} | "
          f"briefing há {agora - float(b.get('t') or 0):.0f} s | radar há {agora - float(r.get('t') or 0):.0f} s")
    for par, p in (e.get("abertas") or {}).items():
        print(f"ABERTA {par[:-4]} {p['lado']} entrada {p['entrada']:.6g} há {(agora - p['entrada_t']) / 60:.0f} min | resultado {p.get('resultado_aberto', 0):+.2f} US$ | "
              f"pico {p.get('pico', 0):+.2%} | stop {(p.get('stop') or {}).get('preco')} alvo {(p.get('alvo') or {}).get('preco')} prazo {p.get('max_min')} min"
              f" | {'plano do agente' if p.get('plano_agente') else 'plano antigo do motor'} | {str(p.get('motivo'))[:120]}")
    todas = (r.get("entradas") or []) + (r.get("descartes") or [])
    btc = next((x for x in todas if x["moeda"] == "BTCUSDT"), None)
    if btc:
        print(f"BTC 15m {btc['v15']:+.2f}% 1h {btc['v1h']:+.2f}% 4h {btc['v4h']:+.2f}%")
    print("RADAR (moeda lado | 15m 1h 4h | vol rel | acima EMA20 5m | stop/alvo sugeridos | estilo | nota | descarte):")
    for x in sorted(todas, key=lambda x: -abs(x.get("v4h") or 0)):
        print(f"  {x['moeda'][:-4]} {x['lado']} | {x['v15']:+.2f} {x['v1h']:+.2f} {x['v4h']:+.2f} | {x['vol_rel']}x | {'sim' if x.get('acima_ema20_5m') else 'não'} | "
              f"{x['stop_pct']}%/{x['alvo_pct']}% | {x['estilo']} | {x['nota']} | {x.get('descarte') or '—'}{' | meme' if x.get('meme') else ''}")
    est = _json(ORDENS_EST, {}) or {}
    try:
        ords = [json.loads(l) for l in ORDENS.read_text().splitlines() if l.strip()][-6:]
    except OSError:
        ords = []
    for o in ords:
        s = est.get(o["id"], {})
        print(f"ORDEM {o['id']} {o['moeda'][:-4]} {o['lado']} ({o.get('conf')}): {s.get('estado', 'pendente')} {s.get('texto', '')}")
    fech = [f for f in e.get("fechadas") or [] if f.get("plano_agente")]
    if fech:
        print(f"PLACAR do Operador: {len(fech)} ops, {sum(1 for f in fech if f['resultado_usd'] > 0)} ganhas, US$ {sum(f['resultado_usd'] for f in fech):+.2f} "
              f"(taxas {sum(f.get('taxas') or 0 for f in fech):.2f})")
        for c in ("alta", "média"):
            fc = [f for f in fech if f.get("conf") == c]
            if fc:
                print(f"  conf {c}: {len(fc)} ops, {sum(1 for f in fc if f['resultado_usd'] > 0)} ganhas, US$ {sum(f['resultado_usd'] for f in fc):+.2f}")
        for f in fech[-5:]:
            print(f"  {f['moeda'][:-4]} {f['lado']} {f['resultado_usd']:+.3f} ({str(f.get('motivo_saida'))[:40]}) — tese: {str(f.get('motivo'))[:110]}")
    else:
        print("PLACAR do Operador: nenhuma operação fechada ainda no modo agente")
    if LICOES.exists():
        print("LIÇÕES (Juiz):\n" + "\n".join(LICOES.read_text().splitlines()[-15:]))


def main(argv):
    if argv[:1] == ["ver"]:
        return ver()
    if argv[:1] == ["sair"] and len(argv) >= 3:
        out = subprocess.run([sys.executable, "-I", str(AQUI / "motor.py"), "sair", _par(argv[1]), "laboratorio", " ".join(argv[2:])[:200]],
                             capture_output=True, text=True, timeout=30)
        print((out.stdout or out.stderr)[-300:])
        return
    if argv[:1] != ["abrir"]:
        print(__doc__)
        return
    ap = argparse.ArgumentParser(prog="ordem_bingx.py abrir")
    ap.add_argument("moeda")
    ap.add_argument("lado", choices=["compra", "venda"])
    ap.add_argument("--conf", required=True, choices=["alta", "média", "baixa"])
    ap.add_argument("--tese", required=True)
    ap.add_argument("--stop", type=float, required=True)
    for k, d in (("alvo", None), ("prazo", 240.0), ("movel-arma", None), ("movel-guarda", 0.6), ("risco", 0.05), ("teto", 0.01), ("validade", 10.0)):
        ap.add_argument(f"--{k}", type=float, default=d)
    a = ap.parse_args(argv[1:])
    m, agora = _par(a.moeda), time.time()
    r = _json(EQUIPE / "radar.json", {}) or {}
    x = next((x for x in (r.get("entradas") or []) + (r.get("descartes") or []) if x["moeda"] == m), None)
    erros = []
    if agora - float(r.get("t") or 0) > 180:
        erros.append("radar velho (> 3 min): motor parado? avise o baleias")
    if not x:
        erros.append(f"{m} fora do radar: só opere o que tem dado")
    for nome, v, lo, hi in (("stop", a.stop, 0.005, 0.04), ("prazo", a.prazo, 15, 1440), ("risco", a.risco, 0.01, 0.10), ("teto", a.teto, 0.002, 0.03),
                            ("validade", a.validade, 2, 30), ("movel-guarda", a.movel_guarda, 0.3, 0.9)):
        if not lo <= v <= hi:
            erros.append(f"{nome} {v} fora de {lo}–{hi}")
    if a.alvo is not None and a.alvo < a.stop:
        erros.append("alvo menor que o stop")
    if a.movel_arma is not None and not 0.003 <= a.movel_arma <= 0.5:
        erros.append("movel-arma fora de 0,3%–50%")
    if a.conf == "baixa":
        erros.append("conf baixa não opera: espere confirmação")
    if len(a.tese) < 25:
        erros.append("tese curta: diga o porquê com números do ver")
    if erros:
        print("RECUSADA:", "; ".join(erros))
        sys.exit(2)
    o = gravar({"id": uuid.uuid4().hex[:8], "t": agora, "tipo": "abrir", "moeda": m, "lado": a.lado, "preco_ref": x["preco"], "stop_pct": a.stop,
                "alvo_pct": a.alvo, "prazo_min": int(a.prazo), "movel_arma": a.movel_arma, "movel_guarda": a.movel_guarda, "risco_pct": a.risco,
                "teto": a.teto, "validade_min": a.validade, "conf": a.conf, "por": "laboratorio", "tese": " ".join(a.tese.split())[:300]})
    print(f"ordem {o['id']} gravada: {a.lado} {m[:-4]} perto de {x['preco']}; stop −{a.stop:.2%}"
          + (f", alvo +{a.alvo:.2%}" if a.alvo else ", sem alvo fixo") + f", prazo {int(a.prazo)} min"
          + (f", stop móvel a partir de +{a.movel_arma:.2%} guardando {a.movel_guarda:.0%} do pico" if a.movel_arma else ", sem stop móvel")
          + f"; risco {a.risco:.0%} da carteira; vale {a.validade:.0f} min. O motor executa em até 30 s; confira com: ordem_bingx.py ver")


if __name__ == "__main__":
    main(sys.argv[1:])
