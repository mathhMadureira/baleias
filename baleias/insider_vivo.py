"""Compras de diretores ao vivo: lê os formulários 4 novos, registra a previsão antes do resultado e resolve ~1 mês depois."""
import json
from datetime import date, timedelta

from . import alerta, banco, config, insider, precos_acoes, sec
from .aprendizado import aprovado

FONTE = insider.FONTE


def novos_formularios(c, cliente_sec, precos, modelo, hoje=None):
    hoje = hoje or date.today()
    registrados = 0
    for acesso, link in cliente_sec.recentes().items():
        if c.execute("INSERT OR IGNORE INTO sec_vistos VALUES(?, strftime('%s','now')*1000)", (acesso,)).rowcount == 0:
            continue
        c.commit()
        try:
            xml = cliente_sec.formulario(link)
            e = sec.compras_do_xml(xml, hoje.isoformat(), acesso) if xml else None
        except Exception as erro:  # um formulário malformado não pode parar o monitor
            print("formulário ilegível:", acesso, type(erro).__name__, flush=True)
            continue
        if not e or c.execute("SELECT 1 FROM insider_sinais WHERE acesso=?", (acesso,)).fetchone():
            continue
        anteriores = [dict(r) for r in c.execute("SELECT ticker, dono, data FROM insider_sinais WHERE data>=?", ((hoje - timedelta(days=30)).isoformat(),))]
        serie = precos.diario(e["ticker"], hoje - timedelta(days=45), hoje)
        previo = serie[-1][2] / serie[-22][2] - 1 if serie and len(serie) >= 22 else None
        nomes = insider.caracteristicas(e, insider.cluster(e, anteriores), previo)
        resolvidos = c.execute("SELECT COUNT(*) n FROM insider_resultados").fetchone()["n"]
        ok, media, desvio = aprovado(modelo, nomes, resolvidos)
        c.execute("INSERT INTO insider_sinais(acesso,data,ticker,cargo,dono,valor,preco,caracteristicas,previsto,desvio,aprovado,t_ms) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now')*1000)",
                  (acesso, e["data"], e["ticker"], e["cargo"], e["dono"], e["valor"], e["preco"], json.dumps(nomes), media, desvio, int(ok)))
        c.commit()
        registrados += 1
        if ok:
            alerta.enviar(f"🏛️ {e['cargo'].upper()} comprou {e['ticker']}: US$ {e['valor']:,.0f} a ~US$ {e['preco']:.2f}\n"
                          f"Esperado em ~1 mês sobre o S&P, depois do custo: {media:+.2f}% (±{desvio:.2f}), com {resolvidos} compras aprendidas\n"
                          "Teste, não recomendação. Pode perder.")
            c.execute("UPDATE insider_sinais SET alertado=1 WHERE acesso=?", (acesso,))
            c.commit()
    return registrados


def resolver(c, precos, modelo, hoje=None):
    hoje = hoje or date.today()
    pendentes = c.execute("SELECT s.* FROM insider_sinais s LEFT JOIN insider_resultados r ON r.acesso=s.acesso "
                          "WHERE r.acesso IS NULL AND s.data<=?", ((hoje - timedelta(days=33)).isoformat(),)).fetchall()
    feitos = 0
    for s in pendentes:
        inicio = date.fromisoformat(s["data"]) - timedelta(days=5)
        a = insider.avaliar(dict(s), precos.diario(s["ticker"], inicio, hoje), precos.diario("SPY", inicio, hoje))
        if not a:
            continue
        c.execute("INSERT INTO insider_resultados VALUES(?,?,?,?,?,?,?,strftime('%s','now')*1000)",
                  (s["acesso"], a["d_entrada"], a["d_saida"], a["bruto"], a["spy"], a["excesso"], a["r_curto"]))
        modelo.aprender(json.loads(s["caracteristicas"]), a["excesso"] * 100)
        feitos += 1
    if feitos:
        banco.salvar_modelo(c, FONTE, modelo)
        c.commit()
    return feitos


class Rotina:
    """Chamada a cada ciclo do monitor; só age no próprio ritmo (SEC a cada 5 min, resultados a cada hora)."""

    def __init__(self, c):
        self.c, self.modelo, self.ciclo = c, banco.carregar_modelo(c, FONTE), 0
        self.sec = sec.Cliente() if config.SEC_CONTATO else None
        self.precos = precos_acoes.Cliente()

    def rodar(self):
        self.ciclo += 1
        r = {"insider_novos": 0, "insider_resolvidos": 0}
        if self.sec and self.ciclo % 10 == 1:
            self.precos.cache.clear()
            r["insider_novos"] = novos_formularios(self.c, self.sec, self.precos, self.modelo)
        if self.ciclo % 120 == 1:
            r["insider_resolvidos"] = resolver(self.c, self.precos, self.modelo)
            try:
                from lab import ao_vivo
                r["tendencia_dias"] = ao_vivo.atualizar(self.c)
            except Exception as e:
                print("tendência ao vivo falhou:", type(e).__name__, str(e)[:150], flush=True)
        return r
