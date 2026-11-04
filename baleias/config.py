import os
from pathlib import Path

RAIZ = Path(os.environ.get("BALEIAS_DADOS", Path(__file__).resolve().parent.parent / "dados"))
BANCO = RAIZ / "baleias.db"

INFO_URL = "https://api.hyperliquid.xyz/info"
RANKING_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

# Documentação oficial: 1200 de peso por minuto por IP. Fica uma folga.
PESO_POR_MINUTO = 900

HORIZONTE_MS = 4 * 3600_000
HORIZONTES_REGISTRO_MS = {"1h": 3600_000, "4h": HORIZONTE_MS, "24h": 24 * 3600_000}

TAXA_TAKER = 0.00045
SLIPPAGE_MAIOR = 0.0001
SLIPPAGE_MENOR = 0.0005
MAIORES = {"BTC", "ETH", "SOL", "HYPE"}

CARTEIRAS = 20
CONTA_MINIMA = 100_000.0
GIRO_MES_MAXIMO = 100.0
OPERACOES_DIA_MAXIMAS = 200.0

NOCIONAL_MINIMO = 10_000.0
JANELA_AGRUPAR_MS = 120_000
AUMENTO_MINIMO = 0.5
INTERVALO_S = 30
ATRASO_BACKTEST_MS = 60_000

SINAIS_PARA_ALERTAR = 30
Z_DECISAO = 1.0
ESQUECIMENTO = 0.999
VARIANCIA_PRIOR = 1.0  # em (%)^2 por característica
RUIDO_INICIAL = 4.0    # em (%)^2


def custo_ida_e_volta(moeda: str) -> float:
    s = SLIPPAGE_MAIOR if moeda in MAIORES else SLIPPAGE_MENOR
    return 2 * (TAXA_TAKER + s)
