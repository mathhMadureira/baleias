"""Stop móvel (H49, pedido do dono em 15/11: "realizar lucro e ir subindo o stop, acompanhando o movimento").

Quando o lucro aberto chega a ARMA (+0,5%), a saída passa a ficar em GUARDA (70%) do maior lucro já alcançado e sobe junto com ele;
nunca desce. Conferido minuto a minuto nas velas de 1 min da Binance, como na simulação que o aprovou (403 operações dos robôs da nuvem:
−8,25 → −0,51 no total; melhor nas duas metades do período e em todos os robôs).

Custo de máquina: uma chamada à Binance por posição aberta por rodada (velas de 1 min desde a última conferência).
O stop de segurança de cada robô também é conferido no mesmo caminho de minutos, na ordem em que os preços aconteceram.
Uso nos robôs: MINUTOS[par] = buscar(par, desde_ms, ate_ms) antes do passo; depois conferir(p, ...).
"""
import json
import urllib.request

ARMA, GUARDA = 0.005, 0.70
DADOS = "https://data-api.binance.vision"
MINUTOS = {}          # {par: [(t_ms, máxima, mínima), ...]} preenchido pelo main de cada robô


def buscar(par, desde_ms, ate_ms):
    """Velas de 1 min FECHADAS de [desde_ms, ate_ms). Em erro de rede devolve [] (o robô cai na regra antiga da vela de 15 min)."""
    saida, t = [], int(desde_ms)
    try:
        while t < ate_ms and len(saida) < 5000:
            with urllib.request.urlopen(f"{DADOS}/api/v3/klines?symbol={par}&interval=1m&startTime={t}&endTime={int(ate_ms) - 1}&limit=1000", timeout=20) as r:
                k = json.load(r)
            if not k:
                break
            saida += [(int(x[0]), float(x[2]), float(x[3]), float(x[4])) for x in k if int(x[6]) < ate_ms]   # (t, máxima, mínima, fechamento)
            t = int(k[-1][0]) + 60_000
            if len(k) < 1000:
                break
    except (OSError, ValueError):
        return []
    return saida


def armar_em(alvo_pct, movel=True):
    """Dono (19/11): alvos maiores. Com alvo, o stop móvel só arma na METADE do caminho até o alvo (antes armava a +0,5% e fechava quase
    tudo antes de alvos acima de 0,5%: com alvo de 1,2% só 3% chegavam). Sem alvo: +0,5%, como na H49."""
    if movel is False:                                          # R2 (dono, 23/11): o agente desligou o móvel desta posição
        return float("inf")
    return max(ARMA, 0.5 * alvo_pct) if alvo_pct else ARMA


def conferir(p, minutos, stop_pct, ate_ms, desde_ms, alvo_pct=None, movel=True):
    """Percorre os minutos de [max(desde_ms, p['movel_ate']), ate_ms). Devolve (preço, motivo, t_ms) se o stop de segurança ou o stop
    móvel foi tocado, ou None. Guarda em p o pico de lucro ('pico') e até onde já conferiu ('movel_ate')."""
    if not minutos:
        return None
    e = p["entrada"]
    venda = p["lado"] in ("venda", "SELL")
    pico = p.get("pico", 0.0)
    ant = p.get("fecho_ant")                                    # resultado a favor no fechamento do minuto anterior
    inicio = max(int(desde_ms), int(p.get("movel_ate", 0)))
    arma = armar_em(alvo_pct, movel)
    for m in minutos:
        t, h, l = m[0], m[1], m[2]
        if t < inicio or t >= ate_ms:
            continue
        favoravel = (1 - l / e) if venda else (h / e - 1)
        adverso = (1 - h / e) if venda else (l / e - 1)
        if pico >= arma and adverso <= GUARDA * pico:          # devolveu até 70% do pico: realiza
            g = GUARDA * pico
            if ant is not None and ant < g:                     # correção 19/11 (H66): o minuto anterior já fechou abaixo do nível → sai na abertura
                g = ant
            p["pico"], p["movel_ate"] = pico, t + 60_000
            return e * (1 - g if venda else 1 + g), f"stop móvel (pico +{pico:.2%}, guardou {g:+.2%})", t
        if adverso <= -stop_pct:
            p["pico"], p["movel_ate"] = pico, t + 60_000
            return e * (1 + stop_pct if venda else 1 - stop_pct), f"stop de segurança −{stop_pct:.1%}", t
        if alvo_pct and favoravel >= alvo_pct:                 # revisão 15/11: o alvo do robô (Scalper +0,5%) vale antes de o stop móvel devolver
            p["pico"], p["movel_ate"] = max(pico, favoravel), t + 60_000
            return e * (1 - alvo_pct if venda else 1 + alvo_pct), f"lucro realizado +{alvo_pct:.1%}", t
        pico = max(pico, favoravel)                            # o pico do minuto só arma a partir do minuto seguinte (não sabemos a ordem)
        if len(m) > 3:
            ant = p["fecho_ant"] = (1 - m[3] / e) if venda else (m[3] / e - 1)
        p["movel_ate"] = t + 60_000
    p["pico"] = pico
    return None


def preparar(abertas, entrada_ms, agora_ms):
    """Busca os minutos de cada posição aberta (desde a última conferência). entrada_ms(p) → início da posição em ms."""
    MINUTOS.clear()
    for par, p in abertas.items():
        MINUTOS[par] = buscar(par, max(entrada_ms(p), int(p.get("movel_ate", 0))), agora_ms)


def precos_da_rodada(pares, agora_ms):
    """P1 do Treinador (lab, 18/11): entrar no preço da rodada, não no fechamento de uma vela de 15 min antiga.
    {par: fechamento da última vela de 1 min FECHADA até agora_ms}. Moeda sem resposta fica de fora (o chamador usa o preço antigo e anota)."""
    out = {}
    for par in dict.fromkeys(pares):
        try:
            with urllib.request.urlopen(f"{DADOS}/api/v3/klines?symbol={par}&interval=1m&endTime={int(agora_ms) - 1}&limit=3", timeout=15) as r:
                k = [x for x in json.load(r) if int(x[6]) < agora_ms]
            if k:
                out[par] = float(k[-1][4])
        except (OSError, ValueError):
            continue
    return out

