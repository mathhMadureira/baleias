"""Robô LBank (H53) — SIMULADO: day trade em TODAS as moedas do perpétuo da LBank (memecoins e HOOD inclusive; desde 16/11) com os preços públicos do perpétuo da LBank.

Nenhuma chave, nenhuma ordem: só dados públicos (`marketData` do perpétuo e velas de 1 min da API à vista da LBank).
Regra (rota R6 da H52 adaptada; lab/PROTOCOLO_LAB.md, H53):
  - lado = regime da amplitude das 140 moedas da Binance (executor.regime, H44): baixa → vende as que mais caem em 24 h (≤ −1%);
    alta → compra as que mais sobem (≥ +1%); neutro → segue a tendência de 24 h da própria moeda quando |variação| ≥ 3%;
  - saídas: stop móvel (executor.stop_movel: arma +0,5%, guarda 70%) e stop de 2% minuto a minuto, lado contra o regime (no neutro: a moeda
    virar), 24 h no máximo;
  - US$ 25 a 10× por posição, até 4, carteira de US$ 10, piso de US$ 5, 0,06% por lado. Funding não entra (anotado na H53).
Obedece às ordens do chefe da mesa (baleias.equipe). Estado: dados/robo_lbank.json.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

from baleias import config

PERP = "https://lbkperp.lbank.com"
SPOT = "https://api.lbank.info"
UA = {"User-Agent": "baleias/1.0"}
# Pedido do dono (16/11): o robô vê TODAS as moedas do perpétuo da LBank (memecoins inclusive), sem lista fixa, como os robôs da Binance.
# Velas de 1 min vêm do par à vista de mesmo nome (base_usdt); as exceções de nome ficam aqui.
SPOT_NOME = {"HOODUSDT": "hoodx_usdt"}
VOLUME_MIN = 1_000_000          # mesmo corte do universo da Binance (lab/universo.py): com dinheiro real, abaixo disso a ordem não executa no preço


def par_spot(perp):
    return SPOT_NOME.get(perp, perp[:-4].lower() + "_usdt")


ORCAMENTO, ALAV, CUSTO_LADO, STOP, MAX_POS, CAPITAL, PISO, MAX_HORAS = 25.0, 10.0, 0.0006, 0.02, 4, 10.0, 5.0, 24
MIN_REGIME, MIN_NEUTRO = 0.01, 0.03
ARQ, NOME = "robo_lbank.json", "Robô LBank"


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        d = json.load(r)
    if str(d.get("error_code", 0)) != "0":
        raise RuntimeError(f"LBank {d.get('error_code')}: {d.get('msg')}")
    return d.get("data")


def mercado():
    """{perpétuo: (último preço, variação de 24 h)} de todas as moedas USDT do perpétuo da LBank com volume ≥ US$ 1 mi em 24 h."""
    out = {}
    for x in _get(f"{PERP}/cfd/openApi/v1/pub/marketData?productGroup=SwapU") or []:
        s = str(x.get("symbol", ""))
        if s.endswith("USDT"):
            ultimo, abertura = float(x.get("lastPrice") or 0), float(x.get("openPrice") or 0)
            if ultimo > 0 and abertura > 0 and float(x.get("turnover") or 0) >= VOLUME_MIN:
                out[s] = (ultimo, ultimo / abertura - 1)
    return out


def minutos(par_spot, desde_ms, ate_ms):
    """Velas de 1 min da LBank à vista em [desde_ms, ate_ms) no formato do stop móvel: (t_ms, máxima, mínima)."""
    saida, t = [], int(desde_ms // 1000)
    try:
        while t * 1000 < ate_ms and len(saida) < 3000:
            k = _get(f"{SPOT}/v2/kline.do?symbol={par_spot}&size=500&type=minute1&time={t}") or []
            novos = [(int(x[0]) * 1000, float(x[2]), float(x[3])) for x in k if int(x[0]) * 1000 + 60_000 <= ate_ms and int(x[0]) >= t]
            if not novos:
                break
            saida += novos
            t = novos[-1][0] // 1000 + 60
            if len(k) < 500:
                break
    except (OSError, ValueError, RuntimeError):
        return []
    return saida


def velas15(perp):
    """Últimas 21 velas de 15 min do par à vista da LBank ([t, o, h, l, c, v]); a última, ainda aberta, sai. [] sem dados."""
    try:
        k = _get(f"{SPOT}/v2/kline.do?symbol={par_spot(perp)}&size=21&type=minute15&time={int(time.time()) - 21 * 900}") or []
    except (OSError, ValueError, RuntimeError):
        return []
    return [x for x in k if int(x[0]) + 900 <= time.time()]


def lado_desejado(regime, var24):
    if regime == "baixa":
        return "venda" if var24 <= -MIN_REGIME else None
    if regime == "alta":
        return "compra" if var24 >= MIN_REGIME else None
    if abs(var24) >= MIN_NEUTRO:
        return "compra" if var24 > 0 else "venda"
    return None


def _fechar(e, par, saida, motivo, agora):
    p = e["abertas"].pop(par)
    s = 1 if p["lado"] == "compra" else -1
    noc = p.get("nocional", ORCAMENTO)
    resultado = noc * s * (saida / p["entrada"] - 1) - 2 * CUSTO_LADO * noc
    e["caixa"] += p["gasto"] + resultado
    e["fechadas"].append({**p, "saida": saida, "saida_t": agora, "motivo": motivo, "resultado_usd": resultado})
    e["fechadas"] = e["fechadas"][-3000:]
    return f"🟣 {NOME} SAIU da {'COMPRA' if s > 0 else 'VENDA'} em {par[:-4]} ({motivo}) a {saida:.6g}: {resultado:+.3f} USDT"


def passo(e, mkt, regime, mins, agora, pausado=False, lado_ordem=None):
    """mkt: {par: (preço, var24)}; mins: {par: minutos desde a última conferência}. Devolve os textos."""
    from executor import stop_movel as SM
    textos = []
    for par in list(e["abertas"]):
        p = e["abertas"][par]
        r = SM.conferir(p, mins.get(par), STOP, agora * 1000, int(p["entrada_t"] * 1000))
        if r:
            textos.append(_fechar(e, par, r[0], r[1], r[2] / 1000))
            continue
        if par not in mkt:
            continue
        preco, var = mkt[par]
        if not mins.get(par) and (preco <= p["entrada"] * (1 - STOP) if p["lado"] == "compra" else preco >= p["entrada"] * (1 + STOP)):
            textos.append(_fechar(e, par, preco, f"stop de segurança −{STOP:.0%} (preço da rodada; moeda sem velas de 1 min)", agora))
            continue
        quer = lado_ordem or lado_desejado(regime, var)
        if regime and quer and quer != p["lado"]:
            textos.append(_fechar(e, par, preco, f"tendência de 24 h virou para {regime}", agora))
        elif not regime and quer and quer != p["lado"]:
            textos.append(_fechar(e, par, preco, "a moeda virou de lado em 24 h", agora))
        elif agora - p["entrada_t"] > MAX_HORAS * 3600:
            textos.append(_fechar(e, par, preco, f"tempo máximo ({MAX_HORAS} h)", agora))
    if e["caixa"] + sum(q["gasto"] for q in e["abertas"].values()) < PISO or pausado:
        return textos
    candidatos = []
    for par, (preco, var) in mkt.items():
        lado = lado_desejado(regime, var)
        if lado and (not lado_ordem or lado == lado_ordem) and par not in e["abertas"]:
            candidatos.append((abs(var), par, lado, preco, var))
    for _, par, lado, preco, var in sorted(candidatos, reverse=True):
        from executor import tamanho as TM
        noc = TM.nocional(e)                                   # H58: proporcional à carteira
        if len(e["abertas"]) >= MAX_POS or not noc:
            break
        e["caixa"] -= noc / ALAV
        e["abertas"][par] = {"moeda": par, "lado": lado, "entrada": preco, "entrada_t": agora, "gasto": noc / ALAV, "nocional": noc}
        textos.append(f"🟣 {NOME} ENTROU {'COMPRADO' if lado == 'compra' else 'VENDIDO'} em {par[:-4]} a {preco:.6g} "
                      f"({var:+.1%} em 24 h; regime {regime or 'neutro'})")
    return textos


def main():
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    arq = config.RAIZ / ARQ
    e = json.loads(arq.read_text()) if arq.exists() else {"caixa": CAPITAL, "abertas": {}, "fechadas": [], "eventos": [],
                                                           "inicio": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    agora = time.time()
    try:
        mkt = mercado()
    except (OSError, ValueError, RuntimeError) as ex:
        print(f"🟣 {NOME}: LBank fora do ar ({ex}); nada feito nesta rodada")
        return
    cache = Path(os.environ.get("CEREBROS_MOEDAS", config.RAIZ / "cerebros_moedas")) / "velas_v4.json"
    velas = json.loads(cache.read_text()) if cache.exists() else {}
    from executor import regime as RG
    reg, s24, _ = RG.de_velas({par: [x for x in k if x[6] < agora * 1000] for par, k in velas.items()})
    mins = {par: minutos(par_spot(par), max(int(p["entrada_t"] * 1000), int(p.get("movel_ate", 0))), agora * 1000) for par, p in e["abertas"].items()}
    from baleias import equipe
    pausado, lado_ord = equipe.lado_da_ordem("lbank", None)
    from executor import guarda_dia as GD                   # H54: dia que ficou positivo não é devolvido
    guarda, pre = GD.checar(e), []
    if guarda == "fechar":
        for par in list(e["abertas"]):
            pre.append(_fechar(e, par, mkt.get(par, (e["abertas"][par]["entrada"], 0))[0], GD.motivo(e), agora))
        pre.append(GD.texto(NOME, e))
    pausado = pausado or guarda != "normal"
    textos = pre + passo(e, mkt, reg, mins, agora, pausado=pausado, lado_ordem=lado_ord)
    e["regime"] = {"lado": reg, "subindo_24h": s24, "t": int(agora)}
    e["patrimonio"] = e["caixa"] + sum(q["gasto"] + q.get("nocional", ORCAMENTO) * (1 if q["lado"] == "compra" else -1) * (mkt.get(par, (q["entrada"], 0))[0] / q["entrada"] - 1)
                                       for par, q in e["abertas"].items())
    e["eventos"] = ([{"t": agora, "texto": x} for x in textos] + e["eventos"])[:100]
    arq.write_text(json.dumps(e, ensure_ascii=False))
    equipe.postar_eventos("lbank", textos)
    print(f"🟣 {NOME}: patrimônio US$ {e['patrimonio']:.2f} · {len(e['fechadas'])} fechadas · {len(e['abertas'])} abertas · regime {reg or 'neutro'}")
    for x in textos:
        print("  ", x)


if __name__ == "__main__":
    main()
