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
Avisos (27/11, treino): stop < 1,5%, entrada depois de esticar, moeda que perdeu 2× em 48 h, só um lado, alvo longe sem stop móvel.
Com aviso, a ordem só passa com --ciente "<por que desta vez é diferente>"; o Juiz confere depois.
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
CETICO = EQUIPE / "cetico.json"            # 27/11 (H88): decisões do cético {id: {decisao, motivo, t}}
ESPERA_CETICO_S = 150                      # sem resposta nesse tempo, a ordem segue (o cético não trava a mesa)


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
    pad = _json(EQUIPE / "padroes.json", {}) or {}
    if pad.get("moedas"):
        print(f"ESTRUTURA E PADRÕES (15 min; leitor a cada 2 min, há {agora - float(pad.get('t') or 0):.0f} s). res/sup = distância em ATR; "
              "andou = quanto o movimento já foi desde o último fundo (compra) / topo (venda); range = posição no range de 24 h:")
        for m, x in sorted(pad["moedas"].items()):
            e_ = x.get("estrutura") or {}
            if not e_:
                continue
            rs, sp = e_.get("resistencia") or {}, e_.get("suporte") or {}
            ln = " ".join(f"{k}({tf}) {d['estado']} {d['dist_pct']:+.2f}%" for tf in ("15m", "1h") for k, d in (x.get(f"linhas_{tf}") or {}).items())
            sg = "; ".join(f"{s_['padrao']} {s_['lado']} {s_['contexto']} {tf}" + (f" [medido n {s_['medido']['n']}, {s_['medido']['media_pct']:+.2f}%, t {s_['medido']['t']:+.1f}]" if s_.get("medido") else "")
                           for tf in ("15m", "1h") for s_ in x.get(f"sinais_{tf}") or [])
            print(f"  {m[:-4]}: res {rs.get('dist_atr', '—')} ATR ({rs.get('toques', 0)}×) | sup {sp.get('dist_atr', '—')} ATR ({sp.get('toques', 0)}×) | "
                  f"andou ↑{e_.get('subiu_do_fundo_atr')} ↓{e_.get('caiu_do_topo_atr')} ATR | range {e_.get('range_pos_pct')}%"
                  + (f" | {ln}" if ln else "") + (f" | AGORA: {sg}" if sg else ""))
    try:                                                   # 27/11 (H89): o "analista de notícias e do X" do Grok Bot, com fontes públicas
        sys.path.insert(0, str(AQUI.parent))
        import tendencias as T_
        print(T_.texto(T_.ler()))
    except Exception as ex:
        print(f"EM ALTA: indisponível ({type(ex).__name__})")
    est = _json(ORDENS_EST, {}) or {}
    cet = _json(CETICO, {}) or {}
    try:
        ords = [json.loads(l) for l in ORDENS.read_text().splitlines() if l.strip()][-6:]
    except OSError:
        ords = []
    for o in ords:
        s = est.get(o["id"], {})
        c = cet.get(o["id"]) or {}
        print(f"ORDEM {o['id']} {o['moeda'][:-4]} {o['lado']} ({o.get('conf')}): {s.get('estado', 'pendente')} {s.get('texto', '')}"
              + (f" | cético: {c['decisao']} — {c.get('motivo', '')[:120]}" if c else (" | cético: aguardando" if o.get("cetico") else "")))
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
    if LICOES.exists():                                    # 27/11 (dono: "treine os agentes"): padrões medidos inteiros + lições recentes
        ls = LICOES.read_text().splitlines()
        pad = [l for l in ls if l.startswith("## Padrões")]
        if pad:
            i = ls.index(pad[0]); f_ = next((k for k in range(i + 1, len(ls)) if ls[k].startswith("## ")), len(ls))
            print("\n".join(ls[i:f_]))
        print("LIÇÕES recentes (Juiz):\n" + "\n".join([l for l in ls if l.startswith("- ")][-12:]))


def avisos(m, lado, stop, alvo, movel_arma, x, e, agora=None):
    """27/11 (dono: "treine os agentes para isso não acontecer"): os erros medidos nas 46 primeiras operações viram AVISO na hora da
    decisão. Não é regra: com --ciente "<por que mesmo assim>" a ordem passa, e o Juiz confere depois se o porquê se sustentou."""
    agora = agora or time.time()
    av = []
    if stop < 0.015:
        av.append(f"stop {stop:.2%} < 1,5%: no histórico, 21 ops com stop curto somaram −2,58 (as com stop ≥ 1,5%, +1,64)")
    if x:
        a_favor = lambda v: (v or 0) * (1 if lado == "compra" else -1)
        if a_favor(x.get("v1h")) >= 3 or a_favor(x.get("v15")) >= 1.5:
            av.append(f"já andou a favor (15m {x.get('v15'):+.2f}%, 1h {x.get('v1h'):+.2f}%): em 13 de 16 stops o preço nunca andou +0,5% depois da entrada — entrada no topo")
        if x.get("descarte"):
            av.append(f"o radar marcou '{x['descarte']}'")
    fe = [f for f in (e.get("fechadas") or []) if f.get("moeda") == m and agora - float(f.get("saida_t") or 0) < 48 * 3600]
    perdas = [f for f in fe if (f.get("resultado_usd") or 0) < 0]
    if len(perdas) >= 2:
        av.append(f"{m[:-4]} perdeu {len(perdas)} vezes em 48 h ({sum(f['resultado_usd'] for f in perdas):+.2f}): ELSA, ETHFI e 1000PEPE repetidas somaram −1,51")
    ult = [f.get("lado") for f in (e.get("fechadas") or [])[-10:]] + [p.get("lado") for p in (e.get("abertas") or {}).values()]
    if len(ult) >= 6 and all(l == lado for l in ult):
        av.append(f"as últimas {len(ult)} foram todas '{lado}': 42 de 46 foram compras (−3,20); as 4 vendas deram +2,26")
    pad = (_json(EQUIPE / "padroes.json", {}) or {})            # 27/11 (dono, BOME): resistência colada e movimento que já passou
    if agora - float(pad.get("t") or 0) < 600:
        try:
            sys.path.insert(0, str(AQUI.parent))
            import padroes as P_
            av += P_.leitura_entrada(lado, ((pad.get("moedas") or {}).get(m) or {}).get("estrutura") or {})
        except ImportError:
            pass
    if alvo and alvo >= 0.04 and not movel_arma:
        av.append(f"alvo {alvo:.0%} sem stop móvel: 0 de 46 chegaram ao alvo; o pico médio dos ganhos foi +1,1%")
    return av


def decidir_cetico(oid, decisao, motivo, agora=None):
    """H88: o cético (Risco) aprova ou veta uma ordem antes de o motor executar. Veto exige motivo com números."""
    agora = agora or time.time()
    try:
        o = next(json.loads(l) for l in ORDENS.read_text().splitlines() if l.strip() and json.loads(l).get("id") == oid)
    except (OSError, StopIteration):
        print(f"RECUSADA: ordem {oid} não existe")
        sys.exit(2)
    if len(motivo.strip()) < 15:
        print("RECUSADA: motivo curto — diga o porquê com números do ver")
        sys.exit(2)
    if agora - float(o.get("t") or 0) > ESPERA_CETICO_S and decisao == "vetada":
        print(f"tarde demais: a ordem {oid} já seguiu sem o cético ({ESPERA_CETICO_S} s). Se a tese é ruim, mande sair: ordem_bingx.py sair {o['moeda'][:-4]} \"<motivo>\"")
        return
    with open(CETICO.with_suffix(".lock"), "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        d = _json(CETICO, {}) or {}
        d[oid] = {"decisao": decisao, "motivo": " ".join(motivo.split())[:300], "t": agora, "moeda": o["moeda"], "lado": o["lado"],
                  "preco_ref": o.get("preco_ref"), "plano": {k: o.get(k) for k in ("stop_pct", "alvo_pct", "prazo_min", "movel_arma", "movel_guarda")}}
        d = {k: v for k, v in d.items() if agora - float(v.get("t") or 0) < 60 * 86400}
        CETICO.write_text(json.dumps(d, ensure_ascii=False))
    print(f"ordem {oid} {decisao} pelo cético: {motivo[:120]}")


def main(argv):
    if argv[:1] == ["ver"]:
        return ver()
    if argv[:1] == ["sair"] and len(argv) >= 3:
        out = subprocess.run([sys.executable, "-I", str(AQUI / "motor.py"), "sair", _par(argv[1]), "laboratorio", " ".join(argv[2:])[:200]],
                             capture_output=True, text=True, timeout=30)
        print((out.stdout or out.stderr)[-300:])
        return
    if argv[:1] in (["aprovar"], ["vetar"]) and len(argv) >= 3:
        return decidir_cetico(argv[1], "aprovada" if argv[0] == "aprovar" else "vetada", " ".join(argv[2:]))
    if argv[:1] != ["abrir"]:
        print(__doc__)
        return
    ap = argparse.ArgumentParser(prog="ordem_bingx.py abrir")
    ap.add_argument("moeda")
    ap.add_argument("lado", choices=["compra", "venda"])
    ap.add_argument("--conf", required=True, choices=["alta", "média", "baixa"])
    ap.add_argument("--tese", required=True)
    ap.add_argument("--ciente", default="", help="por que entrar mesmo com os avisos (o Juiz confere)")
    ap.add_argument("--stop", type=float, required=True)
    for k, d in (("alvo", None), ("prazo", 240.0), ("movel-arma", None), ("movel-guarda", 0.6), ("risco", 0.05), ("teto", 0.01), ("validade", 10.0)):
        ap.add_argument(f"--{k}", type=float, default=d)
    a = ap.parse_args(argv[1:])
    m, agora = _par(a.moeda), time.time()
    r = _json(EQUIPE / "radar.json", {}) or {}
    x = next((x for x in (r.get("entradas") or []) + (r.get("descartes") or []) if x["moeda"] == m), None)
    erros = []
    if not x:                                                  # 27/11: moeda fora do radar → preço público da BingX agora
        try:
            import urllib.request
            u = f"https://open-api.bingx.com/openApi/swap/v2/quote/price?symbol={m[:-4]}-USDT"
            px = float(json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=10))["data"]["price"])
            x = {"moeda": m, "preco": px, "v15": 0, "v1h": 0, "fora_do_radar": True}
        except Exception:
            x = None
    if agora - float(r.get("t") or 0) > 180:
        erros.append("radar velho (> 3 min): motor parado? avise o baleias")
    if not x:
        erros.append(f"{m}: sem preço no radar nem na BingX agora")
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
    av = avisos(m, a.lado, a.stop, a.alvo, a.movel_arma, x, _json(CONTA, {}) or {}, agora)
    if av and len(a.ciente.strip()) < 15:
        print("AVISOS (erros que já custaram dinheiro à carteira):\n- " + "\n- ".join(av)
              + "\nRepense a ordem. Se ainda quiser entrar, repita o comando com --ciente \"<por que desta vez é diferente>\".")
        sys.exit(3)
    o = gravar({"id": uuid.uuid4().hex[:8], "t": agora, "tipo": "abrir", "moeda": m, "lado": a.lado, "preco_ref": x["preco"], "stop_pct": a.stop,
                "alvo_pct": a.alvo, "prazo_min": int(a.prazo), "movel_arma": a.movel_arma, "movel_guarda": a.movel_guarda, "risco_pct": a.risco,
                "teto": a.teto, "validade_min": a.validade, "conf": a.conf, "por": "laboratorio", "tese": " ".join(a.tese.split())[:300],
                "avisos": av, "ciente": a.ciente.strip()[:200], "cetico": True})
    try:                                                   # H88: acorda o cético (Risco) com a ordem inteira
        sys.path.insert(0, str(AQUI.parent))
        import acordar as K_
        K_.acordar("guardiao", f"NOVA ORDEM {o['id']}: {a.lado} {m[:-4]} perto de {x['preco']}, stop {a.stop:.2%}, conf {a.conf}. "
                   f"Tese: {o['tese'][:220]}" + (f" | avisos ignorados: {'; '.join(av)[:150]} | ciente: {o['ciente'][:100]}" if av else "")
                   + f" | Seja o CÉTICO: ordem_bingx.py aprovar {o['id']} \"<por quê>\" ou vetar {o['id']} \"<por quê, com números>\" em até {ESPERA_CETICO_S} s.",
                   chave=f"ordem {o['id']}", intervalo_s=0)
    except Exception as ex:
        print(f"(cético não acordado: {type(ex).__name__}; a ordem segue em {ESPERA_CETICO_S} s)")
    print(f"ordem {o['id']} gravada: {a.lado} {m[:-4]} perto de {x['preco']}; stop −{a.stop:.2%}"
          + (f", alvo +{a.alvo:.2%}" if a.alvo else ", sem alvo fixo") + f", prazo {int(a.prazo)} min"
          + (f", stop móvel a partir de +{a.movel_arma:.2%} guardando {a.movel_guarda:.0%} do pico" if a.movel_arma else ", sem stop móvel")
          + f"; risco {a.risco:.0%} da carteira; vale {a.validade:.0f} min. O cético tem {ESPERA_CETICO_S} s para vetar; depois o motor executa em até 30 s. Confira com: ordem_bingx.py ver")


if __name__ == "__main__":
    main(sys.argv[1:])
