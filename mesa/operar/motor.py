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
PADRAO = {"ligado": True, "max_pos": 8, "lados": "ambos", "nota_min": 0.0, "bloqueadas": [], "preferidas": [], "sair_agora": [],
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


def montar(e, cmd, radar, risco, agora):
    """Lista COMPLETA de posições desejadas (formato da decisão do corretora.py)."""
    abertas = e.get("abertas") or {}
    sair = set(cmd["sair_agora"])
    if risco and risco.get("acao") == "SAIR" and agora - float(risco.get("t") or 0) < 600:
        sair.add(str(risco.get("moeda", "")).upper())
    lista = [{"moeda": par, "lado": p["lado"], "motivo": p.get("motivo", ""), "stop_pct": p.get("stop_pct"), "alvo_pct": p.get("alvo_pct"),
              "max_min": p.get("max_min")} for par, p in abertas.items() if par not in sair]
    if not cmd["ligado"] or not radar:
        return lista, sair
    recentes = {x.get("moeda") for x in e.get("fechadas") or [] if agora - float(x.get("saida_t") or 0) < ESFRIA_S}
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
        lista.append({"moeda": m, "lado": r["lado"], "stop_pct": r["stop_pct"] / 100, "alvo_pct": r["alvo_pct"] / 100, "max_min": r["max_min"],
                      "motivo": f"radar {r['estilo']}: 15m {r['v15']:+.2f}%, 1h {r['v1h']:+.2f}%, 4h {r['v4h']:+.2f}%, vol {r['vol_rel']}x, nota {r['nota']}"})
    return lista, sair


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
        conta.rodada({"t": agora, "posicoes": lista})
        e = conta.e
    novas = set(e["abertas"]) - antes_ab
    for par in novas:
        p = e["abertas"][par]
        quadro(f"entrou {par[:-4]} {p['lado']} a {p['entrada']:.6g}, stop {(p.get('stop') or {}).get('preco')}, alvo {(p.get('alvo') or {}).get('preco')}")
    for x in (e.get("fechadas") or [])[antes_fe:]:
        quadro(f"saiu {x['moeda'][:-4]} {x['lado']} a {x.get('saida'):.6g}: {x.get('resultado_usd', 0):+.3f} ({str(x.get('motivo_saida'))[:40]})")
    estado = {"t": agora, "ciclo_s": CICLO_S, "radar_t": _radar["t"], "lidas": (radar or {}).get("lidas"), "abertas": len(e["abertas"]),
              "max_pos": cmd["max_pos"], "ligado": cmd["ligado"], "patrimonio": e.get("patrimonio"), "novas": sorted(novas)}
    (EQUIPE / "motor_estado.json").write_text(json.dumps(estado, ensure_ascii=False))
    print(time.strftime("%H:%M:%S"), json.dumps(estado, ensure_ascii=False), flush=True)
    return estado


def main():
    if sys.argv[1:2] == ["uma"]:
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
