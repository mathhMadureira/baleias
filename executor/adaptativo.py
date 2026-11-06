"""Aprendizado com os próprios erros: várias versões do robô (limiar da previsão × tempo de segurar) são avaliadas em toda
oportunidade, pelo resultado que TERIAM tido depois do custo, e a escolha é por amostragem de Thompson.
"Não operar" vale zero: se todas as versões perdem, o robô aprende sozinho a ficar de fora.
"""
import json
import math
import random
import time
import urllib.request

LIMIARES = (0.0, 0.10, 0.25)         # % de movimento previsto necessário (0,25 = custo + margem)
SEGURAR_MIN = (5, 15, 30, 60, 240)   # 60 e 240 min: horizontes mais longos, como os vencedores estudados
LADOS = ("compra", "venda")          # venda = operar na queda (vendido)
BRACOS = [f"{lado}_lim{l:.2f}_seg{s}" for lado in LADOS for l in LIMIARES for s in SEGURAR_MIN]
INTERVALO_OPORTUNIDADE_S = 300       # no máximo uma oportunidade a cada 5 min (minutos vizinhos são quase a mesma informação)
PRIOR_DP = 0.3                       # % por operação: incerteza inicial
ESQUEMA = """
CREATE TABLE IF NOT EXISTS robo_bracos(braco TEXT PRIMARY KEY, n INTEGER, soma REAL, soma2 REAL);
CREATE TABLE IF NOT EXISTS robo_oportunidades(id INTEGER PRIMARY KEY, t_ms INTEGER, px REAL, previsto REAL, bracos TEXT, resolvida INTEGER DEFAULT 0, resultados TEXT);
"""


def parametros(braco):
    """(lado, limiar, segurar). Nomes antigos, sem lado, são de compra."""
    partes = braco.split("_")
    lado = partes[0] if partes[0] in LADOS else "compra"
    lim, seg = partes[-2], partes[-1]
    return lado, float(lim[3:]), int(seg[3:])


def dispara(braco, previsto):
    lado, lim, _ = parametros(braco)
    return previsto > lim if lado == "compra" else -previsto > lim


def posterior(n, soma, soma2):
    """Média e desvio da média do resultado (%), encolhidos para zero com um prior fraco."""
    if n == 0:
        return 0.0, PRIOR_DP
    media = soma / n
    var = max((soma2 - n * media * media) / max(n - 1, 1), 0.01)
    prec = 1 / PRIOR_DP ** 2 + n / var
    return (n / var) * media / prec, math.sqrt(1 / prec)


def estatisticas(c):
    linhas = {r["braco"]: r for r in c.execute("SELECT * FROM robo_bracos")}
    return {b: (linhas[b]["n"], linhas[b]["soma"], linhas[b]["soma2"]) if b in linhas else (0, 0.0, 0.0) for b in BRACOS}


def escolher(c, previsto, rnd=random):
    """Entre as versões que disparariam com esta previsão, sorteia pela posterior; devolve o braço ou None (não operar)."""
    est = estatisticas(c)
    melhor, valor = None, 0.0  # "não operar" vale zero
    for b in BRACOS:
        if not dispara(b, previsto):
            continue
        m, dp = posterior(*est[b])
        amostra = rnd.gauss(m, dp)
        if amostra > valor:
            melhor, valor = b, amostra
    return melhor


def resultado_versao(px_entrada, velas, segurar_min, stop_pct, custo_pct, lado="compra"):
    """Velas de 1 min a partir da entrada: (t, o, h, l, c). Sai no stop (se o preço andar contra) ou no fechamento do tempo."""
    janela = velas[:segurar_min]
    if len(janela) < segurar_min:
        return None
    for v in janela:
        if (lado == "compra" and v[3] <= px_entrada * (1 - stop_pct / 100)) or (lado == "venda" and v[2] >= px_entrada * (1 + stop_pct / 100)):
            return -stop_pct - custo_pct
    r = (janela[-1][4] / px_entrada - 1) * 100
    return (r if lado == "compra" else -r) - custo_pct


def registrar_oportunidade(c, t_ms, px, previsto):
    ultima = c.execute("SELECT MAX(t_ms) FROM robo_oportunidades").fetchone()[0]
    if ultima is not None and t_ms - ultima < INTERVALO_OPORTUNIDADE_S * 1000:
        return False
    disparam = [b for b in BRACOS if dispara(b, previsto)]
    c.execute("INSERT INTO robo_oportunidades(t_ms,px,previsto,bracos) VALUES(?,?,?,?)", (t_ms, px, previsto, json.dumps(disparam)))
    c.commit()
    return True


def _velas_binance(t_inicio_ms, minutos, abrir=urllib.request.urlopen):
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={t_inicio_ms}&limit={minutos}"
    with abrir(url, timeout=20) as r:
        return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in json.load(r)]


def resolver(c, stop_pct, custo_pct, agora_ms=None, buscar=_velas_binance):
    """Calcula o que cada versão teria ganhado e atualiza a memória. É aqui que o robô aprende com os erros."""
    agora_ms = agora_ms or int(time.time() * 1000)
    feitas = 0
    for o in c.execute("SELECT * FROM robo_oportunidades WHERE resolvida=0 AND t_ms<=?", (agora_ms - (max(SEGURAR_MIN) + 2) * 60_000,)).fetchall():
        velas = buscar(o["t_ms"] + 60_000 - o["t_ms"] % 60_000, max(SEGURAR_MIN))
        res = {}
        for b in json.loads(o["bracos"]):
            lado, _, seg = parametros(b)
            r = resultado_versao(o["px"], velas, seg, stop_pct, custo_pct, lado)
            if r is None:
                continue
            res[b] = r
            c.execute("INSERT INTO robo_bracos VALUES(?,1,?,?) ON CONFLICT(braco) DO UPDATE SET n=n+1, soma=soma+excluded.soma, soma2=soma2+excluded.soma2",
                      (b, r, r * r))
        c.execute("UPDATE robo_oportunidades SET resolvida=1, resultados=? WHERE id=?", (json.dumps(res), o["id"]))
        feitas += 1
    c.commit()
    return feitas


def painel(c):
    saida = []
    for b, (n, s, s2) in estatisticas(c).items():
        m, dp = posterior(n, s, s2)
        lado, lim, seg = parametros(b)
        saida.append({"braco": b, "lado": lado, "limiar": lim, "segurar": seg, "n": n, "media_bruta": s / n if n else None, "media": m, "dp": dp})
    return sorted(saida, key=lambda x: -x["media"])
