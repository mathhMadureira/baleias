"""Motor da equipe (25/11, dono: "volume e agilidade"): o laço rápido em CÓDIGO; os agentes de IA comandam pelo motor.json.

Arquitetura (Anthropic "Building effective agents"; TiMi; IBKR "cognitive latency"): a IA decide a estratégia devagar, o código executa rápido.
A cada CICLO_S segundos:
  1. lê equipe/motor.json (comando do Operador): ligado, max_pos, lados, bloqueadas, preferidas, sair_agora, nota_min;
  2. a cada RADAR_S roda o radar rápido (BingX inteira em ~6–10 s);
  3. monta a lista: as abertas ficam (menos as de sair_agora e a que o Risco mandou SAIR em equipe/risco.json); as vagas livres recebem
     as melhores do radar (preferidas primeiro), fora as bloqueadas, as do lado proibido e as que saíram há menos de ESFRIA_S;
  4. executa pela Conta do corretora.py (mercado, stop e alvo guardados na corretora, stop móvel, prazo, chave de foco) e anota no quadro.
Uso: python3 -u motor.py            (laço; o serviço baleias-motor roda isto)
     python3 -I motor.py uma         (uma volta só, para teste)
     python3 -I motor.py ver                                   → comando atual, estado e posições
     python3 -I motor.py set <chave> '<valor JSON>' <agente> "<motivo>"   (max_pos, lados, nota_min, ligado, bloqueadas, preferidas)
     python3 -I motor.py sair <MOEDA> <agente> "<motivo>"      → fecha na próxima volta (≤ 30 s)
     python3 -I motor.py bloquear <MOEDA> <agente> "<motivo>"
"""
import fcntl
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import corretora as C  # noqa: E402

SHARED = Path("/home/servidor-de-producao/OpenBot/Shared/baleias")
EQUIPE = SHARED / "equipe"
AGENTE = "laboratorio"
CICLO_S, RADAR_S, ESFRIA_S = 30, 60, 30 * 60
PADRAO = {"ligado": True, "estilo": "posição", "risco_pct": 0.05, "max_pos": 3, "alav": 20, "margem_pct": 0.30, "alvo_min_pct": 0.05, "lados": "ambos", "nota_min": 0.0, "bloqueadas": [], "preferidas": [], "sair_agora": [],
          "atualizado_por": "padrão", "motivo": ""}


def _json(p, padrao=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return padrao


def comando():
    c = {**PADRAO, **(_json(EQUIPE / "motor.json", {}) or {})}
    c["max_pos"] = max(0, min(int(c.get("max_pos") or 0), C.MAX_POS))
    c["bloqueadas"] = {str(x).upper() if str(x).upper().endswith("USDT") else str(x).upper() + "USDT" for x in c.get("bloqueadas") or []}
    c["preferidas"] = [str(x).upper() if str(x).upper().endswith("USDT") else str(x).upper() + "USDT" for x in c.get("preferidas") or []]
    c["sair_agora"] = {str(x).upper() if str(x).upper().endswith("USDT") else str(x).upper() + "USDT" for x in c.get("sair_agora") or []}
    return c


def falar(para, tipo, texto):
    """O motor fala no canal da equipe (25/11, dono: "agentes conversando o tempo todo, como se tivessem vida própria")."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("canal_m", SHARED / "canal.py")
        k = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(k)
        k.falar("motor", para, tipo, texto)
    except BaseException:
        pass


def quadro(texto, descarte=None):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("quadro_m", SHARED / "quadro.py")
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        if descarte:
            q.descarte(AGENTE, descarte[0], descarte[1])
        else:
            q.registrar(AGENTE, "⚙ motor: " + texto)
    except Exception:
        pass


_radar = {"t": 0, "dado": None}


def ler_radar(agora):
    if agora - _radar["t"] >= RADAR_S or not _radar["dado"]:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("radar_m", SHARED / "radar_rapido.py")
            r = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(r)
            _radar["dado"], _radar["t"] = r.radar(15), agora
        except Exception as ex:
            print(f"radar falhou: {type(ex).__name__}: {ex}", flush=True)
    return _radar["dado"]


def tese_quebrada(p, agora):
    """Evento de saída verificado por CÓDIGO a cada volta (antes o Risco olhava a cada 3 min): posição aberta há 15+ min cujas
    3 últimas velas FECHADAS de 5 min foram contra ela com volume crescente. Devolve o motivo ou None."""
    if agora - p["entrada_t"] < 15 * 60:
        return None
    try:                                                     # 25/11 (dono): nunca cortar um ganho pequeno — a tese só "quebra" no prejuízo
        import urllib.request as _u
        with _u.urlopen(f"https://open-api-vst.bingx.com/openApi/swap/v2/quote/price?symbol={p['moeda'][:-4]}-USDT", timeout=8) as r:
            agora_px = float(json.load(r)["data"]["price"])
        if (agora_px - p["entrada"]) * (1 if p["lado"] == "compra" else -1) >= 0:
            return None
    except Exception:
        return None
    try:
        import urllib.request
        sym = p["moeda"][:-4] + "-USDT" if p.get("moeda") else None
        with urllib.request.urlopen(f"https://open-api-vst.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=5m&limit=5", timeout=10) as r:
            k = sorted(json.load(r)["data"], key=lambda x: x["time"])[:-1][-3:]       # só velas fechadas
    except Exception:
        return None
    if len(k) < 3:
        return None
    s = 1 if p["lado"] == "compra" else -1
    contra = all((float(x["close"]) - float(x["open"])) * s < 0 for x in k)
    vol = [float(x["volume"]) for x in k]
    if contra and vol[0] < vol[1] < vol[2]:
        return f"3 velas de 5 min contra com volume crescente ({vol[0]:.0f} → {vol[2]:.0f})"
    return None


def montar(e, cmd, radar, risco, agora):
    """Lista COMPLETA de posições desejadas (formato da decisão do corretora.py)."""
    abertas = e.get("abertas") or {}
    sair = {m: f"pedido de {cmd.get('atualizado_por') or 'agente'}: {str(cmd.get('motivo') or '')[:60]}" for m in cmd["sair_agora"]}
    if risco and risco.get("acao") == "SAIR" and agora - float(risco.get("t") or 0) < 600:
        sair[str(risco.get("moeda", "")).upper()] = f"Risco mandou sair: {str(risco.get('motivo') or '')[:60]}"
    for par, p in abertas.items():
        if par not in sair:
            motivo = tese_quebrada({**p, "moeda": par}, agora)
            if motivo:
                sair[par] = f"tese quebrou: {motivo}"
                quadro(f"tese quebrou em {par[:-4]}: {motivo}; saio")
    lista = [{"moeda": par, "lado": p["lado"], "motivo": p.get("motivo", ""), "stop_pct": p.get("stop_pct"), "alvo_pct": p.get("alvo_pct"),
              "max_min": p.get("max_min")} for par, p in abertas.items() if par not in sair]
    if not cmd["ligado"] or not radar:
        return lista, sair
    recentes = {x.get("moeda") for x in e.get("fechadas") or []
                if agora - max(float(x.get("saida_t") or 0), float(x.get("registrada_t") or 0)) < ESFRIA_S}
    cands = list(radar.get("entradas") or [])
    cands.sort(key=lambda r: (r["moeda"] not in cmd["preferidas"], -r["nota"]))
    for r in cands:
        if len(lista) >= cmd["max_pos"]:
            break
        m = r["moeda"]
        if m in abertas or m in sair or m in recentes or m in cmd["bloqueadas"] or r["nota"] < cmd["nota_min"]:
            continue
        if cmd["lados"] in ("compra", "venda") and r["lado"] != cmd["lados"]:
            continue
        # 26/11 (placar do Juiz): entradas "scalper" do radar comum somaram −1,73 em 17; as de tendência de 4 h (posição) e as
        # preferidas do Radar pagaram tudo (OPG +2,47). Só entra posição ou preferida, salvo comando estilo = "todos".
        if cmd.get("estilo", "posição") == "posição" and r.get("estilo") != "posição" and m not in cmd["preferidas"]:
            continue
        alav = max(1, min(50, int(cmd.get("alav") or 20)))
        margem = max(0.05, min(0.5, float(cmd.get("margem_pct") or 0.3)))
        stop = r["stop_pct"] / 100
        alvo = max(r["alvo_pct"] / 100, float(cmd.get("alvo_min_pct") or 0), 3 * stop)
        patr = float(e.get("patrimonio") or 10)
        risco = max(0.005, min(0.15, float(cmd.get("risco_pct") or 0.05)))
        noc = round(min(patr * margem * alav, patr * risco / stop), 2)   # dono (26/11): o stop custa no máximo risco_pct da carteira
        lista.append({"moeda": m, "lado": r["lado"], "stop_pct": stop, "alvo_pct": round(alvo, 4), "max_min": max(r["max_min"], 240),
                      "nocional_usd": noc, "alav": alav,
                      "motivo": f"[{'preferida do Radar' if m in cmd['preferidas'] else 'radar'}] {r['estilo']}: 15m {r['v15']:+.2f}%, 1h {r['v1h']:+.2f}%, 4h {r['v4h']:+.2f}%, vol {r['vol_rel']}x, nota {r['nota']}"})
    return lista, sair


def briefing(e, cmd, radar, vivos, agora):
    """Quadro único da equipe (blackboard): escrito pelo motor DEPOIS de cada volta completa, com o que o CÓDIGO verificou.
    Todos os agentes leem isto primeiro: a mesma realidade, sem cada um reler a corretora no meio de uma troca."""
    pos = []
    for par, p in (e.get("abertas") or {}).items():
        ids = set(vivos or {})
        pos.append({"moeda": par, "lado": p["lado"], "entrada": p["entrada"], "ha_min": round((agora - p["entrada_t"]) / 60),
                    "nocional": round(p.get("nocional") or 0, 2), "alav": p.get("alav"),
                    "stop": (p.get("stop") or {}).get("preco"), "alvo": (p.get("alvo") or {}).get("preco"),
                    "stop_ok": None if vivos is None else bool(p.get("stop") and p["stop"]["id"] in ids),
                    "alvo_ok": None if vivos is None else bool(p.get("alvo") and p["alvo"]["id"] in ids),
                    "origem": "preferida do Radar" if "preferida do Radar" in str(p.get("motivo")) else "radar"})
    fe = (e.get("fechadas") or [])[-15:]
    b = {"t": agora, "verificado_pelo_codigo": vivos is not None, "patrimonio": e.get("patrimonio"), "capital": e.get("capital_inicial"),
         "posicoes": pos, "comando": {k: (sorted(v) if isinstance(v, set) else v) for k, v in cmd.items()},
         "ultimas_fechadas": [{"moeda": x.get("moeda"), "lado": x.get("lado"), "resultado": x.get("resultado_usd"),
                               "min": round((float(x.get("saida_t") or 0) - float(x.get("entrada_t") or 0)) / 60),
                               "saida": str(x.get("motivo_saida") or "")[:50],
                               "origem": "preferida do Radar" if "preferida do Radar" in str(x.get("motivo")) else "radar"} for x in fe],
         "radar_top": [{k: r[k] for k in ("moeda", "lado", "v1h", "nota")} for r in (radar or {}).get("entradas", [])[:6]]}
    tmp = EQUIPE / "briefing.tmp"
    tmp.write_text(json.dumps(b, ensure_ascii=False, indent=1))
    tmp.replace(EQUIPE / "briefing.json")


def volta(agora=None):
    agora = agora or time.time()
    cmd = comando()
    radar = ler_radar(agora)
    risco = _json(EQUIPE / "risco.json")
    c = C.conectar(AGENTE)
    with open(C.PASTA / f"{AGENTE}.lock", "w") as trava:
        fcntl.flock(trava, fcntl.LOCK_EX)
        conta = C.Conta(AGENTE, c)
        antes_ab, antes_fe = set(conta.e.get("abertas") or {}), len(conta.e.get("fechadas") or [])
        lista, sair = montar(conta.e, cmd, radar, risco, agora)
        for par, motivo in sair.items():                     # a saída leva o motivo real (quem pediu e por quê), não "fora da lista"
            if par in conta.e.get("abertas", {}):
                try:
                    conta.fechar(par, motivo)
                except Exception as ex:
                    print(f"falha ao fechar {par}: {ex}", flush=True)
        conta.rodada({"t": agora, "posicoes": lista})
        e = conta.e
        try:
            vivos = c.gatilhos_abertos()
        except Exception:
            vivos = None
    briefing(e, cmd, radar, vivos, agora)
    if cmd["sair_agora"] and not (cmd["sair_agora"] & set(e["abertas"])):
        try:
            c2 = _json(EQUIPE / "motor.json", {}) or {}
            c2["sair_agora"] = []
            (EQUIPE / "motor.json").write_text(json.dumps(c2, ensure_ascii=False))
        except OSError:
            pass
    novas = set(e["abertas"]) - antes_ab
    for par in novas:
        p = e["abertas"][par]
        quadro(f"entrou {par[:-4]} {p['lado']} a {p['entrada']:.6g}, stop {(p.get('stop') or {}).get('preco')}, alvo {(p.get('alvo') or {}).get('preco')}")
        falar("todos", "info", f"Entrei {'comprado' if p['lado'] == 'compra' else 'vendido'} em {par[:-4]} a {p['entrada']:.6g} "
              f"(US$ {p.get('nocional', 0):.0f}, {p.get('alav')}×). Stop {(p.get('stop') or {}).get('preco')}, alvo {(p.get('alvo') or {}).get('preco')}. {str(p.get('motivo'))[:90]}")
    for x in (e.get("fechadas") or [])[antes_fe:]:
        quadro(f"saiu {x['moeda'][:-4]} {x['lado']} a {x.get('saida'):.6g}: {x.get('resultado_usd', 0):+.3f} ({str(x.get('motivo_saida'))[:40]})")
        r = x.get("resultado_usd") or 0
        falar("todos", "info", f"{'Lucro' if r > 0 else 'Perda'} em {x['moeda'][:-4]}: {r:+.2f} US$ ({str(x.get('motivo_saida'))[:50]}). Patrimônio {e.get('patrimonio', 0):.2f}.")
        falar("treinador", "pedido", f"Fechou {x['moeda'][:-4]} {x['lado']} com {r:+.2f} US$ por '{str(x.get('motivo_saida'))[:40]}'. O que isso ensina? (resposta curta com número)")
    for par, p in (e.get("abertas") or {}).items():           # posição sofrendo: o motor pede opinião ao Risco, uma vez por posição
        if (p.get("resultado_aberto") or 0) < -0.01 * (p.get("nocional") or 0) * 0.5 and not p.get("perguntou_risco"):
            p["perguntou_risco"] = True
            falar("guardiao", "pedido", f"{par[:-4]} {p['lado']} está em {p.get('resultado_aberto', 0):+.2f} US$ (entrada {p['entrada']:.6g}). Mantenho ou saio? Você decide (motor.py sair).")
    try:
        conta.salvar()
    except Exception:
        pass
    estado = {"t": agora, "ciclo_s": CICLO_S, "radar_t": _radar["t"], "lidas": (radar or {}).get("lidas"), "abertas": len(e["abertas"]),
              "max_pos": cmd["max_pos"], "ligado": cmd["ligado"], "patrimonio": e.get("patrimonio"), "novas": sorted(novas)}
    (EQUIPE / "motor_estado.json").write_text(json.dumps(estado, ensure_ascii=False))
    print(time.strftime("%H:%M:%S"), json.dumps(estado, ensure_ascii=False), flush=True)
    return estado


CHAVES = {"risco_pct", "estilo", "max_pos", "lados", "nota_min", "ligado", "bloqueadas", "preferidas", "sair_agora", "alav", "margem_pct", "alvo_min_pct"}


DONOS = {                                                     # 25/11: cada decisão tem UM dono; os outros propõem no canal (canal.py)
    "lados": {"laboratorio", "baleias"}, "nota_min": {"laboratorio", "baleias"}, "estilo": {"laboratorio", "baleias"}, "ligado": {"laboratorio", "baleias"},
    "preferidas": {"cacador", "baleias"}, "bloqueadas": {"cacador", "laboratorio", "baleias"},
    "sair_agora": {"guardiao", "laboratorio", "baleias"},
    "max_pos": {"baleias"}, "alav": {"baleias"}, "risco_pct": {"baleias"}, "margem_pct": {"baleias"}, "alvo_min_pct": {"baleias"},
}


def mudar(chave, valor, por, motivo):
    if chave not in CHAVES:
        raise SystemExit(f"chave inválida: {chave}; use {sorted(CHAVES)}")
    if por not in DONOS.get(chave, set()):
        raise SystemExit(f"RECUSADO: '{chave}' é decisão de {sorted(DONOS.get(chave, set()))}, não de {por}. "
                         f"Proponha no canal: python3 -I /home/servidor-de-producao/OpenBot/Shared/baleias/canal.py falar {por} "
                         f"{sorted(DONOS.get(chave, {'baleias'}))[0]} proposta \"<o que e por quê, com números>\"")
    arq = EQUIPE / "motor.json"
    with open(EQUIPE / "motor.lock", "w") as t:
        fcntl.flock(t, fcntl.LOCK_EX)
        c = {**PADRAO, **(_json(arq, {}) or {})}
        if chave in ("sair_agora", "bloqueadas") and isinstance(valor, str):
            m = valor.upper() if valor.upper().endswith("USDT") else valor.upper() + "USDT"
            c[chave] = sorted(set(c.get(chave) or []) | {m})
        else:
            c[chave] = valor
        c["atualizado_por"], c["motivo"], c["t"] = por, motivo, time.time()
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False))
        tmp.replace(arq)
    quadro_ag(por, f"motor: {chave} = {json.dumps(valor, ensure_ascii=False)} ({motivo})")
    return c


def quadro_ag(agente, texto):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("quadro_m2", SHARED / "quadro.py")
        q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(q)
        q.registrar(agente, texto)
    except BaseException:
        pass


def main():
    a = sys.argv[1:]
    if a[:1] == ["ver"]:
        e = _json(C.PASTA / f"{AGENTE}.json", {}) or {}
        print(json.dumps({"comando": _json(EQUIPE / "motor.json"), "estado": _json(EQUIPE / "motor_estado.json"),
                          "abertas": {k: {x: v.get(x) for x in ("lado", "entrada", "entrada_t", "stop_pct", "alvo_pct")} for k, v in (e.get("abertas") or {}).items()},
                          "ultimas_fechadas": [{x: f.get(x) for x in ("moeda", "lado", "resultado_usd", "motivo_saida")} for f in (e.get("fechadas") or [])[-10:]],
                          "patrimonio": e.get("patrimonio")}, ensure_ascii=False, indent=1, default=str))
        return
    if a[:1] == ["set"] and len(a) >= 5:
        print(json.dumps(mudar(a[1], json.loads(a[2]), a[3], " ".join(a[4:])), ensure_ascii=False))
        return
    if a[:1] in (["sair"], ["bloquear"]) and len(a) >= 4:
        print(json.dumps(mudar("sair_agora" if a[0] == "sair" else "bloqueadas", a[1], a[2], " ".join(a[3:])), ensure_ascii=False))
        return
    if a[:1] == ["uma"]:
        volta()
        return
    while True:
        t0 = time.time()
        try:
            volta()
        except SystemExit as ex:                       # PARE (foco, endereço): espera e tenta de novo
            print(f"parado: {ex}", flush=True)
        except Exception as ex:
            print(f"erro na volta: {type(ex).__name__}: {ex}", flush=True)
        time.sleep(max(5, CICLO_S - (time.time() - t0)))


if __name__ == "__main__":
    main()
