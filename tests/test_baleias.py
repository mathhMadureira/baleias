import ast
import math
import json
import pathlib
import random
import unittest
import tempfile as _tf, os as _os, json as _js
_FOCO = _os.path.join(_tf.mkdtemp(), "FOCO.json")
open(_FOCO, "w").write(_js.dumps({"foco": "todas"}))
_os.environ["BALEIAS_FOCO"] = _FOCO                 # 24/11: as ferramentas só abrem com a chave de foco liberada
import unittest.mock

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
    def test_limite_de_posicoes_no_mesmo_lado(self):
        from baleias import tempo_real as R
        abertas = {"AUSDT": {"lado": "venda"}, "BUSDT": {"lado": "venda"}, "CUSDT": {"lado": "compra"}}
        self.assertFalse(R.lado_cheio(abertas, "venda")); self.assertTrue(R.lado_cheio({f"{i}USDT": {"lado": "venda"} for i in range(R.MAX_MESMO_LADO)}, "venda"))
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


class MineradorNuvem(unittest.TestCase):
    def _velas(self, ultima_ret, ultimo_vol):
        k, px = [], 100.0
        for i in range(99):
            r = 0.001 if i % 2 else -0.001
            if i == 98:
                r = ultima_ret
            novo = px * (1 + r)
            k.append([i * 900_000, str(px), str(max(px, novo) * 1.001), str(min(px, novo) * 0.999), str(novo), str(ultimo_vol if i == 98 else 100.0), i * 900_000 + 899_999])
            px = novo
        return k

    def test_queda_forte_sem_volume_compra_e_segue_sem_limite_de_vela(self):
        from executor import minerador_nuvem as MN
        k = self._velas(-0.01, 5.0)                                   # queda de 10σ com 5% do volume normal
        self.assertEqual(MN.sinal(k)[0], "compra")
        self.assertIsNone(MN.sinal(self._velas(-0.01, 100.0)))        # com volume normal, não é sinal
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "ultimo_sinal": {}}
        MN.passo(e, {"XUSDT": k}, k[-1][6])
        self.assertIn("XUSDT", e["abertas"])
        seguinte = k + [[k[-1][0] + 900_000, k[-1][4], "100", "98.5", "99.5", "100", k[-1][6] + 900_000]]
        MN.passo(e, {"XUSDT": seguinte}, seguinte[-1][6])
        self.assertIn("XUSDT", e["abertas"])                          # pedido do dono (16/11): não sai só porque a vela acabou
        entrada = float(k[-1][4])
        queda = seguinte + [[seguinte[-1][0] + 900_000, "99.5", "99.6", str(entrada * 0.97), "98", "100", seguinte[-1][6] + 900_000]]
        MN.passo(e, {"XUSDT": queda}, queda[-1][6])
        f = e["fechadas"][0]
        self.assertEqual(f["motivo"], "stop de segurança −2%")
        self.assertAlmostEqual(f["resultado_usd"], MN.ORCAMENTO * -MN.STOP_SEG - 2 * MN.CUSTO_LADO * MN.ORCAMENTO)
        self.assertAlmostEqual(e["caixa"], 10.0 + f["resultado_usd"])


class UmaReguaSo(unittest.TestCase):
    def test_mesa_e_lucros_realizados_contam_as_mesmas_apostas_do_v3(self):
        from unittest import mock
        from baleias import mesa
        ini = mesa.DESAFIO_INICIO
        vela_antes, vela_depois = (ini - 1200) * 1000, (ini + 600) * 1000     # sinal antes do início (aposta feita antes) e depois
        btc = {"inicio_ao_vivo": 1, "operacoes": [{"t": vela_antes, "liquido": 0.02, "aposta": 1}, {"t": vela_depois, "liquido": -0.02, "aposta": 1}]}
        mesa._v3_ops.update(t=0)
        with mock.patch.object(mesa, "_git_json", lambda c: btc if c.endswith("cerebro_v3.json") else {}), \
             mock.patch.object(mesa, "_buscar_estado"), mock.patch.object(mesa, "config") as cfg:
            cfg.RAIZ = pathlib.Path(__import__("tempfile").mkdtemp())
            r = mesa.realizados()
            f = mesa._cerebro(btc, "Cérebro v3", {}, "v3")
        self.assertNotIn("🧠 Cérebro v3", r["totais"])        # decisão do dono (13/11): as apostas de contrato binário saíram dos realizados e do placar
        self.assertAlmostEqual(f["desafio"]["carteira"] - 10, -0.2)   # a régua do cérebro (só a aposta feita depois do início) segue correta na aba de pesquisa


class Equipe(unittest.TestCase):
    """Fusão OpenBot + Baleias (16/11): sala, caixa do dono, ordens do chefe aos robôs."""

    def setUp(self):
        import pathlib, tempfile
        from baleias import config as cfg
        self.cfg, self.antes = cfg, cfg.RAIZ
        cfg.RAIZ = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        self.cfg.RAIZ = self.antes

    def test_caixa_do_dono_entra_na_sala_e_fica_pendente_ate_resposta(self):
        import json
        from baleias import equipe
        caminho, m = equipe.nova_mensagem_dono("quero todos vendidos", t=1000.0)
        arq = self.cfg.RAIZ.parent / caminho.replace("dados/", self.cfg.RAIZ.name + "/", 1)
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(m))
        self.assertEqual(len(equipe.sincronizar_caixa()), 1)
        self.assertEqual(equipe.sincronizar_caixa(), [])                # não duplica
        self.assertEqual([x["texto"] for x in equipe.pendentes_do_dono()], ["quero todos vendidos"])
        equipe.postar("claude", "feito", para="dono", tipo="resposta", ref=m["id"])
        self.assertEqual(equipe.pendentes_do_dono(), [])

    def test_ordens_validas_expiram_e_o_chefe_nao_se_ordena(self):
        from baleias import equipe
        t = 1_000_000.0
        textos = equipe.aplicar_ordens([{"agente": "cacador", "acao": "so_vendas", "horas": 99, "motivo": "baixa"},
                                        {"agente": "claude", "acao": "pausar"}, {"agente": "x", "acao": "pausar"},
                                        {"agente": "rapido", "acao": "explodir"}], agora=t)
        self.assertEqual(len(textos), 1)
        o = equipe.ordens()["cacador"]
        self.assertEqual(o["ate"], t + 24 * 3600)                       # prazo limitado a 24 h
        self.assertEqual(equipe.lado_da_ordem("rapido", "compra"), (False, "compra"))
        import time
        if o["ate"] < time.time():                                      # data no passado: a ordem já venceu
            self.assertIsNone(equipe.ordem_vigente("cacador"))
        self.assertIsNotNone(equipe.ordem_vigente("cacador", agora=t + 3600))

    def test_robo_v4_pausado_nao_entra_e_ordem_de_venda_bloqueia_compra(self):
        from executor import v4_perp_nuvem as V
        def estado():
            return {"caixa": 10.0, "abertas": {}, "fechadas": [], "ultimo_sinal": {}}
        pend = {"AAAUSDT": {"t": 0, "px": 1.0, "prob": 0.9}, "BBBUSDT": {"t": 0, "px": 1.0, "prob": 0.1}}
        e = estado(); V.passo(e, pend, {}, 0, pausado=True)
        self.assertEqual(e["abertas"], {})
        e = estado(); V.passo(e, pend, {}, 0, lado_ordem="venda")
        self.assertEqual({p["lado"] for p in e["abertas"].values()}, {"venda"})

    def test_chefe_responde_e_ordena_pela_decisao(self):
        from baleias import equipe
        from executor import robo_claude_nuvem as RC
        equipe.postar("dono", "vende tudo", para="claude", t=500.0)
        ref = equipe.sala()[0]["id"]
        import time
        agora = time.time()
        RC.falar_e_ordenar({"leitura": "baixa", "respostas": [{"ref": ref, "texto": "ok, mesa vendida"}, {"ref": "falso", "texto": "x"}],
                            "ordens": [{"agente": "minerador", "acao": "so_vendas", "horas": 2}]}, agora)
        self.assertEqual(equipe.pendentes_do_dono(), [])
        self.assertEqual(sum(1 for x in equipe.sala() if x["tipo"] == "resposta"), 1)
        self.assertEqual(equipe.lado_da_ordem("minerador", None), (False, "venda"))


class VigiaV4(unittest.TestCase):
    """Monitoramento do v4 (livro ML for High-Risk Applications): acerto ao vivo × laboratório, por vela, e referência simples."""

    def test_erro_padrao_por_vela_e_alarme(self):
        from executor import vigia_v4 as V
        agora = 2_000_000_000.0
        t0 = int((agora - 86400) * 1000)
        ops = {f"M{i}USDT": [[t0 + v * V.VELA_MS, (0.019 if (v % 10 < 3) else -0.02), 1] for v in range(60)] for i in range(5)}
        r = V.avaliar(ops, agora=agora)
        self.assertEqual(r["n_velas"], 60)                    # 300 apostas, mas só 60 velas independentes
        self.assertAlmostEqual(r["acerto_ao_vivo"], 0.3)
        self.assertTrue(r["veredito"].startswith("ALARME"))
        self.assertEqual(V.avaliar({}, agora=agora)["veredito"][:7], "não sei")

    def test_referencia_simples_que_ganha_e_apontada(self):
        from executor import vigia_v4 as V
        agora = 2_000_000_000.0
        base = int((agora - 2 * 86400) * 1000) // V.VELA_MS * V.VELA_MS
        velas, ops = {}, {}
        for i in range(25):                                   # todas sobem sempre: "segue as 24 h" acerta tudo; o v4 aposta na queda e erra
            par = f"M{i}USDT"
            velas[par] = [[base + k * V.VELA_MS, 0, 0, 0, 100 * 1.001 ** k] for k in range(200)]
            ops[par] = [[base + k * V.VELA_MS, -0.02, -1] for k in range(100, 200)]
        r = V.avaliar(ops, velas, agora=agora)
        self.assertEqual(r["referencias"]["segue_24h_da_moeda"]["acerto"], 1.0)
        self.assertIn("segue_maioria_24h", r["referencia_ganha"])


class RoboLivre(unittest.TestCase):
    """H47: robô sem regras de decisão; só custo real e liquidação."""

    def _velas(self, n, passo_pct, moedas=25, t0=0):
        return {f"M{i}USDT": [[t0 + k * 900_000, 0, 100 * (1 + passo_pct * (i + 1)) ** k * 1.0005, 100 * (1 + passo_pct * (i + 1)) ** k * 0.9995,
                               100 * (1 + passo_pct * (i + 1)) ** k] for k in range(n)] for i in range(moedas)}

    def test_entra_nas_lideres_do_lado_da_maioria_e_reinveste(self):
        from executor import robo_livre_nuvem as L
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "sem_custo": 0.0, "custo_pago": 0.0}
        L.passo(e, self._velas(120, 0.001), 0)
        self.assertEqual(len(e["abertas"]), 4)
        self.assertEqual({p["lado"] for p in e["abertas"].values()}, {"compra"})
        self.assertEqual(set(e["abertas"]), {"M24USDT", "M23USDT", "M22USDT", "M21USDT"})   # as que mais subiram
        self.assertAlmostEqual(sum(p["nocional"] for p in e["abertas"].values()), 200.0)     # carteira inteira a 20×

    def test_liquidacao_leva_a_margem_inteira(self):
        from executor import robo_livre_nuvem as L
        e = {"caixa": 0.0, "abertas": {"M0USDT": {"moeda": "M0USDT", "lado": "compra", "entrada": 100.0, "margem": 2.5, "nocional": 50.0,
                                                  "entrada_t": 0, "conferido_ate": 0}}, "fechadas": [], "sem_custo": 0.0, "custo_pago": 0.0}
        velas = {"M0USDT": [[0, 100, 100, 95, 96]]}
        L.passo(e, velas, 0)
        self.assertEqual(e["fechadas"][0]["resultado_usd"], -2.5)
        self.assertEqual(e["caixa"], 0.0)



class StopMovel(unittest.TestCase):
    """H49: o stop sobe junto com o lucro (arma a +0,5%, guarda 70% do pico), conferido minuto a minuto."""

    def test_sobe_com_o_pico_e_realiza(self):
        from executor import stop_movel as SM
        p = {"lado": "compra", "entrada": 100.0}
        m = [(0, 100.3, 99.9), (60_000, 101.0, 100.4), (120_000, 102.0, 101.0), (180_000, 101.5, 101.3)]   # pico +2%; volta a +1,3%
        r = SM.conferir(p, m, 0.01, 10**9, 0)
        self.assertAlmostEqual(r[0], 101.4)                   # 70% de +2% = +1,4%
        self.assertEqual(r[2], 180_000)
        self.assertIn("stop móvel", r[1])

    def test_venda_e_stop_de_seguranca_na_ordem_dos_minutos(self):
        from executor import stop_movel as SM
        p = {"lado": "venda", "entrada": 100.0}
        r = SM.conferir(p, [(0, 100.2, 99.8), (60_000, 101.2, 100.0)], 0.01, 10**9, 0)
        self.assertEqual(r[0], 101.0)
        self.assertIn("segurança", r[1])
        p = {"lado": "venda", "entrada": 100.0}
        self.assertIsNone(SM.conferir(p, [(0, 100.1, 99.6)], 0.01, 10**9, 0))     # pico 0,4%: ainda não armou
        self.assertAlmostEqual(p["pico"], 0.004)
        self.assertEqual(p["movel_ate"], 60_000)                                  # continua de onde parou na próxima rodada

    def test_robo_claude_usa_os_minutos(self):
        from executor import robo_claude_nuvem as RC, stop_movel as SM
        p = {"moeda": "AUSDT", "lado": "compra", "entrada": 100.0, "entrada_t": 0, "gasto": 2.5, "nocional": 25.0, "stop_pct": 0.03, "conferido_ate": 0}
        e = {"caixa": 7.5, "abertas": {"AUSDT": p}, "fechadas": [], "licoes": []}
        SM.MINUTOS.clear(); SM.MINUTOS["AUSDT"] = [(0, 101.0, 100.0), (60_000, 101.2, 100.6)]
        try:
            RC.passo(e, {}, {"AUSDT": [[0, 100, 101.2, 100, 100.8]]}, 1000.0)
        finally:
            SM.MINUTOS.clear()
        self.assertAlmostEqual(e["fechadas"][0]["saida"], 100.7)


class Torneio(unittest.TestCase):
    """H50: campeão = maior fator de lucro com ≥ 30 operações; desafiante julgado no mesmo período."""

    def _e(self, res, t0=0, cart=10.0):
        return {"fechadas": [{"entrada_t": t0 + i, "resultado_usd": r} for i, r in enumerate(res)], "patrimonio": cart}

    def test_campeao_exige_30_operacoes_e_desafiante_no_mesmo_periodo(self):
        from executor import torneio as T
        est = {"caçador": self._e([0.1, -0.2] * 20), "rapido": self._e([1.0] * 10),                    # rápido: ótimo, mas só 10 ops
               "scalper": self._e([0.2, -0.1] * 30, t0=0, cart=13.0), "scalper_b": self._e([0.5, -0.1] * 20, t0=20)}
        r = T.avaliar(est)
        self.assertEqual(r["campeao"], "scalper")
        v = next(x for x in r["vereditos"] if x["desafiante"] == "scalper_b")
        self.assertEqual(v["campeao_mede"]["ops"], 40)          # só as operações do campeão desde que o desafiante começou
        self.assertTrue(v["veredito"].startswith("GANHOU"))
        self.assertIsNone(T.avaliar({"x": self._e([1.0] * 5)})["campeao"])

    def test_nao_existe_campeao_no_prejuizo(self):
        """Regra do dono (16/11): maior fator de lucro e maior acerto não bastam; carteira abaixo de US$ 10 não é campeã."""
        from executor import torneio as T
        est = {"scalper": self._e([0.3, -0.1] * 20, cart=9.5), "rapido": self._e([0.1, -0.2] * 20, cart=8.0)}
        self.assertIsNone(T.avaliar(est)["campeao"])
        est["rapido"] = self._e([0.2, -0.1] * 20, cart=10.5)
        self.assertEqual(T.avaliar(est)["campeao"], "rapido")


class Radar(unittest.TestCase):
    """H56/R3: movimento ≥ 4σ sem volume → entra contra; stop de 1% e alvo de 2% conferidos segundo a segundo."""

    def test_entra_contra_e_sai_no_stop(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("sem numpy")
        from executor import radar_nuvem as R
        rng = random.Random(1)
        n = 3700
        c = [100.0]
        for _ in range(n - 1):
            c.append(c[-1] * (1 + rng.gauss(0, 0.0001)))
        c[-1] = c[-2] * 1.01                                           # salto de 1% num segundo (≈ 100σ), volume baixo
        s = np.array([[i * 1000.0, x * 1.00001, x * 0.99999, x, 1000.0 if i < n - 1 else 10.0] for i, x in enumerate(c)])
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "espera": {}}
        R.passo(e, {"BTCUSDT": s}, {"BTCUSDT": s[-2, 0]})
        self.assertEqual(e["abertas"]["BTCUSDT"]["lado"], "venda")
        seg = [n * 1000.0, c[-1] * 1.011, c[-1], c[-1] * 1.011, 10.0]  # sobe mais 1,1%: stop de 1%
        R.passo(e, {"BTCUSDT": np.vstack([s, seg])}, {"BTCUSDT": s[-1, 0]})
        self.assertFalse(e["abertas"])
        self.assertAlmostEqual(e["fechadas"][0]["resultado_usd"], -0.25 - 0.03, places=6)


class GuardaDia(unittest.TestCase):
    """H54: dia que chegou a +0,25 e devolveu metade fecha tudo e trava até o dia UTC seguinte; dia negativo segue operando."""

    def test_guarda_revogada_nao_trava_e_solta_as_travas_dela(self):
        from executor import guarda_dia as GD
        t0 = 1795000000 - 1795000000 % 86400 + 3600
        e = {"patrimonio": 10.0}
        self.assertEqual(GD.checar(e, t0), "normal")
        e["patrimonio"] = 10.40
        self.assertEqual(GD.checar(e, t0 + 60), "normal")             # pico +0,40
        e["patrimonio"] = 10.05
        self.assertEqual(GD.checar(e, t0 + 120), "normal")            # devolveu: antes fechava; agora segue operando (18/11)
        e2 = {"patrimonio": 10.1, "guarda_dia": {"data": GD._hoje(t0), "inicio": 10.0, "pico": 0.4, "travado": True, "por": "guarda"}}
        self.assertEqual(GD.checar(e2, t0 + 180), "normal")           # trava antiga da guarda é solta
        e3 = {"patrimonio": 23.0, "guarda_dia": {"data": GD._hoje(t0), "inicio": 10.0, "pico": 13.0, "travado": True, "por": "meta"}}
        self.assertEqual(GD.checar(e3, t0 + 240), "travado")          # a meta de US$ 12 continua

    def test_lbank_memecoins_primeiro(self):
        from executor import robo_lbank_nuvem as L
        self.assertTrue(L.meme("PEPEUSDT") and L.meme("1000SHIBUSDT") and not L.meme("SOLUSDT"))
        self.assertEqual(L.lado_desejado(None, 0.015, True), "compra")      # memecoin no neutro: 1% basta
        self.assertIsNone(L.lado_desejado(None, 0.015, False))              # outras moedas: 3%
        e = {"caixa": 10.0, "abertas": {}, "fechadas": []}
        with unittest.mock.patch.object(L, "minutos", return_value=[(0, 1, 1)]):
            L.passo(e, {"SOLUSDT": (100.0, 0.20), "XUSDT": (1.0, 0.15), "AUSDT": (1.0, 0.12), "BUSDT": (1.0, 0.11),
                        "PEPEUSDT": (1.0, 0.02), "DOGEUSDT": (1.0, -0.05)}, None, {}, 1000.0)
        self.assertIn("PEPEUSDT", e["abertas"])
        self.assertEqual(e["abertas"]["DOGEUSDT"]["lado"], "venda")         # short na memecoin que cai

    def test_meta_do_dia(self):
        from executor import guarda_dia as GD
        t0 = 1794787200
        e = {"patrimonio": 10.0}
        self.assertEqual(GD.checar(e, t0), "normal")
        e["patrimonio"] = 10.49
        self.assertEqual(GD.checar(e, t0 + 60), "normal")
        e["patrimonio"] = 10.55
        self.assertEqual(GD.checar(e, t0 + 120), "normal")            # meta é US$ 12: +0,55 segue operando
        e["patrimonio"] = 22.1
        self.assertEqual(GD.checar(e, t0 + 180), "fechar")
        self.assertTrue(GD.motivo(e).startswith("meta do dia"))
        e2 = {"patrimonio": 10.6, "guarda_dia": {"data": GD._hoje(t0), "inicio": 10.0, "pico": 0.6, "travado": True}}
        self.assertEqual(GD.checar(e2, t0 + 240), "normal")           # travado pela meta antiga de 0,50: destrava

    def test_tamanho_proporcional(self):
        from executor import tamanho as TM
        self.assertAlmostEqual(TM.nocional({"caixa": 10.0, "abertas": {}}), 25.0)
        self.assertAlmostEqual(TM.nocional({"caixa": 7.5, "abertas": {"X": {"gasto": 4.5}}}), 30.0)   # carteira realizada 12 → 30
        self.assertAlmostEqual(TM.nocional({"caixa": 6.0, "abertas": {}}), 15.0)                      # encolhe na perda
        self.assertEqual(TM.nocional({"caixa": 1.0, "abertas": {"X": {"gasto": 9.0}}}), 0.0)            # margem de 2,50 não cabe


class BancoEPausa(unittest.TestCase):
    """16/11: banco tesoureiro (sem crédito, sem empréstimo) e nenhum robô pausado no prejuízo ou com operações abertas."""

    def test_banco_soma_e_acha_lados_opostos_sem_mexer_nos_robos(self):
        import copy
        from executor import banco as B
        est = {"rapido": {"patrimonio": 9.0, "abertas": {"BTCUSDT": {"moeda": "BTCUSDT", "lado": "compra", "gasto": 2.5}}, "fechadas": []},
               "cacador": {"patrimonio": 12.0, "abertas": {"BTCUSDT": {"moeda": "BTCUSDT", "lado": "venda", "gasto": 2.5},
                                                           "ETHUSDT": {"moeda": "ETHUSDT", "lado": "venda", "gasto": 2.5}}, "fechadas": []},
               "livre": {"patrimonio": 0.86, "caixa": 0.86, "abertas": {}, "fechadas": []}}
        antes = copy.deepcopy(est)
        b = B.rodar(est)
        self.assertEqual(est, antes)                                   # não empresta, não muda carteira de ninguém
        self.assertEqual(b["tesouro"]["carteiras"], 21.86)
        self.assertEqual(b["tesouro"]["no_lucro"], ["cacador"])
        self.assertEqual(b["exposicao"]["bruta"], 75.0)
        self.assertEqual(b["exposicao"]["liquida"], 25.0)              # BTC comprado e vendido se anula
        self.assertEqual([c["moeda"] for c in b["exposicao"]["conflitos"]], ["BTCUSDT"])

    def test_pausa_recusada_no_prejuizo_ou_com_abertas(self):
        import json, pathlib, tempfile, time
        from baleias import config, equipe
        with tempfile.TemporaryDirectory() as d:
            antigo, config.RAIZ = config.RAIZ, pathlib.Path(d)
            try:
                arq = lambda ag: pathlib.Path(d) / equipe.POR_ID[ag]["arquivo"]
                arq("rapido").write_text(json.dumps({"patrimonio": 8.0, "abertas": {}}))
                arq("cacador").write_text(json.dumps({"patrimonio": 12.0, "abertas": {"BTCUSDT": {"lado": "compra"}}}))
                arq("minerador").write_text(json.dumps({"patrimonio": 12.0, "abertas": {}}))
                txt = equipe.aplicar_ordens([{"agente": ag, "acao": "pausar", "horas": 6} for ag in ("rapido", "cacador", "minerador")])
                self.assertEqual(sum(x.startswith("🚫") for x in txt), 2)
                self.assertIsNone(equipe.ordem_vigente("rapido"))
                self.assertIsNone(equipe.ordem_vigente("cacador"))
                self.assertEqual(equipe.ordem_vigente("minerador")["acao"], "pausar")   # no lucro e sem abertas: pode
                o = equipe.ordens(); o["rapido"] = {"acao": "pausar", "ate": time.time() + 3600}
                equipe._gravar(equipe.ORDENS, o)                                       # pausa antiga em vigor não vale no prejuízo
                self.assertEqual(equipe.lado_da_ordem("rapido", None), (False, None))
            finally:
                config.RAIZ = antigo


class FocoScalper(unittest.TestCase):
    """H51: o Scalper D evita só o segmento que perde com prova (≥ 50 operações, z ≤ −2)."""

    def test_foco_so_com_prova_e_o_robo_obedece(self):
        import json, pathlib, tempfile, random
        from baleias import config as cfg
        from executor import torneio as T, v4_perp_nuvem as V
        random.seed(1)
        t_venda = 1_800_000_000 + 3 * 3600                     # 03 h UTC
        f = [{"lado": "venda", "prob": 0.4, "entrada_t": t_venda, "resultado_usd": -0.1 + random.uniform(-0.02, 0.02)} for _ in range(60)]
        f += [{"lado": "compra", "prob": 0.6, "entrada_t": t_venda + 6 * 3600, "resultado_usd": 0.05 + random.uniform(-0.2, 0.2)} for _ in range(60)]
        ruins, seg = T.foco(f)
        self.assertIn("lado:venda", ruins)
        self.assertNotIn("lado:compra", ruins)
        self.assertEqual(T.foco(f[:40])[0], [])                # só 40 operações: não sei, não exclui nada
        antes, antes_foco = cfg.RAIZ, V.FOCO
        cfg.RAIZ = pathlib.Path(tempfile.mkdtemp()); V.FOCO = "foco.json"
        try:
            (cfg.RAIZ / "foco.json").write_text(json.dumps({"excluir": ["lado:venda"]}))
            self.assertTrue(V.evitar("venda", 0.4, t_venda))
            self.assertFalse(V.evitar("compra", 0.6, t_venda))
        finally:
            cfg.RAIZ, V.FOCO = antes, antes_foco


class RevisaoDe15de11(unittest.TestCase):
    """Defeitos achados na revisão de 15/11 (cada teste falhava antes da correção)."""

    def test_alvo_vale_antes_do_stop_movel(self):
        from executor import stop_movel as SM
        p = {"lado": "compra", "entrada": 100.0}
        r = SM.conferir(p, [(0, 100.3, 99.9), (60_000, 100.6, 100.2)], 0.015, 10**9, 0, alvo_pct=0.005)
        self.assertAlmostEqual(r[0], 100.5)
        self.assertIn("lucro realizado", r[1])

    def test_claude_fecha_o_que_ficou_fora_da_lista(self):
        import time
        from executor import robo_claude_nuvem as RC
        agora = time.time()
        p = {"moeda": "AUSDT", "lado": "venda", "entrada": 100.0, "entrada_t": agora - 3600, "gasto": 2.5, "nocional": 25.0, "stop_pct": 0.03,
             "conferido_ate": int(agora * 1000)}
        e = {"caixa": 7.5, "abertas": {"AUSDT": p}, "fechadas": [], "licoes": []}
        RC.passo(e, {"t": agora, "posicoes": [], "fechar": []}, {"AUSDT": [[int(agora * 1000) - 900_000, 100, 100, 99, 99.5]]}, agora)
        self.assertEqual(e["abertas"], {})
        self.assertIn("fora da lista", e["fechadas"][0]["motivo_saida"])

    def test_eventos_nao_apagam_mensagem_do_dono(self):
        import pathlib, tempfile
        from baleias import config as cfg, equipe
        antes = cfg.RAIZ
        cfg.RAIZ = pathlib.Path(tempfile.mkdtemp())
        try:
            equipe.postar("dono", "quero todos vendidos", para="claude", t=1.0)
            equipe.postar_eventos("rapido", [f"entrada {i}" for i in range(equipe.MAX_SALA + 50)], t=2.0)
            self.assertEqual([x["texto"] for x in equipe.pendentes_do_dono()], ["quero todos vendidos"])
        finally:
            cfg.RAIZ = antes


class RotaR6(unittest.TestCase):
    """H52: com a rota R6 a posição não sai no fim da vela; sai por stop, tendência contra ou 24 h."""

    def _rodar(self, minutos, regime, agora_ms):
        from executor import v4_perp_nuvem as V, stop_movel as SM
        antes = (V.ROTA, V.STOP_SEG)
        V.ROTA, V.STOP_SEG = "r6", 0.02
        p = {"moeda": "AUSDT", "lado": "venda", "entrada": 100.0, "entrada_t": 0.0, "vela_saida": 900_000, "prob": 0.4, "gasto": 2.5}
        e = {"caixa": 7.5, "abertas": {"AUSDT": p}, "fechadas": [], "ultimo_sinal": {}}
        SM.MINUTOS.clear(); SM.MINUTOS["AUSDT"] = minutos
        velas = {"AUSDT": [[0, 100, 100, 99, 99.5], [900_000, 99.5, 99.8, 99.0, 99.2]]}
        try:
            V.passo(e, {}, velas, agora_ms, regime=regime)
        finally:
            V.ROTA, V.STOP_SEG = antes
            SM.MINUTOS.clear()
        return e

    def test_segura_depois_do_fim_da_vela(self):
        e = self._rodar([(0, 100.1, 99.7), (60_000, 99.9, 99.6)], "baixa", 1_800_000)
        self.assertIn("AUSDT", e["abertas"])

    def test_sai_quando_a_tendencia_vira(self):
        e = self._rodar([(0, 100.1, 99.7)], "alta", 1_800_000)
        self.assertIn("virou", e["fechadas"][0]["motivo"])

    def test_stop_de_2_pct(self):
        e = self._rodar([(0, 100.5, 99.9), (60_000, 102.1, 100.4)], "baixa", 1_800_000)
        self.assertAlmostEqual(e["fechadas"][0]["saida"], 102.0)


class LBankSoLeitura(unittest.TestCase):
    """Conector da LBank: assinatura conferida com o exemplo oficial; recusa chave com saque; nenhuma função de ordem."""

    def test_assinatura_igual_ao_exemplo_oficial(self):
        from executor.lbank import assinar
        p = {"api_key": "fb4e39e5-6a06-4291-9f80-d10176a0badd", "asset": "USDT", "echostr": "echostr123456789012345678901234567890",
             "productGroup": "SwapU", "signature_method": "HmacSHA256", "timestamp": "1665990154559"}
        self.assertEqual(assinar(p, "093F44F700FC48F17DDB67390C895CE5"), "809133cb69a17beba0be076b99b4d90de872476e36da87978ab2889970ccd06d")

    def test_recusa_saque_e_nao_tem_ordem(self):
        from executor import lbank as L
        self.assertTrue(L.problemas_da_chave({"enableWithdrawals": True, "ipRestrict": True})[0].startswith("GRAVE"))
        self.assertEqual(L.problemas_da_chave({"enableWithdrawals": False, "ipRestrict": True, "enableReading": True}), [])
        nomes = [n for n in dir(L.LBankLeitura) if not n.startswith("__")]
        self.assertFalse([n for n in nomes if any(x in n.lower() for x in ("ordem", "order", "comprar", "vender", "sacar", "withdraw", "cancel"))])

    def test_le_saldos_com_resposta_falsa(self):
        import io, json
        from executor.lbank import LBankLeitura
        resp = {"result": "true", "error_code": 0, "data": [{"coin": "usdt", "assetAmt": "12.5", "usableAmt": "10", "freezeAmt": "2.5"},
                                                             {"coin": "btc", "assetAmt": "0", "usableAmt": "0", "freezeAmt": "0"}]}
        pedidos = []
        def abrir(req, timeout=0):
            pedidos.append(req)
            return io.BytesIO(json.dumps(resp).encode())
        c = LBankLeitura("k" * 20, "s" * 32, abrir=abrir)
        c._desvio_ms = 0.0                                          # sem o pedido da hora do servidor neste teste
        s = c.saldos()
        self.assertEqual(s, {"USDT": {"total": 12.5, "livre": 10.0, "preso": 2.5}})
        self.assertIn(b"sign=", pedidos[0].data)
        self.assertNotIn(b"s" * 32, pedidos[0].data)                # o segredo nunca vai no pedido


class RoboLBank(unittest.TestCase):
    """H53: Robô LBank simulado — lado pelo regime, segura, sai quando o lado vira."""

    def test_lado_desejado(self):
        from executor.robo_lbank_nuvem import lado_desejado
        self.assertEqual(lado_desejado("baixa", -0.05), "venda")
        self.assertIsNone(lado_desejado("baixa", 0.02))
        self.assertEqual(lado_desejado("alta", 0.02), "compra")
        self.assertIsNone(lado_desejado(None, 0.02))
        self.assertEqual(lado_desejado(None, -0.04), "venda")

    @unittest.mock.patch("executor.robo_lbank_nuvem.velas15", lambda par: [])
    @unittest.mock.patch("executor.robo_lbank_nuvem.minutos", lambda *a: [(0, 1.0, 1.0)])
    def test_entra_nas_que_mais_caem_e_sai_quando_vira(self):
        from executor import robo_lbank_nuvem as L
        e = {"caixa": 10.0, "abertas": {}, "fechadas": []}
        mkt = {"SOLUSDT": (70.0, -0.06), "PEPEUSDT": (1e-5, -0.10), "DOGEUSDT": (0.2, -0.02), "WIFUSDT": (1.0, -0.03),
               "BONKUSDT": (1e-5, -0.04), "HOODUSDT": (75.0, 0.03)}
        L.passo(e, mkt, "baixa", {}, 1000.0)
        self.assertEqual(set(e["abertas"]), {"PEPEUSDT", "DOGEUSDT", "BONKUSDT", "WIFUSDT"})    # 18/11: memecoins primeiro (SOL fica fora)
        self.assertEqual({p["lado"] for p in e["abertas"].values()}, {"venda"})
        L.passo(e, {"PEPEUSDT": (0.9e-5, 0.02)}, "alta", {}, 2000.0)
        self.assertEqual(e["fechadas"][0]["moeda"], "PEPEUSDT")
        self.assertGreater(e["fechadas"][0]["resultado_usd"], 0)                                 # vendeu a 1e-5, saiu a 0,9e-5


class PainelMesa(unittest.TestCase):
    """Painel da mesa em tela única (17/11): cada número vem do arquivo do robô; nada é inventado."""

    def _estados(self, agora):
        from baleias import mesa
        Z = mesa.ZERO_T
        hoje = __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime(agora))
        f = lambda t, r, **k: {"moeda": "BTCUSDT", "lado": "compra", "entrada": 100.0, "entrada_t": t, "saida": 101.0, "saida_t": t + 600, "resultado_usd": r, **k}
        return {
            "cacador": {"inicio": "2026-11-16", "patrimonio": 10.7, "caixa": 8.0, "guarda_dia": {"data": hoje, "resultado": 0.3, "pico": 0.4, "travado": False},
                        "fechadas": [f(Z - 7200, -0.1), f(Z + 100, 0.5, motivo="stop móvel (pico +0.6%)"), f(Z + 5000, 0.3)],
                        "abertas": {"ETHUSDT": {"moeda": "ETHUSDT", "lado": "venda", "entrada": 2000.0, "entrada_t": agora - 120, "nocional": 25.0},
                                    "XYZUSDT": {"moeda": "XYZUSDT", "lado": "compra", "entrada": 1.0, "entrada_t": agora - 60, "gasto": 2.5}}},
            "claude": {"inicio": "2026-11-16", "patrimonio": 10.2, "guarda_dia": {"data": hoje, "resultado": 0.2, "pico": 0.5, "travado": True, "por": "guarda"},
                       "fechadas": [f(Z + 200, 0.2, motivo="entrada pela tendência", motivo_saida="guarda do dia: chegou a +0.50")]},
            "rapido": {"inicio": "2026-11-16", "patrimonio": 12.5, "guarda_dia": {"data": hoje, "resultado": 12.5, "pico": 12.5, "travado": True, "por": "meta"}, "fechadas": []},
            "scalper": {"inicio": "2026-11-16", "patrimonio": 10.0, "guarda_dia": {"data": "2026-01-01", "resultado": 0.9, "pico": 1.0, "travado": True, "por": "guarda"}, "fechadas": []},
            "minerador": {"inicio": "2026-11-16", "patrimonio": 10.0, "fechadas": []},
            "livre": {"inicio": "2026-11-16 21:57 UTC", "patrimonio": 0.9, "quebrou": True, "fechadas": []},
            "lbank": {"inicio": "2026-11-16", "patrimonio": 9.0, "fechadas": [],
                      "abertas": {"SOLUSDT": {"moeda": "SOLUSDT", "lado": "venda", "entrada": 100.0, "entrada_t": agora - 30, "gasto": 2.5}}},
            "testnet": {"inicio": "2026-11-12", "capital_inicial": 10.0, "carteira": 4.96, "trava": "2026-11-17 conta abaixo de US$ 5",
                        "fechadas": [f(Z - 86400 * 3, -5.04)]},
        }

    def _montar(self):
        from baleias import mesa
        agora = mesa.ZERO_T + 86400
        ordens = {"minerador": {"acao": "pausar", "ate": agora + 3600}, "scalper": {"acao": "pausar", "ate": agora - 1}}
        precos = {"ETHUSDT": 1990.0, "SOLUSDT": 50.0}            # preço Binance; o Robô LBank tem de usar o da LBank
        from baleias import equipe
        return mesa.montar_painel(self._estados(agora), ordens, {"tesouro": {"carteiras": 1.0}}, precos, {"SOLUSDT": 99.0}, {"robo_v4_cacador.json": agora - 50}, agora,
                                  equipe_lista=equipe.ROBOS_APOSENTADOS + equipe.EQUIPE), agora

    def test_placar_usa_os_numeros_do_arquivo_e_do_torneio(self):
        from executor import torneio as T
        d, agora = self._montar()
        l = {x["id"]: x for x in d["linhas"]}
        e = self._estados(agora)["cacador"]
        m = T.medir(e)
        self.assertEqual((l["cacador"]["ops"], l["cacador"]["acerto"], l["cacador"]["fator_lucro"]), (m["ops"], m["acerto"], m["fator_lucro"]))
        self.assertAlmostEqual(l["cacador"]["carteira"], 10.7)
        self.assertAlmostEqual(l["cacador"]["desde_zero"], 0.7)
        self.assertAlmostEqual(l["cacador"]["hoje"], 0.3)                       # da guarda do dia
        self.assertEqual(l["cacador"]["atualizado"], agora - 50)
        self.assertEqual(l["testnet"]["carteira"], 4.96)                          # testnet grava "carteira", não "patrimonio"
        self.assertFalse(l["testnet"]["zerado"])
        self.assertEqual([x["id"] for x in d["linhas"]][0], "rapido")             # ordenado pela carteira
        self.assertEqual(d["banco"], {"tesouro": {"carteiras": 1.0}})             # banco.json passa sem mudança

    def test_estado_de_cada_robo(self):
        d, _ = self._montar()
        est = {x["id"]: x["estado"] for x in d["linhas"]}
        self.assertEqual(est["claude"], "guarda")
        self.assertEqual(est["rapido"], "meta")
        self.assertEqual(est["scalper"], "operando")          # trava da guarda de outro dia e ordem vencida não contam
        self.assertEqual(est["minerador"], "pausado")
        self.assertEqual(est["livre"], "sem_dinheiro")
        self.assertEqual(est["testnet"], "sem_dinheiro")
        self.assertEqual(est["cacador"], "operando")

    def test_curva_comeca_no_zero_e_termina_na_carteira(self):
        from baleias import mesa
        d, agora = self._montar()
        c = {x["id"]: x for x in d["linhas"]}["cacador"]
        self.assertEqual(c["curva"][0], [mesa.ZERO_T, 10.0])
        self.assertEqual(c["curva"][-1][1], 10.7)
        self.assertTrue(all(p[0] >= mesa.ZERO_T for p in c["curva"]))           # operação com data antes do zero não fica antes dele
        self.assertAlmostEqual(c["curva"][1][1], 9.9)
        self.assertEqual(c["antes_do_zero"], {"n": 1, "soma": -0.1})
        t = {x["id"]: x for x in d["linhas"]}["testnet"]
        self.assertLess(t["curva"][0][0], mesa.ZERO_T)                            # testnet não foi zerado: curva desde o início dele

    def test_posicoes_abertas_com_preco_de_agora(self):
        d, _ = self._montar()
        p = {(x["robo"], x["moeda"]): x for x in d["abertas"]}
        self.assertAlmostEqual(p[("cacador", "ETH")]["resultado_usd"], 25.0 * (1 - 1990 / 2000), places=4)   # vendido e o preço caiu: ganha
        self.assertIsNone(p[("cacador", "XYZ")]["resultado_usd"])                                                # sem preço: não sei
        self.assertAlmostEqual(p[("lbank", "SOL")]["resultado_usd"], 25.0 * (1 - 99 / 100), places=4)          # preço da LBank, margem × 10
        self.assertEqual(p[("lbank", "SOL")]["fonte_preco"], "LBank")

    def test_linha_do_tempo_com_motivo_da_saida(self):
        d, _ = self._montar()
        ts = [x["t"] for x in d["tempo"]]
        self.assertEqual(ts, sorted(ts, reverse=True))
        s = [x for x in d["tempo"] if x["robo"] == "claude" and x["tipo"] == "saida"][0]
        self.assertEqual(s["motivo"], "guarda do dia: chegou a +0.50")
        e = [x for x in d["tempo"] if x["robo"] == "claude" and x["tipo"] == "entrada"][0]
        self.assertEqual(e["motivo"], "entrada pela tendência")
        s2 = [x for x in d["tempo"] if x["robo"] == "cacador" and x["tipo"] == "saida" and x["resultado_usd"] == 0.5][0]
        self.assertEqual(s2["motivo"], "stop móvel (pico +0.6%)")
        self.assertTrue(any(x.get("aberta") for x in d["tempo"]))

    def test_tela_sem_biblioteca_externa_e_com_as_seis_partes(self):
        html = (pathlib.Path(__file__).resolve().parent.parent / "baleias" / "terminal.html").read_text()
        self.assertNotIn("<script src", html.replace("<script defer src", "<script src"))
        self.assertNotIn("Polymarket", html)                                      # regra 6 do dono
        for parte in ('id="desk"', 'id="pos"', 'id="log"', 'id="fe"', 'id="eq"', 'id="mult"', 'id="curva"', 'id="kill"', "/api/vivo"):   # 25/11: painel estilo app
            self.assertIn(parte, html)


class ChefeOpenBotTestnet(unittest.TestCase):
    """H59 (17/11): o chefe OpenBot opera a conta de teste e aparece na equipe com estado próprio."""

    def test_na_equipe_com_arquivo_proprio(self):
        from baleias import equipe
        a = equipe.POR_ID["openbot_testnet"]
        self.assertEqual(a["arquivo"], "robo_openbot_testnet.json")
        self.assertEqual(len({x["arquivo"] for x in equipe.EQUIPE}), len(equipe.EQUIPE))      # dois robôs nunca no mesmo arquivo
        self.assertNotIn("openbot_testnet", {"cacador", "rapido", "scalper", "minerador", "lbank"})

    def test_painel_usa_o_preco_do_testnet(self):
        from baleias import mesa
        agora = mesa.ZERO_T + 3600
        e = {"inicio": "2026-11-18 01:04 UTC", "capital_inicial": 10.0, "caixa": 5.0, "patrimonio": 9.92, "fechadas": [],
             "abertas": {"ZECUSDT": {"moeda": "ZECUSDT", "lado": "compra", "entrada": 961.76, "entrada_t": agora - 60, "nocional": 25.0,
                                     "gasto": 2.5, "preco_testnet": 961.43}}}
        d = mesa.montar_painel({"openbot_testnet": e}, {}, None, {"ZECUSDT": 1000.0}, {}, {}, agora)
        p = d["abertas"][0]
        self.assertEqual(p["agora"], 961.43)                                   # não o preço da Binance real (1000)
        self.assertAlmostEqual(p["resultado_usd"], 25.0 * (961.43 / 961.76 - 1), places=4)
        self.assertEqual(p["fonte_preco"], "testnet (última rodada)")
        self.assertEqual(d["linhas"][0]["estado"], "operando")


class P1EntradaNaRodada(unittest.TestCase):
    """P1 do Treinador, aprovada pelo Laboratório (18/11): nada de aposta velha nem de entrada no preço/hora de uma vela passada."""

    def test_so_aposta_da_ultima_vela(self):
        from executor import v4_perp_nuvem as V
        velas = {"AUSDT": [[1000, 0, 0, 0, 1], [1900, 0, 0, 0, 1]], "BUSDT": [[1900, 0, 0, 0, 1]]}
        p = {"AUSDT": {"t": 1900, "px": 1.0, "prob": 0.6}, "CUSDT": {"t": 1000, "px": 1.0, "prob": 0.7}}
        self.assertEqual(set(V.pendentes_frescos(p, velas)), {"AUSDT"})

    def test_robo_dos_agentes_entra_no_preco_da_rodada(self):
        from executor import robo_claude_nuvem as R
        agora = 1795000000.0
        k = [[int(agora * 1000) - 900_000 * (100 - i), "1", "1", "1", "1.0"] for i in range(100)]
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "licoes": []}
        d = {"t": agora - 10, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "teste"}]}
        R.passo(e, d, {"AUSDT": k}, agora, vivos={"AUSDT": 1.05})
        a = e["abertas"]["AUSDT"]
        self.assertEqual(a["entrada"], 1.05)                       # preço da rodada, não o fechamento de 15 min (1,0)
        self.assertEqual(a["entrada_t"], agora)
        self.assertGreaterEqual(a["conferido_ate"], agora * 1000)  # stop de 15 min só em velas depois da entrada

    def test_sem_preco_da_rodada_nao_entra_no_fechamento_velho(self):
        """Auditoria 19/11: a Binance não respondeu o preço de 1 min de uma moeda → antes entrava no fechamento de 15 min (preço passado)."""
        from executor import robo_claude_nuvem as R
        agora = 1795000000.0
        k = [[int(agora * 1000) - 900_000 * (100 - i), "1", "1", "1", "1.0"] for i in range(100)]
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "licoes": []}
        d = {"t": agora - 10, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "teste"},
                                           {"moeda": "ZZZUSDT", "lado": "venda", "motivo": "fora das velas"}]}
        textos = R.passo(e, d, {"AUSDT": k}, agora, vivos={})
        self.assertEqual(e["abertas"], {})                                  # antes: abria AUSDT a 1,0 (fechamento de 15 min)
        self.assertTrue(any(t.find("A não entrou — sem o preço da rodada") >= 0 for t in textos))
        self.assertTrue(any("ZZZ" in t and "fora das velas" in t for t in textos))   # antes: pulava calado


class OperarLivre(unittest.TestCase):
    """H62 (18/11): o agente escolhe stop, alvo e prazo de cada posição; a nuvem confere minuto a minuto."""

    def test_stop_alvo_e_prazo_do_agente(self):
        from executor import robo_claude_nuvem as R, stop_movel as SM
        agora = 1795000000.0
        k = [[int(agora * 1000) - 900_000 * (100 - i), "1", "1", "1", "1.0"] for i in range(100)]
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "licoes": []}
        d = {"t": agora - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "scalper", "stop_pct": 0.004, "alvo_pct": 0.006, "max_min": 2}]}
        R.passo(e, d, {"AUSDT": k}, agora, vivos={"AUSDT": 1.0})
        a = e["abertas"]["AUSDT"]
        self.assertEqual((a["stop_pct"], a["alvo_pct"], a["max_min"]), (0.004, 0.006, 5))     # R2 (23/11): o alvo é o do agente
        SM.MINUTOS["AUSDT"] = [(int(agora * 1000) + 60_000, 1.007, 0.999)]                   # tocou +0,7%: realiza no alvo de +0,6%
        R.passo(e, d, {"AUSDT": k}, agora + 180, vivos={"AUSDT": 1.013})
        SM.MINUTOS.clear()
        f = e["fechadas"][-1]
        self.assertAlmostEqual(f["saida"], 1.006)
        self.assertIn("lucro realizado", f["motivo_saida"])
        self.assertEqual(R.parametros({"stop_pct": 0.5, "alvo_pct": "x"}), {"stop_pct": 0.04})                # R2: sem alvo forçado
        self.assertEqual(R.parametros({"alvo_pct": 0.004}), {"alvo_pct": 0.004})              # R2: sem mínimo de 1%
        self.assertEqual(R.parametros({"stop_pct": 0.01, "alvo_pct": 0.9, "movel": False}), {"stop_pct": 0.01, "alvo_pct": 0.5, "movel": False})
        self.assertEqual(R.parametros({"stop_pct": 0.005, "alvo_pct": 0.03}), {"stop_pct": 0.005, "alvo_pct": 0.03})


class StopMovelSemOlharFuturo(unittest.TestCase):
    """19/11 (H66): o stop móvel não pode sair num preço que já tinha passado — sai na abertura se o minuto anterior fechou abaixo do nível."""

    def test_sai_na_abertura_quando_o_fechamento_ja_passou(self):
        from executor import stop_movel as SM
        p = {"entrada": 100.0, "lado": "compra"}
        m = [(0, 102.0, 100.0, 100.4), (60_000, 100.5, 100.2, 100.3)]     # pico +2% (nível +1,4%), mas fechou a +0,4%
        r = SM.conferir(p, m, 0.03, 10**9, 0)
        self.assertAlmostEqual(r[0], 100.4)                              # sai no fechamento anterior, não a 101,4
        p = {"entrada": 100.0, "lado": "compra"}
        m = [(0, 102.0, 100.0, 101.9), (60_000, 101.9, 101.0, 101.2)]
        self.assertAlmostEqual(SM.conferir(p, m, 0.03, 10**9, 0)[0], 101.4)   # fechamento acima do nível: sai no nível


class AlvoMaior(unittest.TestCase):
    """Dono (19/11): alvos maiores; com alvo, o stop móvel só arma na metade do caminho até ele."""

    def test_movel_nao_corta_antes_da_metade_do_alvo(self):
        from executor import stop_movel as SM
        self.assertEqual((SM.armar_em(None), SM.armar_em(0.006), SM.armar_em(0.03)), (0.005, 0.005, 0.015))
        p = {"entrada": 100.0, "lado": "compra"}
        m = [(0, 101.0, 100.0, 100.9), (60_000, 100.9, 100.6, 100.7)]          # pico +1% e devolve: sem alvo, o móvel fecha
        self.assertIsNotNone(SM.conferir(dict(p), m, 0.01, 10**9, 0))
        self.assertIsNone(SM.conferir(dict(p), m, 0.01, 10**9, 0, alvo_pct=0.03))   # alvo 3%: o móvel só arma a +1,5%


class GatilhosH67(unittest.TestCase):
    """H67 (19/11): o agente arma níveis; a nuvem entra no minuto em que o preço cruza, sem esperar a próxima rodada do agente."""

    def _base(self):
        agora = 1795000000.0
        k = [[int(agora * 1000) - 900_000 * (100 - i), "1", "1", "1", "1.0"] for i in range(100)]
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "licoes": []}
        d = {"t": agora - 5, "posicoes": [], "gatilhos": [
            {"moeda": "AUSDT", "lado": "compra", "acima": 1.02, "stop_pct": 0.01, "alvo_pct": 0.03, "motivo": "rompimento"},
            {"moeda": "AUSDT", "lado": "venda", "abaixo": 1.05, "motivo": "já passou"}]}
        return agora, k, e, d

    def test_arma_dispara_no_nivel_e_valida(self):
        from executor import robo_claude_nuvem as R
        agora, k, e, d = self._base()
        R.passo(e, d, {"AUSDT": k}, agora, vivos={"AUSDT": 1.0})
        self.assertEqual([g["tipo"] for g in e["gatilhos"]], ["acima"])           # o "abaixo de 1,05" já tinha passado: não arma
        t0 = int((agora - 5) * 1000)
        mins = {"AUSDT": [(t0 + 60_000, 1.01, 0.99, 1.005), (t0 + 120_000, 1.03, 1.00, 1.025)]}
        R.passo(e, d, {"AUSDT": k}, agora + 180, vivos={"AUSDT": 1.025}, minutos_gatilho=mins)
        a = e["abertas"]["AUSDT"]
        self.assertAlmostEqual(a["entrada"], 1.02)
        self.assertEqual((a["stop_pct"], a["alvo_pct"]), (0.01, 0.03))
        self.assertEqual(e["gatilhos"], [])
        self.assertEqual(R.validar_gatilhos([{"moeda": "AUSDT", "lado": "compra", "motivo": "x"}]),
                         ["AUSDT: o gatilho precisa de UM nível, 'acima' ou 'abaixo', com preço > 0"])
        self.assertTrue(R.validar_gatilhos([{"moeda": "AUSDT", "lado": "compra", "acima": 1, "motivo": "x", "validade_min": 999}]))

    def test_sem_olhar_futuro_e_vencimento(self):
        from executor import robo_claude_nuvem as R
        g = {"tipo": "acima", "nivel": 1.02, "desde_ms": 1000}
        self.assertEqual(R.disparou(g, [(1000, 1.01, 1.0, 1.04), (61_000, 1.05, 1.03, 1.04)]), (1.04, 61_000))   # o fechamento anterior já passou: entra nele
        agora, k, e, d = self._base()
        R.passo(e, d, {"AUSDT": k}, agora, vivos={"AUSDT": 1.0})
        R.passo(e, d, {"AUSDT": k}, agora + 3 * 3600, vivos={"AUSDT": 1.0}, minutos_gatilho={})
        self.assertEqual(e["gatilhos"], [])                                       # validade padrão de 120 min
        self.assertEqual(e["abertas"], {})


class TamanhoH64(unittest.TestCase):
    """H64 (18/11, aprovada no lab/colher_balde.py): a fatia de cada entrada cresce com o ganho e encolhe na perda."""

    def test_fator_cresce_e_encolhe(self):
        from executor import robo_claude_nuvem as R
        self.assertEqual(R.tamanho(10.0), (25.0, 10))               # carteira inicial: igual à H58
        noc, a = R.tamanho(12.0)
        self.assertAlmostEqual(noc, 36.0)                           # 3,0 × 12
        self.assertEqual(a, 20)
        self.assertAlmostEqual(R.tamanho(8.0)[0], 16.0)             # 2,0 × 8
        self.assertEqual(R.tamanho(40.0), (200.0, 20))              # teto 5×
        self.assertAlmostEqual(R.tamanho(4.0)[0], 5.0)              # piso 1,25×

    def test_h73_dobra_a_posicao_das_carteiras_simuladas(self):
        """H73 (22/11, dono: "pode aumentar o tamanho da perda também"): 5 × a carteira a 20× na nuvem; a conta de teste fica na H64."""
        from executor import robo_claude_nuvem as R
        self.assertEqual(R.tamanho(10.0, R.FATOR_H73), (50.0, 20))
        self.assertEqual(R.tamanho(8.0, R.FATOR_H73), (40.0, 20))
        self.assertEqual(R.tamanho(10.0), (25.0, 10))               # sem fator_fixo: H64, usado pelo testnet

    def test_quatro_margens_cabem_e_perda_para_na_margem(self):
        from executor import robo_claude_nuvem as R
        agora = 1795000000.0
        k = [[int(agora * 1000) - 900_000 * (100 - i), "1", "1", "1", "1.0"] for i in range(100)]
        e = {"caixa": 14.0, "abertas": {}, "fechadas": [], "licoes": []}
        ps = [{"moeda": m, "lado": "compra", "motivo": "teste"} for m in ("AUSDT", "BUSDT", "CUSDT", "DUSDT")]
        R.passo(e, {"t": agora - 5, "posicoes": ps}, {m["moeda"]: k for m in ps}, agora, vivos={m["moeda"]: 1.0 for m in ps})
        self.assertEqual(len(e["abertas"]), 4)
        a = e["abertas"]["AUSDT"]
        self.assertAlmostEqual(a["nocional"], 5.0 * 14.0 * R.POR_POS)   # H73: 5 × a carteira; R2: metade por posição (até 8)
        self.assertEqual(a["alav"], 20)
        self.assertGreaterEqual(e["caixa"], -1e-9)
        R.fechar(e, "AUSDT", a, 0.5, "teste", agora + 60)            # −50% a 20×: perde só a margem
        self.assertAlmostEqual(e["fechadas"][-1]["resultado_usd"], -a["gasto"])


class CarteirasTopH63(unittest.TestCase):
    """H63 (18/11): raspagem das melhores carteiras da Hyperliquid; abertura nova vira evento resolvido em 60–75 min."""

    def test_filtro_fixo(self):
        from executor import carteiras_nuvem as C
        w = lambda m, s, a, roi=0.2, vlm=2e6: [["day", {"pnl": "1"}], ["week", {"pnl": s, "roi": "0.1"}], ["month", {"pnl": m, "roi": str(roi), "vlm": str(vlm)}],
                                              ["allTime", {"pnl": a}]]
        linhas = [{"ethAddress": "0xa", "accountValue": "100000", "windowPerformances": w("10", "1", "5")},
                  {"ethAddress": "0xb", "accountValue": "100000", "windowPerformances": w("10", "-1", "5")},          # semana no prejuízo
                  {"ethAddress": "0xc", "accountValue": "10000", "windowPerformances": w("10", "1", "5")},           # conta pequena
                  {"ethAddress": "0xd", "accountValue": "100000", "windowPerformances": w("10", "1", "5", vlm=5e5)}]  # giro 5× < 10×
        self.assertEqual([c["endereco"] for c in C.selecionar(linhas)], ["0xa"])
        self.assertEqual((C.par_binance("kPEPE"), C.par_binance("BTC"), C.par_binance("xyz:TSLA")), ("PEPEUSDT", "BTCUSDT", None))

    def test_feed_e_juiz(self):
        from executor import carteiras_nuvem as C
        antes = {"0x1": {"BTC": {"lado": "venda", "valor_usd": 100, "entrada": 1, "alavancagem": 5}}}
        agora = {"0x1": {"ETH": {"lado": "compra", "valor_usd": 50, "entrada": 2, "alavancagem": 3}}, "0x2": {"SOL": {"lado": "compra", "valor_usd": 9}}}
        ev = C.diferencas(antes, agora, {"ETH": "2000", "BTC": "60000"}, 1000)
        self.assertEqual(sorted((x["tipo"], x["coin"]) for x in ev), [("abriu", "ETH"), ("fechou", "BTC")])   # 0x2 é nova na lista: não conta
        ev = C.resolver(ev, {"ETH": "2020"}, 1000 + 3700)
        r = [x for x in ev if x["tipo"] == "abriu"][0]
        self.assertAlmostEqual(r["resultado"], 0.01 - 0.0012, places=6)
        ev2 = C.resolver([{"t": 0, "tipo": "abriu", "coin": "X", "lado": "compra", "px": 1.0}], {"X": "1"}, 5000)
        self.assertTrue(ev2[0].get("descartado"))                                                              # janela perdida
        self.assertEqual(C.avaliar(ev)["n"], 1)


class CacadorH68(unittest.TestCase):
    """H68 (19/11): o Caçador varre o universo na nuvem; juiz 15/60 min com controle aleatório; nada olha o futuro."""

    @staticmethod
    def _k1m(n=160, explode=0.0, vol_fim=1.0, t0=1_795_000_000_000):
        k, px = [], 100.0
        for i in range(n):
            px *= 1 + (0.0005 if i % 2 else -0.0005)
            if i == n - 1:
                px *= 1 + explode
            v = 1000.0 * (vol_fim if i == n - 1 else 1.0)
            k.append([t0 + 60_000 * i, px, px * 1.001, px * 0.999, px, 0, t0 + 60_000 * i + 59_999, v])
        return k

    def test_explosao_de_1_min_com_volume(self):
        from executor import cacador_nuvem as C
        s, zmax, _ = C.sinais_1m(self._k1m(explode=0.01, vol_fim=10))
        e1 = [x for x in s if x["tipo"] == "explosao_1m"]
        self.assertEqual(len(e1), 1)
        self.assertEqual(e1[0]["lado"], "compra")
        self.assertGreater(zmax, 3)
        self.assertEqual(C.sinais_1m(self._k1m(explode=0.01, vol_fim=1))[0], [])          # sem volume não é explosão
        self.assertEqual(C.sinais_1m(self._k1m())[0], [])                                 # ruído normal: nada

    def test_rompimento_de_24h_e_sugestao_com_alvo_3x_stop(self):
        from executor import cacador_nuvem as C
        k15 = [[i, 1.0, 1.01, 0.99, 1.0, 0, i, 1] for i in range(100)]
        s, _ = C.sinais_grafico(1.02, k15, k15)
        r = [x for x in s if x["tipo"] == "rompimento_24h"][0]
        self.assertEqual((r["lado"], r["invalidacao"]), ("compra", 1.01))
        sg = C.sugestao(1.02, "compra", 1.01, "24h")
        self.assertGreaterEqual(sg["alvo_pct"] + 1e-9, max(0.01, 3 * sg["stop_pct"]))
        self.assertEqual(sg["max_min"], 120)                                 # REGRAS §5: alvo de 2,94% → 120 min
        self.assertEqual(C.sugestao(1.0, "compra", 0.997, "1m")["max_min"], 60)   # stop 0,3% → alvo 1% → 60 min

    def test_juiz_resolve_no_minuto_certo_com_controle_e_sem_repetir(self):
        import random as rnd
        from executor import cacador_nuvem as C
        tm = 1_795_000_020_000 - 1_795_000_020_000 % 60_000
        lidas = {"AUSDT": (1.0, tm), "BUSDT": (2.0, tm)}
        e = {}
        op = {"par": "AUSDT", "tipo": "explosao_1m", "lado": "compra", "forca": 90}
        C.registrar(e, [op], tm / 1000, lidas, rnd.Random(1))
        self.assertEqual([x["tipo"] for x in e["pendentes"]], ["explosao_1m", "controle"])
        C.registrar(e, [op], tm / 1000 + 600, lidas, rnd.Random(1))
        self.assertEqual(len(e["pendentes"]), 2)                                          # mesmo sinal em 30 min não repete
        pedidos = []

        def preco_em(par, t):
            pedidos.append((par, t))
            return 1.01 if par == "AUSDT" else 2.0
        C.resolver(e, preco_em, tm + 10 * 60_000)
        self.assertEqual(pedidos, [])                                                     # 15 min ainda não fecharam: nada resolvido
        C.resolver(e, preco_em, tm + 15 * 60_000)
        self.assertIn(("AUSDT", tm + 14 * 60_000), pedidos)                               # o minuto que FECHA 15 min depois da entrada
        a = [x for x in e["pendentes"] if x["tipo"] == "explosao_1m"][0]
        self.assertAlmostEqual(a["r15"], 0.01 - 0.0012)
        self.assertNotIn("r60", a)
        C.resolver(e, preco_em, tm + 60 * 60_000)
        self.assertEqual(e["pendentes"], [])
        self.assertEqual(e["placar"]["explosao_1m"]["15"][str(tm // 3_600_000)][0], 1)

    def test_avaliar_controle_aleatorio_da_o_custo_e_valida_o_juiz(self):
        """Controle: entradas sorteadas num passeio aleatório têm de dar ≈ −0,12%; o juiz só vale assim."""
        import random as rnd
        from executor import cacador_nuvem as C
        r = rnd.Random(7)
        placar = {}
        for i in range(3000):
            tm = (i // 10) * 3_600_000
            C.somar(placar, "controle", 15, tm, r.gauss(0, 0.004) - C.CUSTO)
            C.somar(placar, "explosao_1m", 15, tm, r.gauss(0, 0.004) - C.CUSTO)
        j = C.avaliar(placar)
        self.assertTrue(j["controle"]["15"]["controle_ok"])
        self.assertAlmostEqual(j["controle"]["15"]["media_pct"], -0.12, delta=3 * j["controle"]["15"]["ep_pct"])
        self.assertFalse(j["explosao_1m"]["15"]["passa"])                                 # sem vantagem não passa
        placar["controle"]["15"] = {"0": [400, 0.4, 300]}                                  # controle com +0,1%: simulador errado
        self.assertFalse(C.avaliar(placar)["explosao_1m"]["15"]["controle_ok"])

    def test_universo_dex_e_listagem(self):
        from executor import cacador_nuvem as C
        tk = [{"symbol": s, "quoteVolume": v} for s, v in (("PEPEUSDT", 9e6), ("BTCUSDT", 1e9), ("USDCUSDT", 1e9), ("XUSDT", 1e3), ("NVDABUSDT", 9e6))]
        self.assertEqual(C.filtrar([x["symbol"] for x in tk], tk), ["PEPEUSDT", "BTCUSDT"])   # memecoin primeiro; sem estável, morta e ação
        self.assertEqual(C.novas_listagens([], ["AUSDT"], 0, []), [])                       # 1ª leitura só guarda a lista
        self.assertEqual([x["par"] for x in C.novas_listagens(["AUSDT"], ["AUSDT", "NOVAUSDT"], 10, [])], ["NOVAUSDT"])
        ag = 10 ** 12
        bom = {"liquidez": 80_000, "criado_ms": ag - 3_600_000, "compras_1h": 50, "vendas_1h": 40, "volume_1h": 90_000}
        self.assertEqual(len(C.dex_filtrar([bom, {**bom, "vendas_1h": 0}, {**bom, "criado_ms": ag - 60_000}], ag)), 1)   # sem venda / nova demais: fora

    def test_agente_entra_em_moeda_fora_das_velas_com_preco_da_rodada(self):
        from executor import robo_claude_nuvem as R
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "licoes": []}
        d = {"t": 1795000000.0 - 5, "posicoes": [{"moeda": "NOVAUSDT", "lado": "compra", "motivo": "aviso do Caçador", "stop_pct": 0.01}]}
        R.passo(e, d, {}, 1795000000.0, vivos={"NOVAUSDT": 2.5})
        self.assertEqual(e["abertas"]["NOVAUSDT"]["entrada"], 2.5)


class UniversoComPrazo(unittest.TestCase):
    """Auditoria 19/11 (A16): a raspagem do chefe (mesa/chefe/universo.py) levou 27 min; agora tem prazo total e devolve o que leu como parcial."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("universo_chefe", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "chefe" / "universo.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_leitura_para_no_prazo_e_devolve_o_que_terminou(self):
        import time
        U = self._mod()

        def ler(par):
            time.sleep(3 if par == "LENTAUSDT" else 0.01)
            return par, [1]
        t0 = time.time()
        k, faltaram = U.ler_com_prazo(ler, ["AUSDT", "BUSDT", "LENTAUSDT"], 0.5)
        self.assertLess(time.time() - t0, 1.5)                              # não espera a lenta
        self.assertEqual(sorted(k), ["AUSDT", "BUSDT"])
        self.assertEqual(faltaram, ["LENTAUSDT"])
        v, estourou = U.com_prazo(lambda: time.sleep(3) or "x", 0.3, [])
        self.assertEqual((v, estourou), ([], True))
        self.assertEqual(U.com_prazo(lambda: "ok", 2, None), ("ok", False))
        self.assertEqual(U.PRAZO_S, 360.0)


class CloneDoChefeQuebrado(unittest.TestCase):
    """Auditoria 19/11 (A5): o clone do ramo `estado` do chefe ficou corrompido depois de um desligamento e toda rodada falhava.
    mesa/chefe/ler.py guarda o clone quebrado de lado e clona de novo; com o clone bom e sem rede, só para com o erro."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ler_chefe", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "chefe" / "ler.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def setUp(self):
        import subprocess
        import tempfile
        self.d = pathlib.Path(tempfile.mkdtemp())
        run = lambda *a, c=None: subprocess.run(["git", *(["-C", str(c)] if c else []), *a], check=True, capture_output=True)
        org = self.d / "org"
        run("init", "-q", "-b", "estado", str(org))
        (org / "dados").mkdir()
        (org / "dados" / "x.json").write_text("{}")
        run("add", ".", c=org)
        run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x", c=org)
        self.remoto = str(org)

    def test_clone_corrompido_e_refeito_e_o_quebrado_fica_guardado(self):
        U = self._mod()
        U.EST, U.REMOTO = self.d / "estado", "file://" + self.remoto
        (U.EST / ".git").mkdir(parents=True)
        (U.EST / ".git" / "HEAD").write_text("")                       # cortado pelo desligamento
        rev, _ = U.atualizar()
        self.assertTrue(rev)
        self.assertTrue((U.EST / "dados" / "x.json").exists())
        self.assertTrue(any(p.name.startswith("estado.corrompido-") for p in self.d.iterdir()))

    def test_sem_rede_com_clone_bom_nao_mexe_no_clone(self):
        import subprocess
        U = self._mod()
        U.EST = self.d / "estado"
        subprocess.run(["git", "clone", "-q", "--branch", "estado", "file://" + self.remoto, str(U.EST)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(U.EST), "remote", "set-url", "origin", str(self.d / "nao-existe")], check=True)
        with self.assertRaises(RuntimeError):
            U.atualizar()
        self.assertTrue((U.EST / "dados" / "x.json").exists())
        self.assertFalse(any(p.name.startswith("estado.corrompido-") for p in self.d.iterdir()))


class CloneDoAgenteSemRede(unittest.TestCase):
    """Auditoria 24/11: em mesa/operar/operar.py, "fatal: unable to access" (rede caída) era tratado como clone corrompido: o clone bom
    do Treinador ia para o lado (treinador.corrompido-1795550934, git fsck limpo) e a rodada clonava de novo pela rede ruim."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("operar_mesa", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "operar.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def setUp(self):
        import subprocess
        import tempfile
        self.d = pathlib.Path(tempfile.mkdtemp())
        run = lambda *a, c=None: subprocess.run(["git", *(["-C", str(c)] if c else []), *a], check=True, capture_output=True)
        org = self.d / "org"
        run("init", "-q", "-b", "estado", str(org))
        (org / "dados").mkdir()
        (org / "dados" / "x.json").write_text("{}")
        run("add", ".", c=org)
        run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x", c=org)
        self.remoto = "file://" + str(org)
        self.c = self.d / "clones" / "treinador"
        run("clone", "-q", "--branch", "estado", self.remoto, str(self.c))

    def test_sem_rede_com_clone_bom_nao_mexe_no_clone(self):
        import subprocess
        U = self._mod()
        U.AQUI, U.REMOTO = self.d, str(self.d / "nao-existe")         # sem rede: nem o fetch nem um clone novo alcançam o remoto
        subprocess.run(["git", "-C", str(self.c), "remote", "set-url", "origin", str(self.d / "nao-existe")], check=True)
        with self.assertRaises(subprocess.CalledProcessError):
            U.atualizar(self.c)
        self.assertTrue((self.c / "dados" / "x.json").exists())
        self.assertFalse(any(".corrompido-" in p.name for p in (self.d / "clones").iterdir()))

    def test_clone_corrompido_ainda_e_refeito(self):
        U = self._mod()
        U.AQUI, U.REMOTO = self.d, self.remoto
        (self.c / ".git" / "HEAD").write_text("")                       # cortado pelo desligamento
        U.atualizar(self.c)
        self.assertTrue((self.c / "dados" / "x.json").exists())
        self.assertTrue(any(".corrompido-" in p.name for p in (self.d / "clones").iterdir()))


class RegrasFonteUnica(unittest.TestCase):
    """REGRAS.md (19/11, pedido do dono: "conflitos de regras"): o texto único bate com o que a execução impõe, e gravar corta igual."""

    def _regras(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("regras_mesa", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "regras.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_texto_bate_com_o_codigo(self):
        from executor import robo_claude_nuvem as R, stop_movel as SM
        txt = (pathlib.Path(__file__).resolve().parent.parent / "mesa" / "REGRAS.md").read_text()
        self.assertEqual(R.LIMITES["stop_pct"], (0.003, 0.04))
        self.assertIn("stop: 0,3% a 4%", txt)
        self.assertEqual((R.ALVO_X_STOP, R.ALVO_MIN, R.LIMITES["alvo_pct"][1]), (None, None, 0.50))
        self.assertIn("alvo: opcional, 0,2% a 50%", txt)
        self.assertEqual((SM.armar_em(0.03), SM.armar_em(None), SM.GUARDA), (0.015, 0.005, 0.70))
        self.assertEqual(SM.armar_em(0.03, False), float("inf"))
        self.assertIn("máx(0,5%, alvo ÷ 2)", txt)
        self.assertEqual(R.parametros({"stop_pct": 0.02, "alvo_pct": 0.01})["alvo_pct"], 0.01)       # R2: o alvo pedido vale
        G = self._regras()
        self.assertIsNone(G.ESTICADA_4H)
        self.assertIn("R2", txt)

    def test_cortes_duros_so_em_entrada_nova(self):
        G = self._regras()
        var = [{"par": "AUSDT", "var": {"4h": -16.0}, "padroes": []},
               {"par": "BUSDT", "var": {"4h": 1.0}, "padroes": [{"tempo": "1h", "padrao": "topo duplo", "sentido": "baixa", "confirmado": True}]}]
        pos = [{"moeda": "AUSDT", "lado": "venda", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 120},
               {"moeda": "BUSDT", "lado": "compra", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 120},
               {"moeda": "DUSDT", "lado": "compra", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 30}]
        erros = G.conferir_decisao(pos, {}, var)
        self.assertEqual(erros, [])                                                     # R2 (23/11): C2 e C3 não cortam mais
        self.assertTrue(G.conferir_decisao([{"moeda": "EUSDT", "lado": "compra"}], {}, var))   # sem stop: recusa
        self.assertTrue(G.cortes_duros("compra", 60, None))                             # C1 continua
        self.assertEqual(G.conferir_decisao(pos[:1], {"AUSDT": {}}, var), [])           # já aberta: não corta
        self.assertEqual([G.prazo_sugerido(a) for a in (0.01, 0.02, 0.04)], [60, 120, 240])


class UniversoSemErroEngolido(unittest.TestCase):
    """19/11 ~21:50 UTC: a raspagem do chefe deu "0 de 116 moedas" sem causa (velas() engolia o erro). Agora tenta de novo e diz o motivo."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("universo_chefe2", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "chefe" / "universo.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_tenta_de_novo_e_registra_o_motivo(self):
        import urllib.error
        U = self._mod()
        chamadas = {"n": 0}

        def falha_uma_vez(url, t=30):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise TimeoutError("rede lenta")
            return [[0, 1, 1, 1, 1, 0, 0]] * 98
        with unittest.mock.patch.object(U, "_get", falha_uma_vez), unittest.mock.patch.object(U.time, "sleep", lambda s: None):
            par, k = U.velas("AUSDT")
        self.assertEqual((par, len(k), chamadas["n"]), ("AUSDT", 98, 2))       # a 2ª tentativa leu
        self.assertNotIn("AUSDT", U.FALHAS)

        def limite(url, t=30):
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        with unittest.mock.patch.object(U, "_get", limite), unittest.mock.patch.object(U.time, "sleep", lambda s: None):
            self.assertEqual(U.velas("BUSDT")[1], [])
        self.assertEqual(U.FALHAS["BUSDT"], "HTTP 429")
        self.assertEqual(U.resumo_falhas(["CUSDT"], ["BUSDT", "CUSDT"]), "1 × HTTP 429, 1 × prazo da rodada")   # a causa aparece no ERRO
        self.assertGreaterEqual(U.VELAS_MIN_S, 120)


class CorretoraDemoH71(unittest.TestCase):
    """H71 (20/11): cada operador na própria conta de demonstração. Corretora falsa: nada sai da máquina."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("corretora_mesa", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "corretora.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def _falsa(self, M, recusa_stop=False):
        class Falsa:
            NOME, BASE, VALIDADO = "falsa", "x", True

            def __init__(s):
                s.px, s.pos, s.gat, s.ex, s.n = {"AUSDT": 100.0, "BUSDT": 50.0}, {}, {}, [], 0

            def _id(s):
                s.n += 1
                return str(s.n)

            def contrato(s, par):
                return {"mult": 0.01, "minimo": 1, "tick": 0.01, "alav_max": 50, "preco": s.px[par]} if par in s.px else None

            def preco(s, par):
                return s.px[par]

            def alavancagem(s, par, n):
                pass

            def mercado(s, par, lado, q, reduzir=False):
                sinal = 1 if lado == "compra" else -1
                atual = s.pos.get(par, {"contratos": 0})["contratos"] + sinal * q
                s.pos[par] = {"contratos": atual, "entrada": s.px[par], "marca": s.px[par], "pnl": 0.0}
                if not atual:
                    del s.pos[par]
                s.ex.append({"par": par, "t_ms": __import__("time").time() * 1000, "contratos": sinal * q, "preco": s.px[par], "taxa": 0.001})
                return {"id": s._id(), "preco": s.px[par], "contratos": q}

            def gatilho(s, par, lado_pos, q, preco, tipo):
                if recusa_stop and tipo == "stop":
                    raise M.ErroCorretora("recusado")
                i = s._id()
                s.gat[i] = (par, tipo, preco)
                return {"id": i, "preco": round(preco, 2)}

            def cancelar(s, i, par=None):
                s.gat.pop(i, None)

            def gatilhos_abertos(s):
                return {i: g[0] for i, g in s.gat.items()}

            def posicoes(s):
                return dict(s.pos)

            def execucoes(s, par, desde_ms):
                return [x for x in s.ex if x["par"] == par and x["t_ms"] >= desde_ms - 2000]

            def velas_1m(s, par, desde_ms):
                return []
        return Falsa()

    def _conta(self, M, falsa):
        import tempfile
        return M.Conta("laboratorio", falsa, arquivo=pathlib.Path(tempfile.mkdtemp()) / "c.json")

    def test_entra_com_stop_e_alvo_na_corretora_e_fecha_fora_da_lista(self):
        import time
        M = self._mod()
        f = self._falsa(M)
        c = self._conta(M, f)
        d = {"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "teste", "stop_pct": 0.01, "alvo_pct": 0.012, "max_min": 120}]}
        c.rodada(d)
        a = c.e["abertas"]["AUSDT"]
        self.assertEqual(a["alvo_pct"], 0.012)                                   # R2: o alvo do agente
        self.assertEqual(sorted((g[1], g[2]) for g in f.gat.values()), [("alvo", 101.2), ("stop", 99.0)])
        self.assertAlmostEqual(a["nocional"], a["contratos"] * 100 * 0.01)
        self.assertLessEqual(a["nocional"], M.MAX_NOC * M.tamanho(10.0)[0])
        c.rodada({"t": time.time(), "posicoes": []})                              # decisão nova sem a moeda: fecha a mercado
        self.assertEqual(c.e["abertas"], {})
        self.assertEqual(f.gat, {})                                             # stop e alvo cancelados
        self.assertAlmostEqual(c.e["fechadas"][-1]["resultado_usd"], -0.002)     # preço igual: só as taxas da corretora

    def test_stop_recusado_fecha_na_hora(self):
        import time
        M = self._mod()
        f = self._falsa(M, recusa_stop=True)
        c = self._conta(M, f)
        c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "venda", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 60}]})
        self.assertEqual((c.e["abertas"], f.pos), ({}, {}))
        self.assertIn("stop recusado", c.e["fechadas"][-1]["motivo_saida"])

    def test_rede_falha_depois_da_ordem_nao_larga_posicao_sem_stop(self):
        """Auditoria 20/11: a ordem a mercado executou e a leitura das taxas falhou → antes a posição ficava na corretora fora do estado e sem stop."""
        import time
        M = self._mod()
        f = self._falsa(M)
        orig, n = f.execucoes, [0]

        def execucoes(par, desde_ms):
            n[0] += 1
            if n[0] == 1:
                raise M.ErroCorretora("Gate GET /trades: TimeoutError")
            return orig(par, desde_ms)
        f.execucoes = execucoes
        c = self._conta(M, f)
        c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 60}]})
        self.assertIn("AUSDT", c.e["abertas"])                                   # antes: {} com a posição viva na corretora
        self.assertIn(("AUSDT", "stop", 99.0), f.gat.values())
        self.assertIsNone(c.e["abertas"]["AUSDT"]["taxa_entrada"])               # não lida ≠ zero
        c.rodada({"t": time.time(), "posicoes": []})
        self.assertAlmostEqual(c.e["fechadas"][-1]["resultado_usd"], -0.002)     # a taxa de entrada entra na saída

    def test_erro_no_fim_da_rodada_salva_o_estado(self):
        """Auditoria 20/11: o estado só era salvo no fim; erro de rede depois de uma entrada perdia a posição (a próxima rodada a fechava como desconhecida)."""
        import time
        M = self._mod()
        f = self._falsa(M)
        orig, n = f.posicoes, [0]

        def posicoes():
            n[0] += 1
            if n[0] >= 3:                                                        # 1ª conciliar, 2ª piso; a 3ª é a do patrimônio final
                raise M.ErroCorretora("Gate GET /positions: TimeoutError")
            return orig()
        f.posicoes = posicoes
        c = self._conta(M, f)
        with self.assertRaises(M.ErroCorretora):
            c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "venda", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 60}]})
        self.assertIn("AUSDT", M.Conta("laboratorio", f, arquivo=c.arq).e["abertas"])   # antes: arquivo nem existia


    def test_concilia_stop_executado_enquanto_a_maquina_dormia(self):
        import time
        M = self._mod()
        f = self._falsa(M)
        c = self._conta(M, f)
        c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 120}]})
        q = c.e["abertas"]["AUSDT"]["contratos"]
        stop_id = c.e["abertas"]["AUSDT"]["stop"]["id"]
        f.px["AUSDT"] = 99.0                                                    # a corretora executou o stop
        f.gat.pop(stop_id)
        del f.pos["AUSDT"]
        f.ex.append({"par": "AUSDT", "t_ms": time.time() * 1000, "contratos": -q, "preco": 99.0, "taxa": 0.001})
        f.gat["99"] = ("BUSDT", "stop", 1.0)                                    # gatilho desconhecido na conta
        c.conciliar()
        fe = c.e["fechadas"][-1]
        self.assertIn("stop", fe["motivo_saida"])
        self.assertAlmostEqual(fe["resultado_usd"], -1.0 * q * 0.01 - 0.002)
        self.assertNotIn("99", f.gat)                                           # cancelado
        self.assertEqual(f.gat, {})                                             # o alvo da posição fechada também

    def test_prazo_e_seguranca_do_endereco(self):
        import time
        M = self._mod()
        f = self._falsa(M)
        c = self._conta(M, f)
        d = {"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 5}]}
        c.rodada(d)
        c.rodada(d, agora=time.time() + 6 * 60)
        self.assertIn("prazo", c.e["fechadas"][-1]["motivo_saida"])
        with unittest.mock.patch.object(M, "_chave", lambda n: "x"), unittest.mock.patch.object(M.Bybit, "saldo", lambda self: (0.0, 0.0)):
            with self.assertRaises(SystemExit):
                M.conectar("treinador")                                         # Bybit sem saldo de demonstração: PARA sem enviar nada
        with self.assertRaises(SystemExit):
            M.conectar("caçador")
        with unittest.mock.patch.object(M.BingX, "BASE", "https://open-api.bingx.com"):
            with self.assertRaises(SystemExit):
                M.conectar("laboratorio")                                       # endereço real (não o de demonstração): PARA


class MotorDoChefeComRedeFalhando(unittest.TestCase):
    """Auditoria 20/11: mesmos dois defeitos no motor da conta de teste do chefe (mesa/chefe/testnet.py). Corretora falsa: nada sai da máquina."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("testnet_chefe_mesa", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "chefe" / "testnet.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def _falsa(self, T, falhas):
        class Falsa:
            desvio_ms = 0

            def __init__(s):
                s.n = 0

            def regras(s, par):
                return {}

            def alavancagem(s, par, a):
                pass

            def livro(s, par):
                return 100.0, 100.0

            def quantidade(s, par, noc, px):
                return round(noc / px, 3)

            def ordem_mercado(s, par, lado, q, reduce_only=False):
                s.q = q
                return {"orderId": 7}

            def consultar(s, par, oid):
                s.n += 1
                if s.n <= falhas:
                    raise T.ErroFuturos("GET /fapi/v1/order: TimeoutError")
                return {"status": "FILLED", "executada": s.q, "preco_medio": 100.0}
        return Falsa()

    def _e(self):
        return {"caixa": 10.0, "abertas": {}, "fechadas": [], "eventos": []}

    def test_consulta_falha_uma_vez_e_a_posicao_entra_com_stop(self):
        from unittest import mock
        T = self._mod()
        e, f = self._e(), self._falsa(T, falhas=1)
        with mock.patch.object(T.time, "sleep", lambda s: None), \
                mock.patch.object(T, "colocar_stop", lambda f_, par, lado, q, preco, tipo="STOP_MARKET": {"id": tipo, "via": "algo", "preco": round(preco, 2)}):
            T.abrir(f, e, "AUSDT", "compra", "t", 1, {"stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 60})   # antes: ErroFuturos escapava
        self.assertEqual(e["abertas"]["AUSDT"]["stop"]["preco"], 99.0)

    def test_consulta_nunca_responde_avisa_sem_quebrar(self):
        from unittest import mock
        T = self._mod()
        e, f = self._e(), self._falsa(T, falhas=99)
        with mock.patch.object(T.time, "sleep", lambda s: None):
            T.abrir(f, e, "AUSDT", "venda", "t", 1, {"stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 60})
        self.assertEqual((e["abertas"], e["caixa"]), ({}, 10.0))
        self.assertIn("🚨", e["eventos"][0]["texto"])

    def test_erro_no_meio_da_rodada_salva_o_estado(self):
        from unittest import mock
        T = self._mod()
        e, salvos = self._e(), []

        def conciliar(f, e_):
            e_["caixa"] = 9.5                                                      # algo que a rodada já registrou
            raise T.ErroFuturos("GET /fapi/v2/positionRisk: TimeoutError")
        with mock.patch.object(T, "conectar", lambda: None), mock.patch.object(T, "carregar", lambda: e), \
                mock.patch.object(T, "conciliar", conciliar), mock.patch.object(T, "salvar", lambda e_: salvos.append(dict(e_))):
            with self.assertRaises(T.ErroFuturos):
                T.rodada()
        self.assertEqual(salvos[-1]["caixa"], 9.5)                                 # antes: nada salvo


class BybitLiberaComSaldo(unittest.TestCase):
    """20/11: a Bybit Demo libera as ordens sozinha quando o saldo de demonstração for > 0; só api-demo.bybit.com."""

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("corretora_bybit", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "corretora.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_libera_so_com_saldo_e_so_no_endereco_da_demo(self):
        M = self._mod()
        with unittest.mock.patch.object(M, "_chave", lambda n: "x"):
            with unittest.mock.patch.object(M.Bybit, "saldo", lambda self: (500.0, 500.0)):
                self.assertIsInstance(M.conectar("treinador"), M.Bybit)
                with unittest.mock.patch.object(M.Bybit, "BASE", "https://api.bybit.com"):
                    with self.assertRaises(SystemExit):
                        M.conectar("treinador")                                 # conta real: PARA
            def falha(self):
                raise M.ErroCorretora("10003 API key is invalid")
            with unittest.mock.patch.object(M.Bybit, "saldo", falha):
                with self.assertRaises(SystemExit):
                    M.conectar("treinador")                                     # sem conseguir ler o saldo: PARA
            self.assertIsInstance(M.conectar("treinador", permitir_travada=True), M.Bybit)   # --validar só lê
        self.assertEqual(M.BingX.VALIDADO, "saldo")                             # BingX: IP liberado em 20/11, mesma regra de saldo

    def test_ordem_a_mercado_espera_a_execucao(self):
        M = self._mod()
        respostas = [{"orderId": "7"}, {"list": [{"orderStatus": "New", "cumExecQty": "0"}]},
                     {"list": [{"orderStatus": "Filled", "cumExecQty": "0.003", "avgPrice": "62000"}]}]
        with unittest.mock.patch.object(M, "_chave", lambda n: "x"):
            b = M.Bybit()
        with unittest.mock.patch.object(b, "_pedir", lambda *a, **k: respostas.pop(0)), \
                unittest.mock.patch.object(b, "contrato", lambda par: {"mult": 0.001}), unittest.mock.patch.object(M.time, "sleep", lambda s: None):
            o = b.mercado("BTCUSDT", "compra", 3)
        self.assertEqual((o["id"], o["preco"], o["contratos"]), ("7", 62000.0, 3))

    def test_horario_fora_da_janela_tenta_de_novo(self):
        import io
        M = self._mod()
        with unittest.mock.patch.object(M, "_chave", lambda n: "x"):
            b = M.Bybit()
        b.desvio_ms = 0
        corpos = [b'{"retCode": 10002, "retMsg": "invalid request, please check your server timestamp"}', b'{"retCode": 0, "result": {"ok": 1}}']

        class R(io.BytesIO):
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False
        with unittest.mock.patch.object(M.urllib.request, "urlopen", lambda *a, **k: R(corpos.pop(0))), \
                unittest.mock.patch.object(b, "_relogio", lambda: 1):
            self.assertEqual(b._pedir("GET", "/v5/x"), {"ok": 1})
        self.assertEqual(corpos, [])


class SemReentradaESemParametroPadrao(unittest.TestCase):
    """20/11 (rotina do chefe): o stop executou, a moeda seguia na decisão e o testnet.py a REABRIA na mesma rodada, com stop padrão de −3,3% e sem
    alvo nem prazo. Agora: saiu por stop/alvo/prazo depois da decisão = não reentra até decisão nova; sem stop, alvo e prazo na decisão = não entra."""

    def _mod(self, rel, nome):
        import importlib.util
        spec = importlib.util.spec_from_file_location(nome, pathlib.Path(__file__).resolve().parent.parent / "mesa" / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_chefe_nao_reabre_depois_do_stop(self):
        import time
        from unittest import mock
        T = self._mod("chefe/testnet.py", "testnet_reentrada")
        agora = time.time()
        pos = {"moeda": "AUSDT", "lado": "venda", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 120}
        d = {"t": agora - 600, "posicoes": [pos]}
        e = {"caixa": 10.0, "patrimonio": 9.9, "abertas": {"AUSDT": {"moeda": "AUSDT", "lado": "venda", "entrada_t": agora - 500, "gasto": 2.5}}, "fechadas": [], "eventos": []}

        def conciliar(f, e_):                                                    # a corretora executou o stop enquanto a rodada não olhava
            if "AUSDT" not in e_["abertas"]:
                return
            p = e_["abertas"].pop("AUSDT")
            e_["fechadas"].append({**p, "saida_t": agora - 60, "motivo": "stop de segurança −1,00% na corretora"})
            e_["caixa"] += 2.4
        abertos = []
        with mock.patch.object(T, "conectar", lambda: None), mock.patch.object(T, "carregar", lambda: e), mock.patch.object(T, "conciliar", conciliar), \
                mock.patch.object(T, "mover_stops", lambda f, e_: None), mock.patch.object(T, "patrimonio", lambda f, e_: 9.9), \
                mock.patch.object(T.GD, "checar", lambda e_, a: "normal"), mock.patch.object(T, "decisao_do_chefe", lambda: d), \
                mock.patch.object(T, "abrir", lambda *a: abertos.append(a[2])), mock.patch.object(T, "salvar", lambda e_: None), \
                mock.patch.object(T, "publicar", lambda: "x"):
            T.rodada()
            self.assertEqual(abertos, [])                                         # antes: ["AUSDT"]
            d2 = {"t": agora - 5, "leitura_t": agora - 30, "posicoes": [pos]}    # decisão NOVA, lida depois da saída: pode entrar
            with mock.patch.object(T, "decisao_do_chefe", lambda: d2):
                T.rodada()
            self.assertEqual(abertos, ["AUSDT"])

    def test_chefe_nao_abre_sem_parametros_da_decisao(self):
        T = self._mod("chefe/testnet.py", "testnet_param")
        e = {"caixa": 10.0, "abertas": {}, "fechadas": [], "eventos": []}
        T.abrir(None, e, "AUSDT", "compra", "t", 1, {"alvo_pct": 0.03})           # sem stop: nem fala com a corretora
        self.assertEqual(e["abertas"], {})
        self.assertIn("não entra", e["eventos"][0]["texto"])
        self.assertEqual(T.faltam({"stop_pct": 0.01}), [])                          # R2: alvo e prazo opcionais

    def test_operador_nao_reabre_e_nao_entra_sem_parametros(self):
        import time
        M = self._mod("operar/corretora.py", "corretora_reentrada")
        f = CorretoraDemoH71._falsa(None, M)
        c = CorretoraDemoH71._conta(None, M, f)
        pos = {"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.01, "alvo_pct": 0.03, "max_min": 120}
        d = {"t": time.time() - 30, "posicoes": [pos]}
        c.rodada(d)
        q = c.e["abertas"]["AUSDT"]["contratos"]
        f.gat.pop(c.e["abertas"]["AUSDT"]["stop"]["id"])                         # o stop executou na corretora
        del f.pos["AUSDT"]
        f.ex.append({"par": "AUSDT", "t_ms": time.time() * 1000, "contratos": -q, "preco": 99.0, "taxa": 0.001})
        c.rodada(d)
        self.assertEqual(c.e["abertas"], {})                                      # a mesma decisão não reabre
        c.rodada({"t": time.time() + 1, "posicoes": [{"moeda": "BUSDT", "lado": "venda", "motivo": "t", "alvo_pct": 0.03}]})
        self.assertEqual(c.e["abertas"], {})                                      # R2: sem stop não entra
        self.assertIn("não entra", c.e["eventos"][0]["texto"])

    def test_stop_entre_a_leitura_e_a_decisao_nao_reabre(self):
        """20/11 14:21 UTC: o stop de NEAR executou às 14:21:26, depois da leitura (14:20) e antes da decisão (14:23:35); NEAR reabriu."""
        T = self._mod("chefe/testnet.py", "testnet_janela")
        M = self._mod("operar/corretora.py", "corretora_janela")
        e = {"fechadas": [{"moeda": "NEARUSDT", "saida_t": 1795184486, "motivo": "stop de segurança na corretora"},
                          {"moeda": "AUSDT", "saida_t": 1795184486, "motivo": "o chefe inverteu o lado"}]}
        d = {"t": 1795184615, "leitura_t": 1795184400}
        for mod in (T, M):
            self.assertEqual(mod.saidas_desde(e, d), {"NEARUSDT"})            # antes: comparava com t (publicação) e deixava NEAR reabrir
            self.assertEqual(mod.saidas_desde(e, {"t": 1795184615}), {"NEARUSDT"})   # sem leitura_t: decisão − 15 min
            self.assertEqual(mod.saidas_desde(e, {"t": 1795184615 + 1000, "leitura_t": 1795184615 + 900}), set())   # decisão nova: pode entrar



class CerebroAcordaAProxima(unittest.TestCase):
    """23/11 (auditoria): o agendador do GitHub deixou 3h20 e 2h sem rodada do cérebro; a rodada tem de disparar a seguinte."""

    def test_fluxo_dispara_a_propria_rodada_seguinte(self):
        y = (pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/cerebro.yml").read_text()
        self.assertIn("actions: write", y)
        self.assertIn("gh workflow run cerebro.yml", y)
        self.assertIn("!cancelled()", y)                     # rodada cancelada à mão (código novo) não acorda outra
        self.assertIn("cancel-in-progress: false", y)        # a fila segura uma pendente, não derruba a viva


class JuizoH70SemLacoInfinito(unittest.TestCase):
    """23/11: erro de rede permanente deixava baixar() do juiz da H70 em laço infinito (só dormia e tentava de novo)."""

    def test_rede_teimosa_desiste_da_fonte(self):
        import tempfile
        from lab import juizo_h70 as J
        chamadas = []

        def falha(*a, **k):
            chamadas.append(1)
            if len(chamadas) > 50:
                raise AssertionError("laço infinito")
            raise OSError("sem rede")

        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.object(J, "CACHE", pathlib.Path(d)), \
                unittest.mock.patch.object(J.urllib.request, "urlopen", falha), unittest.mock.patch.object(J.time, "sleep", lambda s: None):
            r = J.baixar("XUSDT", 0, 60_000)
        self.assertLessEqual(len(chamadas), 10)
        self.assertIsNotNone(r)


class RotinaCitaARegraEmVigor(unittest.TestCase):
    """Auditoria 24/11: depois da R2 a ROTINA.md dos agentes ainda dizia "versão R1"; a rotina tem de citar a versão em vigor do REGRAS.md."""

    def test_rotina_cita_a_versao_atual(self):
        import re
        from mesa import regras
        raiz = pathlib.Path(__file__).resolve().parent.parent
        rotina = (raiz / "mesa" / "operar" / "ROTINA.md").read_text()
        self.assertIn(f"versão {regras.VERSAO}", (raiz / "mesa" / "REGRAS.md").read_text().splitlines()[0])
        self.assertEqual(set(re.findall(r"versão (R\d+)", rotina)), {regras.VERSAO})


class MesaAoVivo(unittest.TestCase):
    """24/11: o painel mostra a missão, o foco, a rodada (quadro.jsonl) e a carteira única do operador."""

    def test_rodada_e_carteira(self):
        import importlib, importlib.util, json, os, tempfile, time
        raiz = pathlib.Path(tempfile.mkdtemp())
        sh = raiz / "Shared" / "baleias"
        (sh / "operar" / "corretoras").mkdir(parents=True)
        (sh / "equipe").mkdir()
        agora = time.time()
        (sh / "FOCO.json").write_text(json.dumps({"foco": "bingx", "descricao": "equipe na BingX VST"}))
        (sh / "equipe" / "quadro.jsonl").write_text("\n".join(json.dumps(x) for x in [
            {"t": agora - 100, "agente": "cacador", "texto": "3 entradas"}, {"t": agora - 50, "agente": "memecoins", "texto": "PEPE"}]) + "\n")
        (sh / "operar" / "corretoras" / "laboratorio.json").write_text(json.dumps({"corretora": "BingX VST", "patrimonio": 12.5, "capital_inicial": 10,
            "abertas": {"PEPEUSDT": {"lado": "compra", "entrada": 1.0, "entrada_t": agora, "stop": {"id": "1", "preco": 0.98}, "alvo": {"id": "2", "preco": 1.04}}},
            "fechadas": [{"moeda": "DOGEUSDT", "lado": "venda", "resultado_usd": 2.5, "saida_t": agora - 500}], "eventos": [], "atualizado": agora}))
        os.environ["BALEIAS_OPENBOT"] = str(raiz)
        os.environ["BALEIAS_SEM_REDE"] = "1"
        try:
            from baleias import vivo as V
            V = importlib.reload(V)
            d = V.vivo(agora)
        finally:
            del os.environ["BALEIAS_OPENBOT"]
            importlib.reload(V)
        self.assertEqual(d["foco"]["foco"], "bingx")
        self.assertAlmostEqual(d["missao"]["progresso"], 0.25)
        f = {a["id"]: a for a in d["fluxo"]}
        self.assertTrue(f["cacador"]["nesta_rodada"])
        self.assertTrue(f["laboratorio"].get("trabalhando"))                   # a vez é do operador
        self.assertEqual(d["carteira"]["abertas"][0]["stop"], 0.98)
        spec = importlib.util.spec_from_file_location("quadro_t", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "quadro.py")
        Q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(Q)
        Q.ARQ = raiz / "q.jsonl"
        Q.registrar("guardiao", "veto PEPE")
        Q.DESCARTES = raiz / "d.jsonl"
        self.assertEqual(Q.descarte("cacador", "pepeusdt", "Liquidez baixa: US$ 30 mil")["regra"], "liquidez baixa")
        self.assertEqual(Q.ler()[-1]["agente"], "guardiao")
        self.assertEqual(Q.registrar("cacador", "x", conf="media")["conf"], "média")
        with self.assertRaises(SystemExit):
            Q.registrar("cacador", "x", conf="certeza")
        with self.assertRaises(SystemExit):
            Q.registrar("intruso", "x")

class RoboUnico(unittest.TestCase):
    """24/11 (auditoria + livro 151): o robô único impõe os limites; a estratégia só devolve pesos."""

    def _mod(self):
        import importlib.util, tempfile
        spec = importlib.util.spec_from_file_location("robo_unico", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "robo" / "robo.py")
        R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(R)
        R.DADOS = pathlib.Path(tempfile.mkdtemp())
        return R

    def _buscar(self, agora, precos):
        def f(simbolo, tempo, n):
            p = precos[simbolo]
            fim = int(agora // 86400 * 86400 * 1000)          # última vela fechada termina na virada do dia
            return [[fim - (n - i) * 86_400_000, "0", "0", "0", str(p[i] if i < len(p) else p[-1]), "0", fim - (n - i - 1) * 86_400_000 - 1]
                    for i in range(n)]
        return f

    def test_limites(self):
        R = self._mod()
        agora = 1795600000.0
        alta = {s: [100.0 * (1.01 ** i) for i in range(62)] for s in ("BTCUSDT", "ETHUSDT")}
        e = R.passo("ma_5x60", agora, self._buscar(agora, alta))
        self.assertAlmostEqual(sum(abs(v) for v in e["posicoes"].values()), 10.0 * (1 - 0.0006), delta=0.05)   # 1× o patrimônio
        self.assertTrue(all(v > 0 for v in e["posicoes"].values()))                                           # alta: comprado
        n = len(e["eventos"])
        e = R.passo("ma_5x60", agora + 60, self._buscar(agora + 60, alta))
        self.assertEqual(len(e["eventos"]), n)                                                                 # mesmo alvo: nenhuma ordem
        self.assertEqual(R.limitar({"A": 1.0, "B": -1.0}), {"A": 0.5, "B": -0.5})
        e2 = R.passo("ma_5x60", agora + 10 * 86400, self._buscar(agora, alta))                                 # vela velha
        self.assertIn("sem dado bom", e2["eventos"][-1]["texto"])
        queda = {s: v[:-1] + [v[-1] * 0.9] for s, v in alta.items()}                                            # −10% num dia
        e3 = R.passo("ma_5x60", agora + 86400, self._buscar(agora + 86400, queda))
        self.assertTrue(e3["parado"])
        self.assertEqual(e3["posicoes"], {})
        e4 = R.passo("ma_5x60", agora + 2 * 86400, self._buscar(agora + 2 * 86400, alta))                          # parado: não volta sozinho
        self.assertTrue(e4["parado"])
        self.assertEqual(e4["posicoes"], {})


class FocoDaEquipe(unittest.TestCase):
    """24/11 (dono): uma chave central decide onde a equipe opera; sem chave = parado."""

    def test_chave(self):
        import importlib.util, json, os, tempfile
        spec = importlib.util.spec_from_file_location("foco_t", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "foco.py")
        F = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(F)
        F.ARQ = pathlib.Path(tempfile.mkdtemp()) / "FOCO.json"
        self.assertFalse(F.pode_operar("binance")[0])                 # sem arquivo: parado
        F.definir("binance", "teste")
        self.assertTrue(F.pode_operar("binance")[0])
        self.assertFalse(F.pode_operar("bybit")[0])
        F.definir("todas")
        self.assertTrue(F.pode_operar("gate")[0])
        F.definir("parado")
        self.assertFalse(F.pode_operar("gate")[0])
        with self.assertRaises(SystemExit):
            F.definir("binance_real")

    def test_corretora_respeita_o_foco(self):
        import json, os, time
        M = CorretoraDemoH71._mod(None) if hasattr(CorretoraDemoH71, "_mod") else None
        old = os.environ["BALEIAS_FOCO"]
        try:
            arq = pathlib.Path(old).with_name("FOCO_parado.json")
            arq.write_text(json.dumps({"foco": "parado"}))
            os.environ["BALEIAS_FOCO"] = str(arq)
            import importlib.util
            spec = importlib.util.spec_from_file_location("corretora_foco", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "corretora.py")
            M = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(M)
            f = CorretoraDemoH71._falsa(None, M)
            c = CorretoraDemoH71._conta(None, M, f)
            c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.01}]})
            self.assertEqual(c.e["abertas"], {})
            self.assertTrue(any("foco da equipe = parado" in x["texto"] for x in c.e["eventos"]))
        finally:
            os.environ["BALEIAS_FOCO"] = old


class GarantiaDoLucro(unittest.TestCase):
    """25/11 (dono): posição que passou de +2% tem o stop levado à entrada + taxas; não volta a ser perda."""

    def test_stop_vai_para_a_entrada(self):
        import time
        M = CorretoraDemoH71._mod(None) if hasattr(CorretoraDemoH71, "_mod") else None
        import importlib.util
        spec = importlib.util.spec_from_file_location("corretora_garantia", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "corretora.py")
        M = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(M)
        f = CorretoraDemoH71._falsa(None, M)
        c = CorretoraDemoH71._conta(None, M, f)
        c.rodada({"t": time.time() - 5, "posicoes": [{"moeda": "AUSDT", "lado": "compra", "motivo": "t", "stop_pct": 0.015, "alvo_pct": 0.10, "max_min": 240}]})
        p = c.e["abertas"]["AUSDT"]
        f.velas_1m = lambda par, desde: [(int(time.time() * 1000) - 60_000, p["entrada"] * 1.010, p["entrada"])]   # pico +1%: só a garantia
        f.preco = lambda par: p["entrada"] * 1.009
        c.mover_stops()
        self.assertAlmostEqual(c.e["abertas"]["AUSDT"]["stop"]["preco"], p["entrada"] * (1 + M.GARANTIA_PCT), delta=p["entrada"] * 0.0006)
        self.assertEqual(c.e["abertas"]["AUSDT"]["stop_tipo"], "garantia")


class CanalDaEquipe(unittest.TestCase):
    """25/11 (dono): agentes conversam sem conflito — mensagens tipadas, proposta vai ao dono, o motor recusa quem não é dono."""

    def test_canal_e_donos(self):
        import importlib.util, tempfile, time
        raiz = pathlib.Path(tempfile.mkdtemp())
        spec = importlib.util.spec_from_file_location("canal_t", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "canal.py")
        K = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(K)
        K.ARQ = raiz / "canal.jsonl"
        p = K.falar("guardiao", "laboratorio", "proposta", "lados = venda: BTC -1,2% em 30 min")
        self.assertEqual([m["id"] for m in K.pendentes("laboratorio")], [p["id"]])
        K.falar("laboratorio", "guardiao", "resposta", "aceito", ref=p["id"])
        self.assertEqual(K.pendentes("laboratorio"), [])
        with self.assertRaises(SystemExit):
            K.falar("guardiao", "todos", "proposta", "x")                       # proposta vai ao dono, não a todos
        self.assertEqual(len(K.ler("treinador")), 0)
        K.falar("baleias", "todos", "info", "velha", agora=time.time() - 25 * 3600)
        self.assertFalse(any(m["texto"] == "velha" for m in K._ler()))           # 24 h: some
        K.falar("baleias", "todos", "info", "teste")
        self.assertEqual(len(K.ler("treinador")), 1)
        spec = importlib.util.spec_from_file_location("motor_t", pathlib.Path(__file__).resolve().parent.parent / "mesa" / "operar" / "motor.py")
        Mo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(Mo)
        Mo.EQUIPE = raiz
        with self.assertRaises(SystemExit):
            Mo.mudar("lados", "venda", "guardiao", "x")                           # Risco não é dono de 'lados'
        self.assertEqual(Mo.mudar("lados", "venda", "laboratorio", "x")["lados"], "venda")
