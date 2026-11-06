"""Roda dentro do monitor: uma previsão por horizonte a cada minuto fechado, resolvida quando a vela final fecha."""
import json

from . import banco, previsao as P

FONTE = "previsao_btc"


def _modelos(c):
    r = c.execute("SELECT estado FROM modelo WHERE fonte=?", (FONTE,)).fetchone()
    if not r:
        return {h: P.Logistica() for h in P.HORIZONTES}
    d = json.loads(r["estado"])
    return {int(h): P.Logistica.de_json(v) for h, v in d.items()}


def _salvar(c, modelos):
    estado = json.dumps({str(h): m.para_json() for h, m in modelos.items()})
    c.execute("INSERT INTO modelo VALUES(?,?,strftime('%s','now')*1000) ON CONFLICT(fonte) DO UPDATE SET estado=excluded.estado, atualizado_ms=excluded.atualizado_ms",
              (FONTE, estado))


def ciclo(c, cliente, agora_ms, modelos=None):
    modelos = modelos or _modelos(c)
    velas = cliente.velas(P.MOEDA, "1m", agora_ms - 90 * 60_000, agora_ms)
    fechadas = [v for v in velas if v["T"] < agora_ms]
    if len(fechadas) < 61:
        return {"previstas": 0, "resolvidas": 0}
    por_t = {v["t"]: float(v["c"]) for v in fechadas}
    resolvidas = 0
    for p in c.execute("SELECT * FROM previsoes WHERE subiu IS NULL").fetchall():
        alvo = p["t_base_ms"] + p["horizonte"] * 60_000
        if alvo in por_t:
            subiu = por_t[alvo] > p["px_base"]
            if por_t[alvo] == p["px_base"]:
                c.execute("UPDATE previsoes SET px_final=?, subiu=-1, acertou=-1 WHERE id=?", (por_t[alvo], p["id"]))  # empate: fora da conta
                continue
            acertou = (p["prob_alta"] > 0.5) == subiu
            c.execute("UPDATE previsoes SET px_final=?, subiu=?, acertou=? WHERE id=?", (por_t[alvo], int(subiu), int(acertou), p["id"]))
            modelos[p["horizonte"]].aprender(json.loads(p["caracteristicas"]), subiu)
            resolvidas += 1
        elif agora_ms - alvo > 30 * 60_000:
            c.execute("UPDATE previsoes SET subiu=-2, acertou=-2 WHERE id=?", (p["id"],))  # sem vela: descartada
    ultima = fechadas[-1]
    x = P.caracteristicas([float(v["c"]) for v in fechadas[-61:]], [float(v["v"]) for v in fechadas[-61:]])
    previstas = 0
    for h in P.HORIZONTES:
        cur = c.execute("INSERT OR IGNORE INTO previsoes(horizonte,t_base_ms,px_base,prob_alta,caracteristicas) VALUES(?,?,?,?,?)",
                        (h, ultima["t"], float(ultima["c"]), modelos[h].prob(x), json.dumps(x)))
        previstas += cur.rowcount
    _salvar(c, modelos)
    c.commit()
    return {"previstas": previstas, "resolvidas": resolvidas}


def resumo(c):
    saida = {}
    for h in P.HORIZONTES:
        linhas = c.execute("SELECT acertou, subiu FROM previsoes WHERE horizonte=? AND acertou IN (0,1) ORDER BY t_base_ms", (h,)).fetchall()
        n = len(linhas)
        ac = sum(x["acertou"] for x in linhas)
        altas = sum(x["subiu"] for x in linhas)
        recentes = linhas[-200:]
        saida[h] = {"geral": P.placar(ac, n), "ultimas_200": P.placar(sum(x["acertou"] for x in recentes), len(recentes)),
                    "sempre_alta": P.placar(altas, n), "pendentes": c.execute("SELECT COUNT(*) FROM previsoes WHERE horizonte=? AND subiu IS NULL", (h,)).fetchone()[0]}
    saida["empates"] = {f"{int(p * 100)}%": round(P.empate(p), 4) for p in (0.70, 0.80, 0.85, 0.90, 0.95)}
    return saida
