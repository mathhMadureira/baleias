"""Escolhe quem observar. Grande não basta: o filtro tira formador de mercado e operador de alta frequência."""
from . import config


def _janela(linha, nome):
    for janela, dados in linha["windowPerformances"]:
        if janela == nome:
            return {k: float(v) for k, v in dados.items()}
    return {"pnl": 0.0, "roi": 0.0, "vlm": 0.0}


def nota(linha):
    """Retorno limitado, para um único mês de sorte não dominar. É uma ordenação, não uma previsão."""
    mes, total = _janela(linha, "month"), _janela(linha, "allTime")
    return min(mes["roi"], 1.0) + 0.5 * min(total["roi"], 2.0)


def candidatas(linhas):
    saida = []
    for linha in linhas:
        conta = float(linha["accountValue"])
        mes, total = _janela(linha, "month"), _janela(linha, "allTime")
        if conta < config.CONTA_MINIMA or mes["pnl"] <= 0 or total["pnl"] <= 0:
            continue
        if mes["vlm"] / conta > config.GIRO_MES_MAXIMO or mes["vlm"] <= 0:
            continue
        saida.append({"carteira": linha["ethAddress"].lower(), "conta": conta, "nota": nota(linha),
                      "roi_mes": mes["roi"], "roi_total": total["roi"], "giro_mes": mes["vlm"] / conta})
    return sorted(saida, key=lambda c: -c["nota"])


def ativa_e_humana(operacoes, dias):
    """Tem operação em perpétuo e não opera em frequência de robô de mercado."""
    perps = [f for f in operacoes if f.get("dir", "") in ("Open Long", "Open Short", "Close Long", "Close Short")]
    return bool(perps) and len(operacoes) / max(dias, 1) <= config.OPERACOES_DIA_MAXIMAS


def escolher(cliente, linhas, agora_ms, quantidade=config.CARTEIRAS, dias=14, bloqueadas=()):
    escolhidas = []
    for c in candidatas(linhas):
        if c["carteira"] in bloqueadas:
            continue
        ops = cliente.operacoes(c["carteira"], agora_ms - dias * 86_400_000, agora_ms)
        # A API devolve no máximo 2000 por vez: lote cheio em 14 dias já é mais do que o teto permitido.
        if len(ops) >= 2000 or not ativa_e_humana(ops, dias):
            continue
        c["operacoes_dia"] = len(ops) / dias
        escolhidas.append(c)
        if len(escolhidas) >= quantidade:
            break
    return escolhidas
