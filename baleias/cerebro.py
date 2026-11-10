"""Cérebro de day trade (BTC, 15 min): sinapses especialistas + rede neural + aprendizado com o erro + criação/poda de sinapses.

- Cada SINAPSE é uma rota de previsão da próxima vela (sobe/desce). Algumas são fixas (vêm do laboratório); uma é uma rede neural
  (MLP 22→12→1) que aprende por retropropagação a cada vela; outras nascem sozinhas.
- APRENDER COM O ERRO: depois de cada vela, toda sinapse que opinou é conferida. O peso de voto cai quando ela erra e sobe quando
  acerta (algoritmo Hedge, pesos multiplicativos). A rede neural corrige seus próprios pesos pelo gradiente do erro.
- NOVA ROTA: se o acerto do cérebro nas últimas 200 apostas ficar abaixo de 50% (limite superior de Wilson < 52%), ele cria
  sinapses novas (indicador × prazo × limiar × sentido sorteados de uma gramática). Nascem em OBSERVAÇÃO (sem voto) e só ganham
  voto com ≥ 150 previsões e limite inferior de Wilson > 50%; com 150 e acerto < 48%, são podadas.
- DECISÃO: contrato binário simulado (paga 0,51, recebe 1 se acertar). A probabilidade vem do acerto real de cada sinapse que
  opinou (encolhido para 50% quando há poucos dados), ponderado pelo peso de voto. Aposta só com ≥ 53% para um lado.
  Por que binário: num contrato linear, 15 min mexem ~0,16% e o custo é ~0,09% → precisaria acertar ~78%. No binário, ~51%.
Só biblioteca padrão (roda no painel, sem numpy).
"""
import json
import math
import random

PRECO = 0.51              # contrato binário Sobe/Desce de 15 min: paga 0,51 para receber 1 se acertar (1 centavo de spread)
APOSTA = 0.02             # 2% do capital por aposta
LIMIAR = 0.53             # só aposta com probabilidade calibrada ≥ 53% para um lado (equilíbrio ≈ 51%)
ETA = 0.08                # taxa de aprendizado do Hedge
MAX_SINAPSES = 24


def wilson(a, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    f = a / n
    c = (f + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(f * (1 - f) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


# ---------------- características de cada vela ----------------
def caracteristicas(v):
    """v: lista de velas (t, o, h, l, c, vol), a última fechada. Devolve dict de medidas sem olhar o futuro."""
    o, h, l, c, vol = ([x[k] for x in v] for k in (1, 2, 3, 4, 5))
    i = len(v) - 1
    r = [0.0] + [math.log(c[j] / c[j - 1]) for j in range(1, len(c))]
    janela = r[max(1, i - 95):i + 1]
    dp = math.sqrt(sum(x * x for x in janela) / len(janela)) or 1e-6
    n = 14
    tr = [max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1])) for j in range(i - n + 1, i + 1)]
    faixa = max(h[i - n + 1:i + 1]) - min(l[i - n + 1:i + 1])
    chop = 100 * math.log10(sum(tr) / faixa) / math.log10(n) if faixa > 0 and sum(tr) > 0 else 100.0
    vip = sum(abs(h[j] - l[j - 1]) for j in range(i - n + 1, i + 1))
    vim = sum(abs(l[j] - h[j - 1]) for j in range(i - n + 1, i + 1))
    ganhos = [max(r[j], 0) for j in range(i - 13, i + 1)]
    perdas = [max(-r[j], 0) for j in range(i - 13, i + 1)]
    rsi = 100 - 100 / (1 + (sum(ganhos) / (sum(perdas) or 1e-9)))
    media_vol = sum(vol[i - 96:i]) / 96 if i >= 96 else sum(vol[:i]) / max(1, i)
    hora = (v[i][0] // 900_000) % 96 / 96 * 2 * math.pi
    f = {f"r{k}": math.log(c[i] / c[i - k]) / (dp * math.sqrt(k)) for k in (1, 2, 4, 8, 16, 32)}
    f.update({"vi": (vip - vim) / (sum(tr) or 1e-9), "chop": chop, "rsi": rsi, "vol": math.log((vol[i] + 1) / (media_vol + 1)),
              "corpo": (c[i] - o[i]) / ((h[i] - l[i]) or 1e-9), "rompe": 1.0 if c[i] > max(h[i - 55:i]) else (-1.0 if c[i] < min(l[i - 55:i]) else 0.0),
              "hs": math.sin(hora), "hc": math.cos(hora), "dp": dp})
    f["corvos"] = 1.0 if all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2] else 0.0
    f["soldados"] = 1.0 if all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2] else 0.0
    return f


ENTRADAS_REDE = ["r1", "r2", "r4", "r8", "r16", "r32", "vi", "chop", "rsi", "vol", "corpo", "rompe", "hs", "hc", "corvos", "soldados"]


def vetor(f):
    escala = {"chop": (50, 15), "rsi": (50, 15)}
    saida = []
    for k in ENTRADAS_REDE:
        x = f[k]
        if k in escala:
            m, s = escala[k]
            x = (x - m) / s
        saida.append(max(-4.0, min(4.0, x)))
    return saida


# ---------------- rede neural (MLP) em Python puro ----------------
class Rede:
    def __init__(self, entradas, ocultos=12, semente=7, pesos=None):
        rnd = random.Random(semente)
        self.n, self.m = entradas, ocultos
        if pesos:
            self.W1, self.b1, self.W2, self.b2 = pesos
        else:
            self.W1 = [[rnd.gauss(0, 1 / math.sqrt(entradas)) for _ in range(entradas)] for _ in range(ocultos)]
            self.b1 = [0.0] * ocultos
            self.W2 = [rnd.gauss(0, 1 / math.sqrt(ocultos)) for _ in range(ocultos)]
            self.b2 = 0.0

    def prever(self, x):
        self._h = [math.tanh(sum(w * xi for w, xi in zip(lin, x)) + b) for lin, b in zip(self.W1, self.b1)]
        z = sum(w * hj for w, hj in zip(self.W2, self._h)) + self.b2
        self._x = x
        return 1 / (1 + math.exp(-max(-30, min(30, z))))

    def aprender(self, x, y, taxa=0.01, l2=1e-4):
        """Retropropagação de um exemplo (entropia cruzada): corrige os próprios pesos pelo erro."""
        p = self.prever(x)
        d = p - y
        for j in range(self.m):
            g = d * self.W2[j] * (1 - self._h[j] ** 2)
            self.W2[j] -= taxa * (d * self._h[j] + l2 * self.W2[j])
            for k in range(self.n):
                self.W1[j][k] -= taxa * (g * x[k] + l2 * self.W1[j][k])
            self.b1[j] -= taxa * g
        self.b2 -= taxa * d
        return p

    def exportar(self):
        return [self.W1, self.b1, self.W2, self.b2]


# ---------------- sinapses ----------------
def opiniao(sinapse, f, rede=None):
    """Devolve +1 (sobe), −1 (desce) ou 0 (não opina)."""
    tipo = sinapse["tipo"]
    if tipo == "rede":
        p = rede.prever(vetor(f))
        return 1 if p > 0.52 else (-1 if p < 0.48 else 0)
    if tipo == "vortice_invertido":
        return 0 if f["chop"] >= 38.2 or f["vi"] == 0 else (-1 if f["vi"] > 0 else 1)
    if tipo == "regra":
        x, lim = f[sinapse["medida"]], sinapse["limiar"]
        dispara = x >= lim if sinapse["lado"] == "alto" else x <= lim
        return sinapse["sentido"] if dispara else 0
    return 0


def sinapses_iniciais():
    return [
        {"id": "rede_neural", "tipo": "rede", "origem": "rede neural 16→12→1, aprende a cada vela"},
        {"id": "vortice_invertido", "tipo": "vortice_invertido", "origem": "H18/H19: contra o Vórtice quando CHOP < 38,2"},
        {"id": "reversao_queda", "tipo": "regra", "medida": "r4", "limiar": -2.5, "sentido": 1, "lado": "baixo", "origem": "H14: queda anormal de 1 h → sobe"},
        {"id": "reversao_alta", "tipo": "regra", "medida": "r4", "limiar": 2.5, "sentido": -1, "lado": "alto", "origem": "física: alta anormal de 1 h → devolve"},
        {"id": "tres_corvos", "tipo": "regra", "medida": "corvos", "limiar": 1.0, "sentido": 1, "lado": "alto", "origem": "H6: três corvos → sobe (efeito pequeno)"},
        {"id": "tres_soldados", "tipo": "regra", "medida": "soldados", "limiar": 1.0, "sentido": -1, "lado": "alto", "origem": "H6: três soldados → desce (efeito pequeno)"},
        {"id": "rompimento", "tipo": "regra", "medida": "rompe", "limiar": 1.0, "sentido": 1, "lado": "alto", "origem": "Tartaruga em 15 min: rompeu a máxima de 55"},
    ]


GRAMATICA = {"medida": ["r1", "r2", "r4", "r8", "r16", "r32", "vi", "vol", "corpo"], "limiar": [1.0, 1.5, 2.0, 2.5, 3.0], "sentido": [1, -1], "lado": ["alto", "baixo"]}


def nova_sinapse(rnd, existentes):
    """Cria uma rota nova que ainda não existe (indicador × limiar × sentido × lado)."""
    ids = {s["id"] for s in existentes}
    for _ in range(50):
        m, lim, sen, lado = (rnd.choice(GRAMATICA[k]) for k in ("medida", "limiar", "sentido", "lado"))
        limiar = lim if lado == "alto" else -lim
        if m in ("vi", "corpo"):
            limiar = limiar / 5          # medidas que vivem entre −1 e 1
        sid = f"nova_{m}_{lado}_{abs(limiar):g}_{'sobe' if sen > 0 else 'desce'}"
        if sid not in ids:
            return {"id": sid, "tipo": "regra", "medida": m, "limiar": limiar, "sentido": sen, "lado": lado,
                    "origem": f"criada pelo cérebro: quando {m} {'≥' if lado == 'alto' else '≤'} {limiar:g}, aposta {'sobe' if sen > 0 else 'desce'}"}
    return None


# ---------------- o cérebro ----------------
class Cerebro:
    def __init__(self, estado=None, semente=11):
        e = estado or {}
        self.rnd = random.Random(semente + len(e.get("diario", [])))
        self.sinapses = e.get("sinapses") or [dict(s, peso=1.0, status="ativa" if s["tipo"] != "regra" or not s["id"].startswith("nova") else "observacao",
                                                   acertos=0, previsoes=0, nascida=None) for s in sinapses_iniciais()]
        self.rede = Rede(len(ENTRADAS_REDE), pesos=e.get("rede"))
        self.historico = e.get("historico", [])          # apostas do cérebro: 1 acertou, 0 errou
        self.diario = e.get("diario", [])                # o que ele aprendeu/corrigiu/criou/podou
        self.operacoes = e.get("operacoes", [])
        self.capital = e.get("capital", 700.0)
        self.pendente = e.get("pendente")
        self.passos = e.get("passos", 0)
        self.ultima_t = e.get("ultima_t")

    def exportar(self):
        return {"sinapses": self.sinapses, "rede": self.rede.exportar(), "historico": self.historico[-2000:], "diario": self.diario[-300:],
                "operacoes": self.operacoes[-2000:], "capital": self.capital, "pendente": self.pendente, "passos": self.passos, "ultima_t": self.ultima_t}

    def _anotar(self, t, texto):
        self.diario.append({"t": t, "texto": texto})

    def conferir(self, t, retorno, f_anterior):
        """Chega o resultado da vela apostada: aprende com o erro de cada sinapse e da rede neural."""
        p = self.pendente
        if not p:
            return None
        subiu = 1 if retorno > 0 else 0
        erros = []
        for s in self.sinapses:
            op = p["opinioes"].get(s["id"], 0)
            if op == 0:
                continue
            acertou = (op > 0) == bool(subiu)
            s["previsoes"] += 1
            s["acertos"] += acertou
            if s["status"] == "ativa":
                s["peso"] *= math.exp(-ETA * (0 if acertou else 1) + ETA * 0.5)   # erra: perde peso; acerta: ganha
                s["peso"] = max(1e-3, min(50.0, s["peso"]))
            if not acertou and s["status"] == "ativa":
                erros.append(s["id"])
        # a rede neural corrige os próprios pesos com o resultado real
        self.rede.aprender(vetor(f_anterior), subiu)
        resultado = None
        if p.get("aposta") and retorno != 0:
            acertou = (p["aposta"] > 0) == bool(subiu)
            self.historico.append(1 if acertou else 0)
            ganho = APOSTA * ((1 / PRECO - 1) if acertou else -1.0)      # fração do capital
            self.capital *= 1 + ganho
            self.operacoes.append({"t": p["t"], "aposta": p["aposta"], "prob": p["prob"], "retorno": retorno, "liquido": ganho, "capital": self.capital})
            resultado = {"acertou": acertou, "ganho": ganho}
            if not acertou and erros:
                self._anotar(t, f"❌ Errou ({'sobe' if p['aposta'] > 0 else 'desce'}). Peso reduzido de: {', '.join(erros[:5])}. Rede neural corrigida.")
        self._revisar(t)
        self.pendente = None
        return resultado

    def _revisar(self, t):
        """Promove/poda sinapses e, se o cérebro estiver errando mais que acertando, cria rotas novas."""
        for s in self.sinapses:
            a, n = s["acertos"], s["previsoes"]
            lo, hi = wilson(a, n)
            if s["status"] == "observacao" and n >= 150:
                if lo > 0.50:
                    s["status"], s["peso"] = "ativa", 1.0
                    self._anotar(t, f"✅ Sinapse {s['id']} PROMOVIDA: {a}/{n} acertos ({a / n:.1%}, IC {lo:.1%}–{hi:.1%}). Passa a votar.")
                elif a / n < 0.48:
                    s["status"] = "podada"
                    self._anotar(t, f"✂ Sinapse {s['id']} PODADA: {a}/{n} acertos ({a / n:.1%}).")
            if s["status"] == "ativa" and s["tipo"] == "regra" and n >= 300 and hi < 0.5:
                s["status"] = "podada"
                self._anotar(t, f"✂ Sinapse {s['id']} PODADA depois de {n} previsões: {a / n:.1%} (IC {lo:.1%}–{hi:.1%}).")
        recente = self.historico[-200:]
        if len(recente) >= 100:
            lo, hi = wilson(sum(recente), len(recente))
            vivas = [s for s in self.sinapses if s["status"] != "podada"]
            if hi < 0.52 and len(vivas) < MAX_SINAPSES and (self.passos % 48 == 0):
                for _ in range(2):
                    nova = nova_sinapse(self.rnd, self.sinapses)
                    if nova:
                        self.sinapses.append(dict(nova, peso=0.0, status="observacao", acertos=0, previsoes=0, nascida=t))
                        self._anotar(t, f"🌱 NOVA SINAPSE (rota de teste): {nova['origem']}. Começa em observação.")

    def decidir(self, t, f, px):
        """Vela fechou: cada sinapse opina; a probabilidade é o acerto real de cada uma (encolhido), ponderado pelo peso."""
        self.passos += 1
        opinioes, soma, total = {}, 0.0, 0.0
        for s in self.sinapses:
            if s["status"] == "podada":
                continue
            op = opiniao(s, f, self.rede)
            opinioes[s["id"]] = op
            if op and s["status"] == "ativa":
                acerto = (s["acertos"] + 20) / (s["previsoes"] + 40)        # encolhe para 50% com poucos dados
                p_sobe = acerto if op > 0 else 1 - acerto
                soma += s["peso"] * p_sobe
                total += s["peso"]
        prob = soma / total if total else 0.5
        aposta = 1 if prob >= LIMIAR else (-1 if prob <= 1 - LIMIAR else None)
        self.pendente = {"t": t, "px": px, "opinioes": opinioes, "prob": prob, "aposta": aposta}
        self.ultima_t = t
        return self.pendente

    def resumo(self):
        h = self.historico
        lo, hi = wilson(sum(h), len(h))
        return {"apostas": len(h), "acerto": sum(h) / len(h) if h else None, "ic": [lo, hi] if h else None, "capital": self.capital,
                "sinapses": [{k: s.get(k) for k in ("id", "status", "peso", "acertos", "previsoes", "origem")} for s in self.sinapses],
                "diario": self.diario[-40:][::-1], "pendente": self.pendente and {k: self.pendente[k] for k in ("t", "px", "prob", "aposta")},
                "curva": [[o["t"], round(o["capital"], 2)] for o in self.operacoes[-1500:]], "passos": self.passos}
