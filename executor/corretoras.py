"""Escolhe a corretora do modo real pelo .env: CORRETORA=bybit ou CORRETORA=binance (padrão)."""
import os


def escolher():
    """Devolve (cliente, função que confere a chave, nome)."""
    if os.environ.get("CORRETORA", "binance").lower() == "bybit":
        from .bybit import Bybit, verificar_chave
        return Bybit(), verificar_chave, "Bybit"
    from .binance import Binance, verificar_chave
    return Binance(), verificar_chave, "Binance"
