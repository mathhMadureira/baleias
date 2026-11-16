"""Equipe — a fusão do OpenBot com o Baleias: os robôs viram AGENTES persistentes de uma mesa de operações só.

Do OpenBot (nightly-labs/openbot) vieram as ideias, reescritas aqui em Python puro (nenhum código copiado; licença do OpenBot é
não comercial e o app é Electron/TypeScript):
  - agente persistente com nome, avatar, missão e motor próprios       → EQUIPE (o chefe tem instruções em docs/CARTILHA_ROBO_CLAUDE.md)
  - fila de mensagens que sobrevive a queda (gravação atômica)          → dados/caixa/<t>-<id>.json (uma mensagem por arquivo, sem conflito no git)
  - sala compartilhada com UM dono da tarefa e delegação explícita     → dados/sala.json; o dono da tarefa é o Robô Claude (chefe da mesa)
  - mensagens e ordens de agente para agente                           → ordens do chefe para os robôs (pausar, só vendas, só compras, liberar)
  - alarme quando um agente para de responder                          → robo_claude_nuvem (rotina sem decidir há > 2 h)

Propósito único do software: **uma mesa de operadores de IA que opera cripto sozinha, 24 h, na nuvem, e conversa com o dono.**

Quem escreve o quê (ramo `estado`):
  - dono (painel)            → dados/caixa/*.json         (um arquivo por mensagem, pela API do GitHub)
  - cerebro.yml (nuvem)      → dados/sala.json, dados/ordens.json
  - rotina do Claude         → dados/decisao_claude.json  (com respostas, mensagens e ordens)
"""
import json
import os
import time

from . import config

SALA, ORDENS, CAIXA = "sala.json", "ordens.json", "caixa"
MAX_SALA = 600
MAX_HORAS_ORDEM = 24
CHEFE = "claude"

# id, nome, avatar, arquivo de estado, o que move o agente, missão (uma frase)
EQUIPE = (
    {"id": "claude", "nome": "Robô Claude", "avatar": "🤖", "arquivo": "robo_claude.json", "motor": "Claude (rotina de hora em hora)",
     "missao": "Chefe da mesa: lê o mercado, decide as próprias posições, responde ao dono e dá ordens aos outros robôs."},
    {"id": "cacador", "nome": "Caçador", "avatar": "🎯", "arquivo": "robo_v4_cacador.json", "motor": "Cérebro v4",
     "missao": "Sempre posicionado: as apostas mais confiantes do v4, a favor da tendência de 24 h."},
    {"id": "rapido", "nome": "Rápido nuvem", "avatar": "🌲", "arquivo": "robo_v4_perp.json", "motor": "Cérebro v4",
     "missao": "Todas as apostas do v4 nas 140 moedas, as mais confiantes primeiro, segurando enquanto a tendência dura."},
    {"id": "scalper", "nome": "Scalper nuvem", "avatar": "✂", "arquivo": "robo_scalper_nuvem.json", "motor": "Cérebro v4",
     "missao": "Entradas do v4 com lucro realizado rápido e stop de 1,5%."},
    {"id": "scalper_b", "nome": "Scalper B (sem alvo)", "avatar": "✂", "arquivo": "robo_scalper_b.json", "motor": "Cérebro v4",
     "missao": "Desafiante do Scalper (H50): igual a ele, mas sem o alvo fixo de +0,5% — deixa o stop móvel levar o lucro."},
    {"id": "scalper_c", "nome": "Scalper C (só confiantes)", "avatar": "✂", "arquivo": "robo_scalper_c.json", "motor": "Cérebro v4",
     "missao": "Desafiante do Scalper (H50): igual a ele, mas só nas apostas do v4 com confiança ≥ 0,08 (o único achado robusto da H36)."},
    {"id": "scalper_d", "nome": "Scalper D (foco)", "avatar": "✂", "arquivo": "robo_scalper_d.json", "motor": "Cérebro v4",
     "missao": "Desafiante do Scalper (H51): igual a ele, mas evita os segmentos (lado, horário, confiança) em que o Scalper perde com prova."},
    {"id": "minerador", "nome": "Minerador", "avatar": "⛏", "arquivo": "robo_minerador.json", "motor": "regra H28",
     "missao": "Vende alta forte sem volume e compra queda forte sem volume (a regra de minutos que pagou custo no laboratório)."},
    {"id": "livre", "nome": "Robô Livre", "avatar": "🦅", "arquivo": "robo_livre.json", "motor": "maioria do mercado 24 h, 20×",
     "missao": "Livre de regras (pedido do dono, H47): segue a maioria do mercado nas 4 moedas líderes, carteira inteira a 20×, sem stop."},
    {"id": "lbank", "nome": "Robô LBank", "avatar": "🟣", "arquivo": "robo_lbank.json", "motor": "tendência 24 h + stop móvel (LBank)",
     "missao": "Simulado na LBank (H53): SOL, memecoins e HOOD, a favor da tendência de 24 h, segurando com stop móvel e stop de 2%."},
    {"id": "radar", "nome": "Radar", "avatar": "📡", "arquivo": "robo_radar.json", "motor": "leitura de 1 s em todos os tempos (H56)",
     "missao": "Contínuo: lê o mercado a cada 2 s a partir das velas de 1 s, de 5 s a 4 h; entra contra movimento forte sem volume. Reprovado no laboratório: comparação ao vivo."},
    {"id": "testnet", "nome": "v4 Testnet", "avatar": "🧪", "arquivo": "robo_v4_testnet.json", "motor": "Cérebro v4",
     "missao": "Prova na conta de teste da Binance, com ordens reais, o que as simulações mostram."},
)
POR_ID = {a["id"]: a for a in EQUIPE}
POR_ARQUIVO = {a["arquivo"]: a for a in EQUIPE}
ACOES = {"pausar": "pausado (sem novas entradas)", "so_vendas": "só vendas", "so_compras": "só compras", "liberar": "livre"}


def _ler(nome, padrao):
    arq = config.RAIZ / nome
    try:
        return json.loads(arq.read_text()) if arq.exists() else padrao
    except ValueError:
        return padrao


def _gravar(nome, obj):
    """Gravação atômica (arquivo temporário + rename): uma queda no meio nunca deixa o arquivo pela metade."""
    arq = config.RAIZ / nome
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(arq.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False))
    os.replace(tmp, arq)


def _aparar(s):
    """Revisão 15/11: os eventos dos robôs (entradas/saídas) não podem empurrar para fora as conversas. Guarda as últimas 300 conversas
    e os últimos MAX_SALA eventos, em ordem de tempo."""
    conversas = [x for x in s if x.get("tipo") != "evento"][-300:]
    eventos = [x for x in s if x.get("tipo") == "evento"][-MAX_SALA:]
    return sorted(conversas + eventos, key=lambda x: x["t"])


def _id(t, de):
    return f"{int(t * 1000)}-{de}"


# ---------------- sala ----------------

def sala():
    return _ler(SALA, [])


def postar(de, texto, para="sala", tipo="msg", t=None, ref=None):
    """Acrescenta uma mensagem na sala. de/para: id de agente, 'dono' ou 'sala'. tipo: msg | evento | ordem | resposta."""
    t = t or time.time()
    s = sala()
    m = {"id": _id(t, de), "t": t, "de": de, "para": para, "tipo": tipo, "texto": str(texto)[:1200]}
    if ref:
        m["ref"] = ref
    if any(x["id"] == m["id"] for x in s):
        return None
    s.append(m)
    _gravar(SALA, _aparar(s))
    return m


def postar_eventos(de, textos, t=None):
    """Os textos de entrada/saída de um robô vão para a sala como eventos (o dono vê a mesa inteira numa linha do tempo só)."""
    t = t or time.time()
    s = sala()
    for i, x in enumerate(textos):
        s.append({"id": _id(t + i / 1000, de), "t": t, "de": de, "para": "sala", "tipo": "evento", "texto": str(x)[:600]})
    if textos:
        _gravar(SALA, _aparar(s))


# ---------------- caixa de entrada do dono ----------------

def nova_mensagem_dono(texto, para=CHEFE, t=None):
    """Monta o arquivo de uma mensagem do dono (o painel envia para o ramo estado pela API do GitHub). Devolve (caminho, objeto)."""
    t = t or time.time()
    para = para if para in POR_ID or para == "sala" else CHEFE
    m = {"id": _id(t, "dono"), "t": t, "de": "dono", "para": para, "tipo": "msg", "texto": str(texto).strip()[:1200]}
    return f"dados/{CAIXA}/{m['id']}.json", m


def sincronizar_caixa():
    """Copia para a sala as mensagens novas do dono que chegaram em dados/caixa/. Devolve as copiadas."""
    pasta = config.RAIZ / CAIXA
    if not pasta.is_dir():
        return []
    s = sala()
    ids = {x["id"] for x in s}
    novas = []
    for arq in sorted(pasta.glob("*.json")):
        try:
            m = json.loads(arq.read_text())
        except ValueError:
            continue
        if not isinstance(m, dict) or m.get("id") in ids or not str(m.get("texto", "")).strip():
            continue
        m = {"id": str(m["id"])[:40], "t": float(m.get("t", time.time())), "de": "dono", "para": str(m.get("para", CHEFE))[:20],
             "tipo": "msg", "texto": str(m["texto"])[:1200]}
        s.append(m)
        novas.append(m)
    if novas:
        s.sort(key=lambda x: x["t"])
        _gravar(SALA, _aparar(s))
    return novas


def pendentes_do_dono():
    """Mensagens do dono que o chefe ainda não respondeu (vão no retrato para a rotina do Claude ler)."""
    s = sala()
    respondidas = {x.get("ref") for x in s if x.get("tipo") == "resposta"}
    return [{"id": x["id"], "hora_utc": time.strftime("%d/%m %H:%M", time.gmtime(x["t"])), "para": x["para"], "texto": x["texto"]}
            for x in s if x["de"] == "dono" and x["id"] not in respondidas][-10:]


# ---------------- ordens do chefe para os robôs ----------------

def ordens():
    return _ler(ORDENS, {})


def pausa_proibida(agente):
    """Regra do dono (16/11): nenhum robô é pausado no prejuízo (carteira abaixo de US$ 10) ou com operações abertas."""
    a = POR_ID.get(agente)
    e = _ler(a["arquivo"], None) if a else None
    if not e:
        return False
    return float(e.get("patrimonio", e.get("carteira", 10.0)) or 0) < 10.0 or bool(e.get("abertas"))


def ordem_vigente(agente, agora=None):
    """{'acao', 'motivo', 'ate'} da ordem em vigor para o agente, ou None (ordem vence sozinha em até 24 h).
    Ordem de pausa não vale enquanto o robô estiver no prejuízo ou com operações abertas (pausa_proibida)."""
    o = ordens().get(agente)
    agora = agora or time.time()
    if not o or o.get("acao") == "liberar" or o.get("ate", 0) < agora:
        return None
    if o.get("acao") == "pausar" and pausa_proibida(agente):
        return None
    return o


def aplicar_ordens(lista, de=CHEFE, agora=None):
    """Valida e grava as ordens do chefe. lista: [{'agente','acao','horas','motivo'}]. Devolve os textos para a sala.
    O chefe não dá ordem a si mesmo; ação desconhecida é ignorada; prazo entre 1 e 24 h."""
    agora = agora or time.time()
    atuais = ordens()
    textos = []
    for o in lista or []:
        if not isinstance(o, dict):
            continue
        ag, acao = str(o.get("agente", "")).lower(), str(o.get("acao", "")).lower()
        if ag not in POR_ID or ag == de or acao not in ACOES:
            continue
        try:
            horas = min(MAX_HORAS_ORDEM, max(1.0, float(o.get("horas", 6))))
        except (TypeError, ValueError):
            horas = 6.0
        motivo = str(o.get("motivo", ""))[:200]
        if acao == "pausar" and pausa_proibida(ag):
            textos.append(f"🚫 Pausa de {POR_ID[ag]['avatar']} {POR_ID[ag]['nome']} recusada: regra do dono, nenhum robô é pausado no prejuízo "
                          "ou com operações abertas (o Banco reduz o tamanho dele em vez disso)")
            postar(de, textos[-1], para=ag, tipo="ordem", t=agora + len(textos) / 1000)
            continue
        atuais[ag] = {"acao": acao, "motivo": motivo, "de": de, "t": agora, "ate": agora + horas * 3600}
        a = POR_ID[ag]
        textos.append(f"📣 Ordem para {a['avatar']} {a['nome']}: {ACOES[acao]}" + (f" por {horas:.0f} h" if acao != "liberar" else "") + (f" — {motivo}" if motivo else ""))
        postar(de, textos[-1], para=ag, tipo="ordem", t=agora + len(textos) / 1000)
    if textos:
        _gravar(ORDENS, atuais)
    return textos


def lado_da_ordem(agente, regime_lado):
    """Combina a regra da tendência (venda/compra/None) com a ordem do chefe. Devolve (pausado, lado_permitido)."""
    o = ordem_vigente(agente)
    if not o:
        return False, regime_lado
    if o["acao"] == "pausar":
        return True, regime_lado
    return False, "venda" if o["acao"] == "so_vendas" else "compra"


# ---------------- retrato da equipe (para o chefe e para o painel) ----------------

def retrato(estados=None):
    """Carteira, posições e ordem vigente de cada agente. estados: {arquivo: estado} (se None, lê de dados/)."""
    out = []
    for a in EQUIPE:
        e = (estados or {}).get(a["arquivo"]) if estados is not None else _ler(a["arquivo"], None)
        if not e:
            continue
        o = ordem_vigente(a["id"])
        ab = e.get("abertas") or {}
        out.append({"id": a["id"], "nome": a["nome"], "avatar": a["avatar"], "motor": a["motor"], "missao": a["missao"],
                    "carteira": round(float(e.get("patrimonio", e.get("carteira", 10.0)) or 0), 2), "n_abertas": len(ab),
                    "abertas": [[str(par).replace("USDT", ""), p.get("lado")] for par, p in list(ab.items())[:8]],
                    "n_fechadas": len(e.get("fechadas", [])),
                    "ordem": {"acao": o["acao"], "motivo": o.get("motivo", ""), "ate_utc": time.strftime("%d/%m %H:%M", time.gmtime(o["ate"]))} if o else None})
    return out

