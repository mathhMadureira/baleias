"""Transforma operações brutas em entradas: só abertura de posição ou aumento relevante, perpétuo, agrupado."""
from . import config


def e_perpetuo_comum(moeda):
    """Perpétuo de cripto ou ação americana do mercado xyz. Spot e outros mercados HIP-3 ficam fora."""
    if moeda.startswith("@") or "/" in moeda:
        return False
    return ":" not in moeda or config.e_acao(moeda)


def detectar(operacoes, agora_ms=None, nocional_minimo=config.NOCIONAL_MINIMO):
    """Agrupa fills da mesma carteira, moeda e direção. Grupo ainda aberto (recente demais) fica para depois."""
    abertas = {}
    saida = []
    for f in sorted(operacoes, key=lambda x: (x["time"], x["tid"])):
        direcao = f.get("dir")
        if direcao not in ("Open Long", "Open Short") or not e_perpetuo_comum(f["coin"]):
            continue
        chave = (f["coin"], direcao)
        px, tam, inicio = float(f["px"]), float(f["sz"]), abs(float(f["startPosition"]))
        grupo = abertas.get(chave)
        if grupo and f["time"] - grupo["fim"] <= config.JANELA_AGRUPAR_MS:
            grupo["fim"], grupo["tam"], grupo["nocional"] = f["time"], grupo["tam"] + tam, grupo["nocional"] + px * tam
            grupo["tids"].append(f["tid"])
            continue
        if grupo:
            saida.append(abertas.pop(chave))
        abertas[chave] = {"moeda": f["coin"], "lado": "long" if direcao == "Open Long" else "short",
                          "inicio_pos": inicio, "tam": tam, "nocional": px * tam, "t": f["time"], "fim": f["time"],
                          "tids": [f["tid"]]}
    saida.extend(abertas.values())
    fechados = []
    for g in sorted(saida, key=lambda x: x["t"]):
        if agora_ms is not None and agora_ms - g["fim"] <= config.JANELA_AGRUPAR_MS:
            continue
        aumento = g["inicio_pos"] > 0
        if aumento and g["tam"] / g["inicio_pos"] < config.AUMENTO_MINIMO:
            continue
        if g["nocional"] < nocional_minimo:
            continue
        g["tipo"] = "aumento" if aumento else "abertura"
        g["px_medio"] = g["nocional"] / g["tam"]
        fechados.append(g)
    return fechados


def caracteristicas(carteira, moeda, lado, tipo, nocional, consenso, movimento_previo, noticia=None):
    """Só o que se conhece no instante do sinal. Movimento prévio positivo = o preço já andou a favor do lado."""
    if nocional < 50_000:
        tamanho = "<50k"
    elif nocional < 250_000:
        tamanho = "50-250k"
    elif nocional < 1_000_000:
        tamanho = "250k-1M"
    else:
        tamanho = ">1M"
    if movimento_previo is None:
        previo = "desconhecido"
    elif movimento_previo > 0.005:
        previo = "ja_subiu_a_favor"
    elif movimento_previo < -0.005:
        previo = "veio_contra"
    else:
        previo = "neutro"
    return ["vies", f"lado:{lado}", f"tipo:{tipo}", f"tamanho:{tamanho}",
            f"ativo:{'acao_eua' if config.e_acao(moeda) else 'maior' if moeda in config.MAIORES else 'menor'}",
            f"noticia:{'desconhecido' if noticia is None else 'sim' if noticia else 'nao'}",
            f"consenso:{'sim' if consenso else 'nao'}", f"previo:{previo}", f"carteira:{carteira}"]


def retorno_bruto(lado, entrada, saida):
    r = saida / entrada - 1
    return r if lado == "long" else -r


def retorno_liquido(lado, moeda, entrada, saida):
    return retorno_bruto(lado, entrada, saida) - config.custo_ida_e_volta(moeda)


def lado_controle(identificador):
    """Sorteio estável: mesmo sinal, mesmo lado, em qualquer rodada."""
    import hashlib
    return "long" if hashlib.sha256(str(identificador).encode()).digest()[0] % 2 == 0 else "short"


def extremos(lado, entrada, velas):
    """Maior ganho e maior perda possíveis no caminho, em retorno bruto."""
    if not velas:
        return 0.0, 0.0
    melhor_alta = max(float(v["h"]) for v in velas) / entrada - 1
    pior_queda = min(float(v["l"]) for v in velas) / entrada - 1
    return (melhor_alta, pior_queda) if lado == "long" else (-pior_queda, -melhor_alta)


def classificar_erro(bruto, liquido, melhor, pior, previo, carteira_saiu):
    """Por que deu certo ou errado. A ordem importa: a primeira explicação que serve fica."""
    if liquido > 0:
        return "acerto"
    if bruto > 0:
        return "custo_comeu_o_ganho"
    if carteira_saiu:
        return "carteira_saiu_antes"
    if previo is not None and previo > 0.005:
        return "entrada_tardia"
    if melhor > config.custo_ida_e_volta("x") * 2:
        return "devolveu_o_ganho"
    return "contra_desde_o_inicio"
