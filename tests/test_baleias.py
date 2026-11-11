import ast
import math
import json
import pathlib
import random
import unittest

from baleias import aprendizado as A, api, backtest as B, config, selecao, sinais as S

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "baleias"


def fill(t, tid, direcao="Open Long", coin="ETH", px=100.0, sz=200.0, inicio=0.0):
    return {"time": t, "tid": tid, "dir": direcao, "coin": coin, "px": str(px), "sz": str(sz), "startPosition": str(inicio)}


class SoLeitura(unittest.TestCase):
    def test_tipo_fora_da_lista_e_recusado(self):
        with self.assertRaises(ValueError):
            api.Cliente(abrir=lambda *a, **k: None).info("order")

    def test_nenhum_arquivo_assina_ou_envia_ordem(self):
        for arq in RAIZ.glob("*.py"):  # só o pacote do monitor; o executor fica em executor/
            fonte = arq.read_text()
            for proibido in ("/exchange", "eth_account", "sign_", "PRIVATE_KEY", "secret_key"):
                self.assertNotIn(proibido, fonte, f"{proibido} em {arq.name}")
            ast.parse(fonte)

    def test_limitador_espera_quando_o_saldo_acaba(self):
        relogio = [0.0]
        dormiu = []
        l = api.Limitador(60, relogio=lambda: relogio[0], dormir=lambda s: (dormiu.append(s), relogio.__setitem__(0, relogio[0] + s)))
        l.gastar(60)
        l.gastar(30)
        self.assertAlmostEqual(dormiu[0], 30.0)


class Deteccao(unittest.TestCase):
    def test_agrupa_fills_proximos_em_um_sinal(self):
        r = S.detectar([fill(0, 1), fill(60_000, 2)], agora_ms=1_000_000)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["nocional"], 40_000.0)
        self.assertEqual(r[0]["tipo"], "abertura")

    def test_grupo_recente_ainda_nao_vira_sinal(self):
        self.assertEqual(S.detectar([fill(0, 1)], agora_ms=config.JANELA_AGRUPAR_MS), [])

    def test_ignora_fechamento_spot_e_hip3(self):
        self.assertEqual(S.detectar([fill(0, 1, "Close Long"), fill(0, 2, "Buy", "@107"), fill(0, 3, "Open Long", "flx:TSLA")], 9_999_999), [])

    def test_aumento_pequeno_nao_conta(self):
        self.assertEqual(S.detectar([fill(0, 1, sz=200, inicio=1000)], 9_999_999), [])
        self.assertEqual(S.detectar([fill(0, 1, sz=600, inicio=1000)], 9_999_999)[0]["tipo"], "aumento")

    def test_nocional_minimo(self):
        self.assertEqual(S.detectar([fill(0, 1, sz=10)], 9_999_999), [])


class Contas(unittest.TestCase):
    def test_custo_entra_no_resultado(self):
        self.assertAlmostEqual(S.retorno_liquido("long", "BTC", 100, 101), 0.01 - 2 * (0.00045 + 0.0001))
        self.assertAlmostEqual(S.retorno_liquido("short", "XYZ", 100, 99), 0.01 - 2 * (0.00045 + 0.0005))

    def test_extremos_short_invertem(self):
        v = [{"h": "110", "l": "95"}]
        self.assertEqual(S.extremos("short", 100, v), (pytest_aprox(0.05), pytest_aprox(-0.10)))

    def test_classe_de_erro(self):
        self.assertEqual(S.classificar_erro(.02, .01, .03, -.01, None, False), "acerto")
        self.assertEqual(S.classificar_erro(.0005, -.0005, .001, -.01, None, False), "custo_comeu_o_ganho")
        self.assertEqual(S.classificar_erro(-.01, -.012, .001, -.02, None, True), "carteira_saiu_antes")
        self.assertEqual(S.classificar_erro(-.01, -.012, .001, -.02, .02, False), "entrada_tardia")
        self.assertEqual(S.classificar_erro(-.01, -.012, .02, -.02, None, False), "devolveu_o_ganho")
        self.assertEqual(S.classificar_erro(-.01, -.012, .0, -.02, None, False), "contra_desde_o_inicio")

    def test_controle_e_estavel(self):
        self.assertEqual(S.lado_controle(123), S.lado_controle(123))


def pytest_aprox(x):
    class A:
        def __eq__(self, o):
            return abs(o - x) < 1e-9
    return A()


class Aprendizado(unittest.TestCase):
    def test_aprende_qual_caracteristica_ganha(self):
        random.seed(1)
        m = A.Modelo()
        for _ in range(600):
            boa = random.random() < .5
            nomes = ["vies", "x:boa" if boa else "x:ruim"]
            m.aprender(nomes, (1.0 if boa else -1.0) + random.gauss(0, 1))
        self.assertGreater(m.prever(["vies", "x:boa"])[0], .5)
        self.assertLess(m.prever(["vies", "x:ruim"])[0], -.5)

    def test_incerteza_cai_com_dados(self):
        m = A.Modelo()
        m.aprender(["a"], 0.0)
        antes = m.prever(["a"])[1]
        for _ in range(50):
            m.aprender(["a"], 0.0)
        self.assertLess(m.prever(["a"])[1], antes)

    def test_sem_dados_nao_aprova(self):
        ok, _, _ = A.aprovado(A.Modelo(), ["a"], resolvidos=0)
        self.assertFalse(ok)

    def test_ruido_puro_nao_vira_aprovacao_frequente(self):
        random.seed(2)
        m = A.Modelo()
        aprovados = 0
        for i in range(800):
            nomes = ["vies", f"c:{i % 5}"]
            ok, _, _ = A.aprovado(m, nomes, m.n)
            aprovados += ok
            m.aprender(nomes, random.gauss(-.2, 2))
        self.assertLess(aprovados / 800, .25)

    def test_memoria_sobrevive_a_reinicio(self):
        m = A.Modelo()
        m.aprender(["a", "b"], 1.0)
        n = A.Modelo.de_json(m.para_json())
        self.assertEqual(m.prever(["a", "b"]), n.prever(["a", "b"]))
        self.assertEqual(n.n, 1)

    def test_licao_exige_amostra_e_intervalo(self):
        self.assertEqual(A.licoes([(["vies", "x"], 1.0)] * 5), [])
        l = A.licoes([(["vies", "x"], -1.0 + .01 * (i % 2)) for i in range(30)])
        self.assertEqual(l[0]["efeito"], "perde")


class SemOlharOFuturo(unittest.TestCase):
    def test_nao_aprende_antes_da_saida(self):
        ev = [{"t_entrada": 0, "t_saida": 100, "nomes": ["vies"], "liquido": .5},
              {"t_entrada": 50, "t_saida": 150, "nomes": ["vies"], "liquido": .5},
              {"t_entrada": 120, "t_saida": 220, "nomes": ["vies"], "liquido": .5}]
        r, _ = B.prequencial(ev)
        self.assertEqual([x["aprendidos"] for x in r], [0, 0, 1])
        self.assertEqual(r[1]["previsto"], 0.0)

    def test_previsao_nao_muda_quando_o_resultado_atual_muda(self):
        base = [{"t_entrada": i * 200, "t_saida": i * 200 + 100, "nomes": ["vies"], "liquido": .01} for i in range(5)]
        a, _ = B.prequencial(base)
        alterado = [dict(x) for x in base]
        alterado[-1]["liquido"] = -9.0
        b, _ = B.prequencial(alterado)
        self.assertEqual(a[-1]["previsto"], b[-1]["previsto"])

    def test_entrada_e_depois_do_sinal(self):
        velas = [{"t": i * 300_000, "o": str(100 + i), "c": str(100 + i), "h": str(101 + i), "l": str(99 + i)} for i in range(80)]
        t = [v["t"] for v in velas]
        a = B.avaliar({"fim": 600_000, "lado": "long", "moeda": "BTC"}, velas, t)
        self.assertGreaterEqual(a["t_entrada"], 600_000 + config.ATRASO_BACKTEST_MS)


class Selecao(unittest.TestCase):
    def linha(self, conta=1e6, vlm=1e7, pnl=10.0, roi=.1):
        janela = {"pnl": str(pnl), "roi": str(roi), "vlm": str(vlm)}
        return {"ethAddress": "0xABC", "accountValue": str(conta), "windowPerformances": [["month", janela], ["allTime", janela]]}

    def test_filtra_pequena_perdedora_e_formador(self):
        self.assertEqual(len(selecao.candidatas([self.linha()])), 1)
        self.assertEqual(selecao.candidatas([self.linha(conta=1e3)]), [])
        self.assertEqual(selecao.candidatas([self.linha(pnl=-1)]), [])
        self.assertEqual(selecao.candidatas([self.linha(vlm=1e9)]), [])

    def test_nota_limita_mes_de_sorte(self):
        self.assertEqual(selecao.nota(self.linha(roi=50)), 1.0 + .5 * 2.0)


if __name__ == "__main__":
    unittest.main()


class Painel(unittest.TestCase):
    def test_estado_com_banco_vazio_e_com_resultado(self):
        import json as J
        from baleias import banco as Bn, painel
        c = Bn.abrir(":memory:")
        vazio = painel.estado(c)
        self.assertEqual(vazio["resumo"]["sinais"], 0)
        c.execute("INSERT INTO carteiras(carteira,conta,nota,ativa,marca_ms) VALUES('0xabc',1e6,1,1,0)")
        c.execute("INSERT INTO sinais(fonte,carteira,moeda,lado,tipo,nocional,t_carteira_ms,t_sinal_ms,px_entrada,caracteristicas,previsto,desvio,aprovado,tid_chave) "
                  "VALUES('ao_vivo','0xabc','ETH','long','abertura',5e4,0,1,100,?,0.1,1,0,'k')", (J.dumps(["vies"]),))
        c.execute("INSERT INTO resultados(sinal_id,liquido,controle_liquido,classe) VALUES(1,0.002,-0.001,'acerto')")
        e = painel.estado(c)
        self.assertEqual(e["resumo"]["resolvidos"], 1)
        self.assertEqual(e["sinais"][0]["liquido"], 0.2)
        self.assertEqual(e["carteiras"][0]["resolvidos"], 1)
        self.assertEqual(e["classes"], {"acerto": 1})
        J.dumps(e)

    def test_servidor_so_escuta_localmente(self):
        self.assertIn('("127.0.0.1", porta)', (RAIZ / "painel.py").read_text())


class Atraso(unittest.TestCase):
    def test_grupo_velho_nao_vira_sinal_ao_vivo(self):
        from baleias import banco as Bn, monitor
        c = Bn.abrir(":memory:")
        c.execute("INSERT INTO carteiras(carteira,conta,nota,ativa,marca_ms) VALUES('0xabc',1e6,1,1,0)")
        agora = 50 * 3_600_000

        class Falso:
            def operacoes(self, *a):
                return [fill(agora - 3 * 3_600_000, 1), fill(agora - 3 * 60_000, 2, coin="BTC", px=50_000, sz=1)]

            def precos(self):
                return {"ETH": 100.0, "BTC": 50_000.0}

            def velas(self, *a):
                return []

        perdidos = []
        novos = monitor.registrar_sinais(c, Falso(), A.Modelo(), agora, perdidos)
        self.assertEqual(len(novos), 1)
        self.assertEqual(len(perdidos), 1)
        self.assertEqual(c.execute("SELECT moeda FROM sinais").fetchone()["moeda"], "BTC")
        de_novo = []
        monitor.registrar_sinais(c, Falso(), A.Modelo(), agora + 30_000, de_novo)
        self.assertEqual(de_novo, [], "o mesmo perdido não pode ser contado de novo")


class AcoesENoticias(unittest.TestCase):
    def test_aceita_acao_xyz_e_recusa_outros_mercados(self):
        self.assertTrue(S.e_perpetuo_comum("xyz:NVDA"))
        self.assertFalse(S.e_perpetuo_comum("flx:TSLA"))
        self.assertFalse(S.e_perpetuo_comum("@107"))
        self.assertTrue(S.e_perpetuo_comum("BTC"))

    def test_custo_de_acao_e_mais_alto(self):
        self.assertGreater(config.custo_ida_e_volta("xyz:NVDA"), config.custo_ida_e_volta("DOGE"))
        self.assertIn("ativo:acao_eua", S.caracteristicas("0x", "xyz:NVDA", "long", "abertura", 6e4, False, 0.0))

    def test_falha_de_noticia_vira_desconhecido(self):
        from baleias import noticias
        def quebra(*a, **k):
            raise OSError("sem rede")
        self.assertIsNone(noticias.buscar("BTC", 0, abrir=quebra))
        self.assertIn("noticia:desconhecido", S.caracteristicas("0x", "BTC", "long", "abertura", 6e4, False, 0.0, None))
        self.assertIn("noticia:nao", S.caracteristicas("0x", "BTC", "long", "abertura", 6e4, False, 0.0, False))

    def test_le_rss_e_filtra_por_tempo(self):
        import io
        from baleias import noticias
        xml = (b'<rss><channel><item><title>BTC sobe</title><link>http://a</link><pubDate>Wed, 05 Nov 2026 12:00:00 GMT</pubDate>'
               b'<source url="x">Fonte</source></item><item><title>velha</title><link>http://b</link>'
               b'<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item><item><title>sem data</title></item></channel></rss>')
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        itens = noticias.buscar("BTC", 1_790_000_000_000, abrir=lambda *a, **k: R(xml))
        self.assertEqual([i["titulo"] for i in itens], ["BTC sobe"])
        self.assertEqual(itens[0]["fonte"], "Fonte")
        self.assertEqual(noticias.consulta("xyz:NVDA"), "NVDA stock")


class Rastros(unittest.TestCase):
    def test_avisa_saida_uma_vez(self):
        import json as J
        from baleias import banco as Bn, monitor
        c = Bn.abrir(":memory:")
        c.execute("INSERT INTO sinais(fonte,carteira,moeda,lado,tipo,nocional,t_carteira_ms,t_sinal_ms,px_entrada,caracteristicas,previsto,desvio,aprovado,alertado,tid_chave) "
                  "VALUES('ao_vivo','0xabc','ETH','long','abertura',5e4,100,110,100,?,1,1,1,1,'k')", (J.dumps(["vies"]),))
        for tid, t in ((1, 200), (2, 300)):
            c.execute("INSERT INTO operacoes VALUES(?,?,?,?,?,?)", (tid, "0xabc", "ETH", "Close Long", t, "{}"))
        avisos = []
        import baleias.alerta as AL
        original = AL.enviar
        AL.enviar = avisos.append
        try:
            self.assertEqual(monitor.seguir_rastros(c, 400), 1)
            self.assertEqual(monitor.seguir_rastros(c, 500), 0)
        finally:
            AL.enviar = original
        self.assertIn("SAIU", avisos[0])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM rastros").fetchone()[0], 2)


class Insider(unittest.TestCase):
    XML = b"""<ownershipDocument><aff10b5One>0</aff10b5One><issuer><issuerTradingSymbol>abc</issuerTradingSymbol></issuer>
<reportingOwner><reportingOwnerId><rptOwnerCik>1</rptOwnerCik></reportingOwnerId><reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>1</isOfficer>
<officerTitle>Chief Executive Officer</officerTitle></reportingOwnerRelationship></reportingOwner><nonDerivativeTable>
<nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionAmounts>
<transactionShares><value>10000</value></transactionShares><transactionPricePerShare><value>12.5</value></transactionPricePerShare>
<transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
<nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding><transactionAmounts>
<transactionShares><value>999999</value></transactionShares><transactionPricePerShare><value>12</value></transactionPricePerShare>
<transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""

    def test_le_compra_e_ignora_venda(self):
        from baleias import sec
        e = sec.compras_do_xml(self.XML, "2026-10-01", "x")
        self.assertEqual((e["ticker"], e["cargo"], e["valor"]), ("ABC", "ceo", 125000.0))

    def test_plano_automatico_e_valor_baixo_ficam_fora(self):
        from baleias import sec
        self.assertIsNone(sec.compras_do_xml(self.XML.replace(b"<aff10b5One>0", b"<aff10b5One>1"), "2026-10-01", "x"))
        self.assertIsNone(sec.compras_do_xml(self.XML.replace(b"10000</value>", b"100</value>"), "2026-10-01", "x"))
        self.assertIsNone(sec.compras_do_xml(self.XML.replace(b">abc<", b">None<"), "2026-10-01", "x"))

    def test_entra_no_dia_util_seguinte_e_mede_contra_spy(self):
        from baleias import insider
        dias = [f"2026-10-{d:02d}" for d in range(1, 31)]
        serie = [(d, 10.0 + i, 10.5 + i) for i, d in enumerate(dias)]
        spy = [(d, 100.0, 101.0) for d in dias]
        a = insider.avaliar({"data": "2026-10-01"}, serie, spy, dias=5)
        self.assertEqual(a["d_entrada"], "2026-10-02")
        self.assertEqual(a["d_saida"], "2026-10-06")
        self.assertAlmostEqual(a["excesso"], (15.5 / 11.0 - 1) - (101 / 100 - 1) - 2 * config.INSIDER_CUSTO_LADO)

    def test_sem_dias_suficientes_nao_avalia(self):
        from baleias import insider
        self.assertIsNone(insider.avaliar({"data": "2026-10-01"}, [("2026-10-02", 1, 1)], [("2026-10-02", 1, 1)], dias=5))

    def test_cluster_exige_outro_dono_e_janela(self):
        from baleias import insider
        e = {"ticker": "A", "dono": "1", "data": "2026-10-20"}
        self.assertTrue(insider.cluster(e, [{"ticker": "A", "dono": "2", "data": "2026-10-01"}]))
        self.assertFalse(insider.cluster(e, [{"ticker": "A", "dono": "1", "data": "2026-10-01"}]))
        self.assertFalse(insider.cluster(e, [{"ticker": "A", "dono": "2", "data": "2026-08-01"}]))


class InsiderVivo(unittest.TestCase):
    def test_registra_uma_vez_e_resolve_depois(self):
        from datetime import date
        from baleias import banco as Bn, insider_vivo as IV
        c = Bn.abrir(":memory:")
        xml = Insider.XML

        class Sec:
            def recentes(self):
                return {"acc-1": "http://x/acc-1-index.htm"}

            def formulario(self, link):
                return xml

        dias = [f"2026-{m:02d}-{d:02d}" for m in (9, 10, 11) for d in range(1, 29)]

        class Precos:
            cache = {}

            def diario(self, t, ini, fim):
                return [(d, 10.0, 11.0) for d in dias if d <= fim.isoformat()]

        m = A.Modelo()
        self.assertEqual(IV.novos_formularios(c, Sec(), Precos(), m, date(2026, 10, 1)), 1)
        self.assertEqual(IV.novos_formularios(c, Sec(), Precos(), m, date(2026, 10, 1)), 0)
        self.assertEqual(IV.resolver(c, Precos(), m, date(2026, 10, 20)), 0)
        self.assertEqual(IV.resolver(c, Precos(), m, date(2026, 11, 20)), 1)
        self.assertEqual(m.n, 1)


class Previsao(unittest.TestCase):
    def test_empate_da_binaria(self):
        from baleias import previsao as P
        self.assertAlmostEqual(P.empate(0.85), 1 / 1.85)
        self.assertAlmostEqual(P.empate(1.0), 0.5)

    def test_placar_wilson(self):
        from baleias import previsao as P
        p = P.placar(55, 100)
        self.assertLess(p["baixo"], 0.55)
        self.assertGreater(p["alto"], 0.55)
        self.assertIsNone(P.placar(0, 0))

    def test_logistica_aprende_padrao_simples(self):
        from baleias import previsao as P
        random.seed(3)
        m = P.Logistica(taxa=0.1)
        for _ in range(3000):
            x = random.gauss(0, 1)
            m.aprender({"vies": 1.0, "r1": x}, x + random.gauss(0, .5) > 0)
        self.assertGreater(m.prob({"vies": 1.0, "r1": 1.0}), 0.7)

    def test_ciclo_preve_e_resolve_sem_olhar_o_futuro(self):
        from baleias import banco as Bn, previsao_vivo as PV
        c = Bn.abrir(":memory:")

        class Cli:
            def __init__(self, n):
                self.n = n

            def velas(self, *a):
                return [{"t": i * 60_000, "T": i * 60_000 + 59_999, "c": str(100 + (i % 3)), "v": "1"} for i in range(self.n)]

        r = PV.ciclo(c, Cli(70), 70 * 60_000)
        self.assertEqual(r["previstas"], 3)
        base = c.execute("SELECT t_base_ms FROM previsoes WHERE horizonte=1").fetchone()[0]
        self.assertEqual(base, 69 * 60_000)
        self.assertEqual(PV.ciclo(c, Cli(70), 70 * 60_000)["previstas"], 0)
        r2 = PV.ciclo(c, Cli(72), 72 * 60_000)
        self.assertGreaterEqual(r2["resolvidas"], 1)
        self.assertIsNotNone(PV.resumo(c)[1])


class Executor(unittest.TestCase):
    def test_assinatura_igual_a_documentacao(self):
        from executor.binance import assinar
        self.assertEqual(assinar("NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j",
                                 "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559"),
                         "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71")

    def test_recusa_chave_com_saque(self):
        from executor.binance import verificar_chave
        class B:
            def __init__(self, r): self.r = r
            def restricoes(self): return self.r
        self.assertTrue(any("SAQUE" in p for p in verificar_chave(B({"enableWithdrawals": True, "enableSpotAndMarginTrading": True, "ipRestrict": True}))))
        self.assertEqual(verificar_chave(B({"enableWithdrawals": False, "enableSpotAndMarginTrading": True, "ipRestrict": True})), [])

    def test_travas(self):
        from executor import robo
        boa = {"media": 0.01, "desvio": 0.5, "r2": -0.1}
        self.assertIsNone(robo.decidir(boa, 0.2, 0, False, False), "sem travas de evidência e custo: compra se prevê alta")
        self.assertIn("PARAR", robo.decidir(boa, 0.2, 0, False, True))
        self.assertIn("aberta", robo.decidir(boa, 0.2, 0, True, False))
        self.assertIn("perda", robo.decidir(boa, 0.2, -2.5, False, False))
        self.assertIsNone(robo.decidir({**boa, "media": -0.01}, 0.2, 0, False, False), "previsão de queda também pode operar")

    def test_stop_vende_antes_do_tempo(self):
        import os, sqlite3
        from executor import robo
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        c.execute(robo.ESQUEMA)
        from executor import adaptativo; c.executescript(adaptativo.ESQUEMA)
        adaptativo.escolher = lambda c, p, rnd=None: "compra_lim0.00_seg15"
        precos = [100.0]
        class B:
            def livro(self, s): return (precos[0], precos[0])
        class S:
            def atualizar(self): return {"media": 0.1, "desvio": 0.1, "r2": 0.0, "t_ms": 1_000_000, "px": 100.0}
        os.environ.pop("BINANCE_REAL", None)
        self.assertIn("comprou", robo.passo(c, B(), S(), agora_s=1060))
        precos[0] = 100.0 * (1 - robo.STOP_PCT / 100) - 0.01
        self.assertIn("stop", robo.passo(c, B(), S(), agora_s=1100))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM robo_oportunidades").fetchone()[0], 1, "registra oportunidade mesmo com posição aberta")

    def test_simulado_compra_e_vende(self):
        import os, sqlite3
        from executor import robo
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        c.execute(robo.ESQUEMA)
        from executor import adaptativo; c.executescript(adaptativo.ESQUEMA)
        adaptativo.escolher = lambda c, p, rnd=None: "compra_lim0.00_seg15"
        class B:
            def livro(self, s): return (100.0, 100.0)
        class S:
            def atualizar(self): return {"media": 0.5, "desvio": 0.1, "r2": 0.05, "t_ms": 1_000_000, "px": 100.0}
        os.environ.pop("BINANCE_REAL", None)
        self.assertIn("comprou", robo.passo(c, B(), S(), agora_s=1060))
        self.assertIn("aberta", robo.passo(c, B(), S(), agora_s=1100))
        self.assertIn("vendeu", robo.passo(c, B(), S(), agora_s=1060 + 15 * 60 + 1))
        self.assertLess(c.execute("SELECT resultado_usdt FROM robo_operacoes").fetchone()[0], 0)

    def test_pesquisa_sem_olhar_o_futuro(self):
        from executor import pesquisa as P
        random.seed(5)
        px, v = 100.0, []
        for i in range(900):
            px *= 1 + random.gauss(0, 0.001)
            v.append((i * 60_000, px, px * 1.0005, px * 0.9995, px, 10.0, 100, 5.0))
        x1 = P.caracteristicas(v, 500)
        v2 = v[:501] + [(t, p * 3, h * 3, l * 3, c * 3, vol, n, tb) for t, p, h, l, c, vol, n, tb in v[501:]]
        self.assertEqual(x1, P.caracteristicas(v2, 500), "características no minuto 500 não podem mudar com o futuro")
        ops, r2 = P.simular(v, 15, 1.0, 0.2)
        self.assertLessEqual(r2, 0.05)  # passeio aleatório: não pode "achar" previsibilidade


class Adaptativo(unittest.TestCase):
    def setUp(self):
        import importlib, sqlite3
        from executor import adaptativo
        self.A = importlib.reload(adaptativo)
        self.c = sqlite3.connect(":memory:"); self.c.row_factory = sqlite3.Row
        self.c.executescript(self.A.ESQUEMA)

    def test_resultado_com_stop_e_custo(self):
        velas = [(i, 100, 100.2, 99.9, 100.1) for i in range(5)]
        self.assertAlmostEqual(self.A.resultado_versao(100, velas, 5, 0.5, 0.2), 0.1 - 0.2)
        velas[2] = (2, 100, 100, 99.4, 99.6)
        self.assertAlmostEqual(self.A.resultado_versao(100, velas, 5, 0.5, 0.2), -0.5 - 0.2)
        self.assertIsNone(self.A.resultado_versao(100, velas[:3], 5, 0.5, 0.2))

    def test_aprende_a_nao_operar_quando_tudo_perde(self):
        rnd = random.Random(1)
        for b in self.A.BRACOS:
            self.c.execute("INSERT INTO robo_bracos VALUES(?,?,?,?)", (b, 200, -0.2 * 200, (0.04 + 0.09) * 200))
        escolhas = [self.A.escolher(self.c, 1.0, rnd) for _ in range(200)]
        self.assertLess(sum(e is not None for e in escolhas) / 200, 0.05)

    def test_prefere_a_versao_que_ganha(self):
        rnd = random.Random(2)
        for b in self.A.BRACOS:
            media = 0.3 if b == "compra_lim0.25_seg30" else -0.2
            self.c.execute("INSERT INTO robo_bracos VALUES(?,?,?,?)", (b, 200, media * 200, (media * media + 0.05) * 200))
        escolhas = [self.A.escolher(self.c, 1.0, rnd) for _ in range(200)]
        self.assertGreater(escolhas.count("compra_lim0.25_seg30") / 200, 0.9)

    def test_so_disparam_versoes_abaixo_da_previsao(self):
        rnd = random.Random(3)
        for _ in range(100):
            b = self.A.escolher(self.c, 0.07, rnd)
            lado, lim, _ = self.A.parametros(b) if b else (None, 0, 0)
            self.assertTrue(b is None or (lado == "compra" and lim < 0.07))

    def test_resolve_e_aprende_todas_as_versoes(self):
        self.A.registrar_oportunidade(self.c, 0, 100.0, 0.08)
        self.assertFalse(self.A.registrar_oportunidade(self.c, 60_000, 100.0, 0.08), "uma oportunidade a cada 5 min")
        velas = [(i, 100, 100.3, 99.95, 100.2) for i in range(240)]
        self.assertEqual(self.A.resolver(self.c, 0.5, 0.2, agora_ms=10 ** 9, buscar=lambda t, n: velas), 1)
        n = {r["braco"]: r["n"] for r in self.c.execute("SELECT * FROM robo_bracos")}
        self.assertEqual(set(n), {b for b in self.A.BRACOS if self.A.dispara(b, 0.08)})


class Queda(unittest.TestCase):
    def test_versao_vendida_ganha_na_queda_e_tem_stop_na_alta(self):
        from executor import adaptativo as A
        cai = [(i, 100, 100.05, 99.6, 99.7) for i in range(5)]
        self.assertAlmostEqual(A.resultado_versao(100, cai, 5, 0.5, 0.2, "venda"), 0.3 - 0.2)
        sobe = [(i, 100, 100.6, 99.9, 100.5) for i in range(5)]
        self.assertAlmostEqual(A.resultado_versao(100, sobe, 5, 0.5, 0.2, "venda"), -0.5 - 0.2)
        self.assertTrue(A.dispara("venda_lim0.05_seg15", -0.1))
        self.assertFalse(A.dispara("venda_lim0.05_seg15", 0.1))
        self.assertEqual(A.parametros("lim0.05_seg15"), ("compra", 0.05, 15))

    def test_robo_simula_venda_e_bloqueia_no_real(self):
        import os, sqlite3
        from executor import robo, adaptativo
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        c.execute(robo.ESQUEMA); c.executescript(adaptativo.ESQUEMA)
        original = adaptativo.escolher
        adaptativo.escolher = lambda c, p, rnd=None: "venda_lim0.00_seg15"
        precos = [100.0]
        class B:
            def livro(self, s): return (precos[0], precos[0])
        class S:
            def atualizar(self): return {"media": -0.2, "desvio": 0.1, "r2": 0.0, "t_ms": 1_000_000, "px": 100.0}
        try:
            os.environ.pop("BINANCE_REAL", None)
            self.assertIn("queda", robo.passo(c, B(), S(), agora_s=1060))
            precos[0] = 99.0
            self.assertIn("zerou", robo.passo(c, B(), S(), agora_s=1060 + 15 * 60 + 1))
            self.assertGreater(c.execute("SELECT resultado_usdt FROM robo_operacoes").fetchone()[0], 0)
            os.environ["BINANCE_REAL"] = "1"
            class S2:
                def atualizar(self): return {"media": -0.2, "desvio": 0.1, "r2": 0.0, "t_ms": 5_000_000, "px": 100.0}
            self.assertIn("só no simulado", robo.passo(c, B(), S2(), agora_s=5010))
        finally:
            os.environ.pop("BINANCE_REAL", None)
            adaptativo.escolher = original


class Laboratorio(unittest.TestCase):
    def test_sinal_nao_olha_o_futuro(self):
        from lab import tendencia as T
        serie = {f"2020-01-{d:02d}": 100.0 + d for d in range(1, 31)}
        a = T.retornos_estrategia(serie, 5, "comprado_fora", 0.0)
        alterada = dict(serie)
        alterada["2020-01-30"] = 1.0  # despenca no último dia
        b = T.retornos_estrategia(alterada, 5, "comprado_fora", 0.0)
        self.assertEqual({d: v for d, v in a.items() if d < "2020-01-30"}, {d: v for d, v in b.items() if d < "2020-01-30"})

    def test_custo_so_quando_muda_de_posicao(self):
        from lab import tendencia as T
        serie = {f"2020-01-{d:02d}": 100.0 for d in range(1, 21)}
        r = T.retornos_estrategia(serie, 5, "comprado_vendido", 0.01)
        self.assertAlmostEqual(sum(r.values()), -0.01)  # entra vendido uma vez (preço parado → sinal ≤ 0)

    def test_sharpe_deflacionado_penaliza_tentativas(self):
        from lab import tendencia as T
        poucas = T.sharpe_deflacionado(0.05, 1000, 0, 3, [0.05, 0.0])
        muitas = T.sharpe_deflacionado(0.05, 1000, 0, 3, [0.05] + [random.gauss(0, 0.03) for _ in range(99)])
        self.assertGreater(poucas, muitas)

    def test_metricas_queda(self):
        from lab import tendencia as T
        m = T.metricas([0.1] * 20 + [-0.5] + [0.0] * 20, 365)
        self.assertAlmostEqual(m["maior_queda"], -0.5)


class TendenciaAoVivo(unittest.TestCase):
    def test_registra_dia_a_dia_sem_futuro_e_idempotente(self):
        import sqlite3
        from datetime import date, timedelta
        from lab import ao_vivo as AV
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        dias = [(date(2026, 10, 1) + timedelta(days=i)).isoformat() for i in range(45)]
        def buscar(a, desde):
            return {d: 100.0 + i for i, d in enumerate(dias)}  # tudo subindo: comprado
        self.assertEqual(AV.atualizar(c, buscar, hoje=date(2026, 11, 10)), 3)
        self.assertEqual(AV.atualizar(c, buscar, hoje=date(2026, 11, 10)), 0)
        p = json.loads(c.execute("SELECT posicoes FROM lab_tendencia WHERE dia='2026-11-08'").fetchone()[0])
        self.assertTrue(all(v == 1 for v in p.values()))
        primeiro = c.execute("SELECT custo FROM lab_tendencia WHERE dia='2026-11-07'").fetchone()[0]
        segundo = c.execute("SELECT custo FROM lab_tendencia WHERE dia='2026-11-08'").fetchone()[0]
        self.assertGreater(primeiro, 0)
        self.assertEqual(segundo, 0)


class Funding(unittest.TestCase):
    def test_regra_entra_cobre_custo_e_sai_no_negativo(self):
        from lab import funding as F
        self.assertFalse(F.decidir([0.0000125] * 10, False), "janela curta")
        self.assertTrue(F.decidir([0.0000125] * 72, False))
        self.assertFalse(F.decidir([0.000001] * 72, False), "não paga o custo em 14 dias")
        self.assertTrue(F.decidir([0.000001] * 72, True), "quem já está dentro só sai no negativo")
        self.assertFalse(F.decidir([-0.00001] * 72, True))

    def test_simulacao_recebe_funding_e_paga_custo(self):
        from lab import funding as F
        s = [(i * 3_600_000, 0.0000125) for i in range(24 * 10)]
        r = F.simular({"BTC": s})
        total = sum(r.values())
        horas_dentro = 24 * 10 - F.JANELA_H
        esperado = F.PESO * (horas_dentro * 0.0000125 - F.CUSTO_IDA_VOLTA / 2) / F.CAPITAL_POR_EXPOSICAO
        self.assertAlmostEqual(total, esperado)


class ModelosIA(unittest.TestCase):
    def test_avaliacao_sem_futuro_e_previsor_perfeito(self):
        from lab import modelos_ia as M
        precos = [100 + math.sin(i / 7) for i in range(M.CONTEXTO + 200)]
        idx = list(range(M.CONTEXTO, len(precos) - M.H, M.PASSO))
        mapa = iter(idx)
        def oraculo(ctxs):
            return [precos[next(mapa) - 1 + M.H] for _ in ctxs]
        r = M.avaliar(precos, oraculo)
        self.assertAlmostEqual(r["r2"], 1.0)
        zero = M.avaliar(precos, lambda ctxs: [c[-1] for c in ctxs])
        self.assertAlmostEqual(zero["r2"], 0.0)


class Generativa(unittest.TestCase):
    BOA = {"15min": {"direcao": "alta", "confianca": 0.6, "retorno_esperado_pct": 0.1},
           "1h": {"direcao": "queda", "confianca": 0.55, "retorno_esperado_pct": -0.3},
           "4h": {"direcao": "alta", "confianca": 0.7, "retorno_esperado_pct": 0.5}, "motivo": "x"}

    def test_valida_formato(self):
        from lab import generativa as G
        self.assertEqual(G.validar(self.BOA)["1h"]["direcao"], "queda")
        ruim = json.loads(json.dumps(self.BOA)); ruim["4h"]["direcao"] = "compre tudo"
        with self.assertRaises(ValueError):
            G.validar(ruim)

    def test_preve_os_tres_prazos_e_resolve_cada_um_no_seu_tempo(self):
        import sqlite3
        from lab import generativa as G
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        t0 = 1000 * G.SLOT_MS + 60_000
        relogio = [t0 / 1000]
        args = dict(obter=lambda t: {"preco": 100.0}, pergunta=lambda ctx, instrucao=None: (G.validar(self.BOA), 10),
                    preco_em=lambda t: 101.0, preco_ja=lambda: 100.0, relogio=lambda: relogio[0])
        self.assertEqual(G.ciclo(c, t0, **args)["previu"], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM llm_previsoes").fetchone()[0], 3)
        self.assertEqual(G.ciclo(c, t0 + 60_000, **args)["previu"], 0)
        self.assertEqual(G.ciclo(c, t0 + 18 * 60_000, **args)["resolveu"], 2)  # só o de 15 min, na v1 e na v2
        G.ciclo(c, t0 + 5 * 3_600_000, **args)  # novos slots também previram no caminho; aqui só importa o primeiro
        acertos = dict(c.execute("SELECT horizonte, acertou FROM llm_previsoes WHERE slot_ms=?", (1000 * G.SLOT_MS,)).fetchall())
        self.assertEqual(acertos, {"15min": 1, "1h": 0, "4h": 1})


class ErrosCorrigidos(unittest.TestCase):
    def test_simulado_cobra_so_o_que_comprou(self):
        import os, sqlite3
        from executor import robo, adaptativo
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        c.execute(robo.ESQUEMA); c.executescript(adaptativo.ESQUEMA)
        original = adaptativo.escolher
        adaptativo.escolher = lambda c, p, rnd=None: "compra_lim0.00_seg5"
        class B:
            def livro(self, s): return (75_800.0, 75_800.0)
        class S:
            def atualizar(self): return {"media": 0.1, "desvio": 0.1, "r2": 0.0, "t_ms": 1_000_000, "px": 75_800.0}
        try:
            os.environ.pop("BINANCE_REAL", None)
            robo.passo(c, B(), S(), agora_s=1060)
            robo.passo(c, B(), S(), agora_s=1060 + 5 * 60 + 1)
        finally:
            adaptativo.escolher = original
        r = c.execute("SELECT resultado_usdt, custo_compra FROM robo_operacoes").fetchone()
        self.assertLess(r["custo_compra"], 10)
        self.assertAlmostEqual(r["resultado_usdt"] / r["custo_compra"], -(1 - (1 - robo.TAXA_SUPOSTA) ** 2), places=6,
                               msg="preço parado: só as duas taxas, nada de arredondamento")

    def test_fila_continua_alinhada_depois_do_corte(self):
        from executor import sinal as SV
        random.seed(7)
        px, v = 100.0, []
        for i in range(6100):
            px *= 1 + random.gauss(0, 0.001)
            v.append((i * 60_000, px, px, px, px, 10.0, 100, 5.0))
        s = SV.SinalVivo(historico=v[:5990])
        class R:
            def __init__(self, d): self.d = d
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return self.d
        novas = [[t, o, h, l, c, vol, t + 59_999, 0, n, tb, 0, 0] for t, o, h, l, c, vol, n, tb in v[5990:]]
        import io
        s.atualizar(abrir=lambda url, timeout=0: io.BytesIO(json.dumps(novas).encode()))
        for alvo, x, y_pred, j in s.fila:
            self.assertEqual(s.v[j][0] + SV.H * 60_000, s.v[alvo][0] if alvo < len(s.v) else s.v[j][0] + SV.H * 60_000)
            self.assertEqual(x, __import__("executor.pesquisa", fromlist=["x"]).caracteristicas(s.v, j))


class Saude(unittest.TestCase):
    def test_sinal_de_vida(self):
        import sqlite3
        from baleias import saude
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        saude.bater(c, "robo", "ok")
        e = saude.estado(c)
        self.assertEqual((e[0]["nome"], e[0]["msg"]), ("robo", "ok"))
        self.assertLess(e[0]["segundos"], 5)

    def test_monitor_nao_chama_tarefas_lentas(self):
        fonte = (RAIZ / "monitor.py").read_text()
        for lenta in ("generativa", "Rotina(", "insiders.rodar"):
            self.assertNotIn(lenta, fonte)


class LicoesDosTraders(unittest.TestCase):
    def test_v2_pode_se_abster_e_v1_nao(self):
        from lab import generativa as G
        x = json.loads(json.dumps(Generativa.BOA)); x["4h"]["direcao"] = "sem_posicao"
        self.assertEqual(G.validar(x, permite_abster=True)["4h"]["direcao"], "sem_posicao")
        with self.assertRaises(ValueError):
            G.validar(x)

    def test_v2_roda_no_mesmo_contexto_e_abstencao_nao_conta_como_acerto(self):
        import sqlite3
        from lab import generativa as G
        c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
        abst = json.loads(json.dumps(Generativa.BOA)); abst["15min"]["direcao"] = "sem_posicao"
        def perg(ctx, instrucao=None):
            return (G.validar(abst, True) if instrucao is G.INSTRUCAO_V2 else G.validar(Generativa.BOA)), 5
        t0 = 2000 * G.SLOT_MS + 60_000
        r = [t0 / 1000]
        args = dict(obter=lambda t: {"preco": 100.0}, pergunta=perg, preco_em=lambda t: 101.0, preco_ja=lambda: 100.0, relogio=lambda: r[0])
        self.assertEqual(G.ciclo(c, t0, **args).get("previu_v2"), 1)
        G.ciclo(c, t0 + 20 * 60_000, **args)
        v2 = dict(c.execute("SELECT horizonte, acertou FROM llm_previsoes_v2 WHERE slot_ms=? AND px_final IS NOT NULL", (2000 * G.SLOT_MS,)).fetchall())
        self.assertEqual(v2, {"15min": None})
        res = G.resumo(c, "llm_previsoes_v2")["horizontes"]["15min"]
        self.assertEqual((res["resolvidas"], res["abstencoes"]), (0, 1))

    def test_robo_tem_versoes_de_prazo_maior(self):
        from executor import adaptativo as A
        self.assertEqual(len(A.BRACOS), 30)
        self.assertIn("compra_lim0.25_seg240", A.BRACOS)


class FundingAlavancado(unittest.TestCase):
    def test_alavancagem_aumenta_retorno_sem_choque_e_liquida_com_choque(self):
        from lab import funding_alavancado as FA
        horas = [(i * 3_600_000, 0.0000125) for i in range(24 * 20)]
        calmo = {t: (100.0, 100.1, 100.0) for t, _ in horas}
        r1, e1 = FA.simular({"BTC": horas}, {"BTC": calmo}, 1)
        r5, e5 = FA.simular({"BTC": horas}, {"BTC": calmo}, 5)
        self.assertGreater(sum(r5.values()), sum(r1.values()))
        self.assertEqual(e5["liquidacoes"], 0)
        choque = dict(calmo)
        choque[horas[200][0]] = (100.0, 130.0, 101.0)   # máxima +30% numa hora
        _, e10 = FA.simular({"BTC": horas}, {"BTC": choque}, 10)
        _, e2 = FA.simular({"BTC": horas}, {"BTC": choque}, 2)
        self.assertEqual(e10["liquidacoes"], 1)
        self.assertEqual(e2["liquidacoes"], 0)


class Padroes(unittest.TestCase):
    def test_detecta_engolfo_e_mede_sem_sobreposicao(self):
        from lab import padroes as P
        v = [(i * 900_000, 100.0, 100.5, 99.5, 100.0 + (0.01 if i % 2 else -0.01), 10.0) for i in range(130)]
        v[110] = (110 * 900_000, 99.8, 99.9, 99.0, 99.2, 10.0)      # vela de baixa
        v[111] = (111 * 900_000, 99.1, 100.6, 99.0, 100.5, 10.0)    # engolfa a anterior
        a = P.detectar(v)
        self.assertIn("engolfo_alta", a[111])
        self.assertNotIn("engolfo_alta", a[110])
        m = P.medir(v, [["x"] if i in (100, 101, 102, 120) else [] for i in range(len(v))])
        self.assertEqual(m[("x", "1h")]["casos"], 2)   # 101 e 102 caem dentro do horizonte de 100

    def test_passou_exige_treino_teste_e_custo(self):
        from lab import padroes as P
        bom = {"casos": 100, "retorno_medio_pct": 0.3, "t": 4.0}
        self.assertTrue(P.passou(bom, {"casos": 50, "retorno_medio_pct": 0.25, "t": 2.5}))
        self.assertFalse(P.passou(bom, {"casos": 50, "retorno_medio_pct": -0.25, "t": -2.5}))
        self.assertFalse(P.passou(bom, {"casos": 50, "retorno_medio_pct": 0.1, "t": 5}))


class TempoReal(unittest.TestCase):
    def test_ws_le_quadros_fragmentados_e_responde_ping(self):
        import struct
        from baleias.ws import WS

        class Sock:
            def __init__(self, dados):
                self.dados, self.enviado = dados, b""
            def recv(self, n):
                parte, self.dados = self.dados[:n], self.dados[n:]
                return parte
            def sendall(self, b):
                self.enviado += b
        grande = b"x" * 300
        dados = (bytes([0x89, 3]) + b"abc"                       # ping
                 + bytes([0x01, 2]) + b"ol"                      # texto, sem FIN
                 + bytes([0x80, 1]) + b"a"                       # continuação com FIN
                 + bytes([0x81, 126]) + struct.pack("!H", 300) + grande)
        ws = WS(Sock(dados))
        self.assertEqual(ws.receber(), "ola")
        self.assertEqual(ws.s.enviado[0], 0x8A)                  # pong
        self.assertEqual(ws.receber(), grande.decode())

    def test_classifica_eventos(self):
        from baleias import tempo_real as T
        self.assertIsNone(T.de_aggtrade({"p": "70000", "q": "1", "m": False}))
        ev = T.de_aggtrade({"p": "70000", "q": "40", "m": True})
        self.assertEqual(ev["lado"], "venda")
        self.assertTrue(ev["notificar"])
        liq = T.de_liquidacao({"o": {"s": "ETHUSDT", "S": "SELL", "p": "3000", "ap": "3000", "q": "500", "z": "500"}})
        self.assertIn("comprados", liq["texto"])
        f = T.de_hl_fill("0xabcdef0123", {"coin": "BTC", "px": "70000", "sz": "1", "dir": "Open Short", "closedPnl": "0"})
        self.assertIn("ABRIU VENDIDO", f["texto"])
        self.assertIsNone(T.de_hl_fill("0xabc", {"coin": "BTC", "px": "70000", "sz": "0.0001", "dir": "Open Long"}))

    def test_mercado_e_livro(self):
        from baleias import tempo_real as T
        m = T.mercado_de_tickers([{"s": "BTCUSDT", "o": "100", "c": "110", "q": "5"}, {"s": "USDCUSDT", "o": "1", "c": "1", "q": "9"},
                                  {"s": "ETHBTC", "o": "1", "c": "1", "q": "9"}])
        self.assertEqual([x["s"] for x in m], ["BTC"])
        self.assertAlmostEqual(m[0]["pct"], 10)
        f = T.faixas_livro([["99990", "1"], ["50000", "9"]], [["100010", "2"]], 100000)
        self.assertEqual(set(f), {99975.0, 100000.0})            # 50000 fica fora do ±1%

    def test_robo_avisa_entrada_e_saida_sem_repetir_passado(self):
        from baleias import tempo_real as T
        m = T.Motor(enviar=lambda x: None)
        import tempfile
        m.arquivo = pathlib.Path(tempfile.mkdtemp()) / "ao_vivo.jsonl"
        m.novidades_robo([(1, "compra", 100.0, 101.0, 0.1, "b")])
        self.assertEqual(len(m.eventos), 0)
        m.novidades_robo([(2, "venda", 102.0, None, None, "b"), (1, "compra", 100.0, 101.0, 0.1, "b")])
        m.novidades_robo([(2, "venda", 102.0, 101.0, 0.05, "b"), (1, "compra", 100.0, 101.0, 0.1, "b")])
        textos = [e["texto"] for e in m.eventos]
        self.assertEqual(len(textos), 2)
        self.assertIn("ENTROU VENDA", textos[0])
        self.assertIn("SAIU", textos[1])
        self.assertEqual(len(m.pendentes), 2)
        snap = m.instantaneo(desde=1)
        self.assertEqual([e["id"] for e in snap["eventos"]], [2])


class Tradutor(unittest.TestCase):
    def test_traduz_absorcao_liquidacoes_e_paredes(self):
        from baleias import tempo_real as T
        livro = T.paredes([["99990", "60"], ["99800", "1"]], [["100010", "10"], ["100400", "40"]], 100000)
        self.assertGreater(livro["compra_perto"], livro["venda_perto"])
        self.assertEqual(livro["parede_venda"][0], 100400.0)
        texto = T.traduzir({"px0": 100000, "px1": 99800, "compra": 7e6, "venda": 3e6, "liq_long": 600_000, "liq_short": 0, "livro": livro}, media_volume=4e6)
        self.assertIn("compradores agressivos dominaram", texto)
        self.assertIn("absorção", texto)
        self.assertIn("comprados (quem apostou na alta)", texto)
        self.assertIn("Parede de compra", texto)
        self.assertIn("Volume 2.5×", texto)
        calmo = T.traduzir({"px0": 100000, "px1": 100001, "compra": 1e6, "venda": 1e6, "liq_long": 0, "liq_short": 0, "livro": None})
        self.assertIn("sem direção clara", calmo)


class Tartaruga(unittest.TestCase):
    def test_perde_1R_no_stop_e_deixa_o_vencedor_correr(self):
        from lab import tartaruga as T
        import datetime as dt
        base = dt.date(2020, 1, 1)
        dia = lambda k: (base + dt.timedelta(days=k)).isoformat()
        # 60 dias laterais, rompe para cima e sobe 40 dias, depois despenca
        velas = [[dia(k), 100.0, 101.0, 99.0, 100.0] for k in range(60)]
        px = 100.0
        for k in range(60, 100):
            px *= 1.02
            velas.append([dia(k), px / 1.02, px * 1.005, px / 1.02 * 0.995, px])
        for k in range(100, 115):
            px *= 0.95
            velas.append([dia(k), px / 0.95, px / 0.95 * 1.001, px * 0.99, px])
        curva, ops = T.simular({"XUSDT": velas}, dia(0), dia(115), ("compra",))
        self.assertEqual(len(ops), 1)
        self.assertGreater(ops[0]["R"], 3)                # ganho grande, várias vezes o risco
        # stop: rompe e cai logo em seguida
        velas2 = [[dia(k), 100.0, 101.0, 99.0, 100.0] for k in range(60)] + [[dia(60), 100, 103, 100, 102.5], [dia(61), 102.5, 102.6, 80, 81]]
        _, ops2 = T.simular({"XUSDT": velas2}, dia(0), dia(62), ("compra",))
        self.assertEqual(len(ops2), 1)
        self.assertLess(ops2[0]["R"], -0.9)
        self.assertGreater(ops2[0]["R"], -1.3)            # perde ~1R (mais custos), não mais


class RoboTartaruga(unittest.TestCase):
    def _velas(self, extra):
        import datetime as dt
        base = dt.date(2025, 1, 1)
        dia = lambda k: (base + dt.timedelta(days=k)).isoformat()
        return [[dia(k), 100.0, 101.0, 99.0, 100.0] for k in range(60)] + [[dia(60 + i), *x] for i, x in enumerate(extra)]

    def test_entra_no_rompimento_com_1R_e_sai_no_stop(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"
        e = X.novo_estado(700)
        corretora = X.Simulada(None, e)
        velas = self._velas([[100, 106, 100, 105]])
        X.passo_diario(e, corretora, {"XUSDT": velas}, {"XUSDT": 105.0})
        p = e["abertas"]["XUSDT"]
        self.assertAlmostEqual(p["risco_usd"], 7.0, delta=0.3)          # 1% de 700
        self.assertLess(p["gasto"], 700)
        X.checar_stops(e, corretora, {"XUSDT": p["stop"] - 0.01})
        self.assertEqual(e["abertas"], {})
        self.assertLess(e["fechadas"][0]["R"], -0.95)
        self.assertGreater(e["fechadas"][0]["R"], -1.15)
        self.assertIn("SAIU", X.EVENTOS.read_text())

    def test_real_guarda_stop_na_corretora_e_cancela_ao_sair(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"
        chamadas = []

        class Cliente:
            def saldo(self, a): return 700.0
            def comprar_mercado(self, s, usdt): chamadas.append(("compra", s, round(usdt, 2))); return (usdt / 105.0, 105.0, usdt)
            def colocar_stop(self, s, q, stop): chamadas.append(("stop", s, round(stop, 2))); return 42
            def cancelar(self, s, o): chamadas.append(("cancela", s, o))
            def vender_mercado(self, s, q): chamadas.append(("venda", s)); return (90.0, q * 90.0)
            def consultar(self, s, o): return ("NEW", None)
        e = X.novo_estado(0)
        r = X.Real(Cliente(), e)
        velas = self._velas([[100, 106, 100, 105]])
        X.passo_diario(e, r, {"XUSDT": velas}, {"XUSDT": 105.0})
        self.assertEqual([c[0] for c in chamadas], ["compra", "stop"])
        self.assertEqual(e["abertas"]["XUSDT"]["ordem_stop"], 42)
        X.checar_stops(e, r, {"XUSDT": 1.0})                           # stop ainda não executou na corretora
        self.assertIn("XUSDT", e["abertas"])
        # fecha abaixo da mínima de 20 dias: cancela o stop e vende a mercado
        velas2 = velas + [[velas[-1][0][:8] + "28", 105, 105, 80, 80]]
        X.passo_diario(e, r, {"XUSDT": velas2}, {"XUSDT": 80.0})
        self.assertEqual([c[0] for c in chamadas][-2:], ["cancela", "venda"])
        self.assertEqual(e["abertas"], {})


class StopsPerdidos(unittest.TestCase):
    def test_stop_atingido_com_a_maquina_desligada(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"
        e = X.novo_estado(700)
        e["abertas"]["XUSDT"] = {"moeda": "XUSDT", "entrada": 100.0, "qtd": 0.5, "stop": 90.0, "ordem_stop": None, "N": 5.0,
                                 "entrada_t": 1735689600, "gasto": 50.0, "risco_usd": 5.0}       # 2025-01-01
        dados = {"XUSDT": [["2025-01-02", 100, 104, 95, 99], ["2025-01-03", 92, 93, 85, 86], ["2025-01-04", 86, 88, 80, 81]]}
        X.stops_perdidos(e, X.Simulada(None, e), dados)
        self.assertEqual(e["abertas"], {})
        self.assertEqual(e["fechadas"][0]["saida"], 90.0)
        self.assertIn("tocado dentro da vela", X.EVENTOS.read_text())
        self.assertAlmostEqual(e["caixa"], 700 + 0.5 * 90 * (1 - 0.001))


class BotaoParada(unittest.TestCase):
    def test_parar_bloqueia_entradas(self):
        from executor import tartaruga_exec as X
        d = pathlib.Path(__import__("tempfile").mkdtemp())
        antes = X.PARAR
        self.addCleanup(setattr, X, "PARAR", antes)
        X.EVENTOS, X.PARAR = d / "ev.jsonl", d / "PARAR"
        X.PARAR.touch()
        e = X.novo_estado(700)
        velas = RoboTartaruga._velas(None, [[100, 106, 100, 105]])
        X.passo_diario(e, X.Simulada(None, e), {"XUSDT": velas}, {"XUSDT": 105.0})
        self.assertEqual(e["abertas"], {})
        self.assertIn("parada", X.EVENTOS.read_text())


class ClienteBybit(unittest.TestCase):
    def test_assina_e_recusa_chave_com_saque(self):
        import hashlib, hmac, io, json as J
        from executor import bybit as Y
        vistos = []

        def abrir(pedido, timeout=15):
            vistos.append(pedido)
            if "query-api" in pedido.full_url:
                corpo = {"retCode": 0, "result": {"permissions": {"Spot": ["SpotTrade"], "Wallet": ["AccountTransfer", "Withdraw"]}, "ips": ["*"], "readOnly": 0}}
            else:
                corpo = {"retCode": 0, "result": {"list": [{"coin": [{"coin": "USDT", "walletBalance": "300", "locked": "20"}]}]}}
            return io.BytesIO(J.dumps(corpo).encode())
        c = Y.Bybit("CHAVE", "SEGREDO", abrir=abrir)
        self.assertEqual(c.saldo("USDT"), 280.0)
        p = vistos[-1]
        ts = p.get_header("X-bapi-timestamp")
        query = p.full_url.split("?", 1)[1]
        self.assertEqual(p.get_header("X-bapi-sign"), hmac.new(b"SEGREDO", f"{ts}CHAVE5000{query}".encode(), hashlib.sha256).hexdigest())
        problemas = Y.verificar_chave(c)
        self.assertTrue(any("SAQUE" in x for x in problemas))
        self.assertTrue(any("IP" in x for x in problemas))


class Reconciliar(unittest.TestCase):
    def test_posicao_sumida_na_corretora(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"

        class Cliente:
            def __init__(self, saldos, status): self.saldos, self.status = saldos, status
            def saldo(self, a): return self.saldos.get(a, 0.0)
            def consultar(self, s, o): return self.status
        base = {"moeda": "XUSDT", "entrada": 100.0, "qtd": 1.0, "stop": 90.0, "ordem_stop": 7, "N": 5.0, "entrada_t": 0, "gasto": 100.0, "risco_usd": 10.0}
        # 1) stop executou com a máquina desligada
        e = X.novo_estado(0); e["abertas"]["XUSDT"] = dict(base)
        X.reconciliar(e, X.Real(Cliente({}, ("FILLED", 89.5)), e), {"XUSDT": 95.0})
        self.assertEqual(e["fechadas"][0]["saida"], 89.5)
        self.assertIn("stop executado na corretora", e["fechadas"][0]["motivo"])
        # 2) ainda tem a moeda: nada muda
        e = X.novo_estado(0); e["abertas"]["XUSDT"] = dict(base)
        X.reconciliar(e, X.Real(Cliente({"X": 1.0}, ("NEW", None)), e), {"XUSDT": 95.0})
        self.assertIn("XUSDT", e["abertas"])
        # 3) vendida por fora (stop não executou): fecha no preço atual e avisa
        e = X.novo_estado(0); e["abertas"]["XUSDT"] = dict(base)
        X.reconciliar(e, X.Real(Cliente({}, ("CANCELED", None)), e), {"XUSDT": 95.0})
        self.assertEqual(e["fechadas"][0]["saida"], 95.0)
        self.assertIn("não encontrada", X.EVENTOS.read_text())


class Cerebro(unittest.TestCase):
    def test_rede_neural_aprende_um_padrao(self):
        from baleias.cerebro import Rede
        import random as R
        r, rnd = Rede(3, ocultos=6, semente=1), R.Random(2)
        dados = [([a, b, 0.0], 1 if a + b > 0 else 0) for a, b in ((rnd.uniform(-1, 1), rnd.uniform(-1, 1)) for _ in range(400))]
        antes = sum((r.prever(x) > 0.5) == bool(y) for x, y in dados) / len(dados)
        for _ in range(30):
            for x, y in dados:
                r.aprender(x, y, taxa=0.05)
        depois = sum((r.prever(x) > 0.5) == bool(y) for x, y in dados) / len(dados)
        self.assertGreater(depois, 0.9)
        self.assertGreater(depois, antes)

    def test_erro_reduz_peso_e_cerebro_cria_e_poda_sinapses(self):
        from baleias import cerebro as C
        c = C.Cerebro()
        f = {k: 0.0 for k in C.ENTRADAS_REDE} | {"chop": 30.0, "rsi": 50.0, "vi": 0.5, "dp": 0.003}
        # Vórtice invertido diz "desce" (vi > 0); o mercado sobe 20 vezes seguidas: peso dele tem que cair
        for i in range(20):
            c.decidir(i, f, 100.0)
            c.conferir(i, +0.002, f)
        vi = next(s for s in c.sinapses if s["id"] == "vortice_invertido")
        self.assertLess(vi["peso"], 1.0)
        self.assertEqual(vi["previsoes"], 20)
        # força o gatilho de rota nova: cérebro errando muito
        c.historico = [0] * 150
        c.passos = 48 * 10
        c._revisar(999)
        novas = [s for s in c.sinapses if s["id"].startswith("nova_")]
        self.assertEqual(len(novas), 2)
        self.assertTrue(all(s["status"] == "observacao" and s["peso"] == 0.0 for s in novas))
        # uma nova que erra muito é podada; uma que acerta é promovida
        novas[0]["previsoes"], novas[0]["acertos"] = 150, 60
        novas[1]["previsoes"], novas[1]["acertos"] = 150, 95
        c._revisar(1000)
        self.assertEqual(novas[0]["status"], "podada")
        self.assertEqual(novas[1]["status"], "ativa")
        self.assertTrue(any("NOVA SINAPSE" in d["texto"] for d in c.diario))

    def test_regra_dispara_nos_dois_lados(self):
        from baleias import cerebro as C
        s_baixo = {"tipo": "regra", "medida": "r4", "limiar": -2.5, "sentido": 1, "lado": "baixo"}
        s_alto = {"tipo": "regra", "medida": "r4", "limiar": 2.5, "sentido": -1, "lado": "alto"}
        self.assertEqual(C.opiniao(s_baixo, {"r4": -3.0}), 1)
        self.assertEqual(C.opiniao(s_baixo, {"r4": -1.0}), 0)
        self.assertEqual(C.opiniao(s_alto, {"r4": 3.0}), -1)


class LivroDeMetodos(unittest.TestCase):
    def test_classifica_e_outros_robos_usam_so_comprovados(self):
        from baleias import cerebro as C
        c = C.Cerebro()
        for s in c.sinapses:
            s["previsoes"], s["acertos"] = 0, 0
        rq = next(s for s in c.sinapses if s["id"] == "reversao_queda")
        rq["previsoes"], rq["acertos"] = 400, 230          # 57,5%: comprovado
        ra = next(s for s in c.sinapses if s["id"] == "reversao_alta")
        ra["previsoes"], ra["acertos"] = 40, 23            # promissor
        livro = c.livro()
        classes = {m["id"]: m["classe"] for m in livro}
        self.assertEqual(classes["reversao_queda"], "comprovado")
        self.assertEqual(classes["reversao_alta"], "promissor")
        self.assertEqual(livro[0]["id"], "reversao_queda")
        voto, usados = C.votar_comprovados(livro, {"r4": -3.0})
        self.assertGreater(voto, 0)
        self.assertEqual(usados, ["reversao_queda"])
        voto, usados = C.votar_comprovados(livro, {"r4": 3.0})   # promissor (reversao_alta) não influencia ninguém
        self.assertEqual((voto, usados), (0.0, []))


class CerebroV2(unittest.TestCase):
    def test_homeostase_esquecimento_e_sono(self):
        from baleias import cerebro as C
        c = C.CerebroV2()
        rede = next(s for s in c.sinapses if s["id"] == "rede_neural")
        rede["peso"] = 30.0
        c._homeostase()
        total = sum(s["peso"] for s in c.sinapses if s["status"] == "ativa")
        self.assertLessEqual(rede["peso"] / total, C.TETO_VOTO + 1e-9)
        f = {k: 0.0 for k in C.ENTRADAS_REDE} | {"chop": 30.0, "rsi": 50.0, "vi": 0.5, "dp": 0.002}
        for i in range(400):                        # o mercado sobe sempre: Vórtice invertido (diz desce) erra sempre
            c.decidir(i, f, 100.0)
            c.conferir(i, +0.002, f)
        vi = next(s for s in c.sinapses if s["id"] == "vortice_invertido")
        self.assertLess(vi["ew_a"] / vi["ew_n"], 0.05)
        self.assertLess(vi["ew_n"], 400)            # esqueceu parte do passado
        self.assertTrue(any("Sono" in d["texto"] for d in c.diario))
        self.assertLessEqual(len(c.hipocampo), C.HIPOCAMPO)
        e = c.exportar()
        self.assertEqual(e["versao"], 2)
        c2 = C.CerebroV2(e)
        self.assertEqual(len(c2.hipocampo), len(c.hipocampo))

    def test_dopamina_pesa_movimento_grande(self):
        from baleias import cerebro as C
        f = {k: 0.0 for k in C.ENTRADAS_REDE} | {"chop": 30.0, "rsi": 50.0, "vi": -0.5, "dp": 0.002}   # Vórtice invertido diz SOBE
        pequeno, grande = C.CerebroV2(), C.CerebroV2()
        for cb, r in ((pequeno, 0.0004), (grande, 0.006)):
            cb.decidir(0, f, 100.0)
            cb.conferir(1, r, f)
        pv = lambda cb: next(s for s in cb.sinapses if s["id"] == "vortice_invertido")["peso"]
        self.assertGreater(pv(grande), pv(pequeno))


class Mesa(unittest.TestCase):
    def test_regras_da_mesa(self):
        from baleias import mesa as M
        dia = 86400 * 20000
        ruim = M.avaliar("x", [(dia, -0.06), (dia + 60, -0.06)], 2)            # −11,6% num dia: violação
        self.assertTrue(ruim["violacoes"])
        self.assertIn("violação", ruim["status"])
        quebrado = M.avaliar("y", [(dia + k * 86400, -0.09) for k in range(10)], 10)
        self.assertIn("eliminado", quebrado["status"])
        bom = M.avaliar("z", [(dia + k * 3600, 0.005) for k in range(30)], 30)
        self.assertIn("aprovado", bom["status"])
        self.assertAlmostEqual(bom["conta"], 10 * 1.005 ** 30)
        novo = M.avaliar("w", [], 0)
        self.assertEqual((novo["conta"], novo["falta"]["operacoes"]), (10.0, 30))


class OrcamentoFixo(unittest.TestCase):
    def test_conta_de_10_abre_duas_de_5(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"
        antes = X.ORCAMENTO_FIXO
        self.addCleanup(setattr, X, "ORCAMENTO_FIXO", antes)
        X.ORCAMENTO_FIXO = 5.0
        e = X.novo_estado(10.0)
        velas = RoboTartaruga._velas(None, [[100, 106, 100, 105]])
        X.passo_diario(e, X.Simulada(None, e), {"AUSDT": velas, "BUSDT": velas, "CUSDT": velas}, {"AUSDT": 105.0, "BUSDT": 105.0, "CUSDT": 105.0})
        self.assertEqual(len(e["abertas"]), 2)                 # duas de US$ 5; a terceira não cabe
        self.assertAlmostEqual(e["caixa"], 0.0)
        self.assertIn("não há caixa", X.EVENTOS.read_text())


class CerebroRapido(unittest.TestCase):
    def test_aprende_com_varias_moedas_e_confere_em_1h(self):
        from baleias import cerebro as C
        cb = C.CerebroRapido()
        def velas(n, sobe):
            v, px = [], 100.0
            for i in range(n):
                px *= 1.001 if sobe else 0.999
                v.append((i * 300_000, px, px * 1.002, px * 0.998, px, 10.0))
            return v
        a, b = velas(150, True), velas(150, False)
        prob, ev, f, lado = cb.observar("AUSDT", a[:130])
        cb.observar("BUSDT", b[:130])
        self.assertEqual(len(cb.previsoes), 2)
        self.assertEqual(cb.resolver("AUSDT", a[:141]), 0)            # 11 velas depois: ainda não deu 1 h
        self.assertEqual(cb.resolver("AUSDT", a[:143]), 1)            # 12 velas depois: confere
        self.assertEqual([p["m"] for p in cb.previsoes], ["BUSDT"])
        self.assertLess(ev, 0.01)
        e = cb.exportar()
        self.assertEqual(C.CerebroRapido(e).previsoes[0]["m"], "BUSDT")


class SinapsesVelez(unittest.TestCase):
    def test_espaco_duplo_e_injecao_em_cerebro_existente(self):
        from baleias import cerebro as C
        c = [100.0] * 215 + [104.0]
        m = C.medidas_velez(c, [x * 1.001 for x in c], [x * 0.999 for x in c], c, len(c) - 1)
        self.assertEqual(m["espaco"], 1.0)
        estado = C.Cerebro().exportar()
        estado["sinapses"] = [s for s in estado["sinapses"] if not s["id"].startswith("velez")]
        cb = C.Cerebro(estado)
        velez = [s for s in cb.sinapses if s["id"].startswith("velez")]
        self.assertEqual(len(velez), len(C.SINAPSES_VELEZ))
        self.assertTrue(all(s["status"] == "observacao" and s["peso"] == 0.0 for s in velez))
        s = next(x for x in velez if x["id"] == "velez_espaco_duplo_alto")
        self.assertEqual(C.opiniao(s, {"espaco": 1.0}), -1)


class VendaSimulada(unittest.TestCase):
    def test_vendido_ganha_na_queda_e_stop_acima(self):
        from executor import tartaruga_exec as X
        X.EVENTOS = pathlib.Path(__import__("tempfile").mkdtemp()) / "ev.jsonl"
        antes = X.ORCAMENTO_FIXO
        self.addCleanup(setattr, X, "ORCAMENTO_FIXO", antes)
        X.ORCAMENTO_FIXO = 5.0
        e = X.novo_estado(10.0)
        c = X.Simulada(None, e)
        X.entrar(e, c, "AUSDT", 100.0, 1.0, "teste", lado="venda", custo_lado=0.0005)
        p = e["abertas"]["AUSDT"]
        self.assertEqual((p["lado"], p["stop"]), ("venda", 102.0))
        margem = 5.0 / X.ALAV_PERP
        self.assertAlmostEqual(e["caixa"], 10.0 - margem)                                       # posição de US$ 5 com margem de 5 ÷ alavancagem
        self.assertAlmostEqual(X.patrimonio(e, {"AUSDT": 90.0}, c), 10.0 + 0.05 * 10)       # caiu 10%: ganhou 0,50
        self.assertFalse(c.stop_saiu("AUSDT", p, 101.0)[0])
        self.assertTrue(c.stop_saiu("AUSDT", p, 102.5)[0])
        X.entrar(e, c, "BUSDT", 50.0, 1.0, "teste", lado="compra", custo_lado=0.0005)
        X.entrar(e, c, "CUSDT", 50.0, 1.0, "teste", lado="compra", custo_lado=0.0005)
        self.assertEqual(len(e["abertas"]), 3)                                                  # conta de 10 mantém 3 posições
        X._sair(e, c, "AUSDT", "teste", 90.0)
        f = e["fechadas"][0]
        self.assertAlmostEqual(f["resultado_usd"], 0.5 - 0.0005 * 0.05 * 190)                  # taxas sobre o tamanho
        self.assertAlmostEqual(e["caixa"], 10.0 - 2 * margem + f["resultado_usd"])
        # no real a venda a descoberto é recusada
        r = X.Real(None, X.novo_estado(0))
        self.assertIsNone(r.e["abertas"].get("BUSDT"))
        X.entrar(r.e, r, "BUSDT", 100.0, 1.0, "teste", lado="venda", custo_lado=0.0005)
        self.assertNotIn("BUSDT", r.e["abertas"])


class Autoconhecimento(unittest.TestCase):
    def test_conclusoes_sobre_si_mesmo(self):
        import time as t
        from baleias import cerebro as C
        agora = t.time()
        f = lambda m, lado, p, r: {"moeda": m, "lado": lado, "prob_lado": p, "resultado_usd": r, "saida_t": agora - 60}
        ops = [f("XUSDT", "venda", 0.6, -0.05) for _ in range(8)] + [f("YUSDT", "compra", 0.56, 0.04) for _ in range(6)] + \
              [f("YUSDT", "compra", 0.57, -0.03) for _ in range(6)] + [f("ZUSDT", "venda", 0.61, -0.02) for _ in range(4)]
        rel = C.autoanalise(ops)
        self.assertIn("XUSDT", rel["geladeira"])
        self.assertIn("venda", rel["margem_lado"])                     # 0/12 vendas com lucro → exige mais certeza
        self.assertTrue(any("vendendo" in c for c in rel["conclusoes"]))
        self.assertTrue(any("confiante demais" in c for c in rel["conclusoes"]))
        self.assertLess(C.prob_calibrada(0.61, rel), 0.61)             # na faixa 60–65% errou tudo: probabilidade corrigida para baixo
        self.assertAlmostEqual(C.prob_calibrada(0.52, rel), 0.52)       # faixa sem dados: não mexe


class RobosNoMesmoProcesso(unittest.TestCase):
    def test_configurado_devolve_ouvinte_e_orcamento_mesmo_com_erro(self):
        from executor import tartaruga_exec as X
        antes = X.ouvinte, X.ORCAMENTO_FIXO
        with self.assertRaises(RuntimeError):
            with X.configurado(print, 5.0):
                self.assertEqual((X.ouvinte, X.ORCAMENTO_FIXO), (print, 5.0))
                raise RuntimeError("falha no meio da operação")
        self.assertEqual((X.ouvinte, X.ORCAMENTO_FIXO), antes)

    def test_dormir_acorda_quando_o_relogio_pula(self):
        from unittest import mock
        from baleias import tempo_real as R
        relogio = iter([1000.0, 1000.0, 5000.0])                      # a máquina dormiu entre duas olhadas no relógio
        with mock.patch.object(R.time, "time", lambda: next(relogio)), mock.patch.object(R.time, "sleep") as dorme:
            R.dormir(1800)
        self.assertEqual(dorme.call_count, 1)                         # não continua esperando os 30 min inteiros

    def test_mesa_do_cerebro_limita_exposicao_por_vela(self):
        from baleias import mesa
        est = {"inicio_ao_vivo": 1, "operacoes": [{"t": 1000, "liquido": -0.02, "aposta": 1}]}
        outras = {f"M{i}USDT": {"v1": {"ops": [[1000, -0.02, 1]]}} for i in range(9)}   # 10 moedas perdem juntas na mesma vela
        f = mesa._cerebro(est, "Cérebro v1", outras, "v1")
        self.assertEqual(f["operacoes"], 10)
        self.assertAlmostEqual(f["conta"], 10 * (1 - 0.06))            # perde no máximo 6% da conta, não 20%


class CerebroRapidoHumor(unittest.TestCase):
    def test_regra_desce_em_dia_de_queda_nao_vira_sabedoria(self):
        from baleias import cerebro as C
        s = {"acertos": 70, "previsoes": 100, "esperado": 68.0}
        self.assertLess(C.CerebroRapido.vantagem(s), 0.02)             # 70% contra 68% do mercado: quase nada
        self.assertGreater(C.CerebroRapido.vantagem({"acertos": 70, "previsoes": 100, "esperado": 50.0}), 0.1)

    def test_horizonte_em_velas_do_tempo_grafico(self):
        from baleias import cerebro as C
        cb = C.CerebroRapido(None)
        v = [(i * 60_000, 100.0, 101, 99, 100.0 + (i >= 30), 1.0) for i in range(60)]   # velas de 1 min; sobe na vela 30
        cb.previsoes = [{"m": "X", "t": 20 * 60_000, "px": 100.0, "x": [0.0] * 16, "opinioes": {}, "prob": 0.5}]
        self.assertEqual(cb.resolver("X", v), 1)                       # conferida 12 velas (12 min) depois, não 1 h depois
        self.assertEqual(cb.passo_ms, 60_000)

    def test_cada_moeda_tem_cerebro_isolado(self):
        from baleias import cerebro as C
        cb = C.CerebrosPorMoeda(None)
        v = [(i * 60_000, 100.0, 101, 99, 100.0 + (i >= 30), 1.0) for i in range(60)]
        cb.resolver("AUSDT", v)
        cb.resolver("BUSDT", v)
        self.assertIsNot(cb.cerebros["AUSDT"], cb.cerebros["BUSDT"])
        cb.cerebros["AUSDT"].sinapses[0]["acertos"] += 99
        self.assertNotEqual(cb.cerebros["AUSDT"].sinapses[0]["acertos"], cb.cerebros["BUSDT"].sinapses[0]["acertos"])
        de_novo = C.CerebrosPorMoeda(json.loads(json.dumps(cb.exportar())))
        self.assertEqual(set(de_novo.cerebros), {"AUSDT", "BUSDT"})

    def test_cerebro_v3_mede_merito_contra_o_humor_do_mercado(self):
        from baleias import cerebro as C
        cb = C.CerebroV3(None)
        cb.base_sobe = 0.3                                              # mercado caindo: 70% das velas descem
        cb.pendente = {"t": 0, "px": 100.0, "opinioes": {cb.sinapses[0]["id"]: -1}, "prob": 0.5, "aposta": None}
        antes = cb.sinapses[0].get("esperado", 0.5 * cb.sinapses[0]["previsoes"])
        cb.conferir(1, -0.01, {k: 0.0 for k in C.caracteristicas([(i, 1.0, 1.0, 1.0, 1.0, 1.0) for i in range(C.JANELA)])})
        self.assertAlmostEqual(cb.sinapses[0]["esperado"] - antes, 0.7)  # acertar "desce" num dia de queda vale só o que passa de 70%
        self.assertLess(cb.base_sobe, 0.3)
        self.assertEqual(json.loads(json.dumps(cb.exportar()))["versao"], "v3")


class FreioDeCorrelacao(unittest.TestCase):
    def test_no_maximo_duas_posicoes_no_mesmo_lado(self):
        from baleias import tempo_real as R
        abertas = {"AUSDT": {"lado": "venda"}, "BUSDT": {"lado": "venda"}, "CUSDT": {"lado": "compra"}}
        self.assertTrue(R.lado_cheio(abertas, "venda"))
        self.assertFalse(R.lado_cheio(abertas, "compra"))

    def test_scalper_le_as_apostas_do_v3(self):
        from unittest import mock
        from baleias import mesa
        btc = {"pendente": {"t": 1000, "px": 100.0, "prob": 0.55, "aposta": 1}}
        outras = {"ETHUSDT": {"v3": {"pendente": {"t": 1000, "px": 10.0, "prob": 0.45, "aposta": -1}}},
                  "SOLUSDT": {"v3": {"pendente": {"t": 1000, "px": 5.0, "prob": 0.5, "aposta": None}}}}
        mesa._sinais.update(t=0)
        with mock.patch.object(mesa, "_git_json", lambda c: btc if c.endswith("cerebro_v3.json") else outras), \
             mock.patch.object(mesa.subprocess, "run"):
            s = {x["par"]: x["lado"] for x in mesa.sinais_v3()}
        self.assertEqual(s, {"BTCUSDT": "compra", "ETHUSDT": "venda"})   # SOL não apostou


class Minerador(unittest.TestCase):
    def test_estatistica_agrupa_por_instante(self):
        try:
            import numpy as np
            from lab import minerador as M
        except ImportError:
            self.skipTest("numpy só no .venv-ml")
        y = np.array([[1.0, 0.0, 1.0, 1.0] * 50, [1.0, 0.0, 1.0, 1.0] * 50])     # duas moedas idênticas (andam juntas)
        ret = np.where(y > 0, 0.01, -0.01)
        um = M.avaliar(np.ones((1, 200), bool), y[:1], ret[:1], True, slice(0, 200))
        dois = M.avaliar(np.ones((2, 200), bool), y, ret, True, slice(0, 200))
        self.assertEqual(um["instantes"], dois["instantes"])            # a moeda repetida não dobra a amostra
        self.assertAlmostEqual(um["t"], dois["t"])
        self.assertAlmostEqual(dois["acerto"], 0.75)


class VelasAoVivo(unittest.TestCase):
    def test_vela_fechada_nao_recebe_o_preco_ao_vivo(self):
        from unittest import mock
        from baleias import tempo_real as R
        m = R.Motor()
        agora_ms = int(R.time.time() * 1000) // 60_000 * 60_000
        antigas = [[agora_ms - 60_000 * (60 - i), "1", "1", "1", "1", "1", 0] for i in range(60)]   # termina no minuto ANTERIOR
        m._cache_velas = {("XUSDT", "1m"): (R.time.time(), antigas)}
        m.mercado = {"X": {"p": 2.0}}
        novas = antigas[1:] + [[agora_ms, "1", "1", "1", "1", "1", 0]]
        resp = mock.MagicMock(); resp.__enter__.return_value = resp
        with mock.patch.object(R.urllib.request, "urlopen", return_value=resp), mock.patch.object(R.json, "load", return_value=novas):
            v = m.velas_ao_vivo("X", "1m", n=10)
        self.assertEqual(v["velas"][-2]["c"], 1.0)        # a vela que fechou fica como fechou
        self.assertEqual(v["velas"][-1]["c"], 2.0)        # o preço ao vivo vai para a vela de agora


class SemTravaPorMoeda(unittest.TestCase):
    def test_cerebro_sem_teto_continua_apostando_depois_de_perder(self):
        from baleias import cerebro as C
        cb = C.CerebroV3(None)
        v = [(1794400000000 + i * 900_000, 1.0, 1.01, 0.99, 1.0 + (i % 7) * 0.001, 1.0) for i in range(C.JANELA)]
        cb.operacoes = [{"t": v[-1][0], "liquido": -0.02, "capital": 500.0}] * 20          # perdeu bem mais que US$ 100 no dia da vela
        def decidir(t, f, px):
            cb.pendente = {"t": t, "px": px, "opinioes": {}, "prob": 0.6, "aposta": 1}
            return cb.pendente
        cb.decidir = decidir
        C.passo(cb, v, teto=float("inf"))
        self.assertEqual(cb.pendente["aposta"], 1)
        C.passo(cb, v, teto=100.0)
        self.assertIsNone(cb.pendente["aposta"])                                           # a trava antiga ainda existe para quem pedir
