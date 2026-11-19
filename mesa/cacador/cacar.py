"""Ferramenta do agente Caçador (H68, 19/11): ele NÃO opera; caça oportunidades e avisa os operadores.

Uso (sempre com python3 -I):
  python3 -I cacar.py ler                  → oportunidades da nuvem (dados/oportunidades.json do ramo `estado`), placar do juiz H68, listagens novas,
                                              memecoins de DEX (só informação) e a leitura de 1 s a 1 dia das 8 melhores (multitempo.py)
  python3 -I cacar.py publicar <arq.json>  → valida as confirmadas, grava em ../oportunidades_cacador.jsonl e imprime o texto do aviso
  python3 -I cacar.py placar               → só o placar do juiz H68 (por sinal e horizonte, com o controle aleatório)
Proposta para publicar: {"confirmadas": [{"moeda": "XUSDT", "lado": "compra|venda", "sinal": "explosao_5m", "entrada": preço, "stop_pct", "alvo_pct",
"max_min", "validade_min", "forca", "motivo"}]}. Alvo ≥ 3 × o stop e ≥ 1% (decisão do dono, 19/11). Nada de dinheiro real, nenhuma chave.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CLONE = AQUI / "clone"
SAIDA = AQUI.parent / "oportunidades_cacador.jsonl"
REMOTO = "https://github.com/mathhMadureira/baleias.git"
REPETE_S, MAX_AVISOS = 30 * 60, 3
sys.path.insert(0, str(AQUI.parent / "operar"))


def git(*a, check=True):
    return subprocess.run(["git", "-C", str(CLONE), *a], capture_output=True, text=True, timeout=120, check=check)


def estado():
    """oportunidades.json mais novo do ramo `estado` (clone raso; clone quebrado é guardado de lado e refeito)."""
    if not (CLONE / ".git").exists():
        subprocess.run(["git", "clone", "-q", "--single-branch", "--branch", "estado", "--depth", "5", REMOTO, str(CLONE)], check=True, timeout=300)
    try:
        git("fetch", "-q", "--depth", "5", "origin", "estado")
        git("reset", "-q", "--hard", "origin/estado")
    except subprocess.CalledProcessError:
        os.replace(CLONE, CLONE.with_name(f"clone.corrompido-{int(time.time())}"))
        return estado()
    try:
        return json.loads((CLONE / "dados" / "oportunidades.json").read_text())
    except (OSError, ValueError):
        return {}


def tabela_placar(j):
    linhas = ["| sinal | horizonte | n | média | t (por hora) | blocos | acerto | controle ok | passa |", "|---|---|---|---|---|---|---|---|---|"]
    for tipo in sorted(j, key=lambda x: (x == "controle", x)):
        for h, x in sorted(j[tipo].items(), key=lambda kv: int(kv[0])):
            linhas.append(f"| {tipo} | {h} min | {x['n']} | {x['media_pct']:+.3f}% | {x['t']} | {x['blocos_pct']} | {x['acerto']:.0%} | "
                          f"{'✓' if x.get('controle_ok') else '—'} | {'✓' if x.get('passa') else '—'} |")
    return "\n".join(linhas)


def cmd_placar(e=None):
    e = e if e is not None else estado()
    j = e.get("juiz_h68") or {}
    print("JUIZ H68 (retorno no lado sugerido − 0,12%; passa com n ≥ 300, média > 0, t ≥ 2,69, 2 de 3 blocos e controle ≈ −0,12%):")
    print(tabela_placar(j) if j else "ainda sem eventos resolvidos (o primeiro sai 15 min depois do primeiro sinal)")
    return j


def cmd_ler():
    e = estado()
    if not e:
        raise SystemExit("ERRO: dados/oportunidades.json ainda não existe no ramo estado (a nuvem não rodou o Caçador)")
    idade = int(time.time() - e.get("t", 0))
    u = e.get("universo") or {}
    print(f"VARREDURA DA NUVEM de {idade} s atrás: {u.get('lidas_1m')} de {u.get('universo')} pares USDT lidos em 1 min "
          f"({u.get('pares_usdt_negociando')} negociando), {u.get('candidatas_15m_1h')} em 15 min e 1 h, {u.get('sinais_rodada')} sinais, {u.get('segundos')} s")
    if idade > 900:
        print("⚠️ varredura com mais de 15 min: a nuvem pode estar parada; não publique oportunidade nova com esse dado")
    ops = e.get("oportunidades") or []
    print("\n| # | moeda | lado | sinal | força | gatilho | invalidação | sugestão stop/alvo/prazo | MM20 a favor (15m 1h 4h) | 1 h | 24 h | meme | nova |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, o in enumerate(ops[:15], 1):
        s = o.get("sugestao") or {}
        print(f"| {i} | {o['moeda']} | {o['lado']} | {o['tipo']} | {o['forca']} | {o['gatilho']} | {o.get('invalidacao'):.6g} | "
              f"{s.get('stop_pct', 0):.2%} / {s.get('alvo_pct', 0):.2%} / {s.get('max_min')} min | {o.get('tempos_mm20_a_favor')} | {o.get('var_1h')}% | "
              f"{o.get('var_24h')}% | {'✓' if o.get('meme') else ''} | {'✓' if o.get('nova_listagem') else ''} |")
    nl = e.get("novas_listagens") or []
    print("\nLISTAGENS NOVAS na Binance (72 h):", ", ".join(f"{x['par']} ({time.strftime('%d/%m %H:%M', time.gmtime(x['desde_t']))} UTC)" for x in nl) or "nenhuma")
    d = e.get("dex") or {}
    print(f"\nMEMECOINS DE DEX (só informação; os operadores operam a Binance): {d.get('lidos', 0)} pares lidos, {len(d.get('aprovados') or [])} passaram nos filtros")
    for x in (d.get("aprovados") or [])[:8]:
        print(f"- {x.get('simbolo')} ({x.get('rede')}, {x.get('fonte')}): liquidez US$ {x.get('liquidez'):,.0f}, {x.get('idade_min')} min, 1 h: "
              f"{x.get('compras_1h')} compras / {x.get('vendas_1h')} vendas, volume US$ {x.get('volume_1h'):,.0f}, {x.get('var_1h')}%")
    print()
    cmd_placar(e)
    import multitempo as MT
    alvos = [o["par"] for o in sorted(ops, key=lambda o: -o["forca"])][:8]
    vt = MT.varrer(alvos, max_moedas=8)
    print(f"\nLEITURA DE 1 s A 1 DIA das {len(vt)} mais fortes (multitempo.py; moeda sem dado fica fora):")
    print(MT.tabela(vt))
    (AQUI / "rodadas").mkdir(exist_ok=True)
    (AQUI / "rodadas" / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-leitura.json").write_text(json.dumps({"t": int(time.time()), "oportunidades": ops[:15],
                                                                                                                "varredura": vt}, ensure_ascii=False))


def validar(c):
    erros = []
    m = str(c.get("moeda", "")).upper()
    if not m.endswith("USDT") or c.get("lado") not in ("compra", "venda") or not str(c.get("motivo", "")).strip():
        return [f"inválida (moeda, lado, motivo): {c}"]
    for k, lo, hi in (("stop_pct", 0.003, 0.04), ("alvo_pct", 0.01, 0.05), ("max_min", 5, 1440), ("validade_min", 5, 240), ("forca", 0, 100)):
        if not isinstance(c.get(k), (int, float)) or not lo <= c[k] <= hi:
            erros.append(f"{m}: {k} = {c.get(k)!r} fora de {lo}–{hi}")
    if isinstance(c.get("stop_pct"), (int, float)) and isinstance(c.get("alvo_pct"), (int, float)) and c["alvo_pct"] + 1e-9 < 3 * c["stop_pct"]:
        erros.append(f"{m}: alvo {c['alvo_pct']} menor que 3 × o stop {c['stop_pct']} (regra do dono, 19/11)")
    if not isinstance(c.get("entrada"), (int, float)) or c["entrada"] <= 0:
        erros.append(f"{m}: falta o preço de entrada")
    return erros


def cmd_publicar(arq):
    d = json.loads(Path(arq).read_text())
    cs = d.get("confirmadas") or []
    erros = [x for c in cs for x in validar(c)]
    if erros:
        raise SystemExit("PROPOSTA INVÁLIDA (nada publicado):\n- " + "\n- ".join(erros))
    agora = int(time.time())
    antigas = []
    if SAIDA.exists():
        for l in SAIDA.read_text().splitlines():
            try:
                antigas.append(json.loads(l))
            except ValueError:
                continue
    recentes = {(x["moeda"], x["lado"]) for x in antigas if agora - x.get("t", 0) < REPETE_S}
    novas = [c for c in cs if (str(c["moeda"]).upper(), c["lado"]) not in recentes][:MAX_AVISOS]
    with SAIDA.open("a") as f:
        for c in novas:
            f.write(json.dumps({"t": agora, **c, "moeda": str(c["moeda"]).upper(), "valida_ate": agora + 60 * c["validade_min"]}, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    if not novas:
        print("nada novo para avisar (vazio ou repetido nos últimos 30 min)")
        return
    print(f"ok: {len(novas)} oportunidade(s) publicada(s) em {SAIDA}")
    print("AVISO (mande este texto aos operadores):")
    print("🔭 Caçador — " + " | ".join(
        f"{c['moeda'][:-4]} {c['lado'].upper()} a {c['entrada']:.6g} (sinal {c.get('sinal', '?')}, força {c['forca']}): stop {c['stop_pct']:.2%}, "
        f"alvo {c['alvo_pct']:.2%}, prazo {c['max_min']} min, vale {c['validade_min']} min. {str(c['motivo'])[:220]}" for c in novas)
        + " — Operador: rode AGORA a sua rotina de operar (/home/servidor-de-producao/OpenBot/Shared/baleias/operar/ROTINA.md, passos 1 a 4) e entre a mercado se a SUA leitura confirmar; o Caçador não opera e não decide por você.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["ler"]:
        cmd_ler()
    elif sys.argv[1:2] == ["placar"]:
        cmd_placar()
    elif sys.argv[1:2] == ["publicar"] and len(sys.argv) == 3:
        cmd_publicar(sys.argv[2])
    else:
        raise SystemExit(__doc__)
