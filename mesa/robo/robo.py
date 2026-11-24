"""Robô único da mesa Baleias (24/11, auditoria + livro 151): UMA execução para toda estratégia, com os limites no código.

Divisão (como no esqueleto do artigo sobre o *151 Trading Strategies*):
- este arquivo: busca velas FECHADAS, confere dado fresco, confere a perda do dia, limita a alavancagem, opera só a diferença;
- a estratégia (estrategias/<nome>.py): uma classe Estrategia com simbolos, tempo, historico e pesos(velas) → {símbolo: −1..+1}.

Modo PAPEL por padrão (não manda ordem nenhuma). Conta de demonstração só depois de a estratégia passar no laboratório e o dono liberar.
Uso:  python3 -I mesa/robo/robo.py passo <estrategia>      → uma rodada (feche de vela); estado em dados/robo_<estrategia>.json
      python3 -I mesa/robo/robo.py estado <estrategia>
"""
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
DADOS = RAIZ / "dados"
FAPI = "https://fapi.binance.com/fapi/v1/klines"
SEG = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}

LIMITES = {                      # duros: a estratégia não muda
    "capital_papel": 10.0,       # US$ (igual às carteiras da mesa)
    "alavancagem_bruta_max": 1.0,  # Σ|posição| ≤ 1 × o patrimônio
    "perda_dia_max": 0.03,       # −3% no dia UTC → zera tudo e para
    "ordem_min_usd": 1.0,        # não ajusta posição por menos que isso
    "custo_lado": 0.0006,        # 0,06% por lado sobre o giro (perpétuo, tomador)
    "velas_velhas": 3,           # última vela fechada mais velha que 3 tempos → não faz nada
}


class ErroDado(Exception):
    pass


def velas(simbolo, tempo, n, agora=None, buscar=None):
    """[(abertura_ms, fechamento)] só de velas FECHADAS; ErroDado se a última fechada for velha."""
    agora = agora or time.time()
    if buscar is None:
        with urllib.request.urlopen(f"{FAPI}?symbol={simbolo}&interval={tempo}&limit={n + 1}", timeout=20) as r:
            k = json.load(r)
    else:
        k = buscar(simbolo, tempo, n + 1)
    fechadas = [(int(x[0]), float(x[4])) for x in k if int(x[6]) < agora * 1000]
    if not fechadas:
        raise ErroDado(f"{simbolo}: sem vela fechada")
    idade = agora - (fechadas[-1][0] / 1000 + SEG[tempo])
    if idade > LIMITES["velas_velhas"] * SEG[tempo]:
        raise ErroDado(f"{simbolo}: última vela fechada há {idade:.0f} s")
    return fechadas[-n:]


def carregar_estrategia(nome):
    arq = AQUI / "estrategias" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"estrategia_{nome}", arq)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Estrategia()


def _arq(nome):
    return DADOS / f"robo_{nome}.json"


def ler_estado(nome):
    try:
        return json.loads(_arq(nome).read_text())
    except (OSError, ValueError):
        return {"modo": "papel", "patrimonio": LIMITES["capital_papel"], "posicoes": {}, "precos": {}, "dia": None, "inicio_dia": None,
                "parado": None, "eventos": [], "rodadas": 0}


def salvar(nome, e):
    e["eventos"] = e["eventos"][-200:]
    DADOS.mkdir(exist_ok=True)
    tmp = _arq(nome).with_suffix(".tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False, indent=1))
    tmp.replace(_arq(nome))


def anotar(e, texto, agora):
    e["eventos"].append({"t": agora, "texto": texto})
    print(texto)


def marcar(e, precos):
    """Papel: atualiza o patrimônio com a variação de preço das posições (em US$ de nocional)."""
    for s, usd in e["posicoes"].items():
        p0, p1 = e["precos"].get(s), precos.get(s)
        if p0 and p1:
            e["patrimonio"] += usd * (p1 / p0 - 1)
            e["posicoes"][s] = usd * p1 / p0
    e["precos"].update(precos)


def virar_dia(e, agora):
    """ANTES de marcar os preços: o dia novo começa com o patrimônio da última rodada (senão, com vela diária, a queda do dia some)."""
    dia = time.strftime("%Y-%m-%d", time.gmtime(agora))
    if dia != e["dia"]:
        e["dia"], e["inicio_dia"] = dia, e["patrimonio"]


def risco_ok(e):
    return e["patrimonio"] >= e["inicio_dia"] * (1 - LIMITES["perda_dia_max"])


def limitar(pesos):
    bruta = sum(abs(w) for w in pesos.values())
    cap = LIMITES["alavancagem_bruta_max"]
    return {s: w * cap / bruta for s, w in pesos.items()} if bruta > cap else dict(pesos)


def rebalancear(e, alvo_pesos, agora):
    """Opera só a diferença entre a posição atual e o alvo; cobra o custo sobre o giro."""
    eq = e["patrimonio"]
    for s in sorted(set(alvo_pesos) | set(e["posicoes"])):
        alvo = alvo_pesos.get(s, 0.0) * eq
        atual = e["posicoes"].get(s, 0.0)
        delta = alvo - atual
        if abs(delta) < LIMITES["ordem_min_usd"]:
            continue
        e["patrimonio"] -= abs(delta) * LIMITES["custo_lado"]
        e["posicoes"][s] = alvo
        if abs(alvo) < 1e-9:
            e["posicoes"].pop(s, None)
        anotar(e, f"[PAPEL] {'compra' if delta > 0 else 'venda'} US$ {abs(delta):.2f} de {s} → posição US$ {alvo:+.2f}", agora)


def zerar(e, agora):
    if e["posicoes"]:
        rebalancear(e, {}, agora)


def passo(nome, agora=None, buscar=None):
    agora = agora or time.time()
    est = carregar_estrategia(nome)
    e = ler_estado(nome)
    if e.get("parado"):
        print(f"parado desde {e['parado']} (perda do dia); só o dono religa")
        return e
    try:
        dados = {s: velas(s, est.tempo, est.historico, agora, buscar) for s in est.simbolos}
    except (ErroDado, OSError, ValueError) as ex:
        anotar(e, f"sem dado bom ({ex}); nada muda", agora)
        salvar(nome, e)
        return e
    precos = {s: v[-1][1] for s, v in dados.items()}
    virar_dia(e, agora)
    marcar(e, precos)
    if not risco_ok(e):
        anotar(e, f"PERDA DO DIA passou de {LIMITES['perda_dia_max']:.0%}: zero tudo e paro", agora)
        zerar(e, agora)
        e["parado"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(agora))
        salvar(nome, e)
        return e
    alvo = limitar(est.pesos(dados))
    rebalancear(e, alvo, agora)
    e["rodadas"] += 1
    e["ultimo"] = {"t": agora, "pesos": alvo, "patrimonio": e["patrimonio"]}
    salvar(nome, e)
    print(f"{nome}: patrimônio US$ {e['patrimonio']:.4f} · pesos {json.dumps(alvo)}")
    return e


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("passo", "estado"):
        sys.exit(__doc__)
    if sys.argv[1] == "passo":
        passo(sys.argv[2])
    else:
        print(json.dumps(ler_estado(sys.argv[2]), ensure_ascii=False, indent=1))
