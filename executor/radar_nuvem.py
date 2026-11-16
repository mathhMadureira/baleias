"""📡 Radar (H56, regra R3) — SIMULADO, contínuo: lê o mercado a cada 2 s a partir das velas de 1 s, em todos os tempos gráficos.

Pedido do dono (16/11): "o que importa é a visão de oportunidade; se encontrar, entra comprado ou vendido; todos lendo o mercado a partir
de 1 segundo". REPROVADO no laboratório (lab/radar_1s.py, H56: R3 −0,017 US$/op depois do custo; +0,013 antes): está na mesa como
comparação ao vivo, por decisão do dono, como o Robô Livre (H47).

Leitura (igual ao teste): em cada segundo, z_w = retorno da janela w ÷ (desvio dos retornos de 1 s da última hora × √w) para
w ∈ {5 s, 15 s, 1 min, 5 min, 15 min, 1 h, 4 h}; a janela de maior |z| manda. Oportunidade: |z| ≥ 4 e volume da janela ≤ média da última
hora → entra CONTRA o movimento. Saída: stop 1%, stop móvel (arma +0,5%, guarda 70%), alvo +2% ou 1 h; 60 s de espera depois de sair.
US$ 25 por posição a 10× (margem 2,50), carteira de US$ 10, 0,06% por lado. Guarda do dia (H54) vale. Estado: dados/robo_radar.json.
Uso: RADAR_DURACAO=300 RADAR_CACHE=/tmp/radar.npz BALEIAS_DADOS=... python -m executor.radar_nuvem
"""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from baleias import config

MOEDAS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "PEPE", "SUI", "LINK", "AVAX", "TRX"]
JANELAS = [5, 15, 60, 300, 900, 3600, 14400]
HIST = 14400 + 3600 + 10
Z, NOC, ALAV, CUSTO, STOP, ALVO, ARMA, GUARDA, MAX_S, ESPERA = 4.0, 25.0, 10.0, 0.0006, 0.01, 0.02, 0.005, 0.70, 3600, 60
CAPITAL, PISO = 10.0, 5.0
ARQ, NOME = "robo_radar.json", "Radar"
DADOS = os.environ.get("BINANCE_DADOS", "https://data-api.binance.vision")
DURACAO = float(os.environ.get("RADAR_DURACAO", "300"))
CACHE = os.environ.get("RADAR_CACHE", "/tmp/radar_cache.npz")


def _klines(par, inicio_ms):
    u = f"{DADOS}/api/v3/klines?symbol={par}&interval=1s&startTime={int(inicio_ms)}&limit=1000"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "baleias/1.0"}), timeout=20) as r:
        return [x for x in json.load(r) if x[6] < time.time() * 1000]          # só segundos fechados


def atualizar(serie, par):
    """serie: array (n, 5) [t_ms, máx, mín, fech, volume US$]. Baixa os segundos novos (na 1ª vez, as últimas HIST)."""
    inicio = serie[-1, 0] + 1000 if len(serie) else time.time() * 1000 - HIST * 1000
    novos = []
    for _ in range(25):
        k = _klines(par, inicio)
        if not k:
            break
        novos += [[float(x[0]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in k]
        inicio = k[-1][0] + 1000
        if len(k) < 1000:
            break
    if novos:
        serie = np.concatenate([serie, np.array(novos)]) if len(serie) else np.array(novos)
    return serie[-HIST:]


def leitura(s, i):
    """(z com sinal, volume relativo) no segundo i da série s, pela janela de maior |z|; None sem histórico de 1 h."""
    if i < 3600:
        return None
    c, v = s[: i + 1, 3], s[: i + 1, 4]
    lc = np.log(c[-3601:])
    r1 = np.diff(lc)
    sig = float(np.sqrt(max(np.mean(r1 ** 2) - np.mean(r1) ** 2, 1e-18)))
    vh = float(np.mean(v[-3600:]))
    melhor = None
    for w in JANELAS:
        if i < w:
            continue
        z = (np.log(c[-1]) - np.log(c[-1 - w])) / (sig * np.sqrt(w))
        if melhor is None or abs(z) > abs(melhor[0]):
            melhor = (float(z), float(np.sum(v[-w:]) / (vh * w)) if vh > 0 else 99.0)
    return melhor


def _fechar(e, par, preco, motivo, t):
    p = e["abertas"].pop(par)
    res = NOC * p["sinal"] * (preco / p["entrada"] - 1) - 2 * CUSTO * NOC
    e["caixa"] += p["gasto"] + res
    e["fechadas"].append({**p, "saida": preco, "saida_t": t, "motivo": motivo, "resultado_usd": res})
    e["fechadas"] = e["fechadas"][-3000:]
    e["espera"][par] = t + ESPERA
    return f"📡 {NOME} SAIU da {'COMPRA' if p['sinal'] > 0 else 'VENDA'} em {par[:-4]} ({motivo}) a {preco:.6g}: {res:+.3f} USDT"


def conferir(e, par, seg):
    """Saída da posição no segundo seg = [t, máx, mín, fech, vol]; mesma ordem do teste (pior primeiro)."""
    p = e["abertas"][par]
    t, h, l = seg[0] / 1000, seg[1], seg[2]
    s, en = p["sinal"], p["entrada"]
    contra = (l / en - 1) if s > 0 else (1 - h / en)
    favor = (h / en - 1) if s > 0 else (1 - l / en)
    if contra <= -STOP:
        return _fechar(e, par, en * (1 - s * STOP), "stop de 1%", t)
    if p["pico"] >= ARMA and contra <= GUARDA * p["pico"]:
        return _fechar(e, par, en * (1 + s * GUARDA * p["pico"]), f"stop móvel (guardou {GUARDA * p['pico']:.2%})", t)
    if favor >= ALVO:
        return _fechar(e, par, en * (1 + s * ALVO), "alvo +2%", t)
    p["pico"] = max(p["pico"], favor)
    if t - p["entrada_t"] >= MAX_S:
        return _fechar(e, par, seg[3], "tempo máximo (1 h)", t)
    return None


def passo(e, series, ultimos, pausado=False):
    """Processa, em ordem, os segundos novos de cada moeda. ultimos: {par: t_ms já processado}. Devolve os textos."""
    textos = []
    for par, s in series.items():
        ini = int(np.searchsorted(s[:, 0], ultimos.get(par, s[-1, 0]), side="right")) if len(s) else 0
        for i in range(ini, len(s)):
            seg = s[i]
            if par in e["abertas"]:
                x = conferir(e, par, seg)
                if x:
                    textos.append(x)
                continue
            if pausado or seg[0] / 1000 < e["espera"].get(par, 0) or e["caixa"] < NOC / ALAV - 1e-9:
                continue
            if e["caixa"] + sum(q["gasto"] for q in e["abertas"].values()) < PISO:
                continue
            r = leitura(s, i)
            if not r or abs(r[0]) < Z or r[1] > 1.0:
                continue
            sinal = -1 if r[0] > 0 else 1
            e["caixa"] -= NOC / ALAV
            e["abertas"][par] = {"moeda": par, "sinal": sinal, "lado": "compra" if sinal > 0 else "venda", "entrada": seg[3],
                                 "entrada_t": seg[0] / 1000, "gasto": NOC / ALAV, "nocional": NOC, "pico": 0.0, "z": round(r[0], 2), "vol": round(r[1], 2)}
            textos.append(f"📡 {NOME} ENTROU {'COMPRADO' if sinal > 0 else 'VENDIDO'} em {par[:-4]} a {seg[3]:.6g} "
                          f"(movimento de {r[0]:+.1f}σ com volume {r[1]:.0%} da média: aposta na volta)")
        if len(s):
            ultimos[par] = float(s[-1, 0])
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "eventos": [], "espera": {},
                                                           "inicio": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    e.setdefault("espera", {})
    try:
        z = np.load(CACHE)
        series = {k: z[k] for k in z.files}
    except (OSError, ValueError):
        series = {}
    ultimos = e.get("ultimos", {})
    from executor import guarda_dia as GD
    inicio = time.time()
    while time.time() - inicio < DURACAO:
        def _um(m):                                    # as 12 moedas ao mesmo tempo (cada pedido leva de 0,2 a 5 s)
            par = m + "USDT"
            try:
                return par, atualizar(series.get(par, np.zeros((0, 5))), par)
            except (OSError, ValueError):
                return par, series.get(par)
        with ThreadPoolExecutor(len(MOEDAS)) as ex:
            for par, s in ex.map(_um, MOEDAS):
                if s is not None:
                    series[par] = s
        guarda, textos = GD.checar(e), []
        if guarda == "fechar":
            for par in list(e["abertas"]):
                s = series.get(par)
                textos.append(_fechar(e, par, float(s[-1, 3]) if s is not None and len(s) else e["abertas"][par]["entrada"], GD.motivo(e), time.time()))
            textos.append(GD.texto(NOME, e))
        for par, s in series.items():                   # 1ª vez ou volta depois de uma pausa > 60 s: começa do segundo atual
            if len(s) and (par not in ultimos or s[-1, 0] - ultimos[par] > 60_000):   # (não opera o passado como se fosse ao vivo)
                ultimos[par] = float(s[-1, 0])
        textos += passo(e, series, ultimos, pausado=guarda != "normal")
        e["patrimonio"] = e["caixa"] + sum(q["gasto"] + NOC * q["sinal"] * (float(series[par][-1, 3]) / q["entrada"] - 1)
                                           for par, q in e["abertas"].items() if par in series and len(series[par]))
        e["ultimos"] = ultimos
        e["eventos"] = ([{"t": time.time(), "texto": x} for x in textos] + e["eventos"])[:100]
        for x in textos:
            print("  ", x, flush=True)
        arq.write_text(json.dumps(e, ensure_ascii=False))
        time.sleep(2)
    np.savez(CACHE, **series)
    print(f"📡 {NOME}: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas")


if __name__ == "__main__":
    main()
