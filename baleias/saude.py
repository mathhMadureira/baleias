"""Sinal de vida de cada serviço: o painel mostra quem parou e há quanto tempo."""
import time

ESQUEMA = "CREATE TABLE IF NOT EXISTS servicos(nome TEXT PRIMARY KEY, t_ms INTEGER, msg TEXT)"


def bater(c, nome, msg=""):
    c.execute(ESQUEMA)
    c.execute("INSERT INTO servicos VALUES(?,?,?) ON CONFLICT(nome) DO UPDATE SET t_ms=excluded.t_ms, msg=excluded.msg",
              (nome, int(time.time() * 1000), str(msg)[:300]))
    c.commit()


def estado(c):
    try:
        agora = time.time() * 1000
        return [{"nome": r["nome"], "segundos": round((agora - r["t_ms"]) / 1000), "msg": r["msg"]} for r in c.execute("SELECT * FROM servicos ORDER BY nome")]
    except Exception:
        return []
