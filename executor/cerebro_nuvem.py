"""Uma rodada do cérebro na nuvem (GitHub Actions a cada 15 min): carrega o estado, vive as velas novas em sequência, salva.

Uso: BALEIAS_DADOS=... BINANCE_DADOS=https://data-api.binance.vision python -m executor.cerebro_nuvem
"""
import json
import time
import urllib.request

from baleias import cerebro as C, config
from lab import tartaruga as T


def rodar(classe, nome, v, inicio_padrao=None):
    arq = config.RAIZ / nome
    estado = json.loads(arq.read_text()) if arq.exists() else None
    cb = classe(estado)
    novo = not cb.passos
    eventos = C.avancar(cb, v)
    if novo:
        eventos = []                         # aquecimento: não vira aviso
    if cb.inicio_ao_vivo is None:
        # placar ao vivo começa no fim do aquecimento (v1: fim do aquecimento local; v2: agora)
        cb.inicio_ao_vivo = inicio_padrao if (inicio_padrao and not novo) else cb.ultima_t
        if novo:
            cb._anotar(cb.ultima_t, f"🧠 Aquecimento na nuvem: viveu {cb.passos} velas. Daqui em diante conta como ao vivo.")
    arq.write_text(json.dumps(cb.exportar()))
    return cb, eventos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=1000", timeout=30) as r:
        v = [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in json.load(r) if x[6] < time.time() * 1000]
    cb, eventos = rodar(C.Cerebro, "cerebro.json", v, inicio_padrao=1794281400000)   # v1: aquecimento local terminou 2026-11-10 03:30 UTC
    cb2, eventos2 = rodar(C.CerebroV2, "cerebro_v2.json", v)
    livro = cb.livro()
    (config.RAIZ / "livro_metodos.json").write_text(json.dumps({"t": time.time(), "metodos": livro}, ensure_ascii=False))
    C.escrever_livro_md(livro, config.RAIZ / "LIVRO_DE_METODOS.md")
    for nome, c, evs in (("v1", cb, eventos), ("v2", cb2, eventos2)):
        r = c.resumo()
        av = r["ao_vivo"]
        print(f"🧠 Cérebro {nome}: ao vivo {av['apostas']} apostas, acerto {av['acerto'] and round(av['acerto'] * 100, 1)}%, "
              f"resultado {av['resultado'] * 100:+.1f}% | capital US$ {r['capital']:,.2f}")
        for texto, _ in evs:
            print(f"   [{nome}] {texto}")
    avisos = [f"[v1] {t}" for t, n in eventos if n] + [f"[v2] {t}" for t, n in eventos2 if n]
    if avisos:
        (config.RAIZ.parent / "avisos.txt").write_text("\n".join(avisos) + "\n")


if __name__ == "__main__":
    main()
