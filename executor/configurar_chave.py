"""Grava a chave da Binance no .env sem mostrar na tela. Rodar num terminal de verdade (não pelo '!' do chat):

    cd ~/baleias && python3 -m executor.configurar_chave
"""
import getpass
import os
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def main():
    if not sys.stdin.isatty():
        print("Abra o Terminal do Ubuntu (Ctrl+Alt+T) e rode lá: cd ~/baleias && python3 -m executor.configurar_chave")
        return 1
    qual = input("Qual corretora? Digite bybit, binance ou testnet (futuros de teste da Binance, sem dinheiro): ").strip().lower()
    if qual not in ("bybit", "binance", "testnet"):
        print("Digite bybit, binance ou testnet. Nada foi gravado.")
        return 1
    pre = "BINANCE_TESTNET" if qual == "testnet" else qual.upper()
    chave = getpass.getpass("Cole a CHAVE API (não aparece ao colar) e tecle Enter: ").strip()
    segredo = getpass.getpass("Cole a CHAVE SECRETA (não aparece ao colar) e tecle Enter: ").strip()
    if len(chave) < 16 or len(segredo) < 30 or " " in chave + segredo:
        print("Parece incompleto (sem espaços; a chave tem 18+ e o segredo 36+ caracteres). Nada foi gravado.")
        return 1
    guarda = (f"{pre}_API_KEY=", f"{pre}_API_SECRET=") + (() if qual == "testnet" else ("CORRETORA=",))   # o testnet não muda a corretora real
    linhas = [l for l in (ENV.read_text().splitlines() if ENV.exists() else []) if not l.startswith(guarda)]
    linhas += [f"{pre}_API_KEY={chave}", f"{pre}_API_SECRET={segredo}"] + ([] if qual == "testnet" else [f"CORRETORA={qual}"])
    ENV.write_text("\n".join(linhas) + "\n")
    os.chmod(ENV, 0o600)
    print(f"✅ Gravado no .env ({len(chave)} e {len(segredo)} caracteres). Agora rode: python3 -m executor.verificar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
