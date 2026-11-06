import json
import sqlite3
import time

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS carteiras(
  carteira TEXT PRIMARY KEY, conta REAL, nota REAL, ativa INTEGER DEFAULT 1, marca_ms INTEGER, motivo_saida TEXT, entrou_ms INTEGER);
CREATE TABLE IF NOT EXISTS sinais(
  id INTEGER PRIMARY KEY, fonte TEXT NOT NULL, carteira TEXT NOT NULL, moeda TEXT NOT NULL, lado TEXT NOT NULL, tipo TEXT NOT NULL,
  nocional REAL, t_carteira_ms INTEGER NOT NULL, t_sinal_ms INTEGER NOT NULL, px_entrada REAL, caracteristicas TEXT NOT NULL,
  previsto REAL, desvio REAL, aprovado INTEGER, alertado INTEGER DEFAULT 0, tid_chave TEXT NOT NULL,
  UNIQUE(fonte, tid_chave));
CREATE TABLE IF NOT EXISTS resultados(
  sinal_id INTEGER PRIMARY KEY REFERENCES sinais(id), t_resolvido_ms INTEGER, px_saida REAL, bruto REAL, liquido REAL,
  controle_liquido REAL, melhor REAL, pior REAL, carteira_saiu INTEGER, classe TEXT, r_1h REAL, r_24h REAL);
CREATE TABLE IF NOT EXISTS modelo(fonte TEXT PRIMARY KEY, estado TEXT, atualizado_ms INTEGER);
CREATE TABLE IF NOT EXISTS licoes(
  id INTEGER PRIMARY KEY, fonte TEXT, t_ms INTEGER, caracteristica TEXT, efeito TEXT, n INTEGER, media REAL, baixo REAL, alto REAL);
CREATE TABLE IF NOT EXISTS operacoes(tid INTEGER PRIMARY KEY, carteira TEXT, moeda TEXT, dir TEXT, t_ms INTEGER, dados TEXT);
CREATE TABLE IF NOT EXISTS noticias(
  id INTEGER PRIMARY KEY, sinal_id INTEGER, moeda TEXT, titulo TEXT, fonte TEXT, link TEXT, t_ms INTEGER, UNIQUE(sinal_id, link));
CREATE TABLE IF NOT EXISTS rastros(
  id INTEGER PRIMARY KEY, sinal_id INTEGER NOT NULL, evento TEXT NOT NULL, t_ms INTEGER, tid INTEGER, UNIQUE(sinal_id, tid));
CREATE TABLE IF NOT EXISTS sec_vistos(acesso TEXT PRIMARY KEY, t_ms INTEGER);
CREATE TABLE IF NOT EXISTS insider_sinais(
  acesso TEXT PRIMARY KEY, data TEXT, ticker TEXT, cargo TEXT, dono TEXT, valor REAL, preco REAL, caracteristicas TEXT,
  previsto REAL, desvio REAL, aprovado INTEGER, alertado INTEGER DEFAULT 0, t_ms INTEGER);
CREATE TABLE IF NOT EXISTS insider_resultados(
  acesso TEXT PRIMARY KEY, d_entrada TEXT, d_saida TEXT, bruto REAL, spy REAL, excesso REAL, r_curto REAL, t_ms INTEGER);
CREATE TABLE IF NOT EXISTS previsoes(
  id INTEGER PRIMARY KEY, horizonte INTEGER, t_base_ms INTEGER, px_base REAL, prob_alta REAL, caracteristicas TEXT,
  px_final REAL, subiu INTEGER, acertou INTEGER, UNIQUE(horizonte, t_base_ms));
CREATE TABLE IF NOT EXISTS perdidos(tid_chave TEXT PRIMARY KEY, carteira TEXT, moeda TEXT, t_carteira_ms INTEGER, t_visto_ms INTEGER);
CREATE INDEX IF NOT EXISTS ix_sinais_resolver ON sinais(fonte, t_sinal_ms);
CREATE INDEX IF NOT EXISTS ix_ops ON operacoes(carteira, moeda, t_ms);
"""


def abrir(caminho=None):
    caminho = caminho or config.BANCO
    if str(caminho) != ":memory:":
        config.RAIZ.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(caminho)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(ESQUEMA)
    return c


def salvar_modelo(c, fonte, modelo):
    c.execute("INSERT INTO modelo VALUES(?,?,?) ON CONFLICT(fonte) DO UPDATE SET estado=excluded.estado, atualizado_ms=excluded.atualizado_ms",
              (fonte, modelo.para_json(), int(time.time() * 1000)))


def carregar_modelo(c, fonte):
    from .aprendizado import Modelo
    r = c.execute("SELECT estado FROM modelo WHERE fonte=?", (fonte,)).fetchone()
    return Modelo.de_json(r["estado"]) if r else Modelo()


def linhas_para_licoes(c, fonte):
    q = "SELECT s.caracteristicas, r.liquido FROM sinais s JOIN resultados r ON r.sinal_id=s.id WHERE s.fonte=?"
    return [(json.loads(x["caracteristicas"]), x["liquido"] * 100) for x in c.execute(q, (fonte,))]
