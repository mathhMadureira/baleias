import argparse
import json
import time

from . import api, backtest, banco, config, monitor, selecao
from .aprendizado import licoes, media_ic


def fmt(ic):
    return "sem dados suficientes" if not ic else f"{ic['media']:+.3f}% [{ic['baixo']:+.3f}, {ic['alto']:+.3f}] n={ic['n']}"


def cmd_backtest(a):
    cliente = api.Cliente()
    t = int(time.time() * 1000)
    linhas = cliente.ranking()
    cands = selecao.candidatas(linhas)
    escolhidas = selecao.escolher(cliente, linhas, t, a.carteiras, a.dias)
    print(f"ranking {len(linhas)} | candidatas {len(cands)} | escolhidas {len(escolhidas)}", flush=True)
    r, modelo, info = backtest.rodar(cliente, [e["carteira"] for e in escolhidas], t, a.dias)
    print(json.dumps(info))
    res = backtest.resumo(r)
    for k, v in res.items():
        print(f"{k:28s} {fmt(v)}")
    classes = {}
    for x in r:
        classes[x["classe"]] = classes.get(x["classe"], 0) + 1
    print("classes:", json.dumps(classes, ensure_ascii=False))
    print("lições candidatas:")
    for l in licoes([(x["nomes"], x["liquido"] * 100) for x in r])[:12]:
        nome = l["caracteristica"][:24]
        print(f"  {l['efeito']:6s} {nome:26s} {l['media']:+.3f}% [{l['baixo']:+.3f}, {l['alto']:+.3f}] n={l['n']}")
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    with open(config.RAIZ / "backtest.json", "w") as f:
        json.dump({"t": t, "info": info, "resumo": res}, f, indent=1)


def cmd_insider_backtest(a):
    from datetime import date, timedelta
    from . import insider, precos_acoes, sec
    eventos = []
    for z in a.arquivos:
        eventos += sec.compras_do_dataset(z)
    eventos.sort(key=lambda e: e["data"])
    print(f"compras que passaram no filtro: {len(eventos)} | tickers {len({e['ticker'] for e in eventos})} | de {eventos[0]['data']} a {eventos[-1]['data']}", flush=True)
    inicio = date.fromisoformat(eventos[0]["data"]) - timedelta(days=45)
    linhas, modelo = insider.backtest(eventos, precos_acoes.Cliente(), inicio, date.today())
    print(f"avaliadas (com preço e 21 dias úteis depois): {len(linhas)}")
    pct = lambda ls, k: media_ic([x[k] * 100 for x in ls])
    apr = [x for x in linhas if x["aprovado"]]
    m = len(linhas) // 2
    print("excesso sobre o S&P, depois do custo (%, por compra, ~1 mês):")
    for nome, ls, k in (("todos", linhas, "liquido"), ("aprovados", apr, "liquido"), ("1ª metade", linhas[:m], "liquido"), ("2ª metade", linhas[m:], "liquido")):
        print(f"  {nome:12s} {fmt(pct(ls, k))}")
    print("retorno absoluto depois do custo:", fmt(pct(linhas, "liquido_cru")), "| S&P no mesmo período:", fmt(pct(linhas, "spy")))
    print("lições candidatas:")
    for l in licoes([(x["nomes"], x["liquido"] * 100) for x in linhas])[:10]:
        print(f"  {l['efeito']:6s} {l['caracteristica']:22s} {l['media']:+.3f}% [{l['baixo']:+.3f}, {l['alto']:+.3f}] n={l['n']}")


def cmd_relatorio(a):
    c = banco.abrir()
    fonte = monitor.FONTE
    q = "SELECT s.previsto, s.desvio, s.aprovado, s.alertado, r.liquido, r.controle_liquido, r.classe FROM sinais s JOIN resultados r ON r.sinal_id=s.id WHERE s.fonte=? ORDER BY s.t_sinal_ms"
    linhas = c.execute(q, (fonte,)).fetchall()
    total = c.execute("SELECT COUNT(*) n, MIN(t_sinal_ms) a FROM sinais WHERE fonte=?", (fonte,)).fetchone()
    ativas = c.execute("SELECT COUNT(*) n FROM carteiras WHERE ativa=1").fetchone()["n"]
    print(f"carteiras ativas {ativas} | sinais {total['n']} | resolvidos {len(linhas)}")
    pct = lambda ls, k: media_ic([x[k] * 100 for x in ls])
    apr = [x for x in linhas if x["aprovado"]]
    print("todos      ", fmt(pct(linhas, "liquido")))
    print("controle   ", fmt(pct(linhas, "controle_liquido")))
    print("aprovados  ", fmt(pct(apr, "liquido")))
    m = len(linhas) // 2
    print("1ª metade  ", fmt(pct(linhas[:m], "liquido")))
    print("2ª metade  ", fmt(pct(linhas[m:], "liquido")))
    if len(linhas) >= 2:
        err = [abs(x["previsto"] - x["liquido"] * 100) for x in linhas]
        print(f"erro de previsão (%): 1ª metade {sum(err[:m]) / max(m, 1):.3f} | 2ª metade {sum(err[m:]) / max(len(err) - m, 1):.3f}")
    classes = {}
    for x in linhas:
        classes[x["classe"]] = classes.get(x["classe"], 0) + 1
    print("por que acertou/errou:", json.dumps(classes, ensure_ascii=False))
    print("lições candidatas:")
    for l in c.execute("SELECT * FROM licoes WHERE fonte=? ORDER BY ABS(media) DESC LIMIT 10", (fonte,)):
        print(f"  {l['efeito']:6s} {l['caracteristica'][:30]:32s} {l['media']:+.3f}% [{l['baixo']:+.3f}, {l['alto']:+.3f}] n={l['n']}")
    for w in c.execute("SELECT carteira, motivo_saida FROM carteiras WHERE ativa=0"):
        print("aposentada:", w["carteira"][:10], w["motivo_saida"])


def main():
    p = argparse.ArgumentParser(prog="baleias")
    s = p.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("backtest")
    b.add_argument("--dias", type=int, default=14)
    b.add_argument("--carteiras", type=int, default=config.CARTEIRAS)
    m = s.add_parser("monitor")
    m.add_argument("--uma-vez", action="store_true")
    s.add_parser("relatorio")
    ib = s.add_parser("insider-backtest")
    ib.add_argument("arquivos", nargs="+")
    pn = s.add_parser("painel")
    pn.add_argument("--porta", type=int, default=8787)
    a = p.parse_args()
    if a.cmd == "backtest":
        cmd_backtest(a)
    elif a.cmd == "monitor":
        monitor.rodar(banco.abrir(), api.Cliente(), a.uma_vez)
    elif a.cmd == "insider-backtest":
        cmd_insider_backtest(a)
    elif a.cmd == "painel":
        from . import painel
        painel.servir(a.porta)
    else:
        cmd_relatorio(a)


main()
