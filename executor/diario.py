"""Execução única do robô Tartaruga — para rodar agendado (Grok Bot, cron, GitHub) sem a máquina ficar ligada.

Uso: python3 -m executor.diario
Faz: confere stops perdidos, decide entradas/saídas do dia (se ainda não decidiu hoje), salva o estado e imprime um resumo curto
em português (o agendador manda esse texto para o celular).
"""
import json
import time

from baleias import config

from lab import tartaruga as T

from . import tartaruga_exec as X
from .binance import Binance
from .robo import real


def main():
    cliente = Binance()
    e = X.carregar()
    corretora = (X.Real if real() else X.Simulada)(cliente, e)
    linhas_antes = X.EVENTOS.stat().st_size if X.EVENTOS.exists() else 0
    precos = corretora.precos(T.MOEDAS_ROBO)
    T.CACHE_VIVO.unlink(missing_ok=True)
    dados = T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO)
    if e.get("ultimo_dia") != time.strftime("%Y-%m-%d", time.gmtime()):
        X.passo_diario(e, corretora, dados, precos)
    else:
        X.stops_perdidos(e, corretora, dados)
    X.checar_stops(e, corretora, precos)
    e["radar"] = X.radar(dados, precos)
    e["patrimonio"] = X.patrimonio(e, precos, corretora)
    e["atualizado"] = time.time()
    e.setdefault("curva", []).append([int(time.time()), round(e["patrimonio"], 4)])
    X.salvar(e)
    novidades = []
    if X.EVENTOS.exists():
        with open(X.EVENTOS) as f:
            f.seek(linhas_antes)
            novidades = [json.loads(x)["texto"] for x in f if x.strip()]
    ini = 0.0 if e.get("modo_real") else X.CAPITAL_SIMULADO
    print(f"🐢 Robô Tartaruga ({'REAL' if real() else 'simulado'}) — patrimônio US$ {e['patrimonio']:,.2f}"
          + (f" ({(e['patrimonio'] / ini - 1) * 100:+.2f}%)" if ini else ""))
    print(f"Posições abertas: {', '.join(m[:-4] for m in e['abertas']) or 'nenhuma'}")
    for t in novidades:
        print(t)
    if not novidades:
        print("Sem entradas nem saídas hoje.")
    print("Mais perto de entrar: " + ", ".join(f"{r['moeda']} {r['falta_pct']:+.1f}%" for r in e["radar"][:5]))


if __name__ == "__main__":
    main()
