"""Laço ao vivo: lê operações novas, registra sinais antes de saber o resultado, resolve os vencidos e aprende."""
import json
import time

from . import alerta, banco, config, selecao, sinais as S
from .aprendizado import aprovado, licoes

FONTE = "ao_vivo"


def agora():
    return int(time.time() * 1000)


def atualizar_carteiras(c, cliente, t):
    atuais = c.execute("SELECT carteira FROM carteiras WHERE ativa=1").fetchall()
    faltam = config.CARTEIRAS - len(atuais)
    if faltam <= 0:
        return 0
    conhecidas = {r["carteira"] for r in c.execute("SELECT carteira FROM carteiras")}
    novas = selecao.escolher(cliente, cliente.ranking(), t, faltam, bloqueadas=conhecidas)
    for n in novas:
        c.execute("INSERT INTO carteiras(carteira,conta,nota,ativa,marca_ms,entrou_ms) VALUES(?,?,?,1,?,?)",
                  (n["carteira"], n["conta"], n["nota"], t, t))
    c.commit()
    return len(novas)


def registrar_sinais(c, cliente, modelo, t, perdidos=None):
    perdidos = [] if perdidos is None else perdidos
    precos, novos = None, []
    for w in c.execute("SELECT carteira, marca_ms FROM carteiras WHERE ativa=1").fetchall():
        lote = cliente.operacoes(w["carteira"], w["marca_ms"] - config.JANELA_AGRUPAR_MS * 2, t)
        for f in lote:
            c.execute("INSERT OR IGNORE INTO operacoes VALUES(?,?,?,?,?,?)", (f["tid"], w["carteira"], f["coin"], f.get("dir"), f["time"], json.dumps(f)))
        # Só operações depois da entrada da carteira viram sinal: nada de história disfarçada de ao vivo.
        recentes = [f for f in lote if f["time"] >= w["marca_ms"]]
        for s in S.detectar(recentes, t):
            if t - s["fim"] > config.ATRASO_MAXIMO_MS:
                cur = c.execute("INSERT OR IGNORE INTO perdidos VALUES(?,?,?,?,?)",
                                (f"{w['carteira']}:{s['tids'][0]}", w["carteira"], s["moeda"], s["fim"], t))
                if cur.rowcount:
                    perdidos.append(s)
                continue
            chave = f"{w['carteira']}:{s['tids'][0]}"
            if c.execute("SELECT 1 FROM sinais WHERE fonte=? AND tid_chave=?", (FONTE, chave)).fetchone():
                continue
            precos = precos or cliente.precos()
            px = precos.get(s["moeda"])
            if not px:
                continue
            velas = cliente.velas(s["moeda"], "1m", t - 16 * 60_000, t)
            previo = S.retorno_bruto(s["lado"], float(velas[0]["o"]), px) if velas else None
            uma_h = c.execute("SELECT 1 FROM sinais WHERE fonte=? AND moeda=? AND lado=? AND carteira<>? AND t_sinal_ms>=? LIMIT 1",
                              (FONTE, s["moeda"], s["lado"], w["carteira"], t - 6 * 3_600_000)).fetchone()
            nomes = S.caracteristicas(w["carteira"], s["moeda"], s["lado"], s["tipo"], s["nocional"], bool(uma_h), previo)
            resolvidos = c.execute("SELECT COUNT(*) n FROM resultados r JOIN sinais x ON x.id=r.sinal_id WHERE x.fonte=?", (FONTE,)).fetchone()["n"]
            ok, media, desvio = aprovado(modelo, nomes, resolvidos)
            cur = c.execute("INSERT INTO sinais(fonte,carteira,moeda,lado,tipo,nocional,t_carteira_ms,t_sinal_ms,px_entrada,caracteristicas,previsto,desvio,aprovado,tid_chave) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (FONTE, w["carteira"], s["moeda"], s["lado"], s["tipo"], s["nocional"], s["fim"], t, px, json.dumps(nomes), media, desvio, int(ok), chave))
            c.commit()
            novos.append(cur.lastrowid)
            if ok:
                dados = {"lado": s["lado"], "moeda": s["moeda"], "tipo": s["tipo"], "carteira": w["carteira"], "nocional": s["nocional"], "px": px,
                         "atraso_s": (t - s["fim"]) / 1000}
                alerta.enviar(alerta.texto(dados, media, desvio, resolvidos))
                c.execute("UPDATE sinais SET alertado=1 WHERE id=?", (cur.lastrowid,))
                c.commit()
        if lote:
            # Volta um pouco, porque um grupo ainda aberto só fecha no próximo ciclo; a chave única impede repetição.
            c.execute("UPDATE carteiras SET marca_ms=MAX(marca_ms, ?) WHERE carteira=?", (max(f["time"] for f in lote) - config.JANELA_AGRUPAR_MS * 2, w["carteira"]))
            c.commit()
    return novos


def resolver(c, cliente, modelo, t):
    pendentes = c.execute("SELECT s.* FROM sinais s LEFT JOIN resultados r ON r.sinal_id=s.id WHERE r.sinal_id IS NULL AND s.fonte=? AND s.t_sinal_ms<=?",
                          (FONTE, t - config.HORIZONTES_REGISTRO_MS["4h"] - 60_000)).fetchall()
    feitos = 0
    for s in pendentes:
        inicio, fim = s["t_sinal_ms"], s["t_sinal_ms"] + config.HORIZONTE_MS
        velas = cliente.velas(s["moeda"], "5m", inicio, fim)
        velas = [v for v in velas if v["t"] < fim]
        if not velas:
            continue
        saida = float(velas[-1]["c"])
        entrada = s["px_entrada"]
        bruto = S.retorno_bruto(s["lado"], entrada, saida)
        liquido = S.retorno_liquido(s["lado"], s["moeda"], entrada, saida)
        controle = S.retorno_liquido(S.lado_controle(s["tid_chave"]), s["moeda"], entrada, saida)
        melhor, pior = S.extremos(s["lado"], entrada, velas)
        fecha = "Close Long" if s["lado"] == "long" else "Close Short"
        saiu = c.execute("SELECT 1 FROM operacoes WHERE carteira=? AND moeda=? AND dir=? AND t_ms BETWEEN ? AND ? LIMIT 1",
                         (s["carteira"], s["moeda"], fecha, inicio, fim)).fetchone() is not None
        nomes = json.loads(s["caracteristicas"])
        previo_nome = next((n for n in nomes if n.startswith("previo:")), "")
        previo = 0.01 if previo_nome == "previo:ja_subiu_a_favor" else None
        classe = S.classificar_erro(bruto, liquido, melhor, pior, previo, saiu)
        uma_h = [v for v in velas if v["t"] < inicio + 3_600_000]
        r1 = S.retorno_liquido(s["lado"], s["moeda"], entrada, float(uma_h[-1]["c"])) if uma_h else None
        c.execute("INSERT INTO resultados(sinal_id,t_resolvido_ms,px_saida,bruto,liquido,controle_liquido,melhor,pior,carteira_saiu,classe,r_1h) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (s["id"], t, saida, bruto, liquido, controle, melhor, pior, int(saiu), classe, r1))
        modelo.aprender(nomes, liquido * 100)
        feitos += 1
    if feitos:
        banco.salvar_modelo(c, FONTE, modelo)
        c.commit()
        registrar_licoes(c, t)
        aposentar(c, modelo, t)
    return feitos


def registrar_licoes(c, t):
    achadas = licoes(banco.linhas_para_licoes(c, FONTE))
    c.execute("DELETE FROM licoes WHERE fonte=?", (FONTE,))
    for l in achadas:
        c.execute("INSERT INTO licoes(fonte,t_ms,caracteristica,efeito,n,media,baixo,alto) VALUES(?,?,?,?,?,?,?,?)",
                  (FONTE, t, l["caracteristica"], l["efeito"], l["n"], l["media"], l["baixo"], l["alto"]))
    c.commit()


def aposentar(c, modelo, t):
    """Carteira cujo peso aprendido é negativo mesmo no melhor caso sai da lista; outra entra no próximo ciclo."""
    for w in c.execute("SELECT carteira FROM carteiras WHERE ativa=1").fetchall():
        p = modelo.peso(f"carteira:{w['carteira']}")
        n = c.execute("SELECT COUNT(*) n FROM resultados r JOIN sinais s ON s.id=r.sinal_id WHERE s.fonte=? AND s.carteira=?", (FONTE, w["carteira"])).fetchone()["n"]
        if p and n >= 15 and p[0] + config.Z_DECISAO * p[1] < 0:
            c.execute("UPDATE carteiras SET ativa=0, motivo_saida=? WHERE carteira=?", (f"peso {p[0]:+.2f}±{p[1]:.2f} após {n} sinais", w["carteira"]))
    c.commit()


def ciclo(c, cliente, modelo):
    t = agora()
    atualizar_carteiras(c, cliente, t)
    perdidos = []
    novos = registrar_sinais(c, cliente, modelo, t, perdidos)
    feitos = resolver(c, cliente, modelo, t)
    return {"novos": len(novos), "resolvidos": feitos, "perdidos_por_atraso": len(perdidos)}


def rodar(c, cliente, uma_vez=False):
    modelo = banco.carregar_modelo(c, FONTE)
    ultimo, ciclos = None, 0
    while True:
        inicio = time.monotonic()
        parede = time.time()
        if ultimo is not None and parede - ultimo > 5 * 60:
            print(time.strftime("%F %T"), f"pausa de {(parede - ultimo) / 60:.0f} min sem ciclo (máquina parada?)", flush=True)
        ultimo = parede
        try:
            r = ciclo(c, cliente, modelo)
            ciclos += 1
            if r["novos"] or r["resolvidos"] or r["perdidos_por_atraso"] or ciclos % 120 == 0:
                print(time.strftime("%F %T"), r, f"ciclo {ciclos}", flush=True)
        except (RuntimeError, OSError, ValueError, KeyError) as e:
            print(time.strftime("%F %T"), "ciclo falhou:", type(e).__name__, str(e)[:200], flush=True)
        if uma_vez:
            return
        time.sleep(max(1, config.INTERVALO_S - (time.monotonic() - inicio)))
