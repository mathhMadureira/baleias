"""Análise do universo inteiro para o chefe (H59, emenda de 18/11): todas as moedas que o v4 prevê, nos dois lados.

Uso: python3 -I universo.py      → imprime as tabelas (10 melhores compras, 10 melhores vendas, memecoins × LBank), a escolha e o porquê,
                                    e grava rodadas/<hora>-universo.json (a escolha vai em "escolha"; ninguém a muda à mão).
Fontes (só públicas, só leitura): dados/cerebro_v4.json do ramo `estado` (probabilidade de subir de cada moeda na última vela fechada),
velas de 15 min da Binance à vista (data-api.binance.vision), ticker de 24 h, regras dos futuros do testnet, preços do perpétuo da LBank.
Regra de escolha (pré-registrada na emenda da H59, lab/PROTOCOLO_LAB.md):
  ordem = confiança do v4 no lado (|p − 0,5|, achado H36); entra só com confiança ≥ 0,12 (19/11; antes 0,08), no lado do regime de 24 h (H44; neutro: os dois),
  fora de moeda esticada (|4 h| ≥ 15%), que exista nos futuros do testnet com nocional mínimo ≤ 1,5 × a posição, no máximo 1 de BTC/ETH;
  mantém as abertas enquanto o regime não virar contra e o v4 não apontar o lado oposto com confiança ≥ 0,12 (19/11; antes 0,03); completa até 4. Abaixo de 0,12: "sem confiança", nunca motivo de descarte.
"""
import json
import os
import urllib.error
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

REPO = Path("/home/servidor-de-producao/baleias")
sys.path.insert(0, str(REPO))
from executor import regime as RG  # noqa: E402

AQUI = Path(__file__).resolve().parent
EST = AQUI / "estado"
DADOS = "https://data-api.binance.vision"
TESTNET = "https://testnet.binancefuture.com"
# 19/11 (dono: "o v4 está barrando as entradas do Caçador"; reestruturado pelo Engenheiro): o v4 só pesa com confiança ≥ 0,12, para entrar E para
# fechar. Abaixo disso é "sem confiança" na tabela: não é observação que bloqueia, não fecha posição e não é motivo de descarte.
CONF_ENTRA, CONF_CONTRA, ESTICADA, MAX_POS, MAX_NOC = 0.12, 0.12, float("inf"), 8, 1.5   # R2: sem corte de 15%, 8 posições
GRUPOS = [{"BTCUSDT", "ETHUSDT"}]
MEMES = ["DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "BRETT", "POPCAT", "FARTCOIN", "PNUT", "PENGU", "TRUMP", "MEME", "NEIRO", "TURBO"]
ALIAS = {f"{m}USDT": f"1000{m}USDT" for m in ("PEPE", "SHIB", "BONK", "FLOKI", "LUNC", "XEC", "SATS", "RATS", "CAT", "WHY", "CHEEMS", "X")}


# Auditoria 19/11 (A16): a rodada do chefe das 16:20 UTC passou 27 min só aqui. Prazo TOTAL do script (cada chamada já tinha timeout, a soma não):
# estourou = segue com o que já leu, marcado como PARCIAL (as moedas lidas por inteiro valem, rotina r12; menos de 50 = ERRO, como antes).
PRAZO_S = float(os.environ.get("UNIVERSO_PRAZO_S", "360"))
INICIO = time.time()


def resta():
    return PRAZO_S - (time.time() - INICIO)


def ler_com_prazo(func, itens, prazo_s, n=8):
    """func(item) → (chave, valor) em paralelo, até prazo_s segundos no total. Devolve ({chave: valor} dos que terminaram, [itens que faltaram]).
    Os que não terminaram são abandonados (não seguram o resto da rodada)."""
    ex = ThreadPoolExecutor(n)
    fut = {ex.submit(func, i): i for i in itens}
    feitos, _ = wait(fut, timeout=max(0.0, prazo_s))
    ex.shutdown(wait=False, cancel_futures=True)
    out = {}
    for f in feitos:
        try:
            k, v = f.result()
            out[k] = v
        except Exception:
            continue
    return out, [fut[f] for f in fut if f not in feitos]


def com_prazo(func, prazo_s, padrao):
    """func() com prazo; estourou ou falhou = (padrao, True)."""
    if prazo_s <= 0:
        return padrao, True
    r, faltou = ler_com_prazo(lambda _: ("x", func()), [0], prazo_s, n=1)
    return (r["x"], False) if "x" in r else (padrao, True)


def _get(url, t=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "baleias/1.0"}), timeout=t) as r:
        return json.load(r)


def estado(nome):
    subprocess.run(["git", "-C", str(EST), "fetch", "-q", "--depth", "60", "origin", "estado"], capture_output=True, timeout=120)
    r = subprocess.run(["git", "-C", str(EST), "show", f"origin/estado:dados/{nome}"], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout else {}


FALHAS = {}                                   # {par: motivo da última falha} — antes o erro era engolido e virava "0 moedas" sem causa
VELAS_MIN_S = 120                             # as velas são a parte essencial: têm pelo menos 2 min, mesmo se o começo da rodada demorou


def velas(par, tentativas=3):
    """Velas de 15 min fechadas. Rede falhou = tenta de novo (até 3 vezes, com pausa curta) e guarda o motivo em FALHAS[par]."""
    for i in range(tentativas):
        try:
            k = [x for x in _get(f"{DADOS}/api/v3/klines?symbol={par}&interval=15m&limit=98", t=20) if x[6] < time.time() * 1000]
            FALHAS.pop(par, None)
            return par, k
        except urllib.error.HTTPError as ex:
            FALHAS[par] = f"HTTP {ex.code}"
            if ex.code in (418, 429):                 # limite de peso da Binance: não insiste nesta rodada
                break
        except (OSError, ValueError) as ex:
            FALHAS[par] = type(ex).__name__
        time.sleep(1 + 2 * i)
    return par, []


def resumo_falhas(faltaram, pares):
    """Texto com a causa: quantas moedas por motivo (rede, HTTP, prazo)."""
    from collections import Counter
    c = Counter(FALHAS.get(p, "?") for p in pares if p in FALHAS)
    if faltaram:
        c["prazo da rodada"] += len(faltaram)
    return ", ".join(f"{n} × {m}" for m, n in c.most_common()) or "nenhuma falha de rede registrada"


def medir(k):
    if len(k) < 97:
        return None
    c = [float(x[4]) for x in k]
    v = [float(x[7]) for x in k]                      # volume em US$
    vol4, media4 = sum(v[-16:]), sum(v[-96:]) / 6
    return {"1h": round((c[-1] / c[-5] - 1) * 100, 2), "4h": round((c[-1] / c[-17] - 1) * 100, 2), "24h": round((c[-1] / c[-97] - 1) * 100, 2),
            "vol4h": round(vol4 / media4, 2) if media4 else None, "preco": c[-1]}


def main():
    v4 = estado("cerebro_v4.json")
    ult = v4.get("ultima") or {}
    if len(ult) < 50:                             # a nuvem às vezes cai para as 33 de reserva (exchangeInfo lento): usa a rodada mais nova
        log = subprocess.run(["git", "-C", str(EST), "log", "--format=%h %ct", "-15", "origin/estado", "--", "dados/cerebro_v4.json"],
                             capture_output=True, text=True).stdout.split("\n")
        for linha in log:                         # com o universo completo, de no máximo 15 min (o v4 prevê a vela de 15 min)
            if not linha.strip():
                continue
            h, ct = linha.split()
            if time.time() - int(ct) > 900:
                break
            u = json.loads(subprocess.run(["git", "-C", str(EST), "show", f"{h}:dados/cerebro_v4.json"], capture_output=True, text=True).stdout).get("ultima") or {}
            if len(u) >= 100:
                print(f"(a rodada mais nova da nuvem trouxe só {len(ult)} moedas; uso a de {time.strftime('%H:%M', time.gmtime(int(ct)))} UTC, com {len(u)})")
                ult = u
                break
    vela_t = max((x["t"] for x in ult.values()), default=0)
    pares = sorted(ult)
    parcial = []
    k, faltaram = ler_com_prazo(velas, pares, max(VELAS_MIN_S, resta() - 150))   # deixa ~2,5 min para o resto; nunca menos de 2 min para as velas
    sem = [p for p in pares if p not in faltaram and len(k.get(p) or []) < 97]
    if faltaram or sem:
        parcial.append(f"velas de 15 min: {len(faltaram) + len(sem)} de {len(pares)} moedas sem leitura ({resumo_falhas(faltaram, pares)})")
    reg, s24, s4 = RG.de_velas(k)
    lado_reg = RG.lado_permitido(reg)
    try:
        tn = {s["symbol"]: s for s in _get(f"{TESTNET}/fapi/v1/exchangeInfo", t=max(5, min(30, resta() - 90)))["symbols"] if s.get("status") == "TRADING"}
    except (OSError, ValueError):
        tn = {}
        parcial.append("regras do testnet não lidas (moedas aparecem como fora do testnet)")
    eu = estado("robo_openbot_testnet.json")
    caixa_real = float(eu.get("caixa", 10)) + sum(float(p.get("gasto", 0)) for p in (eu.get("abertas") or {}).values())
    noc = 2.5 * caixa_real
    linhas = []
    for par in pares:
        m = medir(k.get(par) or [])
        if not m:
            continue
        p = float(ult[par]["prob"])
        s = ALIAS.get(par, par)
        regras = tn.get(s)
        minimo = None
        if regras:
            f = {x["filterType"]: x for x in regras["filters"]}
            minimo = float(f.get("MIN_NOTIONAL", {}).get("notional", 5))
        linhas.append({"moeda": par[:-4], "par": par, "prob": round(p, 4), **m, "testnet": bool(regras), "min_nocional": minimo})
    if len(linhas) < 50:                          # sem o universo lido não há escolha: mantém tudo como está e avisa
        raise SystemExit(f"ERRO: só {len(linhas)} moedas com velas lidas (de {len(pares)}; causa: {resumo_falhas(faltaram, pares)}; "
                         f"{round(time.time() - INICIO)} s); sem análise, sem escolha nesta rodada")
    abertas = (eu.get("abertas") or {})
    manter, motivos = [], {}
    for par, a in abertas.items():
        l = next((x for x in linhas if x["par"] == par), None)
        contra = l and ((l["prob"] <= 0.5 - CONF_CONTRA) if a["lado"] == "compra" else (l["prob"] >= 0.5 + CONF_CONTRA))
        if lado_reg and lado_reg != a["lado"]:
            motivos[par] = f"fecha: regime de 24 h virou para {reg}"
        elif contra:
            motivos[par] = f"fecha: v4 aponta o lado oposto com confiança ≥ 0,12 (p subir {l['prob']:.3f})"
        else:
            manter.append(par)
            motivos[par] = f"mantém: regime {reg or 'neutro'} e v4 não aponta contra (p subir {l['prob'] if l else 'sem dado'})"

    def candidatos(lado):
        out = []
        for l in linhas:
            c = (l["prob"] - 0.5) if lado == "compra" else (0.5 - l["prob"])
            if c <= 0:
                continue
            obs = []
            if abs(l["4h"]) >= ESTICADA:
                obs.append("esticada (|4 h| ≥ 15%)")
            if not l["testnet"]:
                obs.append("não existe no testnet")
            elif l["min_nocional"] and l["min_nocional"] > MAX_NOC * noc:
                obs.append(f"mínimo da corretora US$ {l['min_nocional']:.0f}")
            if c < CONF_ENTRA:
                obs.append("v4 sem confiança (< 0,12): só não entra pela sugestão do v4; não é motivo de descarte")
            if lado_reg and lado_reg != lado:
                obs.append(f"contra o regime ({reg})")
            out.append({**l, "lado": lado, "confianca": round(c, 4), "obs": obs})
        return sorted(out, key=lambda x: -x["confianca"])

    compras, vendas = candidatos("compra"), candidatos("venda")
    escolha = [{"moeda": par, "lado": abertas[par]["lado"], "motivo": motivos[par]} for par in manter]
    usados = set(manter)
    for c in sorted(compras + vendas, key=lambda x: -x["confianca"]):
        if len(escolha) >= MAX_POS:
            break
        if c["obs"] or c["par"] in usados or any(c["par"] in g and usados & g for g in GRUPOS):
            continue
        escolha.append({"moeda": c["par"], "lado": c["lado"],
                        "motivo": (f"v4 {c['prob']:.3f} de subir (confiança {c['confianca']:.3f}, faixa ≥ 0,12 da H36); "
                                   + (f"a favor da tendência de {reg} de 24 h" if reg else "regime neutro, os dois lados valem") + f" ({s24}% subindo); "
                                   f"1 h {c['1h']:+.2f}%, 4 h {c['4h']:+.2f}%, 24 h {c['24h']:+.2f}%, volume 4 h {c['vol4h']}×")})
        usados.add(c["par"])
    try:
        from executor import robo_lbank_nuvem as L
        lb, faltou = com_prazo(L.mercado, min(30, resta() - 90), {})   # só comparação: nunca segura a rodada
        if faltou:
            parcial.append("LBank fora do prazo (comparação de memecoins = não sei)")
    except Exception as ex:                       # LBank fora do ar: a comparação fica "não sei"
        lb, erro_lb = {}, str(ex)[:80]
    memes = []
    for m in MEMES:
        b = next((l for l in linhas if l["moeda"] == m), None)
        x = lb.get(f"{m}USDT")
        if b or x:
            memes.append({"moeda": m, "v4_prob": b and b["prob"], "binance_24h": b and b["24h"], "binance_4h": b and b["4h"],
                          "lbank_preco": x and x[0], "lbank_24h": x and round(x[1] * 100, 2), "binance_preco": b and b["preco"]})
    r = {"t": int(time.time()), "vela_v4_utc": time.strftime("%d/%m %H:%M", time.gmtime(vela_t / 1000 + 900)), "moedas": len(linhas),
         "regime": reg, "subindo_24h": s24, "subindo_4h": s4, "nocional": round(noc, 2), "compras": compras[:10], "vendas": vendas[:10],
         "n_compras": sum(c["confianca"] >= CONF_ENTRA for c in compras), "n_vendas": sum(c["confianca"] >= CONF_ENTRA for c in vendas), "memes": memes, "abertas": motivos, "escolha": escolha}
    (AQUI / "rodadas").mkdir(exist_ok=True)
    (AQUI / "rodadas" / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-universo.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    print(f"Universo: {len(linhas)} moedas · vela do v4 fechada às {r['vela_v4_utc']} UTC · regime {reg or 'neutro'} ({s24}% subindo em 24 h, "
          f"{s4}% em 4 h) · v4 com confiança (≥ 0,12): {r['n_compras']} de compra e {r['n_vendas']} de venda; o resto está SEM CONFIANÇA e não é motivo "
          "de descarte, de corte no REVISOR nem de fechar posição (19/11)")
    for nome, ls in (("COMPRA", compras[:10]), ("VENDA", vendas[:10])):
        print(f"\n| # | {nome} | p subir | confiança | 1 h | 4 h | 24 h | vol 4 h | testnet | observação |\n|---|---|---|---|---|---|---|---|---|---|")
        for i, c in enumerate(ls, 1):
            print(f"| {i} | {c['moeda']} | {c['prob']:.3f} | {c['confianca']:.3f} | {c['1h']:+.2f}% | {c['4h']:+.2f}% | {c['24h']:+.2f}% | "
                  f"{c['vol4h']}× | {'✓' if c['testnet'] else '—'} | {'; '.join(c['obs']) or 'elegível'} |")
    print("\n| memecoin | p subir (v4) | Binance 24 h | LBank 24 h | Binance preço | LBank perp preço |\n|---|---|---|---|---|---|")
    for x in memes:
        f = lambda v, d="": "—" if v is None else f"{v}{d}"
        print(f"| {x['moeda']} | {f(x['v4_prob'])} | {f(x['binance_24h'], '%')} | {f(x['lbank_24h'], '%')} | {f(x['binance_preco'])} | {f(x['lbank_preco'])} |")
    UNIVERSO = {l["par"] for l in linhas}
    cart = estado("carteiras_top.json") or {}         # H63: monitor fomo (as 40 melhores carteiras da Hyperliquid)
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
    sys.path.insert(0, "/home/servidor-de-producao/OpenBot/Shared/baleias/operar")
    import multitempo as MT                                   # 18/11: leitura em todos os tempos gráficos, de 1 s a 1 dia
    alvos = list(abertas) + [c["par"] for c in compras[:4]] + [c["par"] for c in vendas[:4]] + [l["par"] for l in sorted(linhas, key=lambda l: -abs(l["1h"]))[:4]]
    vt, faltou = com_prazo(lambda: MT.varrer(alvos), resta() - 10, [])
    if faltou:
        parcial.append("varredura de 1 s a 1 dia fora do prazo (sem leitura dos tempos nesta rodada)")
    print(f"\nVARREDURA EM TODOS OS TEMPOS (1 s → 1 dia), {len(vt)} moedas")
    print(MT.tabela(vt))
    (AQUI / "rodadas" / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-chefe-varredura.json").write_text(json.dumps(vt, ensure_ascii=False))
    print("\nAbertas:", json.dumps(motivos, ensure_ascii=False))
    print("Escolha:", json.dumps(escolha, ensure_ascii=False, indent=1))
    gasto = round(time.time() - INICIO)
    if parcial:
        print(f"\n⚠️ PARCIAL (prazo de {PRAZO_S:.0f} s; levou {gasto} s): " + "; ".join(parcial)
              + ". Decida só com as moedas lidas por inteiro (rotina r12); o que faltou não entra.")
    else:
        print(f"\n(universo completo em {gasto} s, prazo {PRAZO_S:.0f} s)")


if __name__ == "__main__":
    codigo = 0
    try:
        main()
    except SystemExit as fim:                     # "ERRO: só N moedas..." tem de aparecer (antes do os._exit)
        if fim.code not in (None, 0):
            print(fim.code if isinstance(fim.code, str) else f"saída {fim.code}", file=sys.stderr)
            codigo = 1
    except BaseException:
        import traceback
        traceback.print_exc()
        codigo = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(codigo)                              # leituras abandonadas pelo prazo não seguram o fim do processo (os arquivos já foram gravados)
