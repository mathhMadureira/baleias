"""Motor do pump.fun NO PAPEL (26/11, dono: US$ 10 no pump.fun; 2 dias simulados antes do dinheiro real).

Preços reais, dinheiro simulado. Nenhuma carteira, nenhuma chave, nenhuma transação.
A cada CICLO_S:
  1. descobre moedas ativas na API pública do pump.fun (as que mais negociaram agora e as maiores na curva);
  2. lê o preço de cada uma DIRETO na Solana (conta da curva de lançamento: reservas virtuais → preço em SOL) e o SOL em US$ na Binance;
  3. guarda o histórico de preço (gráfico do painel) e decide:
     v3 SCALPER (lê tudo a cada 5 s) entra se: 5+ min de vida, curva entre 25% e 95%, +4% em 2 min ainda subindo, sem salto > 25%
               em 1 min, 10 maiores carteiras com ≤ 30% do suprimento, e não foi operada nos últimos 20 min;
     sai por: stop −7%, alvo +15%, stop móvel (depois de +8% guarda 60% do pico), prazo 15 min, ou graduação.
     sai por: stop, alvo, stop móvel (depois de +ARMA guarda GUARDA do pico), prazo, ou graduação (sai da curva).
  Custos simulados: taxa do pump.fun 1% + derrapagem 1% em cada lado (4% ida e volta).
v4 (26/11, dono: "quem opera a pump.fun é o agente Memes, com engenharia de dados, prompt e computação"; H82):
  O CÓDIGO não escolhe moeda. Ele (a) monta a cada 60 s o pacote de dados pump/candidatos.json (preço na Solana a cada 5 s:
  variação 1/5/15 min, queda desde o pico, curva, idade, mercado; DexScreener: compras/vendas e volume de 5 min e 1 h, redes);
  (b) executa as ORDENS do agente Memes (pump/ordens.jsonl, via ordem_pump.py): compra condicional com gatilho e teto de preço,
  validade curta, plano de saída próprio (stop, alvo, móvel, prazo); (c) protege as abertas a cada 5 s.
Estado: Shared/baleias/pump/estado.json. Uso: python3 -u motor_pump.py
"""
import base64
import json
import struct
import time
import urllib.request
from pathlib import Path

PASTA = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/pump")
EST = PASTA / "estado.json"
RPC = "https://api.mainnet-beta.solana.com"
API = "https://frontend-api-v3.pump.fun/coins?offset=0&limit=50&includeNsfw=false"
UA = {"User-Agent": "Mozilla/5.0"}
CICLO_S, CAPITAL, POS_USD, MAX_POS = 60, 10.0, 2.0, 3   # descoberta na API a cada 60 s (ela recusa, 429, leituras seguidas)
# v2 (26/11): v1 comprava o pico do impulso (+15% em 3 min) e as 3 primeiras caíram 22–38% em até 2 min (venda do criador e dos primeiros).
# Agora: moeda madura, perto da graduação, subindo devagar, sem concentração — e posições vigiadas a cada RAPIDO_S.
# v3 SCALPER (26/11, dono: "as operações na pump.fun têm de ser constantes, em scalper"; H81). A v2 nunca entrou: pedia 20 leituras
# em 10 min com leitura a cada 30 s. Agora TODAS as moedas conhecidas são lidas na Solana a cada RAPIDO_S e a entrada é por impulso curto.
PROG_MIN, PROG_MAX, IDADE_MIN = 0.25, 0.95, 5           # progresso da curva (fração vendida) e idade mínima (min)
JANELA_S, SUBIDA_MIN, SUBIDA_MAX, SALTO_1M_MAX, TOP10_MAX = 120, 0.04, 0.30, 0.25, 0.30   # +4% a +30% em 2 min, sem salto > 25% em 1 min
STOP, ALVO, ARMA, GUARDA, PRAZO_MIN = 0.07, 0.15, 0.08, 0.60, 15
RAPIDO_S = 5
ESFRIA_S = 20 * 60
TOKENS_CURVA = 793_100_000 * 10 ** 6                    # tokens reais à venda na curva do pump.fun (6 casas)
CUSTO_LADO = 0.02
MODO = "agente"                                         # "agente" = só ordens do Memes (v4); "robo" = sinal próprio (v3)
ORDENS, CANDIDATOS = PASTA / "ordens.jsonl", PASTA / "candidatos.json"
DEX = "https://api.dexscreener.com/tokens/v1/solana/"
PACOTE_S = 20                                           # pacote do Memes refeito a cada 20 s (DexScreener aceita 300 consultas/min)
HIST_S, FINO_S = 3600, 600                              # 5 s nos últimos 10 min; mais antigo, 1 ponto a cada 30 s


def _get(url, dados=None, t=15):
    req = urllib.request.Request(url, data=dados, headers={**UA, **({"Content-Type": "application/json"} if dados else {})})
    with urllib.request.urlopen(req, timeout=t) as r:
        return json.load(r)


def sol_usd():
    return float(_get("https://data-api.binance.vision/api/v3/ticker/price?symbol=SOLUSDT")["price"])


def precos(curvas):
    """{curva: (preço em SOL por token, graduada)} lendo as contas da curva na Solana (até 100 por chamada)."""
    out = {}
    for i in range(0, len(curvas), 100):
        lote = curvas[i:i + 100]
        r = _get(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts", "params": [lote, {"encoding": "base64"}]}).encode())
        for c, v in zip(lote, r["result"]["value"]):
            if not v:
                continue
            raw = base64.b64decode(v["data"][0])
            if len(raw) < 49:
                continue
            vt, vs, rt = struct.unpack_from("<QQQ", raw, 8)
            if vt:
                out[c] = ((vs / 1e9) / (vt / 1e6), bool(raw[48]), 1 - rt / TOKENS_CURVA)
    return out


def top10(mint, curva_ata):
    """Fração do suprimento nas 10 maiores carteiras, sem contar a conta da curva (onde ficam os tokens não vendidos)."""
    try:
        r = _get(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getTokenLargestAccounts", "params": [mint]}).encode())
        contas = [a for a in r["result"]["value"] if a["address"] != curva_ata]
        return sum(float(a["uiAmount"] or 0) for a in contas[:10]) / 1e9
    except Exception:
        return None


def _afinar(h, agora):
    out, ult = [], None
    for t, v in h:
        if agora - t > HIST_S:
            continue
        if agora - t > FINO_S and ult is not None and t // 30 == ult:
            continue
        out.append([t, v])
        ult = t // 30
    return out


def vigiar(e):
    """A cada RAPIDO_S (v3): lê TODAS as conhecidas e as abertas na Solana, sai e entra."""
    agora = time.time()
    moedas = {}
    for m, x in list((e.get("conhecidas") or {}).items()):
        if agora * 1000 - float(x.get("created_timestamp") or 0) > 24 * 3600 * 1000:
            e["conhecidas"].pop(m, None)
        else:
            moedas[m] = x
    for m, p in e["abertas"].items():
        moedas.setdefault(m, {"mint": m, "bonding_curve": p["curva"], "symbol": p["simbolo"], "created_timestamp": p.get("criada_ms", 0)})
    if not moedas:
        return
    px = precos(sorted({x["bonding_curve"] for x in moedas.values()}))
    for m, x in moedas.items():
        c = x["bonding_curve"]
        if c in px:
            if px[c][1]:
                e.setdefault("graduadas", {})[m] = agora
            e["info"][m] = {"simbolo": x.get("symbol"), "curva": c, "criada_ms": x.get("created_timestamp"), "nome": x.get("name")}
            h = e["hist"].setdefault(m, [])
            h.append([round(agora), px[c][0]])
            e["hist"][m] = _afinar(h, agora)
    for m in [m for m, h in e["hist"].items() if not h or agora - h[-1][0] > HIST_S]:
        e["hist"].pop(m, None)
        e["info"].pop(m, None)
    sair(e, px, agora)
    if MODO == "agente":
        executar_ordens(e, moedas, px, agora)
    else:
        entrar(e, moedas, px, agora)
    e["patrimonio"] = patrimonio(e, px)
    e["atualizado"] = agora
    e["lidas"] = len(px)


def carregar():
    try:
        return json.loads(EST.read_text())
    except (OSError, ValueError):
        return {"inicio": time.time(), "caixa": CAPITAL, "capital": CAPITAL, "abertas": {}, "fechadas": [], "hist": {}, "info": {},
                "eventos": [], "curva": []}


def salvar(e):
    e["eventos"] = e["eventos"][-200:]
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = EST.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False))
    tmp.replace(EST)


ACORDAR_LIGADO = False


def acordar(agente, motivo, chave):
    if not ACORDAR_LIGADO:
        return
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("acordar_m", PASTA.parent / "acordar.py")
        k = importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
        k.acordar(agente, motivo, chave)
    except BaseException as ex:
        print(f"acordar {agente} falhou: {ex}", flush=True)


def anotar(e, texto):
    if "SAIU de" in texto:                                   # 27/11: operação fechada → o Juiz é acordado para escrever a lição
        acordar("treinador", f"pump.fun: {texto[:200]}. Escreva a lição em pump/licoes_memes.md.", f"pump {texto[:60]}")
    e["eventos"].append({"t": time.time(), "texto": texto})
    print(time.strftime("%H:%M:%S"), texto, flush=True)


def patrimonio(e, px):
    """Abertas pelo preço de agora; sem preço, pelo último lido (nunca pelo de entrada, que esconderia perda ou ganho)."""
    tot = e["caixa"]
    for m, p in e["abertas"].items():
        preco = px[p["curva"]][0] if p["curva"] in px else ((e["hist"].get(m) or [[0, p["entrada"]]])[-1][1])
        tot += p["qtd"] * preco * e.get("sol", 0) * (1 - CUSTO_LADO)
    return tot


def sair(e, px, agora):
    sol = e.get("sol") or 0
    for m, p in list(e["abertas"].items()):
        if p["curva"] not in px:                            # a conta da curva sumiu: a moeda graduou e a curva foi fechada
            p["sem_curva"] = p.get("sem_curva", 0) + 1
            if p["sem_curva"] >= 3:
                h = e["hist"].get(m) or [[0, p["entrada"]]]
                ult = h[-1][1]
                valor = p["qtd"] * ult * sol * (1 - CUSTO_LADO)
                res = valor - p["usd"]
                e["caixa"] += valor
                e["fechadas"].append({**p, "mint": m, "saida": ult, "saida_t": agora, "resultado": round(res, 4),
                                      "motivo_saida": "curva fechada (graduou): sai no último preço lido"})
                del e["abertas"][m]
                anotar(e, f"{'✅' if res > 0 else '❌'} SAIU de {p['simbolo']}: {res:+.3f} US$ ({ult / p['entrada'] - 1:+.1%}, curva fechada / graduou)")
            continue
        p["sem_curva"] = 0
        preco, graduada = px[p["curva"]][:2]
        var = preco / p["entrada"] - 1
        p["pico"] = max(p.get("pico", 0.0), var)
        motivo = None
        if graduada:
            motivo = "graduou (saiu da curva)"
        elif m in e.get("sair_ja", {}):
            motivo = f"Memes mandou sair: {e['sair_ja'].pop(m)}"
        elif var <= -p.get("stop", STOP):
            motivo = f"stop −{p.get('stop', STOP):.0%}"
        elif var >= p.get("alvo", ALVO):
            motivo = f"alvo +{p.get('alvo', ALVO):.0%}"
        elif p["pico"] >= p.get("arma", ARMA) and var <= p.get("guarda", GUARDA) * p["pico"]:
            motivo = f"stop móvel (pico +{p['pico']:.0%})"
        elif agora - p["t"] > p.get("prazo_min", PRAZO_MIN) * 60:
            motivo = f"prazo {p.get('prazo_min', PRAZO_MIN)} min"
        if motivo:
            valor = p["qtd"] * preco * sol * (1 - CUSTO_LADO)
            res = valor - p["usd"]
            e["caixa"] += valor
            e["fechadas"].append({**p, "mint": m, "saida": preco, "saida_t": agora, "resultado": round(res, 4), "motivo_saida": motivo})
            del e["abertas"][m]
            anotar(e, f"{'✅' if res > 0 else '❌'} SAIU de {p['simbolo']}: {res:+.3f} US$ ({var:+.1%}, {motivo})")



def volta(e):
    agora = time.time()
    moedas = {}
    # 26/11: a API recusa (429) duas leituras seguidas; uma lista por volta, alternando, e espera crescente depois de recusa
    if agora >= e.get("api_livre_t", 0):
        q = ("sort=last_trade_timestamp&order=DESC", "sort=market_cap&order=DESC")[e.get("api_vez", 0) % 2]
        e["api_vez"] = e.get("api_vez", 0) + 1
        try:
            for x in _get(f"{API}&{q}"):
                if isinstance(x, dict) and x.get("bonding_curve") and not x.get("is_banned"):
                    e.setdefault("conhecidas", {})[x["mint"]] = {k: x.get(k) for k in ("mint", "bonding_curve", "associated_bonding_curve", "symbol", "name", "created_timestamp")}
            e["api_espera"] = 0
        except Exception as ex:
            e["api_espera"] = min(600, max(60, 2 * e.get("api_espera", 0)))
            e["api_livre_t"] = agora + e["api_espera"]
            print(f"descoberta falhou ({ex}); espero {e['api_espera']} s", flush=True)
    e["sol"] = sol_usd()
    e["curva"].append([round(agora), round(e.get("patrimonio") or e["caixa"], 4)])
    e["curva"] = e["curva"][-3000:]


def entrar(e, moedas, px, agora):
    """v3 scalper: impulso de +4% em 2 min, ainda subindo, sem salto vertical, curva entre 25% e 95%, 10 maiores ≤ 30%."""
    sol = e.get("sol") or 0
    if not sol or len(e["abertas"]) >= MAX_POS or e["caixa"] < POS_USD:
        return
    recentes = {x["mint"] for x in e["fechadas"] if agora - x["saida_t"] < ESFRIA_S}
    vetadas = e.setdefault("vetadas", {})
    cands = []
    for m, x in moedas.items():
        if m in e["abertas"] or m in recentes or x["bonding_curve"] not in px or agora - vetadas.get(m, 0) < 600:
            continue
        preco, graduada, prog = px[x["bonding_curve"]]
        idade = (agora * 1000 - float(x.get("created_timestamp") or 0)) / 60000
        if graduada or idade < IDADE_MIN or not (PROG_MIN <= prog <= PROG_MAX):
            continue
        h = e["hist"].get(m, [])
        jan = [v for t, v in h if agora - t <= JANELA_S + 3]
        j1 = [v for t, v in h if agora - t <= 63]
        if len(jan) < 0.6 * JANELA_S / RAPIDO_S or len(j1) < 6:
            continue
        sub, salto = jan[-1] / jan[0] - 1, j1[-1] / min(j1) - 1
        if SUBIDA_MIN <= sub <= SUBIDA_MAX and salto <= SALTO_1M_MAX and jan[-1] >= jan[-2] and jan[-1] >= 0.97 * max(jan):
            cands.append((sub, m, x, preco, preco * sol * 1e9, prog))
    for sub, m, x, preco, mcap, prog in sorted(cands, reverse=True)[:2]:
        if len(e["abertas"]) >= MAX_POS or e["caixa"] < POS_USD:
            break
        top = top10(m, x.get("associated_bonding_curve"))
        if top is not None and top > TOP10_MAX:
            vetadas[m] = agora
            anotar(e, f"⛔ {x.get('symbol')}: 10 maiores carteiras com {top:.0%} do suprimento; não entra")
            continue
        # a Solana pública recusa (429) a consulta de maiores carteiras quase sempre: sem resposta, entra marcado "sem checagem" (H81 mede)
        qtd = POS_USD * (1 - CUSTO_LADO) / (preco * sol)
        e["caixa"] -= POS_USD
        e["abertas"][m] = {"simbolo": x.get("symbol"), "curva": x["bonding_curve"], "entrada": preco, "qtd": qtd, "usd": POS_USD, "t": agora,
                           "criada_ms": x.get("created_timestamp"), "mcap_entrada": round(mcap), "pico": 0.0, "versao": "v3", "top10": top,
                           "motivo": f"scalper: +{sub:.1%} em 2 min, curva {prog:.0%}, 10 maiores {'sem checagem' if top is None else f'{top:.0%}'}, mercado US$ {mcap:,.0f}"}
        anotar(e, f"🟢 ENTROU em {x.get('symbol')} (papel, scalper): US$ {POS_USD:.2f}, +{sub:.1%} em 2 min, curva {prog:.0%}, 10 maiores {'sem checagem' if top is None else f'{top:.0%}'}, mercado US$ {mcap:,.0f}")
    for m in [m for m, t in vetadas.items() if agora - t > 3600]:
        vetadas.pop(m)


def _var(h, agora, seg):
    """Variação do último preço contra o preço de `seg` segundos atrás (None sem histórico suficiente)."""
    antes = [v for t, v in h if agora - t >= seg - 3]
    return None if not antes or not h else h[-1][1] / antes[-1] - 1


def montar_candidatos(e, agora):
    """Engenharia de dados do Memes: características por moeda, de fontes conferidas, para ele decidir com tese."""
    sol = e.get("sol") or 0
    base = []
    for m, h in e["hist"].items():
        x = (e.get("conhecidas") or {}).get(m) or e["info"].get(m) or {}
        if m in e["abertas"] or len(h) < 12 or agora - h[-1][0] > 30 or m in e.get("graduadas", {}):
            continue
        if not 25 <= h[-1][1] * 1e9 <= 500:             # curva ativa vale ~28 a ~420 SOL; fora disso a leitura é inválida (graduada, outro formato)
            continue
        idade = (agora * 1000 - float(x.get("created_timestamp") or x.get("criada_ms") or 0)) / 60000
        v1, v5, v15 = _var(h, agora, 60), _var(h, agora, 300), _var(h, agora, 900)
        pico = max(v for t, v in h if agora - t <= 900)
        base.append({"mint": m, "simbolo": x.get("symbol") or x.get("simbolo"), "idade_min": round(idade, 1),
                     "preco_sol": h[-1][1], "mercado_usd": round(h[-1][1] * sol * 1e9),
                     "var_1m": None if v1 is None else round(v1, 4), "var_5m": None if v5 is None else round(v5, 4),
                     "var_15m": None if v15 is None else round(v15, 4), "queda_do_pico_15m": round(h[-1][1] / pico - 1, 4)})
    for m in [m for m, t in e.get("graduadas", {}).items() if agora - t > 86400]:
        e["graduadas"].pop(m)
    # ordem: as que estão vivas e subindo primeiro (perto do pico de 15 min, 5 min positivo); as mortas descem
    base.sort(key=lambda c: (c["queda_do_pico_15m"] > -0.25, (c["var_5m"] or 0) > 0, abs(c["var_5m"] or 0)), reverse=True)
    base = base[:30]
    try:
        dex = {d["baseToken"]["address"]: d for d in _get(DEX + ",".join(c["mint"] for c in base)) if d.get("baseToken")} if base else {}
    except Exception as ex:
        dex = {}
        print(f"DexScreener falhou: {ex}", flush=True)
    for c in base:
        d = dex.get(c["mint"]) or {}
        tx = d.get("txns") or {}
        m5, h1 = tx.get("m5") or {}, tx.get("h1") or {}
        info = d.get("info") or {}
        c.update({"compras_5m": m5.get("buys"), "vendas_5m": m5.get("sells"), "compras_1h": h1.get("buys"), "vendas_1h": h1.get("sells"),
                  "volume_5m_usd": (d.get("volume") or {}).get("m5"), "volume_1h_usd": (d.get("volume") or {}).get("h1"),
                  "redes": sorted({s.get("type") for s in info.get("socials") or []} | ({"site"} if info.get("websites") else set())),
                  "impulsionada": bool(d.get("boosts")), "dex": d.get("dexId"), "mercado_dex_usd": d.get("marketCap")})
        sinais = []
        if c["compras_5m"] is not None and c["vendas_5m"] is not None and c["vendas_5m"] > c["compras_5m"]:
            sinais.append("mais vendas que compras em 5 min")
        if (c["queda_do_pico_15m"] or 0) < -0.25:
            sinais.append("caiu > 25% do pico de 15 min")
        if (c["var_1m"] or 0) > 0.25:
            sinais.append("salto > 25% em 1 min (topo provável)")
        if c["idade_min"] < 5:
            sinais.append("< 5 min de vida (snipers e criador ainda vendendo)")
        if not c["redes"]:
            sinais.append("sem redes sociais")
        md = c.get("mercado_dex_usd")
        if md and not 0.5 <= md / max(1, c["mercado_usd"]) <= 2:
            sinais.append(f"Solana e DexScreener divergem no mercado (US$ {c['mercado_usd']:,} × {md:,.0f}): dado duvidoso, não opere")
        c["alertas"] = sinais
    CANDIDATOS.write_text(json.dumps({"t": agora, "sol_usd": sol, "caixa": round(e["caixa"], 4), "abertas": len(e["abertas"]),
                                      "vagas": MAX_POS - len(e["abertas"]), "candidatas": base[:15]}, ensure_ascii=False, indent=1))


def _ler_ordens(e):
    feitas = set(e.setdefault("ordens_vistas", []))
    novas = []
    try:
        for l in ORDENS.read_text().splitlines():
            if l.strip():
                o = json.loads(l)
                if o.get("id") not in feitas:
                    novas.append(o)
    except (OSError, ValueError):
        pass
    return novas


def _fim_ordem(e, o, estado, texto):
    e["ordens_vistas"] = (e.get("ordens_vistas", []) + [o["id"]])[-500:]
    e.setdefault("ordens_log", []).append({"id": o["id"], "t": time.time(), "mint": o.get("mint"), "simbolo": o.get("simbolo"),
                                           "estado": estado, "texto": texto, "tese": o.get("tese")})
    e["ordens_log"] = e["ordens_log"][-100:]
    anotar(e, f"{'🟢' if estado == 'executada' else '⏹'} ordem {o['id']} {o.get('simbolo')}: {estado} — {texto}")


def executar_ordens(e, moedas, px, agora):
    """Executa as ordens do Memes. Compra: só se o preço estiver entre gatilho e teto (relativos ao preço da ordem) e dentro da validade."""
    sol = e.get("sol") or 0
    espera = e.setdefault("ordens_pendentes", {})
    for o in _ler_ordens(e):
        if o.get("tipo") == "sair":
            if o.get("mint") in e["abertas"]:
                e.setdefault("sair_ja", {})[o["mint"]] = o.get("tese") or "sem motivo"
                _fim_ordem(e, o, "executada", "saída na próxima leitura")
            else:
                _fim_ordem(e, o, "recusada", "não há posição aberta")
        elif o["id"] not in espera:
            espera[o["id"]] = o
    for oid, o in list(espera.items()):
        m = o["mint"]
        x = moedas.get(m) or {"bonding_curve": (e["info"].get(m) or {}).get("curva")}
        c = x.get("bonding_curve")
        if agora - o["t"] > o["validade_min"] * 60:
            espera.pop(oid); _fim_ordem(e, o, "expirou", f"o preço não ficou entre gatilho e teto em {o['validade_min']} min"); continue
        if m in e["abertas"]:
            espera.pop(oid); _fim_ordem(e, o, "recusada", "já há posição nessa moeda"); continue
        if not c or c not in px or not sol:
            continue
        preco, graduada, prog = px[c]
        if graduada:
            espera.pop(oid); _fim_ordem(e, o, "recusada", "a moeda graduou"); continue
        var = preco / o["preco_ref"] - 1
        if var > o["teto"]:
            if o.get("cancelar_acima", True):
                espera.pop(oid); _fim_ordem(e, o, "cancelada", f"preço {var:+.1%} acima do teto {o['teto']:+.0%} (não persegue topo)")
            continue
        if var < o["gatilho"]:
            continue
        usd = min(float(o["usd"]), POS_USD * 1.5)
        if len(e["abertas"]) >= MAX_POS or e["caixa"] < usd:
            espera.pop(oid); _fim_ordem(e, o, "recusada", f"sem vaga ou caixa (abertas {len(e['abertas'])}/{MAX_POS}, caixa US$ {e['caixa']:.2f})"); continue
        qtd = usd * (1 - CUSTO_LADO) / (preco * sol)
        e["caixa"] -= usd
        e["abertas"][m] = {"simbolo": o.get("simbolo"), "curva": c, "entrada": preco, "qtd": qtd, "usd": usd, "t": agora,
                           "criada_ms": x.get("created_timestamp"), "mcap_entrada": round(preco * sol * 1e9), "pico": 0.0, "versao": "v4 Memes",
                           "stop": o["stop"], "alvo": o["alvo"], "arma": o["arma"], "guarda": o["guarda"], "prazo_min": o["prazo_min"],
                           "ordem": oid, "conf": o.get("conf"), "motivo": f"Memes ({o.get('conf')}): {o.get('tese')}"}
        espera.pop(oid)
        _fim_ordem(e, o, "executada", f"comprou US$ {usd:.2f} a {var:+.1%} do preço da ordem; stop −{o['stop']:.0%}, alvo +{o['alvo']:.0%}, prazo {o['prazo_min']} min")


def main():
    global ACORDAR_LIGADO
    ACORDAR_LIGADO = True
    e = carregar()
    proxima, ultimo = 0.0, time.time()
    while True:
        t0 = time.time()
        if t0 - ultimo > 120:                          # 27/11: máquina dormiu; anota (o painel mostra nos eventos)
            anotar(e, f"⏸ a máquina dormiu {(t0 - ultimo) / 60:.0f} min: sem preço nem vigia nesse tempo")
        ultimo = t0
        try:
            if t0 >= proxima:
                volta(e)
                proxima = time.time() + CICLO_S
            vigiar(e)
            if time.time() - e.get("pacote_t", 0) >= PACOTE_S:
                try:
                    montar_candidatos(e, time.time())
                except Exception as ex:
                    print(f"candidatos falhou: {type(ex).__name__}: {ex}", flush=True)
                e["pacote_t"] = time.time()
            salvar(e)
        except Exception as ex:
            print(f"erro: {type(ex).__name__}: {ex}", flush=True)
        time.sleep(max(1, RAPIDO_S - (time.time() - t0)))


if __name__ == "__main__":
    main()
