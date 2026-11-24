"""Ferramenta de operação dos agentes do OpenBot na mesa Baleias (H61, 18/11): cada agente opera a própria carteira simulada de US$ 10.

Uso (sempre com python3 -I):
  python3 -I operar.py ler <agente>                 → mercado agora + a carteira do agente (abertas, fechadas, lições)
  python3 -I operar.py escolher <agente>            → analisa o universo inteiro e imprime a "Escolha" pelo MÉTODO do agente (regra fixa, H61)
  python3 -I operar.py gravar <agente> <proposta>   → valida e grava SÓ dados/decisao_<agente>.json no ramo `estado` (até 5 tentativas)
  python3 -I operar.py aprender <agente>            → o caderno: leitura que você tinha em cada entrada × resultado (o que funcionou PARA VOCÊ)
Agentes e métodos (fixos, pré-registrados na H61; o agente não troca moedas por opinião):
  treinador   — método do Caçador (campeão): as apostas mais confiantes do v4 (só com confiança ≥ 0,12, 19/11); regime de baixa = 4 vendas, alta = 4 compras, neutro = 2 + 2.
  laboratorio — só o achado mais robusto do laboratório (H36): v4 com confiança ≥ 0,12, no lado do regime de 24 h (método fixo, H69).
  O v4 abaixo de 0,12 de confiança aparece como "sem confiança" e nunca é motivo de descarte (19/11).
  guardiao    — regra do dono (H44): tendência de 24 h decide o lado; as moedas que lideram o movimento, memecoins primeiro, nos dois lados.
A execução é da nuvem (executor.robo_claude_nuvem com RC_AGENTE): até 4 posições, stop pela volatilidade, stop móvel, 24 h; tamanho H64: fator 2,5 × carteira ÷ 10 em [1,25; 5] × a carteira (cresce no ganho, encolhe na perda).
Nada de dinheiro real; nenhuma ordem na conta de teste (é só do agente Baleias). Só dados públicos.
"""
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path("/home/servidor-de-producao/baleias")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from executor import regime as RG  # noqa: E402

AQUI = Path(__file__).resolve().parent
DADOS = "https://data-api.binance.vision"
REMOTO = "https://github.com/mathhMadureira/baleias.git"
AGENTES = {"treinador": "Treinador", "laboratorio": "Laboratório", "guardiao": "Guardião"}
MAX_POS, ESTICADA, CONTRA = 8, float("inf"), 0.03   # R2 (dono, 23/11): 8 posições, sem corte de 15% em 4 h
# 19/11 (dono: "o v4 está barrando as entradas do Caçador"): o v4 só pesa com confiança |p − 0,5| ≥ 0,12 (o único corte com prova: 65–68% de
# acerto ao vivo, vigia_v4). Abaixo disso é "sem confiança": não fecha posição, não descarta moeda, não corta no REVISOR.
# O Laboratório mantém o método fixo dele (H61/H69: braço de comparação), com o "contra" de 0,03 para manter posição.
CONF_V4 = 0.12


def v4_rotulo(prob, lado=None):
    """Como o v4 aparece para o agente: com confiança ≥ 0,12, o lado e o número; abaixo, "sem confiança" (nunca motivo de descarte)."""
    if prob is None:
        return "v4: sem leitura"
    conf = abs(prob - 0.5)
    if conf < CONF_V4:
        return f"v4 sem confiança ({prob:.2f})"
    sentido = "subir" if prob > 0.5 else "cair"
    if lado is None:
        return f"v4 {sentido} {prob:.2f} (confiança {conf:.2f})"
    return f"v4 {'A FAVOR' if (prob > 0.5) == (lado == 'compra') else 'CONTRA'} ({prob:.2f}, confiança {conf:.2f})"
MEMES = {"DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "BRETT", "POPCAT", "FARTCOIN", "PNUT", "PENGU", "TRUMP", "MEME", "NEIRO", "TURBO",
         "MOODENG", "GOAT", "MOG", "BOME", "SPX", "PEOPLE", "DOGS", "NOT", "MEW", "GIGA", "PONKE", "ACT", "CHILLGUY", "USELESS", "PUMP"}
GRUPOS = [{"BTCUSDT", "ETHUSDT"}]
AUTOR = ["-c", "user.name=agentes-openbot", "-c", "user.email=agentes-openbot@users.noreply.github.com"]
TRAILER = "Co-authored-by: OpenBot <335604065+openbotgit[bot]@users.noreply.github.com>"


def clone(agente):
    c = AQUI / "clones" / agente
    if not (c / ".git").exists():
        c.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--single-branch", "--branch", "estado", "--depth", "20", REMOTO, str(c)], check=True, timeout=300)
    return c


def git(c, *a, check=True):
    return subprocess.run(["git", "-C", str(c), *a], capture_output=True, text=True, timeout=120, check=check)


def clone_ok(c):
    """True se o clone responde a comandos só locais (sem rede). Falha de rede no fetch NÃO é clone quebrado."""
    if not (Path(c) / ".git").exists():
        return False
    try:
        for a in (("rev-parse", "--verify", "-q", "HEAD"), ("status", "--porcelain", "-uno")):
            if subprocess.run(["git", "-C", str(c), *a], capture_output=True, text=True, timeout=60).returncode:
                return False
    except subprocess.SubprocessError:
        return False
    return True


def atualizar(c):
    try:
        git(c, "fetch", "-q", "--depth", "20", "origin", "estado")
        git(c, "reset", "-q", "--hard", "origin/estado")
    except subprocess.CalledProcessError as ex:
        # auditoria 19/11: depois de um desligamento o clone do chefe ficou corrompido (corrompidos/estado-20261119) e toda rodada falhava.
        # O clone é só uma cópia do ramo: guarda o quebrado de lado (não apaga) e clona de novo.
        if "fatal" not in (ex.stderr or "") and "error" not in (ex.stderr or ""):
            raise
        # auditoria 24/11: "fatal: unable to access" (rede caída) também tem "fatal"; o clone bom do Treinador ia para o lado e a rodada
        # clonava de novo pela rede ruim. Com o clone bom, é rede ou GitHub: a rodada para com o erro, sem mexer no clone.
        if clone_ok(c):
            raise
        os.replace(c, c.with_name(f"{c.name}.corrompido-{int(time.time())}"))
        clone(c.name)
        git(c, "reset", "-q", "--hard", "origin/estado")
    git(c, "clean", "-qfd")


def ler_json_arq(arq):
    """JSON de um arquivo local, ou None se vazio/corrompido (desligamento no meio da gravação)."""
    try:
        return json.loads(Path(arq).read_text())
    except (OSError, ValueError):
        return None


def ler_json(c, nome, padrao=None):
    try:
        return json.loads((c / "dados" / nome).read_text())
    except (OSError, ValueError):
        return padrao


def carteira(c, agente):
    return ler_json(c, f"agente_{agente}.json", {}) or {}


# ---------------- ler ----------------
def cmd_ler(agente):
    c = clone(agente)
    atualizar(c)
    m = ler_json(c, "mercado_agora.json", {})
    e = carteira(c, agente)
    dec = ler_json(c, f"decisao_{agente}.json", {}) or {}
    f = e.get("fechadas") or []
    g = [x["resultado_usd"] for x in f if x["resultado_usd"] > 0]
    p = [-x["resultado_usd"] for x in f if x["resultado_usd"] < 0]
    out = {"agora_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "retrato": m.get("hora_utc"),
           "mercado": {k: m.get(k) for k in ("mercado_1h", "mercado_4h", "mercado_24h", "btc")},
           "medo_ganancia": (m.get("contexto") or {}).get("medo_ganancia"), "vigia_v4": (m.get("vigia_v4") or {}).get("resumo"),
           "minha_carteira": {"patrimonio": e.get("patrimonio"), "caixa": e.get("caixa"),
                              "abertas": {k: {"lado": v["lado"], "entrada": v["entrada"], "stop_pct": v.get("stop_pct"), "pico": v.get("pico")}
                                          for k, v in (e.get("abertas") or {}).items()},
                              "fechadas": len(f), "soma": round(sum(x["resultado_usd"] for x in f), 4),
                              "fator_lucro": round(sum(g) / sum(p), 2) if p else None,
                              "ultimas_fechadas": [{k: x.get(k) for k in ("moeda", "lado", "resultado_usd", "motivo_saida")} for x in f[-6:]],
                              "licoes": [x.get("texto") for x in (e.get("licoes") or [])[-3:]], "guarda_dia": e.get("guarda_dia"),
                              "alerta_rotina": e.get("alerta_rotina"), "ultima_decisao_aplicada": e.get("ultima_decisao_t")},
           "minha_decisao_no_ramo": {"t": dec.get("t"), "posicoes": dec.get("posicoes")},
           "placar_torneio": (ler_json(c, "torneio.json", {}) or {}).get("placar")}
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ---------------- foco, caderno e aprendizado (18/11: cada agente lê sozinho e aprende com as próprias operações) ----------------
CADERNOS = AQUI / "cadernos"


def focar(agente, abertas, linhas, cart, lado_reg):
    """Cada agente varre as moedas do PRÓPRIO foco (leitura independente). Devolve (pares, descrição)."""
    univ = {l["par"] for l in linhas}
    if agente == "treinador":
        alvos = [l["par"] for l in sorted(linhas, key=lambda l: -l["prob"])[:5]] + [l["par"] for l in sorted(linhas, key=lambda l: l["prob"])[:5]]
        foco = "as abertas, as 5 mais prováveis de subir e as 5 de cair pelo v4 (método do Caçador)"
    elif agente == "laboratorio":
        alvos = [l["par"] for l in sorted(linhas, key=lambda l: -abs(l["prob"] - 0.5))[:6]]
        alvos += [x["par"] for x in sorted(cart.get("moedas") or [], key=lambda x: -abs(x["compradas"] - x["vendidas"])) if x.get("par") in univ][:4]
        foco = "as abertas, as 6 de maior confiança do v4 e as 4 moedas onde as melhores carteiras mais concordam"
    elif agente == "guardiao":
        memes = [l["par"] for l in sorted((l for l in linhas if l["meme"]), key=lambda l: -abs(l["24h"]))][:6]
        lado = (lambda l: l["24h"]) if lado_reg == "compra" else (lambda l: -l["24h"]) if lado_reg == "venda" else (lambda l: abs(l["24h"]))
        alvos = memes + [l["par"] for l in sorted(linhas, key=lambda l: -lado(l))[:4]]
        foco = "as abertas, as memecoins que mais andaram em 24 h e as 4 líderes da tendência de 24 h"
    else:
        alvos, foco = [], "as abertas"
    return abertas + alvos, foco


def anotar_caderno(agente, d, abertas_antes, varredura, cart):
    """Guarda a leitura que o agente tinha em cada ENTRADA nova (moeda ainda não aberta): é o material do aprendizado dele."""
    CADERNOS.mkdir(exist_ok=True)
    por = {x["par"]: x for x in varredura or []}
    cm = {x.get("par"): x for x in (cart or {}).get("moedas") or []}
    with (CADERNOS / f"{agente}.jsonl").open("a") as f:
        for p in d.get("posicoes") or []:
            par = str(p.get("moeda", "")).upper()
            if par in abertas_antes:
                continue
            x, w = por.get(par) or {}, cm.get(par) or {}
            f.write(json.dumps({"t": d["t"], "moeda": par, "lado": p.get("lado"), "stop_pct": p.get("stop_pct"), "alvo_pct": p.get("alvo_pct"),
                                "max_min": p.get("max_min"), "var": x.get("var"), "z": x.get("z"), "acima_mm20": x.get("acima_mm20"),
                                "padroes": x.get("padroes"), "dist_max24h": x.get("dist_max24h"), "dist_min24h": x.get("dist_min24h"),
                                "carteiras": [w.get("compradas"), w.get("vendidas")] if w else None, "motivo": str(p.get("motivo", ""))[:200]},
                               ensure_ascii=False) + "\n")


def _caracteristicas(n):
    """Leitura da entrada → grupos a comparar (no lado da operação)."""
    venda = n.get("lado") == "venda"
    mm = n.get("acima_mm20") or {}
    a_favor = sum((not v) if venda else bool(v) for v in mm.values()) if mm else None
    pads = n.get("padroes") or []
    lado_ok = "baixa" if venda else "alta"
    pf = [q for q in pads if q.get("sentido") == lado_ok]
    pc = [q for q in pads if q.get("sentido") and q.get("sentido") != lado_ok]
    cart = n.get("carteiras")
    out = {"tempos a favor (MM20)": "sem leitura" if a_favor is None else "6 de 6" if a_favor == 6 else "4–5 de 6" if a_favor >= 4 else "0–3 de 6",
           "padrão gráfico": "a favor" if pf and not pc else "contra" if pc and not pf else "misto" if pf else "nenhum",
           "melhores carteiras": "sem leitura" if not cart else ("a favor" if (cart[1] or 0) > (cart[0] or 0) else "contra" if (cart[0] or 0) > (cart[1] or 0)
                                                                   else "empate ou nenhuma") if venda else
                                  ("a favor" if (cart[0] or 0) > (cart[1] or 0) else "contra" if (cart[1] or 0) > (cart[0] or 0) else "empate ou nenhuma")}
    z = (n.get("z") or {})
    out["movimento de 1 min fora do normal"] = "sim" if z.get("1m") is not None and abs(z["1m"]) >= 2 else "não"
    return out


def cmd_aprender(agente):
    """Junta o caderno (leitura na entrada) com as operações fechadas da carteira e mostra o que funcionou PARA ESTE agente."""
    c = clone(agente if agente in AGENTES else "treinador")
    atualizar(c)
    arq_cart = "robo_claude.json" if agente == "claude" else f"agente_{agente}.json"
    fech = (ler_json(c, arq_cart, {}) or {}).get("fechadas") or []
    notas = []
    for x in ((CADERNOS / f"{agente}.jsonl").read_text().splitlines() if (CADERNOS / f"{agente}.jsonl").exists() else []):
        try:                                                     # auditoria 19/11: linha cortada por desligamento é ignorada
            notas.append(json.loads(x)) if x.strip() else None
        except ValueError:
            continue
    pares = []
    for f in fech:
        n = next((n for n in reversed(notas) if n["moeda"] == f.get("moeda") and n["lado"] == f.get("lado")
                  and n["t"] - 60 <= float(f.get("entrada_t") or 0) <= n["t"] + 5400), None)
        if n:
            pares.append((n, float(f.get("resultado_usd") or 0)))
    print(f"CADERNO DE {agente.upper()}: {len(notas)} entradas anotadas · {len(fech)} operações fechadas na carteira · {len(pares)} com a leitura da entrada")
    if not pares:
        print("ainda não há operação fechada com leitura anotada: nada a aprender ainda (não sei).")
        return
    grupos = {}
    for n, r in pares:
        for k, v in _caracteristicas(n).items():
            grupos.setdefault(k, {}).setdefault(v, []).append(r)
    for k, vs in grupos.items():
        print(f"\n{k}\n| grupo | operações | acerto | soma US$ | média US$ |\n|---|---|---|---|---|")
        for v, rs in sorted(vs.items(), key=lambda kv: -len(kv[1])):
            aviso = " (poucas: não sei ainda)" if len(rs) < 10 else ""
            print(f"| {v}{aviso} | {len(rs)} | {sum(r > 0 for r in rs) / len(rs):.0%} | {sum(rs):+.3f} | {sum(rs) / len(rs):+.4f} |")
    ult = pares[-5:]
    print("\núltimas: " + "; ".join(f"{n['moeda'][:-4]} {n['lado']} {r:+.3f}" for n, r in ult))


# ---------------- Caçador (H68, 19/11): oportunidades caçadas, mostradas primeiro ----------------
CACADOR_JSONL = AQUI.parent / "oportunidades_cacador.jsonl"


def do_cacador(c, agora=None):
    """(confirmadas pelo agente Caçador ainda válidas, oportunidades da varredura da nuvem). Arquivo vazio ou linha cortada é ignorado."""
    agora = agora or time.time()
    conf = []
    if CACADOR_JSONL.exists():
        for l in CACADOR_JSONL.read_text().splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if isinstance(x, dict) and x.get("valida_ate", 0) >= agora:
                conf.append(x)
    nuvem = ler_json(c, "oportunidades.json", {}) or {}
    ops = nuvem.get("oportunidades") or [] if agora - nuvem.get("t", 0) <= 900 else []
    return conf[-6:], ops[:10]


def mostrar_cacador(conf, ops):
    print("OPORTUNIDADES DO CAÇADOR (H68; ele não opera, você decide pela SUA leitura; postura ativa: confirmou, entre a mercado)")
    if conf:
        print("| moeda | lado | sinal | força | entrada | stop | alvo | prazo | vale até (UTC) | motivo |\n|---|---|---|---|---|---|---|---|---|---|")
        for x in conf:
            print(f"| {x['moeda'][:-4]} | {x['lado']} | {x.get('sinal')} | {x.get('forca')} | {x.get('entrada')} | {x['stop_pct']:.2%} | {x['alvo_pct']:.2%} | "
                  f"{x['max_min']} min | {time.strftime('%H:%M', time.gmtime(x['valida_ate']))} | {str(x.get('motivo', ''))[:160]} |")
    else:
        print("confirmadas pelo Caçador: nenhuma válida agora")
    if ops:
        print("varredura da nuvem (sinais brutos, mais fortes; memecoins primeiro):",
              "; ".join(f"{o['moeda']} {o['lado']} {o['tipo']} força {o['forca']} ({o['gatilho']})" for o in ops[:8]))
    else:
        print("varredura da nuvem: sem leitura de até 15 min")


# ---------------- escolher ----------------
def _get(url, t=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "baleias/1.0"}), timeout=t) as r:
        return json.load(r)


def _velas(par):
    try:
        return par, [x for x in _get(f"{DADOS}/api/v3/klines?symbol={par}&interval=15m&limit=98") if x[6] < time.time() * 1000]
    except (OSError, ValueError):
        return par, []


def _medir(k):
    if len(k) < 97:
        return None
    c = [float(x[4]) for x in k]
    v = [float(x[7]) for x in k]
    m4 = sum(v[-96:]) / 6
    return {"1h": round((c[-1] / c[-5] - 1) * 100, 2), "4h": round((c[-1] / c[-17] - 1) * 100, 2), "24h": round((c[-1] / c[-97] - 1) * 100, 2),
            "vol4h": round(sum(v[-16:]) / m4, 2) if m4 else None}


def _ultima(c):
    """Probabilidades do v4 da rodada mais nova com o universo completo (a nuvem às vezes cai para as 33 de reserva)."""
    ult = (ler_json(c, "cerebro_v4.json", {}) or {}).get("ultima") or {}
    if len(ult) >= 50:
        return ult
    git(c, "fetch", "-q", "--depth", "60", "origin", "estado", check=False)
    for linha in git(c, "log", "--format=%h %ct", "-15", "origin/estado", "--", "dados/cerebro_v4.json", check=False).stdout.split("\n"):
        if not linha.strip():
            continue
        h, ct = linha.split()
        if time.time() - int(ct) > 900:
            break
        u = json.loads(git(c, "show", f"{h}:dados/cerebro_v4.json", check=False).stdout or "{}").get("ultima") or {}
        if len(u) >= 100:
            return u
    return ult


def cmd_escolher(agente):
    c = clone(agente)
    atualizar(c)
    ult = _ultima(c)
    conf_cac, ops_cac = do_cacador(c)
    mostrar_cacador(conf_cac, ops_cac)
    with ThreadPoolExecutor(8) as ex:
        k = dict(ex.map(_velas, sorted(ult)))
    reg, s24, s4 = RG.de_velas(k)
    lado_reg = RG.lado_permitido(reg)
    linhas = []
    for par, x in ult.items():
        m = _medir(k.get(par) or [])
        if m:
            linhas.append({"par": par, "moeda": par[:-4], "prob": float(x["prob"]), "meme": par[:-4].removeprefix("1000") in MEMES, **m})
    if len(linhas) < 50:
        raise SystemExit(f"ERRO: só {len(linhas)} moedas lidas; sem análise nesta rodada (mantenha as abertas, não abra nada novo)")
    por = {l["par"]: l for l in linhas}
    abertas = carteira(c, agente).get("abertas") or {}
    escolha, notas = [], {}
    lim_contra = CONTRA if agente == "laboratorio" else CONF_V4   # só o Laboratório (método fixo) fecha com v4 contra abaixo de 0,12
    for par, a in abertas.items():                       # manter enquanto o regime e o sinal do método não virarem contra
        l = por.get(par)
        if lado_reg and lado_reg != a["lado"]:
            notas[par] = f"fecha: regime de 24 h virou para {reg}"
        elif agente == "guardiao" and l and ((l["24h"] < 0) if a["lado"] == "compra" else (l["24h"] > 0)):
            notas[par] = f"fecha: a tendência de 24 h da moeda virou ({l['24h']:+.2f}%)"
        elif agente != "guardiao" and l and ((l["prob"] <= 0.5 - lim_contra) if a["lado"] == "compra" else (l["prob"] >= 0.5 + lim_contra)):
            notas[par] = f"fecha: v4 aponta o lado oposto com confiança ({l['prob']:.3f} de subir)"
        else:
            escolha.append({"moeda": par, "lado": a["lado"], "motivo": f"mantém: regime {reg or 'neutro'} e o sinal do método não virou contra"})
            notas[par] = "mantém"
    usados = {x["moeda"] for x in escolha}

    def ok(l):
        return abs(l["4h"]) < ESTICADA and l["par"] not in usados and not any(l["par"] in g and usados & g for g in GRUPOS)

    cand = []
    if agente in ("treinador", "laboratorio"):
        minimo = CONF_V4                                  # 19/11: o v4 só sugere entrada com confiança ≥ 0,12 (os dois métodos)
        for l in linhas:
            for lado, conf in (("compra", l["prob"] - 0.5), ("venda", 0.5 - l["prob"])):
                if conf >= minimo and (not lado_reg or lado_reg == lado) and ok(l):
                    cand.append((conf, lado, l))
        cand.sort(key=lambda x: -x[0])
        if agente == "treinador" and not lado_reg:      # neutro: 2 compras + 2 vendas, como o Caçador
            vagas = {"compra": 2 - sum(x["lado"] == "compra" for x in escolha), "venda": 2 - sum(x["lado"] == "venda" for x in escolha)}
            cand = [x for x in cand if vagas[x[1]] > 0 and not vagas.__setitem__(x[1], vagas[x[1]] - 1)]
        for conf, lado, l in cand:
            if len(escolha) >= MAX_POS:
                break
            if l["par"] in usados:
                continue
            escolha.append({"moeda": l["par"], "lado": lado, "motivo": f"v4 {l['prob']:.3f} de subir (confiança {conf:.3f}); regime {reg or 'neutro'} "
                            f"({s24}% subindo em 24 h); 1 h {l['1h']:+.2f}%, 4 h {l['4h']:+.2f}%, 24 h {l['24h']:+.2f}%, volume 4 h {l['vol4h']}×"})
            usados.add(l["par"])
    else:                                                 # guardião: tendência de 24 h, líderes do movimento, memecoins primeiro
        for l in linhas:
            if lado_reg == "venda":
                lado = "venda" if l["24h"] <= -1 else None
            elif lado_reg == "compra":
                lado = "compra" if l["24h"] >= 1 else None
            else:
                lado = ("compra" if l["24h"] > 0 else "venda") if abs(l["24h"]) >= (1 if l["meme"] else 3) else None
            if lado and ok(l):
                cand.append((l["meme"], abs(l["24h"]), lado, l))
        cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for meme, forca, lado, l in cand:
            if len(escolha) >= MAX_POS:
                break
            if l["par"] in usados:
                continue
            escolha.append({"moeda": l["par"], "lado": lado, "motivo": f"{'memecoin ' if meme else ''}lidera o lado {lado} em 24 h ({l['24h']:+.2f}%); "
                            f"regime {reg or 'neutro'} ({s24}% subindo); 1 h {l['1h']:+.2f}%, 4 h {l['4h']:+.2f}%, volume 4 h {l['vol4h']}×"})
            usados.add(l["par"])
    r = {"agente": agente, "t": int(time.time()), "moedas": len(linhas), "regime": reg, "subindo_24h": s24, "subindo_4h": s4,
         "candidatos": len(cand), "abertas": notas, "escolha": escolha}
    (AQUI / "rodadas").mkdir(exist_ok=True)
    (AQUI / "rodadas" / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{agente}-escolha.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    def tab(titulo, ls):                                   # H62: panorama para o agente decidir livremente
        print(f"\n{titulo}\n| moeda | v4 (só pesa com confiança ≥ 0,12) | 1 h | 4 h | 24 h | vol 4 h | meme |\n|---|---|---|---|---|---|---|")
        for l in ls:
            print(f"| {l['moeda']} | {v4_rotulo(l['prob'])} | {l['1h']:+.2f}% | {l['4h']:+.2f}% | {l['24h']:+.2f}% | {l['vol4h']}× | {'✓' if l['meme'] else ''} |")
    n_conf = sum(abs(l["prob"] - 0.5) >= CONF_V4 for l in linhas)
    print(f"\nV4: {n_conf} de {len(linhas)} moedas com confiança ≥ 0,12 agora. Abaixo disso o v4 está SEM CONFIANÇA: não é motivo de descarte, "
          "de corte no REVISOR nem de fechar posição (medido em 19/11: o veto fraco não teve efeito consistente — ver LEITURA_GRAFICOS.md seção 4).")
    tab("v4: maior chance de SUBIR", sorted(linhas, key=lambda l: -l["prob"])[:10])
    tab("v4: maior chance de CAIR", sorted(linhas, key=lambda l: l["prob"])[:10])
    tab("mais movimento em 1 h (scalper)", sorted(linhas, key=lambda l: -abs(l["1h"]))[:10])
    tab("memecoins", [l for l in linhas if l["meme"]][:12])
    UNIVERSO = set(por)
    cart = ler_json(c, "carteiras_top.json", {}) or {}         # H63: monitor fomo (as 40 melhores carteiras da Hyperliquid)
    if cart.get("moedas"):
        idade = int((time.time() - cart.get("t", 0)) / 60)
        print(f"\nMELHORES CARTEIRAS (H63: 40 traders ativos e lucrativos da Hyperliquid; leitura de {idade} min atrás; só moedas do universo)")
        print("| moeda | compradas | vendidas | líquido US$ | abriram 1 h (compra/venda) |\n|---|---|---|---|---|")
        for x in [x for x in cart["moedas"] if x.get("par") in UNIVERSO][:12]:
            print(f"| {x['coin']} | {x['compradas']} | {x['vendidas']} | {x['liquido_usd']:,} | {x['abriram_1h_compra']}/{x['abriram_1h_venda']} |")
        feed = [f for f in cart.get("feed", []) if f.get("par") in UNIVERSO][:10]
        print("feed da última hora:", "; ".join(f"{f['tipo']} {f['lado']} {f['coin']}" + (f" US$ {f['valor_usd']:,.0f}" if f.get("valor_usd") else "") for f in feed) or "nenhuma mudança")
        j = cart.get("juiz_h63") or {}
        print(f"teste do sinal (H63, 60 min, custo 0,12%): {j.get('n', 0)} aberturas resolvidas · média {j.get('media')} · t por hora {j.get('t_por_hora')} (passa com ≥ 300, t ≥ 2)")
    else:
        print("\nMELHORES CARTEIRAS: ainda sem leitura da nuvem")
    import multitempo as MT                                   # 18/11: leitura em todos os tempos gráficos, de 1 s a 1 dia
    alvos, foco = focar(agente, list(abertas), linhas, ler_json(c, "carteiras_top.json", {}) or {}, lado_reg)
    cac = list(dict.fromkeys([x["moeda"] for x in conf_cac] + [o["par"] for o in ops_cac[:3]]))
    alvos = list(abertas) + [p for p in cac if p not in abertas] + [p for p in alvos if p not in abertas and p not in cac]   # Caçador primeiro
    foco += "; antes, as moedas avisadas pelo Caçador" if cac else ""
    vt = MT.varrer(alvos)
    print(f"\nVARREDURA EM TODOS OS TEMPOS (1 s → 1 dia) + PADRÕES GRÁFICOS (15 min, 1 h, 4 h), {len(vt)} moedas — o SEU foco: {foco}")
    print(MT.tabela(vt))
    (AQUI / "rodadas" / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{agente}-varredura.json").write_text(json.dumps(vt, ensure_ascii=False))
    print(f"\n({len(linhas)} moedas no panorama do v4; moeda avisada pelo Caçador fora dele também abre, com o preço de 1 min da rodada da nuvem)")
    print(f"{AGENTES[agente]}: {len(linhas)} moedas · regime {reg or 'neutro'} ({s24}% subindo em 24 h, {s4}% em 4 h) · {len(cand)} candidatos pelo método")
    print("Abertas:", json.dumps(notas, ensure_ascii=False))
    print("Escolha:", json.dumps(escolha, ensure_ascii=False, indent=1))


# ---------------- gravar ----------------
def cmd_gravar(agente, arq):
    d = json.loads(Path(arq).read_text())
    d = {"t": int(time.time()), **{k: v for k, v in d.items() if k != "t"}}
    esc = sorted(glob.glob(str(AQUI / "rodadas" / f"*-{agente}-escolha.json")))
    lt = (ler_json_arq(esc[-1]) or {}).get("t") if esc else None
    d["leitura_t"] = int(lt) if lt and d["t"] - lt <= 900 else d["t"] - 900   # 20/11: o stop pode executar entre a leitura e a publicação
    erros = []
    if not str(d.get("leitura", "")).strip():
        erros.append("falta a leitura")
    if not str(d.get("licao", "")).strip():
        erros.append("falta a lição")
    pos = d.get("posicoes")
    if not isinstance(pos, list) or len(pos) > MAX_POS:
        erros.append(f"posicoes: lista de 0 a {MAX_POS}")
    for p in pos or []:
        if not str(p.get("moeda", "")).upper().endswith("USDT") or p.get("lado") not in ("compra", "venda") or not str(p.get("motivo", "")).strip():
            erros.append(f"posição inválida: {p}")
        for k, (lo, hi) in {"stop_pct": (0.003, 0.04), "alvo_pct": (0.002, 0.50), "max_min": (5, 1440)}.items():   # H62/R2: escolhas do agente
            if k in p and not (isinstance(p[k], (int, float)) and lo <= p[k] <= hi):
                erros.append(f"{p.get('moeda')}: {k} = {p[k]!r} fora de {lo}–{hi}")
    from executor.robo_claude_nuvem import validar_gatilhos                    # H67: níveis armados entre as rodadas
    erros += validar_gatilhos(d.get("gatilhos"))
    if d.get("ordens") or d.get("respostas"):
        erros.append("só o chefe (agente Baleias) dá ordens e responde ao dono")
    for k, v in (("fechar", []), ("motivos_fechar", {}), ("mensagens", []), ("ordens", []), ("respostas", [])):
        d.setdefault(k, v)
    if erros:
        raise SystemExit("DECISÃO INVÁLIDA (nada publicado):\n- " + "\n- ".join(erros))
    vs = sorted(glob.glob(str(AQUI / "rodadas" / f"*-{agente}-varredura.json")))
    if vs and time.time() - Path(vs[-1]).stat().st_mtime <= 900 and ler_json_arq(vs[-1]) is not None:
        d["varredura"] = ler_json_arq(vs[-1])                          # o painel mostra a leitura de 1 s a 1 dia que embasou a decisão
    c = clone(agente)
    sys.path.insert(0, str(AQUI.parent))
    import regras as RG_                                                 # REGRAS.md (fonte única, 19/11): campos obrigatórios e cortes duros C2/C3
    erros_r = RG_.conferir_decisao(d.get("posicoes"), carteira(c, agente).get("abertas") or {}, d.get("varredura"))
    if erros_r:
        raise SystemExit("DECISÃO INVÁLIDA (nada publicado; REGRAS.md):\n- " + "\n- ".join(erros_r))
    d["versao_regras"] = RG_.VERSAO
    alvo = f"dados/decisao_{agente}.json"
    ultimo = ""
    for k in range(1, 6):
        try:
            atualizar(c)
            (c / alvo).write_text(json.dumps(d, ensure_ascii=False))
            git(c, "add", alvo)
            mudou = git(c, "diff", "--cached", "--name-only").stdout.split()
            if mudou != [alvo]:
                raise RuntimeError(f"o commit mexeria em outros arquivos: {mudou}")
            git(c, *AUTOR, "commit", "-q", "-m", f"{agente} decidiu {time.strftime('%H:%M', time.gmtime(d['t']))}", "-m", TRAILER)
            r = git(c, "push", "-q", "origin", "HEAD:estado", check=False)
            if r.returncode == 0:
                commit = git(c, "rev-parse", "--short", "HEAD").stdout.strip()
                try:
                    anotar_caderno(agente, d, set((carteira(c, agente).get("abertas") or {})), d.get("varredura"),
                                   ler_json(c, "carteiras_top.json", {}))
                except (OSError, ValueError, KeyError) as ex:
                    print(f"(caderno não anotado: {str(ex)[:80]})")
                with (AQUI / f"recibos_{agente}.md").open("a") as f:
                    f.write(f"- {time.strftime('%Y-%m-%d %H:%M', time.gmtime(d['t']))} UTC ok · commit {commit} · "
                            f"{[(p['moeda'], p['lado']) for p in d['posicoes']]} · {d['leitura'][:160]}\n")
                print(f"ok: decisão de {agente} t={d['t']} publicada no commit {commit} ({k} tentativa(s))")
                return
            ultimo = (r.stderr or r.stdout)[:200]
        except (subprocess.SubprocessError, RuntimeError, OSError) as ex:
            ultimo = str(ex)[:200]
        time.sleep(3 * k)
    with (AQUI / f"recibos_{agente}.md").open("a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC BLOCKED · {ultimo}\n")
    raise SystemExit(f"FALHOU: push falhou 5 vezes: {ultimo}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "aprender" and (sys.argv[2] in AGENTES or sys.argv[2] == "claude"):
        cmd_aprender(sys.argv[2])
        raise SystemExit(0)
    if len(sys.argv) < 3 or sys.argv[2] not in AGENTES or sys.argv[1] not in ("ler", "escolher", "gravar"):
        raise SystemExit(__doc__)
    {"ler": lambda: cmd_ler(sys.argv[2]), "escolher": lambda: cmd_escolher(sys.argv[2]),
     "gravar": lambda: cmd_gravar(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
