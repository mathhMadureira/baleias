import os
from pathlib import Path


def _carregar_env():
    """Lê ~/baleias/.env para os comandos manuais também verem o contato da SEC (o serviço já recebe pelo systemd)."""
    arq = Path(__file__).resolve().parent.parent / ".env"
    if arq.exists():
        for linha in arq.read_text().splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_carregar_env()

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
# Sinal que chega mais tarde que isto não é o que um alerta ao vivo entregaria (ex.: máquina pausada): é descartado.
ATRASO_MAXIMO_MS = 10 * 60_000
ATRASO_BACKTEST_MS = 60_000

SINAIS_PARA_ALERTAR = 30
Z_DECISAO = 1.0
ESQUECIMENTO = 0.999
VARIANCIA_PRIOR = 1.0  # em (%)^2 por característica
RUIDO_INICIAL = 4.0    # em (%)^2


# Ações e índices americanos negociados na Hyperliquid (HIP-3, mercado "xyz").
DEX_ACOES = "xyz"
# A taxa dos mercados HIP-3 é definida por quem os criou e não conferi o valor: uso o dobro da taxa base, por cautela.
TAXA_TAKER_ACOES_SUPOSTA = 2 * TAXA_TAKER


def e_acao(moeda: str) -> bool:
    return moeda.startswith(DEX_ACOES + ":")


def custo_ida_e_volta(moeda: str) -> float:
    if e_acao(moeda):
        return 2 * (TAXA_TAKER_ACOES_SUPOSTA + SLIPPAGE_MENOR)
    s = SLIPPAGE_MAIOR if moeda in MAIORES else SLIPPAGE_MENOR
    return 2 * (TAXA_TAKER + s)


# --- Compras de diretores (SEC, formulário 4) ---
SEC_CONTATO = os.environ.get("SEC_CONTATO", "")
INSIDER_VALOR_MINIMO = 50_000.0
INSIDER_PRECO_MINIMO = 1.0
INSIDER_DIAS_UTEIS = 21          # saída ~1 mês depois da entrada
INSIDER_DIAS_CURTO = 5
# Corretagem e spread de ação americana: suposição minha, por lado. Não inclui câmbio nem IOF para quem compra do Brasil.
INSIDER_CUSTO_LADO = 0.002
