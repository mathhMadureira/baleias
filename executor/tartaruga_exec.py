"""Robô Tartaruga (H10b): decide e executa sozinho. Só compra, spot, sem alavancagem.

- Uma vez por dia, depois do fechamento das 00:00 UTC: sai de quem fechou abaixo da mínima de 20 dias; entra em quem fechou acima da
  máxima de 55 dias, com risco de 1% do patrimônio e stop 2N.
- Simulado (padrão): preços reais, ordens imaginárias; stop conferido a cada minuto.
- Real (BINANCE_REAL=1): ordem a mercado e stop STOP_LOSS_LIMIT guardado na Binance — o stop executa mesmo com esta máquina desligada.
Estado em dados/robo_tartaruga.json; cada decisão vira uma linha em dados/robo_eventos.jsonl (o painel lê e notifica).
"""
import json
import os
import time
from pathlib import Path

from baleias import config
from lab import tartaruga as T

ESTADO = config.RAIZ / "robo_tartaruga.json"
PARAR = Path(__file__).resolve().parent.parent / "PARAR"   # botão de parada (o mesmo do robô antigo): com este arquivo, nenhuma entrada nova (stops e saídas continuam)
EVENTOS = config.RAIZ / "robo_eventos.jsonl"
CAPITAL_SIMULADO = float(os.environ.get("TARTARUGA_CAPITAL", "700"))
RISCO = float(os.environ.get("TARTARUGA_RISCO", "0.01"))
MAX_POSICOES = int(os.environ.get("TARTARUGA_MAX_POSICOES", "0")) or None   # H13: só no robô-sombra, até passar no teste
relogio = time.time        # o replay troca por um relógio simulado
ouvinte = None             # o replay recebe cada evento por aqui (e o terminal não é inundado)


class Simulada:
    """Mesma interface da corretora real; preenche no preço de mercado e cobra a taxa."""
    real = False

    def __init__(self, cliente, estado):
        self.c, self.e = cliente, estado

    def precos(self, simbolos):
        return self.c.precos(simbolos)

    def usdt_livre(self):
        return self.e["caixa"]

    def comprar(self, simbolo, usdt, px):
        qtd = usdt * (1 - T.CUSTO_LADO) / px
        self.e["caixa"] -= usdt
        return qtd, px, usdt

    def vender(self, simbolo, qtd, px):
        recebido = qtd * px * (1 - T.CUSTO_LADO)
        self.e["caixa"] += recebido
        return px, recebido

    def colocar_stop(self, simbolo, qtd, stop):
        return None

    def cancelar(self, simbolo, ordem):
        pass

    def stop_saiu(self, simbolo, posicao, px):
        """Simulado: o stop 'executa' quando o preço ao vivo toca nele."""
        return (px is not None and px <= posicao["stop"]), px


class Real(Simulada):
    real = True

    def usdt_livre(self):
        return self.c.saldo("USDT")

    def comprar(self, simbolo, usdt, px):
        return self.c.comprar_mercado(simbolo, usdt)

    def vender(self, simbolo, qtd, px):
        return self.c.vender_mercado(simbolo, qtd)

    def colocar_stop(self, simbolo, qtd, stop):
        return self.c.colocar_stop(simbolo, qtd, stop)

    def cancelar(self, simbolo, ordem):
        if ordem:
            self.c.cancelar(simbolo, ordem)

    def stop_saiu(self, simbolo, posicao, px):
        status, medio = self.c.consultar(simbolo, posicao["ordem_stop"])
        return status == "FILLED", medio


def novo_estado(caixa=CAPITAL_SIMULADO):
    return {"caixa": caixa, "abertas": {}, "fechadas": [], "ultimo_dia": None, "inicio": time.strftime("%Y-%m-%d"), "radar": [], "patrimonio": caixa}


def carregar():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else novo_estado()


def salvar(e):
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, indent=1))
    tmp.replace(ESTADO)


def registrar(texto, tipo="robo", t=None):
    linha = {"t": t or relogio(), "tipo": tipo, "texto": texto}
    if ouvinte:
        ouvinte(linha)
        return linha
    with open(EVENTOS, "a") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    print(time.strftime("%F %T"), texto, flush=True)
    return linha


def patrimonio(e, precos, corretora):
    caixa = corretora.usdt_livre()
    return caixa + sum(p["qtd"] * precos.get(m, p["entrada"]) for m, p in e["abertas"].items())


def _sair(e, corretora, m, motivo, px, ja_vendido=None):
    p = e["abertas"].pop(m)
    if ja_vendido is None:
        corretora.cancelar(m, p.get("ordem_stop"))
        px, recebido = corretora.vender(m, p["qtd"], px)
    else:
        px, recebido = ja_vendido, p["qtd"] * ja_vendido * (1 - T.CUSTO_LADO)
        if not corretora.real:
            e["caixa"] += recebido
    resultado = recebido - p["gasto"]
    R = resultado / p["risco_usd"] if p["risco_usd"] else 0.0
    e["fechadas"].append({**p, "saida": px, "saida_t": relogio(), "motivo": motivo, "resultado_usd": resultado, "R": R})
    return registrar(f"🐢 Robô SAIU de {m[:-4]} ({motivo}) a {px:,.6g}: {resultado:+,.2f} USDT ({R:+.1f}R)"
                     f"{'' if corretora.real else ' [simulado]'}")


def radar(dados, precos):
    """Para cada moeda: quanto falta para o rompimento de 55 dias e onde ficaria o stop — o que o robô está esperando."""
    saida = []
    for m, vs in dados.items():
        if len(vs) <= T.ENTRADA:
            continue
        k = len(vs) - 1
        maxima = max(v[2] for v in vs[k - T.ENTRADA + 1:k + 1])
        n = T.atr(vs)[k]
        px = precos.get(m, vs[k][4])
        saida.append({"moeda": m[:-4], "preco": px, "rompimento": maxima, "falta_pct": (maxima / px - 1) * 100,
                      "stop_pct": -T.STOP_N * n / px * 100 if n else None})
    return sorted(saida, key=lambda x: x["falta_pct"])


def stops_perdidos(e, corretora, dados):
    """Simulado: se a máquina ficou desligada, confere nas velas diárias fechadas se a mínima tocou o stop (como no teste histórico).
    Sai no stop, ou na abertura se o dia já abriu abaixo dele. No real o stop está na corretora e isto não é usado."""
    eventos = []
    if corretora.real:
        return eventos
    for m in list(e["abertas"]):
        p = e["abertas"][m]
        visto = p.get("conferido_ate") or time.strftime("%Y-%m-%d", time.gmtime(p["entrada_t"]))
        for d, o, h, l, c in dados.get(m, []):
            if d <= visto:
                continue
            if l <= p["stop"]:
                eventos.append(_sair(e, corretora, m, "stop 2N (atingido com a máquina desligada)", min(o, p["stop"]), ja_vendido=min(o, p["stop"])))
                break
            p["conferido_ate"] = d
    return eventos


def passo_diario(e, corretora, dados, precos):
    eventos = stops_perdidos(e, corretora, dados)
    for m in list(e["abertas"]):
        vs = dados.get(m)
        if vs and len(vs) > T.SAIDA and T.saida_canal(vs, len(vs) - 1, "compra"):
            eventos.append(_sair(e, corretora, m, "fechou abaixo da mínima de 20 dias", precos.get(m)))
    total = patrimonio(e, precos, corretora)
    if PARAR.exists():
        eventos.append(registrar("🛑 Botão de parada ligado (arquivo PARAR): nenhuma entrada nova hoje; stops e saídas seguem normais"))
        e["ultimo_dia"] = time.strftime("%Y-%m-%d", time.gmtime(relogio()))
        return eventos
    for m, vs in dados.items():
        if m in e["abertas"] or m not in precos or len(vs) <= T.ENTRADA:
            continue
        k = len(vs) - 1
        if not T.sinais(vs, k, "compra"):
            continue
        if MAX_POSICOES and len(e["abertas"]) >= MAX_POSICOES:
            eventos.append(registrar(f"🐢 {m[:-4]} rompeu, mas já há {MAX_POSICOES} posições abertas (teto)"))
            continue
        n = T.atr(vs)[k]
        if not n:
            continue
        px = precos[m]
        usdt = min(RISCO * total / (T.STOP_N * n) * px, corretora.usdt_livre() * 0.98)
        if usdt < 6:                       # mínimo da Binance com folga
            eventos.append(registrar(f"🐢 {m[:-4]} rompeu a máxima de 55 dias, mas não há caixa para a posição mínima"))
            continue
        qtd, preco_medio, gasto = corretora.comprar(m, usdt, px)
        stop = preco_medio - T.STOP_N * n
        ordem = corretora.colocar_stop(m, qtd, stop)
        e["abertas"][m] = {"moeda": m, "entrada": preco_medio, "qtd": qtd, "stop": stop, "ordem_stop": ordem, "N": n,
                           "entrada_t": relogio(), "gasto": gasto, "risco_usd": qtd * (preco_medio - stop)}
        eventos.append(registrar(f"🐢 Robô ENTROU COMPRADO em {m[:-4]} a {preco_medio:,.6g} (rompeu a máxima de 55 dias). "
                                 f"Stop {stop:,.6g} ({(stop / preco_medio - 1) * 100:.1f}%), posição US$ {gasto:,.2f}, "
                                 f"risco US$ {qtd * (preco_medio - stop):,.2f} = 1R{'' if corretora.real else ' [simulado]'}"))
    e["ultimo_dia"] = time.strftime("%Y-%m-%d", time.gmtime(relogio()))
    return eventos


def checar_stops(e, corretora, precos):
    eventos = []
    for m in list(e["abertas"]):
        saiu, px = corretora.stop_saiu(m, e["abertas"][m], precos.get(m))
        if saiu:
            eventos.append(_sair(e, corretora, m, "stop 2N", px, ja_vendido=px))
    return eventos


def rodar(cliente, real=False):
    e = carregar()
    if real and not e.get("modo_real"):
        e = novo_estado(caixa=0.0)
        e["modo_real"] = True
    corretora = (Real if real else Simulada)(cliente, e)
    registrar(f"🐢 Robô Tartaruga ligado ({'REAL' if real else 'simulado'}), {len(e['abertas'])} posições abertas")
    dados, precos_ok = None, {}
    while True:
        try:
            precos = corretora.precos(T.MOEDAS_ROBO)
            precos_ok = precos
            g = time.gmtime()
            if e.get("ultimo_dia") != time.strftime("%Y-%m-%d", g) and (g.tm_hour > 0 or g.tm_min >= 2):
                T.CACHE_VIVO.unlink(missing_ok=True)
                dados = T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO)
                passo_diario(e, corretora, dados, precos)
            elif dados is None:
                dados = T.baixar(T.MOEDAS_ROBO, T.CACHE_VIVO, T.DIAS_VIVO)
            checar_stops(e, corretora, precos)
            e["radar"] = radar(dados, precos)
            e["patrimonio"] = patrimonio(e, precos, corretora)
            e["atualizado"] = time.time()
            curva = e.setdefault("curva", [])
            if not curva or time.time() - curva[-1][0] >= 900:          # um ponto a cada 15 min
                curva.append([int(time.time()), round(e["patrimonio"], 4)])
                del curva[:-6000]
            salvar(e)
            msg = f"tartaruga: patrimônio US$ {e['patrimonio']:,.2f}, {len(e['abertas'])} abertas, mais perto: " + \
                  ", ".join(f"{r['moeda']} {r['falta_pct']:+.1f}%" for r in e["radar"][:3])
        except Exception as ex:
            msg = f"tartaruga erro: {type(ex).__name__}: {str(ex)[:160]}"
            print(time.strftime("%F %T"), msg, flush=True)
        yield msg, precos_ok
        time.sleep(60)
