"""Manchetes recentes por ativo, de feeds RSS gratuitos (Google News). Sem IA: casamento por nome do ativo."""
import email.utils
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from . import config

NOMES = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "HYPE": "hyperliquid", "XRP": "XRP crypto", "DOGE": "dogecoin",
         "xyz:SP500": "S&P 500", "xyz:XYZ100": "Nasdaq 100", "xyz:GOLD": "gold price", "xyz:SILVER": "silver price",
         "xyz:CL": "crude oil", "xyz:BRENTOIL": "brent oil"}


def consulta(moeda):
    if moeda in NOMES:
        return NOMES[moeda]
    if config.e_acao(moeda):
        return f"{moeda.split(':', 1)[1]} stock"
    return f"{moeda} crypto"


def ler_rss(xml_bytes):
    """Itens com título, fonte, link e horário (ms). Ignora o que não tem data válida."""
    saida = []
    for item in ET.fromstring(xml_bytes).iter("item"):
        titulo = (item.findtext("title") or "").strip()
        data = item.findtext("pubDate")
        try:
            t = int(email.utils.parsedate_to_datetime(data).timestamp() * 1000)
        except (TypeError, ValueError):
            continue
        fonte = item.find("source")
        saida.append({"titulo": titulo[:300], "fonte": (fonte.text if fonte is not None else "")[:80],
                      "link": (item.findtext("link") or "")[:500], "t_ms": t})
    return saida


def buscar(moeda, desde_ms, abrir=urllib.request.urlopen):
    q = urllib.parse.quote(consulta(moeda) + " when:1d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        with abrir(url, timeout=20) as r:
            itens = ler_rss(r.read())
    except (OSError, ET.ParseError):
        return None  # desconhecido: falha de rede não pode virar "não teve notícia"
    return sorted([i for i in itens if i["t_ms"] >= desde_ms], key=lambda i: -i["t_ms"])[:8]
