import ast
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
            media = 0.3 if b == "compra_lim0.10_seg30" else -0.2
            self.c.execute("INSERT INTO robo_bracos VALUES(?,?,?,?)", (b, 200, media * 200, (media * media + 0.05) * 200))
        escolhas = [self.A.escolher(self.c, 1.0, rnd) for _ in range(200)]
        self.assertGreater(escolhas.count("compra_lim0.10_seg30") / 200, 0.9)

    def test_so_disparam_versoes_abaixo_da_previsao(self):
        rnd = random.Random(3)
        for _ in range(100):
            b = self.A.escolher(self.c, 0.07, rnd)
            lado, lim, _ = self.A.parametros(b) if b else (None, 0, 0)
            self.assertTrue(b is None or (lado == "compra" and lim < 0.07))

    def test_resolve_e_aprende_todas_as_versoes(self):
        self.A.registrar_oportunidade(self.c, 0, 100.0, 0.08)
        self.assertFalse(self.A.registrar_oportunidade(self.c, 60_000, 100.0, 0.08), "uma oportunidade a cada 5 min")
        velas = [(i, 100, 100.3, 99.95, 100.2) for i in range(30)]
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
