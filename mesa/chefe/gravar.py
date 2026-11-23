"""Chefe da mesa (OpenBot) — passos 3 e 4: valida a decisão, grava SÓ dados/decisao_claude.json no ramo `estado` e deixa o recibo.

Uso:
  python3 -I gravar.py decisao.json            → valida, põe t = agora, publica (até 5 tentativas de push) e escreve o recibo
  python3 -I gravar.py --blocked "motivo"      → só escreve um recibo BLOCKED (a rodada falhou 3 vezes)
Nunca toca em outro arquivo do ramo: cada tentativa parte do estado mais novo (fetch + reset para origin/estado) e só copia a decisão.
"""
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EST = AQUI / "estado"
RODADAS = AQUI / "rodadas"
RECIBOS = AQUI / "recibos.jsonl"
RECIBOS_MD = AQUI / "recibos.md"
ARQ = "dados/decisao_claude.json"
OBEDECEM = set()          # 18/11: os robôs foram aposentados; nenhum agente recebe ordem do chefe
ACOES = {"so_vendas", "so_compras", "liberar"}            # pedido do dono (17/11): o chefe não pausa ninguém
TENTATIVAS_PUSH = 5
AUTOR = ["-c", "user.name=chefe-openbot", "-c", "user.email=chefe-openbot@users.noreply.github.com"]
TRAILER = "Co-authored-by: OpenBot <335604065+openbotgit[bot]@users.noreply.github.com>"


def git(*a, check=True):
    r = subprocess.run(["git", "-C", str(EST), *a], capture_output=True, text=True, timeout=120)
    if check and r.returncode:
        raise RuntimeError(f"git {a[0]}: {(r.stderr or r.stdout).strip()[:300]}")
    return r


def validar(d, pendentes):
    """Devolve a lista de problemas (vazia = válida). Não corrige nada sozinho."""
    erros = []
    if not str(d.get("leitura", "")).strip():
        erros.append("falta a leitura")
    if not str(d.get("licao", "")).strip():
        erros.append("falta a lição (cartilha seção 4)")
    pos = d.get("posicoes")
    if not isinstance(pos, list) or len(pos) > 8:                       # R2 (dono, 23/11): até 8 posições
        erros.append("posicoes tem de ser uma lista de 0 a 8")
    else:
        moedas = set()
        for p in pos:
            m = str(p.get("moeda", "")).upper()
            if not m.endswith("USDT") or len(m) < 6:
                erros.append(f"moeda inválida: {m!r}")
            if p.get("lado") not in ("compra", "venda"):
                erros.append(f"lado inválido em {m}: {p.get('lado')!r}")
            if not str(p.get("motivo", "")).strip():
                erros.append(f"sem motivo em {m}")
            if m in moedas:
                erros.append(f"moeda repetida: {m}")
            moedas.add(m)
    if not isinstance(d.get("fechar", []), list) or not isinstance(d.get("motivos_fechar", {}), dict):
        erros.append("fechar tem de ser lista e motivos_fechar dicionário")
    ids = {x["id"] for x in pendentes}
    for r in d.get("respostas", []) or []:
        if r.get("ref") not in ids:
            erros.append(f"resposta para mensagem que não está pendente: {r.get('ref')!r}")
        if not str(r.get("texto", "")).strip():
            erros.append("resposta vazia")
    for x in ids - {r.get("ref") for r in d.get("respostas", []) or []}:
        erros.append(f"mensagem do dono sem resposta: {x}")
    for o in d.get("ordens", []) or []:
        if o.get("agente") not in OBEDECEM:
            erros.append(f"ordem para quem não obedece: {o.get('agente')!r}")
        if o.get("acao") not in ACOES:
            erros.append(f"ação proibida ou desconhecida: {o.get('acao')!r} (só so_vendas, so_compras, liberar)")
        if o.get("acao") != "liberar" and not (1 <= float(o.get("horas", 0) or 0) <= 24):
            erros.append(f"prazo da ordem fora de 1–24 h: {o.get('horas')!r}")
        if not any(c.isdigit() for c in str(o.get("motivo", ""))):
            erros.append(f"ordem sem número do retrato no motivo ({o.get('agente')})")
    for m in d.get("mensagens", []) or []:
        if not str(m.get("texto", "")).strip():
            erros.append("mensagem vazia")
    sys.path.insert(0, "/home/servidor-de-producao/baleias")
    from executor.robo_claude_nuvem import validar_gatilhos               # H67: níveis armados entre as rodadas
    erros += validar_gatilhos(d.get("gatilhos"))
    return erros


def publicar(d):
    """fetch → reset para origin/estado → copia a decisão → commit → push; até TENTATIVAS_PUSH vezes. Devolve (commit, tentativas)."""
    ultimo = ""
    for k in range(1, TENTATIVAS_PUSH + 1):
        try:
            git("fetch", "-q", "--depth", "20", "origin", "estado")
            git("reset", "-q", "--hard", "origin/estado")
            git("clean", "-qfd")
            (EST / ARQ).write_text(json.dumps(d, ensure_ascii=False))
            git("add", ARQ)
            mudou = git("diff", "--cached", "--name-only").stdout.split()
            if mudou != [ARQ]:
                raise RuntimeError(f"o commit mexeria em outros arquivos: {mudou}")
            hm = time.strftime("%H:%M", time.gmtime(d["t"]))
            git(*AUTOR, "commit", "-q", "-m", f"chefe (OpenBot) decidiu {hm}", "-m", TRAILER)
            r = git("push", "-q", "origin", "HEAD:estado", check=False)
            if r.returncode == 0:
                return git("rev-parse", "--short", "HEAD").stdout.strip(), k
            ultimo = (r.stderr or r.stdout).strip()[:300]
        except (RuntimeError, subprocess.SubprocessError, OSError) as ex:
            ultimo = str(ex)[:300]
        time.sleep(3 * k)
    raise RuntimeError(f"push falhou {TENTATIVAS_PUSH} vezes: {ultimo}")


def gravar_atomico(arq, texto):
    """Auditoria 19/11: a máquina desligou no meio de um write_text e deixou rodadas/20261118-231404-decisao.json com 0 byte;
    o testnet.py quebrava ao ler esse arquivo. Agora: arquivo temporário + fsync + troca atômica (nunca fica vazio pela metade)."""
    arq = Path(arq)
    tmp = arq.with_name(arq.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(texto)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, arq)


def ler_json_ok(arq):
    """JSON do arquivo, ou None se vazio/corrompido (desligamento no meio da gravação)."""
    try:
        return json.loads(Path(arq).read_text())
    except (OSError, ValueError):
        return None


def ultima_leitura():
    for arq in sorted(RODADAS.glob("*-leitura.json"), reverse=True):
        d = ler_json_ok(arq)
        if isinstance(d, dict):
            return d
    return {}


def recibo(reg):
    with RECIBOS.open("a") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    leu, dec = reg.get("leu") or {}, reg.get("decidiu") or {}
    linha = (f"\n## {reg['hora_utc']} UTC — {reg['status']}\n"
             f"- leu: estado `{leu.get('commit')}`, retrato {leu.get('retrato')}, 24 h {leu.get('subindo_24h')}% subindo, 4 h {leu.get('subindo_4h')}%, "
             f"BTC 24 h {leu.get('btc_24h')}% (vol {leu.get('btc_vol')}×), guarda do dia {'travada' if leu.get('travado') else 'livre'}, "
             f"{leu.get('pendentes_dono', 0)} mensagem(ns) do dono pendente(s)\n")
    if dec:
        linha += (f"- decidiu: posições {dec.get('posicoes') or 'nenhuma'}; ordens {dec.get('ordens') or 'nenhuma'}; "
                  f"{dec.get('respostas', 0)} resposta(s); {dec.get('mensagens', 0)} mensagem(ns)\n  leitura: {dec.get('leitura')}\n")
    linha += (f"- publicação: commit `{reg['commit']}` em {reg['tentativas']} tentativa(s)\n" if reg["status"] == "ok"
              else f"- **BLOCKED**: {reg.get('motivo')}\n")
    if reg.get("anterior"):
        a = reg["anterior"]
        linha += f"- decisão anterior ({a['decisao_t']}): aplicada pela nuvem = {a['aplicada']}, mensagem na sala = {a['mensagem_na_sala']}\n"
    with RECIBOS_MD.open("a") as f:
        f.write(linha)


def main():
    agora = time.time()
    lei = ultima_leitura()
    m = lei.get("mercado") or {}
    leu = {"commit": lei.get("estado_commit"), "retrato": lei.get("retrato_hora"),
           "subindo_24h": (m.get("mercado_24h") or {}).get("subindo_pct"), "subindo_4h": (m.get("mercado_4h") or {}).get("subindo_pct"),
           "btc_24h": (m.get("btc") or {}).get("24h"), "btc_vol": (m.get("btc") or {}).get("vol_4h_vs_media"),
           "travado": (lei.get("robo_claude") or {}).get("travado_hoje"), "pendentes_dono": len(lei.get("pendentes_do_dono") or [])}
    reg = {"t": int(agora), "hora_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(agora)), "leu": leu, "anterior": lei.get("anterior_do_chefe")}
    if sys.argv[1:2] == ["--blocked"]:
        recibo({**reg, "status": "BLOCKED", "motivo": " ".join(sys.argv[2:])[:500] or "sem motivo", "commit": None, "tentativas": 0})
        print("recibo BLOCKED gravado")
        return 1
    if not lei or agora - float(lei.get("t") or 0) > 900:
        print("ERRO: a leitura tem mais de 15 min (ou não existe); rode ler.py de novo antes de decidir")
        return 2
    d = json.loads(Path(sys.argv[1]).read_text())
    d = {"t": int(agora), **{k: v for k, v in d.items() if k != "t"}}
    d["leitura_t"] = int(float(lei.get("t") or agora))          # 20/11: hora da leitura (o stop pode executar entre a leitura e a publicação)
    for k, padrao in (("fechar", []), ("motivos_fechar", {}), ("respostas", []), ("mensagens", []), ("ordens", [])):
        d.setdefault(k, padrao)
    erros = validar(d, lei.get("pendentes_do_dono") or [])
    vs = sorted(glob.glob(str(RODADAS / "*-chefe-varredura.json")))
    if vs and agora - Path(vs[-1]).stat().st_mtime <= 900 and ler_json_ok(vs[-1]) is not None:
        d["varredura"] = ler_json_ok(vs[-1])                            # leitura de 1 s a 1 dia que embasou a decisão
    sys.path.insert(0, "/home/servidor-de-producao/OpenBot/Shared/baleias")
    import regras as RG_                                                 # REGRAS.md (fonte única, 19/11): campos obrigatórios e cortes duros C2/C3
    erros += RG_.conferir_decisao(d.get("posicoes"), (lei.get("robo_claude") or {}).get("abertas") or {}, d.get("varredura"))
    d["versao_regras"] = RG_.VERSAO
    if erros:
        print("DECISÃO INVÁLIDA (nada publicado):\n- " + "\n- ".join(erros))
        return 3
    dec = {"posicoes": [f"{p['moeda']} {p['lado']}" for p in d["posicoes"]], "ordens": [f"{o['agente']} {o['acao']}" for o in d["ordens"]],
           "respostas": len(d["respostas"]), "mensagens": len(d["mensagens"]), "leitura": d["leitura"]}
    gravar_atomico(RODADAS / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime(agora))}-decisao.json", json.dumps(d, ensure_ascii=False, indent=1))
    try:
        commit, k = publicar(d)
    except RuntimeError as ex:
        recibo({**reg, "status": "falhou", "motivo": str(ex), "decidiu": dec, "decisao_t": d["t"], "commit": None, "tentativas": TENTATIVAS_PUSH})
        print("FALHOU:", ex)
        return 4
    try:                                                   # 18/11: caderno de aprendizado (leitura na entrada × resultado), o mesmo dos agentes
        sys.path.insert(0, "/home/servidor-de-producao/OpenBot/Shared/baleias/operar")
        import operar as OP
        ler_e = lambda n: json.loads((EST / "dados" / n).read_text()) if (EST / "dados" / n).exists() else {}
        OP.anotar_caderno("claude", d, set((ler_e("robo_claude.json").get("abertas") or {})), d.get("varredura"), ler_e("carteiras_top.json"))
    except Exception as ex:
        print(f"(caderno não anotado: {str(ex)[:80]})")
    recibo({**reg, "status": "ok", "decidiu": dec, "decisao_t": d["t"], "commit": commit, "tentativas": k})
    print(f"ok: decisão t={d['t']} publicada no commit {commit} ({k} tentativa(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
