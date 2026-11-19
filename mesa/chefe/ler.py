"""Chefe da mesa (OpenBot) — passo 1: lê o ramo `estado` e mostra o que a cartilha manda olhar.

Uso: python3 -I ler.py            → imprime o resumo (JSON) e grava rodadas/<hora>-leitura.json
Só lê. Também confere se a decisão anterior do chefe foi aplicada pela nuvem e completa o recibo dela.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EST = AQUI / "estado"
REMOTO = "https://github.com/mathhMadureira/baleias.git"
RODADAS = AQUI / "rodadas"
RECIBOS = AQUI / "recibos.jsonl"
AGENTES_ORDENS = ("cacador", "rapido", "scalper", "minerador", "lbank")      # cartilha seção 6: os que obedecem


def git(*a, check=True):
    r = subprocess.run(["git", "-C", str(EST), *a], capture_output=True, text=True, timeout=120)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr.strip()[:300]}")
    return r.stdout


def ler(nome, padrao=None):
    arq = EST / "dados" / nome
    try:
        return json.loads(arq.read_text())
    except (OSError, ValueError):
        return padrao


def clone_ok():
    """True se o clone responde a comandos só locais (sem rede). Falha de rede no fetch NÃO é clone quebrado."""
    if not (EST / ".git").exists():
        return False
    try:
        for a in (("rev-parse", "--verify", "-q", "HEAD"), ("status", "--porcelain", "-uno")):
            if subprocess.run(["git", "-C", str(EST), *a], capture_output=True, text=True, timeout=60).returncode:
                return False
        topo = subprocess.run(["git", "-C", str(EST), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60).stdout.strip()
    except subprocess.SubprocessError:
        return False
    return bool(topo) and Path(topo).resolve() == EST.resolve()      # .git quebrado não pode cair num repositório acima


def refazer_clone():
    """Auditoria 19/11 (A5): depois de um desligamento o clone ficou corrompido (corrompidos/estado-20261119) e toda rodada do chefe
    falhava. O clone é só uma cópia do ramo `estado`: guarda o quebrado de lado (não apaga) e clona de novo."""
    if EST.exists():
        os.replace(EST, EST.with_name(f"{EST.name}.corrompido-{int(time.time())}"))
    r = subprocess.run(["git", "clone", "-q", "--single-branch", "--branch", "estado", "--depth", "20", REMOTO, str(EST)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f"git clone: {r.stderr.strip()[:300]}")


def atualizar():
    if not clone_ok():
        refazer_clone()
    try:
        git("fetch", "-q", "--depth", "20", "origin", "estado")
        git("reset", "-q", "--hard", "origin/estado")
    except RuntimeError:
        if clone_ok():                     # o clone está bom: é rede ou o GitHub; a rodada para com o erro, sem mexer no clone
            raise
        refazer_clone()
        git("reset", "-q", "--hard", "origin/estado")
    git("clean", "-qfd")
    return git("rev-parse", "--short", "HEAD").strip(), int(git("log", "-1", "--format=%ct").strip())


def pendentes_do_dono(sala):
    """Mensagens do dono sem resposta: as da sala sem 'ref' respondido + as da caixa (dados/caixa/) que a nuvem ainda não passou para a sala."""
    respondidas = {x.get("ref") for x in sala if x.get("tipo") == "resposta"}
    ids = {x["id"] for x in sala}
    pend = [x for x in sala if x.get("de") == "dono" and x["id"] not in respondidas]
    for arq in sorted((EST / "dados" / "caixa").glob("*.json")):
        try:
            m = json.loads(arq.read_text())
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("id") not in ids and str(m.get("texto", "")).strip():
            pend.append({**m, "ainda_na_caixa": True})
    return [{"id": x["id"], "hora_utc": time.strftime("%d/%m %H:%M", time.gmtime(float(x["t"]))), "para": x.get("para"),
             "texto": x.get("texto"), "ainda_na_caixa": bool(x.get("ainda_na_caixa"))} for x in pend][-10:]


def conferir_anterior(robo, sala):
    """Completa o recibo da última decisão gravada pelo chefe: a nuvem aplicou? (ultima_decisao_t e a mensagem na sala)."""
    if not RECIBOS.exists():
        return None
    linhas = []
    for x in RECIBOS.read_text().splitlines():          # auditoria 19/11: linha cortada por desligamento é ignorada
        try:
            linhas.append(json.loads(x)) if x.strip() else None
        except ValueError:
            continue
    minhas = [x for x in linhas if x.get("status") == "ok" and x.get("decisao_t")]
    if not minhas:
        return None
    ult = minhas[-1]
    t = ult["decisao_t"]
    aplicada = robo.get("ultima_decisao_t") == t
    na_sala = any(x.get("de") == "claude" and abs(float(x.get("t", 0)) - t) < 900 and x.get("tipo") in ("msg", "resposta")
                  and float(x.get("t", 0)) >= t for x in sala)
    hist = [h for h in robo.get("historico_decisoes", []) if h.get("t") == t]
    return {"decisao_t": t, "aplicada": aplicada, "ultima_decisao_t_no_robo": robo.get("ultima_decisao_t"),
            "no_historico": bool(hist), "mensagem_na_sala": na_sala}


def main():
    rev, t_rev = atualizar()
    agora = time.time()
    m = ler("mercado_agora.json", {})
    robo = ler("robo_claude.json", {})
    sala = ler("sala.json", [])
    ordens = ler("ordens.json", {})
    banco = ler("banco.json", {}) or {}
    dec = ler("decisao_claude.json", {}) or {}
    autor = git("log", "-1", "--format=%an %ci", "--", "dados/decisao_claude.json").strip()
    g = robo.get("guarda_dia") or {}
    hoje = time.strftime("%Y-%m-%d", time.gmtime(agora))
    vigentes = {ag: o for ag, o in ordens.items() if o.get("acao") != "liberar" and o.get("ate", 0) > agora}
    resumo = {
        "t": int(agora), "agora_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(agora)),
        "estado_commit": rev, "estado_idade_s": int(agora - t_rev),
        "retrato_hora": m.get("hora_utc"), "retrato_idade_s": int(agora - (m.get("t") or 0)),
        "mercado": {k: m.get(k) for k in ("mercado_1h", "mercado_4h", "mercado_24h", "btc", "btc_1h_ultimas_24")},
        "maiores_altas_4h": m.get("maiores_altas_4h"), "maiores_quedas_4h": m.get("maiores_quedas_4h"),
        "contexto": {k: v for k, v in (m.get("contexto") or {}).items() if k != "noticias"},
        "noticias_titulos": [f"{n.get('hora_utc')} {n.get('fonte')}: {n.get('titulo')}" for n in (m.get("contexto") or {}).get("noticias", [])][:12],
        "v4": m.get("v4"), "vigia_v4": m.get("vigia_v4"),
        "robo_claude": {"carteira": robo.get("patrimonio"), "abertas": robo.get("abertas"), "guarda_dia": g,
                        "travado_hoje": g.get("data") == hoje and bool(g.get("travado")),
                        "ultimas_fechadas": (m.get("robo_claude") or {}).get("ultimas_fechadas"),
                        "licoes_anteriores": [x.get("texto") for x in (robo.get("licoes") or [])[-5:]],
                        "ultima_decisao_t": robo.get("ultima_decisao_t"), "alerta_rotina": robo.get("alerta_rotina")},
        "equipe": m.get("equipe"), "torneio_placar": (m.get("torneio") or {}).get("placar"), "campeao": (m.get("torneio") or {}).get("campeao"),
        "banco": {"tesouro": banco.get("tesouro"), "exposicao": banco.get("exposicao")},
        "ordens_vigentes": vigentes, "agentes_que_obedecem": AGENTES_ORDENS,
        "pendentes_do_dono": pendentes_do_dono(sala),
        "sala_recente": [{"hora_utc": time.strftime("%d/%m %H:%M", time.gmtime(x["t"])), "de": x["de"], "para": x.get("para"), "tipo": x.get("tipo"),
                          "texto": x["texto"][:300]} for x in sala if x.get("tipo") != "evento"][-8:],
        "decisao_atual_no_ramo": {"t": dec.get("t"), "autor_commit": autor, "leitura": dec.get("leitura"),
                                  "posicoes": dec.get("posicoes"), "ordens": dec.get("ordens")},
        "anterior_do_chefe": conferir_anterior(robo, sala),
    }
    RODADAS.mkdir(exist_ok=True)
    (RODADAS / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime(agora))}-leitura.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1))
    json.dump(resumo, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
