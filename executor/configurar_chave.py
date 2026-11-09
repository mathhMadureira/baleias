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
    chave = getpass.getpass("Cole a CHAVE API (não aparece ao colar) e tecle Enter: ").strip()
    segredo = getpass.getpass("Cole a CHAVE SECRETA (não aparece ao colar) e tecle Enter: ").strip()
    if len(chave) < 30 or len(segredo) < 30 or " " in chave + segredo:
        print("Parece incompleto (chave e segredo da Binance têm ~64 caracteres, sem espaços). Nada foi gravado.")
        return 1
    linhas = [l for l in (ENV.read_text().splitlines() if ENV.exists() else [])
              if not l.startswith(("BINANCE_API_KEY=", "BINANCE_API_SECRET="))]
    linhas += [f"BINANCE_API_KEY={chave}", f"BINANCE_API_SECRET={segredo}"]
    ENV.write_text("\n".join(linhas) + "\n")
    os.chmod(ENV, 0o600)
    print(f"✅ Gravado no .env ({len(chave)} e {len(segredo)} caracteres). Agora rode: python3 -m executor.verificar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
