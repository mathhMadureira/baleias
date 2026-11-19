"""H66 — busca computacional em 4.896 variações com reserva intocada (pré-registrada em lab/PROTOCOLO_LAB.md antes dos dados).

Treino (60%) → 20 melhores pelo t → validação (20%) → a melhor com média > 0 e t ≥ 2 → reserva (20%), uma vez.
Uso: .venv-ml/bin/python -m lab.busca_dobrar
"""
import json
import math
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as janela

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "dados" / "lab" / "h66_1h.npz"
SAIDA = REPO / "dados" / "lab" / "busca_dobrar_resultado.json"
BASE = "https://fapi.binance.com/fapi/v1"
HORA, CUSTO = 3_600_000, 0.0012
STOPS, ALVOS, MOVEL, PRAZOS = (0.005, 0.01, 0.02, 0.03), (None, 2, 3), (False, True), (6, 24, 72)
SAIDAS = [(s, a, m, h) for s in STOPS for a in ALVOS for m in MOVEL for h in PRAZOS]          # 72
NS = len(SAIDAS)


def pedir(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise
        except (OSError, ValueError):
            time.sleep(2 + 3 * k)
    raise OSError("sem resposta")


def baixar():
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        return list(z["moedas"]), z["t"], z["H"], z["L"], z["C"], z["V"]
    moedas = json.loads((REPO / "dados" / "lab" / "h65_cache.json").read_text())["moedas"]
    fim = int(time.time() * 1000) // HORA * HORA
    ini = fim - 365 * 24 * HORA
    t = np.arange(ini, fim, HORA, dtype=np.int64)
    H, L, C, V = (np.full((len(moedas), len(t)), np.nan, dtype=np.float64) for _ in range(4))
    for i, p in enumerate(moedas):
        a = ini
        try:
            while a < fim:
                k = pedir(f"{BASE}/klines?symbol={p}&interval=1h&startTime={a}&endTime={fim - 1}&limit=1500")
                if not k:
                    break
                for x in k:
                    j = (int(x[0]) - ini) // HORA
                    if 0 <= j < len(t) and int(x[6]) < fim:
                        H[i, j], L[i, j], C[i, j], V[i, j] = float(x[2]), float(x[3]), float(x[4]), float(x[7])
                a = int(k[-1][0]) + HORA
                time.sleep(0.15)
                if len(k) < 1500:
                    break
        except (OSError, urllib.error.HTTPError) as ex:
            print(f"  {p}: {str(ex)[:60]}")
        if i % 10 == 0:
            print(f"  velas {i}/{len(moedas)}", flush=True)
    np.savez_compressed(CACHE, moedas=np.array(moedas), t=t, H=H, L=L, C=C, V=V)
    return moedas, t, H, L, C, V


def adiante(x, j):
    y = np.full_like(x, np.nan)
    y[:-j] = x[j:]
    return y


def resultados(h, l, c, lado):
    """R[k, t]: retorno líquido da entrada no fechamento t com a saída k, lado +1/−1. NaN = não resolve nos dados."""
    T = len(c)
    R = np.full((NS, T), np.nan, dtype=np.float32)
    fh = [None] + [adiante(h, j) for j in range(1, 73)]
    fl = [None] + [adiante(l, j) for j in range(1, 73)]
    fc = [None] + [adiante(c, j) for j in range(1, 73)]
    with np.errstate(invalid="ignore", divide="ignore"):
        for s in STOPS:
            for a in ALVOS:
                for m in MOVEL:
                    res = np.full(T, np.nan)
                    vivo = np.isfinite(c)
                    pico = np.zeros(T)
                    ant = np.zeros(T)                       # retorno no fechamento da vela anterior (a favor)
                    alvo = a * s if a else None
                    for j in range(1, 73):
                        hh, ll = fh[j], fl[j]
                        fav = (hh / c - 1) if lado > 0 else (1 - ll / c)
                        adv = (ll / c - 1) if lado > 0 else (1 - hh / c)
                        sem = ~np.isfinite(fav)
                        if m:                               # correção 19/11: se o fechamento anterior já estava abaixo do nível, sai nele (a abertura)
                            sai = vivo & (pico >= 0.005) & (adv <= 0.7 * pico)
                            res[sai] = np.minimum(0.7 * pico, ant)[sai]
                            vivo &= ~sai
                        sai = vivo & (adv <= -s)
                        res[sai] = -s
                        vivo &= ~sai
                        if alvo:
                            sai = vivo & (fav >= alvo)
                            res[sai] = alvo
                            vivo &= ~sai
                        pico = np.where(sem, pico, np.maximum(pico, fav))
                        ant = np.where(np.isfinite(fc[j]), lado * (fc[j] / c - 1), ant)
                        if j in PRAZOS:
                            fim = np.where(vivo, lado * (fc[j] / c - 1), res)
                            k = SAIDAS.index((s, a, m, j))
                            R[k] = (fim - CUSTO).astype(np.float32)
    return R


def rolar(x, n, f):
    y = np.full_like(x, np.nan)
    if len(x) > n:
        y[n:] = f(janela(x[:-1], n)[: len(x) - n], axis=1)     # só velas anteriores
    return y


def sinais(h, l, c, v):
    s = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        for n in (12, 24, 48, 168):
            mx, mn = rolar(h, n, np.max), rolar(l, n, np.min)
            s[f"rompe{n}"] = (c > mx).astype(np.int8) - (c < mn).astype(np.int8)
        for L in (1, 4, 24):
            r = np.full_like(c, np.nan)
            r[L:] = c[L:] / c[:-L] - 1
            sd = rolar(r, 720, np.nanstd)
            z = r / sd
            for k in (2, 3):
                s[f"ret{L}h_z{k}"] = (np.sign(r) * (np.abs(z) >= k)).astype(np.int8)
        for M in (20, 50, 200):
            mm = np.full_like(c, np.nan)
            mm[M - 1:] = janela(c, M).mean(axis=1)
            acima = c > mm
            ant = np.roll(acima, 1)
            ant[0] = acima[0]
            s[f"cruza_mm{M}"] = (acima & ~ant).astype(np.int8) - (~acima & ant & np.isfinite(mm)).astype(np.int8)
        d = np.diff(c, prepend=np.nan)
        g = np.where(d > 0, d, 0.0)
        p = np.where(d < 0, -d, 0.0)
        mg = np.full_like(c, np.nan)
        mp = np.full_like(c, np.nan)
        mg[14:] = janela(g[1:], 14).mean(axis=1)
        mp[14:] = janela(p[1:], 14).mean(axis=1)
        ifr = 100 - 100 / (1 + mg / np.where(mp == 0, 1e-12, mp))
        ifr_ant = np.roll(ifr, 1)
        for lo, hi in ((20, 80), (30, 70)):
            s[f"ifr{lo}_{hi}"] = ((ifr >= hi) & (ifr_ant < hi)).astype(np.int8) - ((ifr <= lo) & (ifr_ant > lo)).astype(np.int8)
        med = rolar(v, 48, np.median)
        for k in (3, 5):
            s[f"volume{k}x"] = (np.sign(d) * (v >= k * med)).astype(np.int8)
    out = {}
    for nome, x in s.items():
        x[~np.isfinite(c)] = 0
        out[nome + "_segue"] = x
        out[nome + "_contra"] = (-x).astype(np.int8)
    return out                                                         # 34


def estat(S, N):
    n = N.sum(axis=-1).astype(np.float64)
    soma = S.sum(axis=-1, dtype=np.float64)
    m = np.where(n > 0, soma / np.maximum(n, 1), 0)
    var = ((S - N * m[..., None]) ** 2).sum(axis=-1, dtype=np.float64)
    t = np.where(var > 0, m / (np.sqrt(var) / np.maximum(n, 1)), 0)
    return n, m, t


def main():
    moedas, T_, H, L, C, V = baixar()
    nm, T = C.shape
    print(f"{nm} moedas, {T} horas", flush=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        r24 = np.full_like(C, np.nan)
        r24[:, 24:] = C[:, 24:] / C[:, :-24] - 1
        val = np.isfinite(r24).sum(axis=0)
        frac = np.where(val >= 30, (r24 > 0).sum(axis=0) / np.maximum(val, 1), 0.5)
    regime = (frac >= 0.7).astype(np.int8) - (frac <= 0.3).astype(np.int8)
    nomes = None
    c1, c2 = int(0.6 * T), int(0.8 * T)
    corte = np.ones(T, dtype=bool)
    corte[c1 - 72:c1] = False                     # entradas cuja saída cruzaria para o trecho seguinte ficam fora
    corte[c2 - 72:c2] = False
    S = N = None
    t0 = time.time()
    for i in range(nm):
        if np.isfinite(C[i]).sum() < 2000:
            continue
        sg = sinais(H[i], L[i], C[i], V[i])
        if nomes is None:
            nomes = list(sg)
            S = np.zeros((len(nomes) * 2 * NS, T), dtype=np.float32)
            N = np.zeros((len(nomes) * 2 * NS, T), dtype=np.uint8)
        Rl, Rc = resultados(H[i], L[i], C[i], 1), resultados(H[i], L[i], C[i], -1)
        for a, nome in enumerate(nomes):
            for f in (0, 1):
                x = sg[nome] if f == 0 else np.where(sg[nome] == regime, sg[nome], 0)
                base = (a * 2 + f) * NS
                for lado, R in ((1, Rl), (-1, Rc)):
                    idx = np.where((x == lado) & corte)[0]
                    if not len(idx):
                        continue
                    vals = R[:, idx]
                    ok = np.isfinite(vals)
                    S[base:base + NS, idx] += np.where(ok, vals, 0)
                    N[base:base + NS, idx] += ok
        print(f"  moeda {i + 1}/{nm} ({moedas[i]}) {time.time() - t0:.0f}s", flush=True)
    rotulo = [f"{nomes[k // (2 * NS)]} | {'regime' if (k // NS) % 2 else 'sem filtro'} | stop {SAIDAS[k % NS][0]:.1%}, alvo "
              f"{(str(SAIDAS[k % NS][1]) + '×stop') if SAIDAS[k % NS][1] else 'nenhum'}, móvel {'sim' if SAIDAS[k % NS][2] else 'não'}, "
              f"{SAIDAS[k % NS][3]} h" for k in range(S.shape[0])]
    n_tr, m_tr, t_tr = estat(S[:, :c1], N[:, :c1])
    cand = np.where(n_tr >= 200)[0]
    top = cand[np.argsort(-t_tr[cand])][:20]
    print(f"\n{len(cand)} variações com ≥ 200 entradas no treino (de {S.shape[0]})")
    n_va, m_va, t_va = estat(S[top, c1:c2], N[top, c1:c2])
    tab = []
    print("| # | variação | treino n / média / t | validação n / média / t |\n|---|---|---|---|")
    for j, k in enumerate(top):
        tab.append({"variacao": rotulo[k], "treino": [int(n_tr[k]), float(m_tr[k]), float(t_tr[k])], "validacao": [int(n_va[j]), float(m_va[j]), float(t_va[j])]})
        print(f"| {j + 1} | {rotulo[k]} | {int(n_tr[k])} / {m_tr[k]:+.3%} / {t_tr[k]:+.2f} | {int(n_va[j])} / {m_va[j]:+.3%} / {t_va[j]:+.2f} |")
    ok = [j for j in range(len(top)) if m_va[j] > 0 and t_va[j] >= 2]
    res = {"variacoes": int(S.shape[0]), "com_200": int(len(cand)), "top20": tab}
    if not ok:
        print("\nNenhuma das 20 passou na validação (média > 0 e t ≥ 2): para aqui; a reserva não é usada.")
        res["veredito"] = "reprovada na validação"
        SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return
    j = max(ok, key=lambda q: t_va[q])
    k = top[j]
    print(f"\nEscolhida: {rotulo[k]}")
    Sr, Nr = S[k, c2:], N[k, c2:]
    n_r, m_r, t_r = estat(Sr[None], Nr[None])
    meio = (T - c2) // 2
    halves = [float(Sr[a:b].sum() / max(Nr[a:b].sum(), 1)) for a, b in ((0, meio), (meio, T - c2))]
    passa = bool(m_r[0] > 0 and t_r[0] >= 2 and all(x > 0 for x in halves))
    print(f"RESERVA: n {int(n_r[0])}, média {m_r[0]:+.3%}, t {t_r[0]:+.2f}, metades {halves[0]:+.3%} {halves[1]:+.3%} → {'PASSOU' if passa else 'reprovada'}")
    res.update({"escolhida": rotulo[k], "reserva": {"n": int(n_r[0]), "media": float(m_r[0]), "t": float(t_r[0]), "metades": halves}, "veredito": "PASSOU" if passa else "reprovada na reserva"})
    rets = []
    for h in range(T - c2):
        if Nr[h]:
            rets += [float(Sr[h] / Nr[h])] * int(Nr[h])
    if rets:
        def fator(p):
            return min(5.0, max(1.25, 2.5 * p / 10))
        dobrou = 0
        for _ in range(10000):
            p = 10.0
            random.shuffle(rets)
            for r in rets:
                p += max(fator(p) * p * r, -p / 4)
                if p >= 20 or p < 5:
                    break
            dobrou += p >= 20
        res["monte_carlo_chance_dobrar"] = dobrou / 10000
        print(f"Monte Carlo (10.000 ordens): chance de dobrar US$ 10 antes do piso de US$ 5 = {dobrou / 100:.1f}%")
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
