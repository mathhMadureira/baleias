"""Checagem antes de ligar o dinheiro real. Não manda nenhuma ordem.

Uso: python3 -m executor.verificar
Confere: chave presente, permissões (sem saque, com spot), trava de IP, saldo em USDT, regras de cada moeda e o que o robô faria hoje.
"""
import sys
import time

from lab import tartaruga as T

from . import tartaruga_exec as X
from .binance import Binance, verificar_chave


def main():
    b = Binance()
    if not b.chave or not b.segredo:
        print("❌ Faltam BINANCE_API_KEY e BINANCE_API_SECRET no ~/baleias/.env")
        return 1
    try:
        problemas = verificar_chave(b)
    except RuntimeError as e:
        print(f"❌ A Binance recusou a chave: {e}")
        return 1
    graves = [p for p in problemas if "SAQUE" in p or "não permite" in p]
    for p in problemas:
        print(("❌ " if p in graves else "⚠️  ") + p)
    if graves:
        return 1
    if not problemas:
        print("✅ Chave só de trade, sem saque, travada por IP")
    usdt = b.saldo("USDT")
    print(f"💵 Saldo livre: {usdt:,.2f} USDT")
    precos = b.precos(T.MOEDAS_ROBO)
    dados = T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO) if T.CACHE_VIVO.exists() else T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO)
    risco = X.RISCO * usdt
    print(f"🎯 Risco por operação: 1% = US$ {risco:,.2f}")
    sinais = []
    for m, vs in dados.items():
        k = len(vs) - 1
        if k > T.ENTRADA and T.sinais(vs, k, "compra"):
            n = T.atr(vs)[k]
            usdt_pos = min(risco / (T.STOP_N * n) * precos[m], usdt * 0.98)
            minimo = b.regras(m)["minimo"]
            sinais.append(f"   {m[:-4]}: compraria US$ {usdt_pos:,.2f} (mínimo da Binance {minimo}) com stop {precos[m] - T.STOP_N * n:,.6g}"
                          + ("  ⚠️ abaixo do mínimo, não entraria" if usdt_pos < max(6, minimo) else ""))
    print("📋 Hoje o robô " + ("entraria em:\n" + "\n".join(sinais) if sinais else "não entraria em nada (nenhum rompimento de 55 dias)."))
    pequenas = [m for m in T.MOEDAS_ROBO if risco / 0.12 < max(6, b.regras(m)["minimo"])]
    if risco < 1:
        print("⚠️  Com esse saldo, muitas posições ficariam abaixo do mínimo de US$ 5–6 da Binance.")
    print("\nPara ligar: BINANCE_REAL=1 no .env e reiniciar o robô (systemctl --user restart baleias-robo).")
    print("Para parar novas entradas a qualquer momento: touch ~/baleias/PARAR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
