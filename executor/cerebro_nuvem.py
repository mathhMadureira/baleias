"""Uma rodada do cérebro na nuvem (GitHub Actions a cada 15 min): carrega o estado, vive as velas novas em sequência, salva.

BTC: estado no ramo `estado` (como sempre). Demais moedas do robô (pedido do dono: todos os robôs em todas as moedas): um cérebro
v1 e um v2 por moeda; o estado completo fica em CEREBROS_MOEDAS (cache do Actions, para não inchar o git) e só o resumo das
apostas ao vivo vai para dados/cerebros_moedas.json.

Uso: BALEIAS_DADOS=... BINANCE_DADOS=https://data-api.binance.vision python -m executor.cerebro_nuvem
"""
import json
import os
import time
from pathlib import Path
import urllib.request

from baleias import cerebro as C, config
from lab import tartaruga as T


def rodar(classe, nome, v, inicio_padrao=None, pasta=None):
    arq = (pasta or config.RAIZ) / nome
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


def velas(par):
    with urllib.request.urlopen(f"{T.DADOS}/api/v3/klines?symbol={par}&interval=15m&limit=1000", timeout=30) as r:
        return [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in json.load(r) if x[6] < time.time() * 1000]


def outras_moedas():
    """Um cérebro v1 e um v2 por moeda (fora o BTC). O resumo junta as apostas ao vivo novas às já guardadas (o cache pode se perder)."""
    pasta = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas"))
    pasta.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / "cerebros_moedas.json"
    resumo = json.loads(arq.read_text()) if arq.exists() else {}
    for par in T.MOEDAS_ROBO:
        if par == "BTCUSDT":
            continue
        try:
            v = velas(par)
        except (OSError, ValueError) as ex:
            print(f"   {par}: sem velas ({type(ex).__name__})")
            continue
        for nome, classe in (("v1", C.Cerebro), ("v2", C.CerebroV2), ("v3", C.CerebroV3)):
            cb, _ = rodar(classe, f"{par}_{nome}.json", v, pasta=pasta)
            r = resumo.setdefault(par, {}).setdefault(nome, {"ops": []})
            ultimo = r["ops"][-1][0] if r["ops"] else 0
            r["ops"] += [[o["t"], round(o["liquido"], 6), o["aposta"]] for o in cb.operacoes
                         if cb.inicio_ao_vivo and o["t"] >= cb.inicio_ao_vivo and o["t"] > ultimo]
            r["ops"] = r["ops"][-3000:]
            r["passos"], r["ultima_t"] = cb.passos, cb.ultima_t
            p = cb.pendente
            r["pendente"] = p and {"t": p["t"], "px": p["px"], "prob": p["prob"], "aposta": p["aposta"]}   # o scalper segue esta aposta ao vivo
    arq.write_text(json.dumps(resumo))
    for nome in ("v1", "v2", "v3"):
        ops = [o for x in resumo.values() for o in x.get(nome, {}).get("ops", [])]
        print(f"🧠 Cérebros {nome} nas outras {len(resumo)} moedas: {len(ops)} apostas ao vivo, "
              f"acerto {sum(o[1] > 0 for o in ops) / len(ops) * 100 if ops else 0:.1f}%")


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    v = velas("BTCUSDT")
    cb, eventos = rodar(C.Cerebro, "cerebro.json", v, inicio_padrao=1794281400000)   # v1: aquecimento local terminou 2026-11-10 03:30 UTC
    cb2, eventos2 = rodar(C.CerebroV2, "cerebro_v2.json", v)
    cb3, eventos3 = rodar(C.CerebroV3, "cerebro_v3.json", v)
    livro = cb.livro()
    (config.RAIZ / "livro_metodos.json").write_text(json.dumps({"t": time.time(), "metodos": livro}, ensure_ascii=False))
    C.escrever_livro_md(livro, config.RAIZ / "LIVRO_DE_METODOS.md")
    for nome, c, evs in (("v1", cb, eventos), ("v2", cb2, eventos2), ("v3", cb3, eventos3)):
        r = c.resumo()
        av = r["ao_vivo"]
        print(f"🧠 Cérebro {nome}: ao vivo {av['apostas']} apostas, acerto {av['acerto'] and round(av['acerto'] * 100, 1)}%, "
              f"resultado {av['resultado'] * 100:+.1f}% | capital US$ {r['capital']:,.2f}")
        for texto, _ in evs:
            print(f"   [{nome}] {texto}")
    outras_moedas()
    avisos = [f"[v1] {t}" for t, n in eventos if n] + [f"[v2] {t}" for t, n in eventos2 if n]
    if avisos:
        (config.RAIZ.parent / "avisos.txt").write_text("\n".join(avisos) + "\n")


if __name__ == "__main__":
    main()
