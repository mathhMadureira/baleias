"""Uma rodada do cérebro na nuvem (GitHub Actions a cada 15 min): carrega o estado, vive as velas novas em sequência, salva.

Uso: BALEIAS_DADOS=... BINANCE_DADOS=https://data-api.binance.vision python -m executor.cerebro_nuvem
"""
import json
import time
import urllib.request

from baleias import cerebro as C, config
from lab import tartaruga as T


def main():
    arq = config.RAIZ / "cerebro.json"
    cb = C.Cerebro(json.loads(arq.read_text()) if arq.exists() else None)
    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=1000", timeout=30) as r:
        v = [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in json.load(r) if x[6] < time.time() * 1000]
    if not cb.passos:
        print("cérebro sem estado: aquecendo com as velas disponíveis")
    eventos = C.avancar(cb, v)
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cb.exportar()))
    livro = cb.livro()
    (config.RAIZ / "livro_metodos.json").write_text(json.dumps({"t": time.time(), "metodos": livro}, ensure_ascii=False))
    C.escrever_livro_md(livro, config.RAIZ / "LIVRO_DE_METODOS.md")
    r = cb.resumo()
    print(f"🧠 Cérebro: {r['apostas']} apostas, acerto {r['acerto'] and round(r['acerto'] * 100, 1)}%, capital US$ {r['capital']:,.2f}")
    for texto, _ in eventos:
        print(texto)
    avisos = [t for t, notificar in eventos if notificar]
    if avisos:
        (config.RAIZ.parent / "avisos.txt").write_text("\n".join(avisos) + "\n")


if __name__ == "__main__":
    main()
