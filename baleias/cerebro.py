"""Cérebro de day trade (BTC, 15 min): sinapses especialistas + rede neural + aprendizado com o erro + criação/poda de sinapses.

- Cada SINAPSE é uma rota de previsão da próxima vela (sobe/desce). Algumas são fixas (vêm do laboratório); uma é uma rede neural
  (MLP 22→12→1) que aprende por retropropagação a cada vela; outras nascem sozinhas.
- APRENDER COM O ERRO: depois de cada vela, toda sinapse que opinou é conferida. O peso de voto cai quando ela erra e sobe quando
  acerta (algoritmo Hedge, pesos multiplicativos). A rede neural corrige seus próprios pesos pelo gradiente do erro.
- NOVA ROTA: se o acerto do cérebro nas últimas 200 apostas ficar abaixo de 50% (limite superior de Wilson < 52%), ele cria
  sinapses novas (indicador × prazo × limiar × sentido sorteados de uma gramática). Nascem em OBSERVAÇÃO (sem voto) e só ganham
  voto com ≥ 150 previsões e limite inferior de Wilson > 50%; com 150 e acerto < 48%, são podadas.
- DECISÃO: contrato binário simulado (paga 0,51, recebe 1 se acertar). A probabilidade vem do acerto real de cada sinapse que
  opinou (encolhido para 50% quando há poucos dados), ponderado pelo peso de voto. Aposta só com ≥ 52% para um lado.
  Por que binário: num contrato linear, 15 min mexem ~0,16% e o custo é ~0,09% → precisaria acertar ~78%. No binário, ~51%.
Só biblioteca padrão (roda no painel, sem numpy).
"""
import json
import math
import random

PRECO = 0.51              # contrato binário Sobe/Desce de 15 min: paga 0,51 para receber 1 se acertar (1 centavo de spread)
APOSTA = 0.02             # 2% do capital por aposta
LIMIAR = 0.52             # aposta com probabilidade calibrada ≥ 52% para um lado (equilíbrio ≈ 51%; 1 ponto de margem)
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
    f.update(medidas_velez(o, h, l, c, i))
    f["corvos"] = 1.0 if all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2] else 0.0
    f["soldados"] = 1.0 if all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2] else 0.0
    return f


JANELA = 220                       # velas que cada cérebro enxerga (a média de 200 do Velez precisa disso)


def medidas_velez(o, h, l, c, i):
    """H23 (Oliver Velez): quadro de força (preço/SMA20/SMA200), 180, vela elefante, estado estreito e espaço duplo. 0 sem dados."""
    if i < 210:
        return {"espaco": 0.0, "v180": 0.0, "eleq": 0.0, "estr": 0.0}
    s20, s200 = sum(c[i - 19:i + 1]) / 20, sum(c[i - 199:i + 1]) / 200
    s20_10 = sum(c[i - 29:i - 9]) / 20
    p = c[i]
    alta, baixa = p > s20 > s200, p < s20 < s200
    faixa_m = sum(h[j] - l[j] for j in range(i - 20, i)) / 20
    elefante = faixa_m > 0 and (h[i] - l[i]) > 2 * faixa_m
    v180 = 1.0 if (c[i - 1] < o[i - 1] and c[i] > o[i] and c[i] >= o[i - 1] and o[i] <= c[i - 1] and alta) else \
        (-1.0 if (c[i - 1] > o[i - 1] and c[i] < o[i] and c[i] <= o[i - 1] and o[i] >= c[i - 1] and baixa) else 0.0)
    eleq = 1.0 if (elefante and alta and c[i] > o[i]) else (-1.0 if (elefante and baixa and c[i] < o[i]) else 0.0)
    estreito = abs(s20 - s200) / p < 0.012 and abs(s20 / s20_10 - 1) < 0.003
    estr = 1.0 if (elefante and estreito and c[i] > max(s20, s200) and c[i] > o[i]) else \
        (-1.0 if (elefante and estreito and c[i] < min(s20, s200) and c[i] < o[i]) else 0.0)
    espaco = 1.0 if (p > s20 * 1.03 and p > s200 * 1.03) else (-1.0 if (p < s20 * 0.97 and p < s200 * 0.97) else 0.0)
    return {"espaco": espaco, "v180": v180, "eleq": eleq, "estr": estr}


SINAPSES_VELEZ = [
    {"id": "velez_espaco_duplo_alto", "tipo": "regra", "medida": "espaco", "limiar": 1.0, "sentido": -1, "lado": "alto",
     "origem": "Velez: preço >3% acima das médias 20 e 200 (espaço duplo) → devolve. H23: passou no binário (BTC 58–64%, moedas 57%)"},
    {"id": "velez_espaco_duplo_baixo", "tipo": "regra", "medida": "espaco", "limiar": -1.0, "sentido": 1, "lado": "baixo",
     "origem": "Velez: preço >3% abaixo das médias 20 e 200 (espaço duplo) → volta. H23: passou no binário"},
    {"id": "velez_180_alta", "tipo": "regra", "medida": "v180", "limiar": 1.0, "sentido": 1, "lado": "alto", "origem": "Velez: 180 de alta a favor das médias (H23: sem vantagem no histórico)"},
    {"id": "velez_180_baixa", "tipo": "regra", "medida": "v180", "limiar": -1.0, "sentido": -1, "lado": "baixo", "origem": "Velez: 180 de baixa a favor das médias (H23: sem vantagem)"},
    {"id": "velez_elefante", "tipo": "regra", "medida": "eleq", "limiar": 1.0, "sentido": 1, "lado": "alto", "origem": "Velez: vela elefante de alta no quadro de força (H23: sem vantagem)"},
    {"id": "velez_estreito_rompe", "tipo": "regra", "medida": "estr", "limiar": 1.0, "sentido": 1, "lado": "alto", "origem": "Velez: rompimento do estado estreito (H23: sem vantagem)"},
]


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
        x, lim = f.get(sinapse["medida"], 0.0), sinapse["limiar"]
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
        ids = {x["id"] for x in self.sinapses}
        for nova in SINAPSES_VELEZ:                   # métodos estudados entram em observação: só votam se provarem ao vivo
            if nova["id"] not in ids:
                self.sinapses.append(dict(nova, peso=0.0, status="observacao", acertos=0, previsoes=0, nascida=e.get("ultima_t")))
        self.rede = Rede(len(ENTRADAS_REDE), pesos=e.get("rede"))
        self.historico = e.get("historico", [])          # apostas do cérebro: 1 acertou, 0 errou
        self.diario = e.get("diario", [])                # o que ele aprendeu/corrigiu/criou/podou
        self.operacoes = e.get("operacoes", [])
        self.capital = e.get("capital", 700.0)
        self.pendente = e.get("pendente")
        self.passos = e.get("passos", 0)
        self.ultima_t = e.get("ultima_t")
        self.inicio_ao_vivo = e.get("inicio_ao_vivo")     # apostas antes disto são aquecimento e não contam na avaliação

    def exportar(self):
        return {"sinapses": self.sinapses, "rede": self.rede.exportar(), "historico": self.historico[-2000:], "diario": self.diario[-300:],
                "operacoes": self.operacoes[-2000:], "capital": self.capital, "pendente": self.pendente, "passos": self.passos, "ultima_t": self.ultima_t,
                "inicio_ao_vivo": self.inicio_ao_vivo}

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

    def livro(self):
        """Livro de Métodos: cada sinapse com a definição exata, o placar e a classificação estatística.
        comprovado = ≥150 previsões e limite inferior de Wilson > 50%; promissor = acerto > 50% sem prova; reprovado = o resto."""
        saida = []
        for s in self.sinapses:
            a, n = s["acertos"], s["previsoes"]
            lo, hi = wilson(a, n)
            if n >= 150 and lo > 0.5 and s["status"] != "podada":
                classe = "comprovado"
            elif n and a / n > 0.5 and s["status"] != "podada":
                classe = "promissor"
            else:
                classe = "reprovado"
            definicao = {k: s[k] for k in ("tipo", "medida", "limiar", "sentido", "lado") if k in s}
            saida.append({"id": s["id"], "classe": classe, "acertos": a, "previsoes": n, "acerto": a / n if n else None,
                          "ic": [lo, hi] if n else None, "status": s["status"], "peso": s["peso"], "definicao": definicao, "origem": s["origem"]})
        ordem = {"comprovado": 0, "promissor": 1, "reprovado": 2}
        return sorted(saida, key=lambda x: (ordem[x["classe"]], -(x["acerto"] or 0)))

    def resumo(self):
        h = self.historico
        lo, hi = wilson(sum(h), len(h))
        vivo = [o for o in self.operacoes if self.inicio_ao_vivo and o["t"] >= self.inicio_ao_vivo]
        av = sum(1 for o in vivo if o["liquido"] > 0)
        lo_v, hi_v = wilson(av, len(vivo))
        ops = [o for o in self.operacoes if o.get("retorno")]
        ref = sum(o["retorno"] > 0 for o in ops) / len(ops) if ops else None     # referência trivial: "sempre sobe" nas mesmas velas
        return {"apostas": len(h), "acerto": sum(h) / len(h) if h else None, "ic": [lo, hi] if h else None, "capital": self.capital,
                "referencia_sempre_sobe": ref, "ao_vivo": {"apostas": len(vivo), "acerto": av / len(vivo) if vivo else None,
                                                            "ic": [lo_v, hi_v] if vivo else None,
                                                            "resultado": sum(o["liquido"] for o in vivo), "desde": self.inicio_ao_vivo},
                "sinapses": [{k: s.get(k) for k in ("id", "status", "peso", "acertos", "previsoes", "origem")} for s in self.sinapses],
                "diario": self.diario[-40:][::-1], "pendente": self.pendente and {k: self.pendente[k] for k in ("t", "px", "prob", "aposta")},
                "curva": [[o["t"], round(o["capital"], 2)] for o in self.operacoes[-1500:]], "passos": self.passos}


def votar_comprovados(livro, f, rede=None):
    """Para os outros robôs: voto (+ sobe, − desce, 0 neutro) dos métodos COMPROVADOS do livro sobre as medidas f de qualquer moeda.
    A rede neural só vota no BTC 15 min (onde foi treinada); as regras são transferíveis."""
    voto = 0.0
    usados = []
    for m in livro:
        if m["classe"] != "comprovado":
            continue
        d = m["definicao"]
        if d.get("tipo") == "rede":
            continue
        op = opiniao(d, f) if d.get("tipo") in ("regra", "vortice_invertido") else 0
        if op:
            voto += op * (m["acerto"] - 0.5)
            usados.append(m["id"])
    return voto, usados


def escrever_livro_md(livro, caminho):
    linhas = ["# Livro de Métodos do Cérebro", "", "Atualizado a cada vela de 15 min do BTC. Comprovado = ≥150 previsões e limite inferior de Wilson > 50%.", "",
              "| Método | Classe | Acerto | Previsões | IC 95% | Definição |", "|---|---|---|---|---|---|"]
    for m in livro:
        ac = f"{m['acerto']:.1%}" if m["acerto"] is not None else "—"
        ic = f"{m['ic'][0]:.1%}–{m['ic'][1]:.1%}" if m["ic"] else "—"
        linhas.append(f"| {m['id']} | {m['classe']} | {ac} | {m['previsoes']} | {ic} | {m['origem']} |")
    caminho.write_text("\n".join(linhas) + "\n")


# ---------------- passo a passo (o mesmo na nuvem e no painel) ----------------
def perda_do_dia(cb, t_ms):
    hoje = __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime(t_ms / 1000))
    return sum(o["capital"] - o["capital"] / (1 + o["liquido"]) for o in cb.operacoes
               if __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime(o["t"] / 1000)) == hoje), hoje


def passo(cb, v, teto=100.0):
    """v: velas fechadas (t, o, h, l, c, vol), a última é a nova. Confere a aposta pendente e decide a próxima.
    Devolve [(texto, notificar)] dos eventos."""
    eventos = []
    f = caracteristicas(v)
    t, px = v[-1][0], v[-1][4]
    if cb.pendente and cb.pendente["t"] < t:
        res = cb.conferir(t, math.log(px / cb.pendente["px"]), cb.pendente["f"])
        if res:
            eventos.append((f"🧠 Cérebro {'acertou ✓' if res['acertou'] else 'errou ✗'}: {res['ganho'] * 100:+.2f}% do capital | US$ {cb.capital:,.2f}", False))
    perda, hoje = perda_do_dia(cb, t)
    p = cb.decidir(t, f, px)
    p["f"] = f
    if perda <= -teto and p.get("aposta"):
        p["aposta"] = None
        if getattr(cb, "dia_teto", None) != hoje:
            cb.dia_teto = hoje
            cb._anotar(t, f"🛑 Teto de perda do dia (US$ {perda:,.2f}): sem apostas até 00:00 UTC.")
    if p.get("aposta"):
        eventos.append((f"🧠 Cérebro aposta {'▲ SOBE' if p['aposta'] > 0 else '▼ DESCE'} no BTC (prob. {p['prob']:.1%}) a {px:,.1f}, por 15 min", True))
    return eventos


def avancar(cb, todas):
    """todas: velas fechadas em ordem (≥ 120). Processa em sequência todas as que vêm depois de cb.ultima_t (revive pausas).
    Devolve [(texto, notificar)]."""
    tempos = [x[0] for x in todas]
    if cb.ultima_t is None:
        inicio = JANELA - 1                  # cérebro novo: aquece vivendo todas as velas disponíveis
    elif cb.ultima_t in tempos:
        inicio = tempos.index(cb.ultima_t) + 1
    else:
        cb.pendente = None                  # pausa maior que a janela: a aposta pendente não tem como ser conferida
        inicio = len(todas) - 1
    eventos = []
    for j in range(max(inicio, JANELA - 1), len(todas)):
        eventos += passo(cb, todas[j - JANELA + 1:j + 1])
    perdidas = len(todas) - max(inicio, JANELA - 1)
    if perdidas > 1:
        cb._anotar(cb.ultima_t, f"⏸ Revivi {perdidas} velas em sequência desde a última vez (pausa ou intervalo da nuvem).")
    return eventos


# ---------------- Cérebro v2: mecanismos do cérebro humano (docs/CEREBRO_HUMANO.md) ----------------
MEIA_VIDA = 300                      # esquecimento: o placar usado para decidir tem meia-vida de ~300 previsões
LAMBDA = 0.5 ** (1 / MEIA_VIDA)
TETO_VOTO = 0.40                     # homeostase: nenhuma sinapse passa de 40% do voto
ETA_DOPAMINA = 0.05
HIPOCAMPO = 3000                     # episódios guardados para o sono
SONO_A_CADA = 96                     # dorme uma vez por dia (96 velas de 15 min)


class CerebroV2(Cerebro):
    def __init__(self, estado=None, semente=23):
        super().__init__(estado, semente)
        e = estado or {}
        self.hipocampo = e.get("hipocampo", [])
        self.surpresa = e.get("surpresa", 0.0)
        for s in self.sinapses:
            s.setdefault("ew_a", 0.0)
            s.setdefault("ew_n", 0.0)
            s.setdefault("ew_r", 0.0)

    def exportar(self):
        return super().exportar() | {"hipocampo": self.hipocampo[-HIPOCAMPO:], "surpresa": self.surpresa, "versao": 2}

    def _acerto_recente(self, s):
        return (s["ew_a"] + 20) / (s["ew_n"] + 40)

    def decidir(self, t, f, px):
        """Igual ao v1, mas a probabilidade usa o placar COM esquecimento, e a metacognição se abstém depois de sequência ruim."""
        self.passos += 1
        opinioes, soma, total = {}, 0.0, 0.0
        for s in self.sinapses:
            if s["status"] == "podada":
                continue
            op = opiniao(s, f, self.rede)
            opinioes[s["id"]] = op
            if op and s["status"] == "ativa":
                a = self._acerto_recente(s)
                soma += s["peso"] * (a if op > 0 else 1 - a)
                total += s["peso"]
        prob = soma / total if total else 0.5
        aposta = 1 if prob >= LIMIAR else (-1 if prob <= 1 - LIMIAR else None)
        recentes = self.historico[-60:]
        if aposta and len(recentes) >= 30 and wilson(sum(recentes), len(recentes))[1] < 0.5:
            aposta = None                       # metacognição: "estou errando demais agora", não decide
        self.pendente = {"t": t, "px": px, "opinioes": opinioes, "prob": prob, "aposta": aposta}
        self.ultima_t = t
        return self.pendente

    def conferir(self, t, retorno, f_anterior):
        p = self.pendente
        if not p:
            return None
        subiu = 1 if retorno > 0 else 0
        movimento = retorno / (f_anterior.get("dp") or 1e-3)        # tamanho do movimento em desvios
        # surpresa (noradrenalina): o acerto recente das sinapses ativas se afastou do de longo prazo?
        eta = ETA_DOPAMINA * (1 + self.surpresa)
        erros = []
        for s in self.sinapses:
            op = p["opinioes"].get(s["id"], 0)
            if op == 0:
                continue
            acertou = (op > 0) == bool(subiu)
            s["previsoes"] += 1
            s["acertos"] += acertou
            s["ew_a"] = LAMBDA * s["ew_a"] + acertou            # esquecimento
            s["ew_n"] = LAMBDA * s["ew_n"] + 1
            recompensa = max(-3.0, min(3.0, op * movimento))      # dopamina: recompensa com o tamanho do movimento
            erro_previsao = recompensa - s["ew_r"]                # erro de previsão de recompensa
            s["ew_r"] = 0.98 * s["ew_r"] + 0.02 * recompensa
            if s["status"] == "ativa":
                s["peso"] = max(1e-3, min(50.0, s["peso"] * math.exp(eta * erro_previsao)))
                if not acertou:
                    erros.append(s["id"])
        self._homeostase()
        x = vetor(f_anterior)
        self.rede.aprender(x, subiu, taxa=0.01 * (1 + self.surpresa))
        self.hipocampo.append([x, subiu])
        self.hipocampo = self.hipocampo[-HIPOCAMPO:]
        resultado = None
        if p.get("aposta") and retorno != 0:
            acertou = (p["aposta"] > 0) == bool(subiu)
            self.historico.append(1 if acertou else 0)
            ganho = APOSTA * ((1 / PRECO - 1) if acertou else -1.0)
            self.capital *= 1 + ganho
            self.operacoes.append({"t": p["t"], "aposta": p["aposta"], "prob": p["prob"], "retorno": retorno, "liquido": ganho, "capital": self.capital})
            resultado = {"acertou": acertou, "ganho": ganho}
            if not acertou and erros:
                self._anotar(t, f"❌ Errou. Dopamina negativa em: {', '.join(erros[:5])}. Rede corrigida (taxa ×{1 + self.surpresa:.1f}).")
        self._medir_surpresa(t)
        self._revisar(t)
        if self.passos % SONO_A_CADA == 0:
            self._dormir(t)
        self.pendente = None
        return resultado

    def _homeostase(self):
        ativas = [s for s in self.sinapses if s["status"] == "ativa"]
        for _ in range(3):
            total = sum(s["peso"] for s in ativas)
            for s in ativas:
                if total and s["peso"] / total > TETO_VOTO:
                    s["peso"] = TETO_VOTO / (1 - TETO_VOTO) * (total - s["peso"])

    def _medir_surpresa(self, t):
        h = self.historico
        if len(h) < 120:
            return
        curto, longo = h[-40:], h[-400:]
        pl = sum(longo) / len(longo)
        z = abs(sum(curto) / len(curto) - pl) / math.sqrt(max(pl * (1 - pl), 1e-3) / len(curto))
        antes = self.surpresa
        self.surpresa = min(3.0, max(0.0, z - 1.0))
        if self.surpresa >= 1.0 > antes:
            self._anotar(t, f"⚡ Surpresa alta (z {z:.1f}): o mercado mudou de comportamento. Aprendendo {1 + self.surpresa:.1f}× mais rápido.")

    def _dormir(self, t):
        """Sono: reencena os episódios do hipocampo (embaralhados, taxa pequena) e renormaliza os pesos (homeostase do sono)."""
        if len(self.hipocampo) < 200:
            return
        episodios = list(self.hipocampo)
        self.rnd.shuffle(episodios)
        for x, y in episodios:
            self.rede.aprender(x, y, taxa=0.002)
        for s in self.sinapses:
            if s["status"] == "ativa":
                s["peso"] = s["peso"] ** 0.8
        self._homeostase()
        self._anotar(t, f"😴 Sono: reencenei {len(episodios)} episódios guardados e renormalizei os pesos das sinapses.")


# ---------------- Cérebro do robô rápido: 33 moedas, velas de 5 min, horizonte de 1 h ----------------
HORIZONTE = 12                     # 12 velas do tempo gráfico (5 min → 1 h; 1 min → 12 min)
CUSTO_SPOT = 0.002                 # ida e volta no spot (0,1% por lado)
CUSTO_PERP = 0.001                 # ida e volta no perpétuo simulado (0,05% por lado): permite comprar E vender a descoberto


class CerebroRapido(Cerebro):
    """O mesmo cérebro (sinapses + rede neural + Hedge + criação/poda), aprendendo com todas as moedas ao mesmo tempo.
    Cada observação vira uma previsão de "sobe na próxima hora", conferida 12 velas depois."""

    def __init__(self, estado=None, semente=31):
        super().__init__(estado, semente)
        e = estado or {}
        self.previsoes = e.get("previsoes", [])          # pendentes: {m, t, px, x, opinioes, prob}
        self.oportunidades = e.get("oportunidades", [])

        self.base_sobe = e.get("base_sobe", 0.5)          # humor do mercado: fração recente de previsões que terminaram em alta
        self.passo_ms = e.get("passo_ms")

    def exportar(self):
        return super().exportar() | {"previsoes": self.previsoes[-3000:], "oportunidades": self.oportunidades[:33], "versao": "rapido",
                                     "base_sobe": self.base_sobe, "passo_ms": self.passo_ms}

    @staticmethod
    def vantagem(s):
        """Acerto ACIMA do que o humor do mercado daria sozinho (encolhido com poucos dados). Num dia em que 68% das velas caem,
        uma regra "desce" com 70% de acerto vale +2%, não +20%: assim o cérebro não confunde tendência do dia com sabedoria."""
        n = s["previsoes"]
        esperado = s.get("esperado", 0.5 * n)
        return (s["acertos"] - esperado) / (n + 40)

    def _revisar(self, t):
        """Como no cérebro base, mas promove/poda pelo acerto acima do esperado (o humor do mercado), não acima de 50%."""
        for s in self.sinapses:
            a, n = s["acertos"], s["previsoes"]
            base = s.get("esperado", 0.5 * n) / n if n else 0.5
            lo, hi = wilson(a, n)
            if s["status"] == "observacao" and n >= 150:
                if lo > base:
                    s["status"], s["peso"] = "ativa", 1.0
                    self._anotar(t, f"✅ Sinapse {s['id']} PROMOVIDA: {a}/{n} ({a / n:.1%}, IC {lo:.1%}–{hi:.1%}) contra {base:.1%} do mercado.")
                elif a / n < base - 0.02:
                    s["status"] = "podada"
                    self._anotar(t, f"✂ Sinapse {s['id']} PODADA: {a}/{n} ({a / n:.1%}) contra {base:.1%} do mercado.")
            if s["status"] == "ativa" and s["tipo"] == "regra" and n >= 300 and hi < base:
                s["status"] = "podada"
                self._anotar(t, f"✂ Sinapse {s['id']} PODADA depois de {n} previsões: {a / n:.1%} contra {base:.1%} do mercado.")
        recente = self.historico[-200:]
        if len(recente) >= 100 and wilson(sum(recente), len(recente))[1] < 0.52 and self.passos % 48 == 0:
            vivas = [s for s in self.sinapses if s["status"] != "podada"]
            if len(vivas) < MAX_SINAPSES:
                for _ in range(2):
                    nova = nova_sinapse(self.rnd, self.sinapses)
                    if nova:
                        self.sinapses.append(dict(nova, peso=0.0, status="observacao", acertos=0, previsoes=0, esperado=0.0, nascida=t))
                        self._anotar(t, f"🌱 NOVA SINAPSE (rota de teste): {nova['origem']}. Começa em observação.")

    def avaliar(self, m, v):
        """Só pensa, não registra: (prob de subir em 1 h, valor esperado, medidas, opiniões). Usado na varredura contínua."""
        f = caracteristicas(v)
        opinioes, soma, total = {}, 0.0, 0.0
        for s in self.sinapses:
            if s["status"] == "podada":
                continue
            op = opiniao(s, f, self.rede)
            opinioes[s["id"]] = op
            if op and s["status"] == "ativa":
                a = self.vantagem(s)
                soma += s["peso"] * (0.5 + a if op > 0 else 0.5 - a)
                total += s["peso"]
        prob = soma / total if total else 0.5
        mov = 0.8 * f["dp"] * math.sqrt(HORIZONTE)
        ev_compra, ev_venda = (2 * prob - 1) * mov - CUSTO_PERP, (1 - 2 * prob) * mov - CUSTO_PERP
        lado, ev = ("compra", ev_compra) if ev_compra >= ev_venda else ("venda", ev_venda)
        f["_mov"] = mov
        return prob, ev, f, opinioes, lado

    def observar(self, m, v):
        """v: velas fechadas (t, o, h, l, c, vol) da moeda m, a última é a nova. Devolve (prob de subir em 1 h, valor esperado)."""
        f = caracteristicas(v)
        opinioes, soma, total = {}, 0.0, 0.0
        for s in self.sinapses:
            if s["status"] == "podada":
                continue
            op = opiniao(s, f, self.rede)
            opinioes[s["id"]] = op
            if op and s["status"] == "ativa":
                a = self.vantagem(s)
                soma += s["peso"] * (0.5 + a if op > 0 else 0.5 - a)
                total += s["peso"]
        prob = soma / total if total else 0.5
        movimento = 0.8 * f["dp"] * math.sqrt(HORIZONTE)          # movimento típico em 1 h
        ev_compra, ev_venda = (2 * prob - 1) * movimento - CUSTO_PERP, (1 - 2 * prob) * movimento - CUSTO_PERP
        lado, ev = ("compra", ev_compra) if ev_compra >= ev_venda else ("venda", ev_venda)
        f["_mov"] = movimento
        self.previsoes.append({"m": m, "t": v[-1][0], "px": v[-1][4], "x": vetor(f), "opinioes": opinioes, "prob": prob})
        return prob, ev, f, lado

    def resolver(self, m, v):
        """Confere as previsões da moeda m cuja hora já passou: cada sinapse aprende com o erro; a rede se corrige."""
        fech = {x[0]: x[4] for x in v}
        if len(v) > 1:
            self.passo_ms = v[-1][0] - v[-2][0]                # duração da vela (1 min, 5 min...): o horizonte é sempre 12 velas
        restantes, feitas = [], 0
        for p in self.previsoes:
            alvo = p["t"] + HORIZONTE * (self.passo_ms or 300_000)
            if p["m"] != m or alvo not in fech:
                if p["m"] != m or alvo > v[-1][0]:
                    restantes.append(p)
                continue
            subiu = 1 if fech[alvo] > p["px"] else 0
            for s in self.sinapses:
                op = p["opinioes"].get(s["id"], 0)
                if not op:
                    continue
                acertou = (op > 0) == bool(subiu)
                s.setdefault("esperado", 0.5 * s["previsoes"])
                s["esperado"] += self.base_sobe if op > 0 else 1 - self.base_sobe   # quanto acertaria só seguindo o humor do mercado
                s["previsoes"] += 1
                s["acertos"] += acertou
                if s["status"] == "ativa":
                    s["peso"] = max(1e-3, min(50.0, s["peso"] * math.exp(-ETA * (0 if acertou else 1) + ETA * 0.5)))
            self.base_sobe += (subiu - self.base_sobe) / 2000      # média móvel de ~2000 previsões
            self.rede.aprender(p["x"], subiu, taxa=0.005)
            if p["prob"] >= LIMIAR or p["prob"] <= 1 - LIMIAR:      # o que o cérebro "apostaria": vira o histórico dele
                self.historico.append(1 if (p["prob"] > 0.5) == bool(subiu) else 0)
            feitas += 1
        self.previsoes = restantes
        if feitas:
            self.passos += 1
            self._revisar(v[-1][0])
        return feitas


class CerebrosPorMoeda:
    """Pedido do dono: análise personalizada e isolada para cada moeda. Um CerebroRapido inteiro (sinapses, rede neural, humor do
    mercado, criação e poda) por moeda; nenhuma moeda aprende com o que aconteceu nas outras. Mesma interface do CerebroRapido."""

    def __init__(self, estado=None):
        e = estado or {}
        self.cerebros = {m: CerebroRapido(x, semente=31 + i) for i, (m, x) in enumerate(sorted(e.get("moedas", {}).items()))}
        self.oportunidades = e.get("oportunidades", [])
        self._diario = e.get("diario", [])

    def _de(self, m):
        if m not in self.cerebros:
            self.cerebros[m] = CerebroRapido(None, semente=31 + len(self.cerebros))
        return self.cerebros[m]

    def resolver(self, m, v):
        return self._de(m).resolver(m, v)

    def observar(self, m, v):
        return self._de(m).observar(m, v)

    def avaliar(self, m, v):
        return self._de(m).avaliar(m, v)

    def _anotar(self, t, texto):
        self._diario.append({"t": t, "texto": texto})

    @property
    def passos(self):
        return sum(c.passos for c in self.cerebros.values())

    @property
    def historico(self):
        return [h for c in self.cerebros.values() for h in c.historico[-200:]]

    @property
    def sinapses(self):
        return [s for c in self.cerebros.values() for s in c.sinapses]

    @property
    def diario(self):
        """Diário comum + o de cada moeda (com o nome dela na frente), em ordem de tempo."""
        todos = list(self._diario) + [{"t": d["t"], "texto": f"[{m[:-4]}] {d['texto']}"} for m, c in self.cerebros.items() for d in c.diario[-20:]]
        return sorted(todos, key=lambda d: d["t"])[-200:]

    def exportar(self):
        return {"moedas": {m: c.exportar() for m, c in self.cerebros.items()}, "oportunidades": self.oportunidades[:33],
                "diario": self._diario[-200:], "versao": "por_moeda"}


# ---------------- autoconhecimento: o robô estuda as próprias operações ----------------
FAIXAS = [(0.5, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 1.01)]


def autoanalise(fechadas, agora=None):
    """Lê as operações fechadas do próprio robô (com prob, lado e moeda guardados na entrada) e tira conclusões que mudam o
    comportamento: calibração (quando digo X%, acerto quanto?), lado em que é pior, moedas em que perde sempre."""
    agora = agora or __import__("time").time()
    ops = [f for f in fechadas if f.get("prob_lado") is not None]
    rel = {"operacoes": len(ops), "calibracao": [], "lados": {}, "moedas": {}, "geladeira": [], "margem_lado": {}, "conclusoes": []}
    for lo, hi in FAIXAS:
        xs = [f for f in ops if lo <= f["prob_lado"] < hi]
        if xs:
            g = sum(f["resultado_usd"] > 0 for f in xs)
            rel["calibracao"].append({"faixa": f"{lo:.0%}–{min(hi, 1):.0%}", "n": len(xs), "acerto": g / len(xs), "previsto": sum(f["prob_lado"] for f in xs) / len(xs)})
    for lado in ("compra", "venda"):
        xs = [f for f in ops if f.get("lado", "compra") == lado]
        if xs:
            g = sum(f["resultado_usd"] > 0 for f in xs)
            lo_, hi_ = wilson(g, len(xs))
            rel["lados"][lado] = {"n": len(xs), "acerto": g / len(xs), "resultado": sum(f["resultado_usd"] for f in xs)}
            if len(xs) >= 10 and hi_ < 0.5:
                rel["margem_lado"][lado] = 0.001          # exige +0,1% a mais de valor esperado nesse lado
                rel["conclusoes"].append(f"sou pior {'comprando' if lado == 'compra' else 'vendendo'}: {g}/{len(xs)} com lucro; passo a exigir mais certeza nesse lado")
    for m in sorted({f["moeda"] for f in ops}):
        xs = [f for f in ops if f["moeda"] == m]
        g = sum(f["resultado_usd"] > 0 for f in xs)
        rel["moedas"][m[:-4]] = {"n": len(xs), "acerto": g / len(xs), "resultado": sum(f["resultado_usd"] for f in xs)}
        recentes = [f for f in xs if agora - f["saida_t"] < 86400]
        if len(xs) >= 6 and g / len(xs) <= 0.2 and recentes:
            rel["geladeira"].append(m)
            rel["conclusoes"].append(f"perco quase sempre em {m[:-4]} ({g}/{len(xs)}): {m[:-4]} vai para a geladeira por 24 h")
    for c in rel["calibracao"]:
        if c["n"] >= 10 and c["acerto"] < c["previsto"] - 0.1:
            rel["conclusoes"].append(f"estou confiante demais na faixa {c['faixa']}: previ {c['previsto']:.0%}, acertei {c['acerto']:.0%} ({c['n']} operações)")
    return rel


def prob_calibrada(p, rel):
    """Corrige a probabilidade pelo que o robô realmente acertou nessa faixa (encolhendo para a previsão com peso 10)."""
    for c in rel.get("calibracao", []):
        lo, hi = (float(x.strip("%")) / 100 for x in c["faixa"].split("–"))
        if lo <= p < (hi if hi < 1 else 1.01):
            return (c["acerto"] * c["n"] + p * 10) / (c["n"] + 10)
    return p
