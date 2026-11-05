"""Formulário 4 da SEC: compras de diretores e executivos. Só leitura; a SEC exige contato no cabeçalho e no máximo 10 pedidos/s."""
import csv
import io
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime

from . import config

ATOM = "{http://www.w3.org/2005/Atom}"
CARGOS = ("ceo", "cfo", "presidente", "diretor", "executivo", "dono10")


class Cliente:
    def __init__(self, abrir=urllib.request.urlopen, intervalo=0.2):
        if not config.SEC_CONTATO:
            raise RuntimeError("defina SEC_CONTATO em ~/baleias/.env (a SEC exige contato)")
        self.abrir, self.intervalo, self.ultimo = abrir, intervalo, 0.0

    def obter(self, url, timeout=60):
        espera = self.ultimo + self.intervalo - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        self.ultimo = time.monotonic()
        pedido = urllib.request.Request(url, headers={"User-Agent": f"baleias-monitor {config.SEC_CONTATO}"})
        with self.abrir(pedido, timeout=timeout) as r:
            return r.read()

    def recentes(self, quantidade=100):
        """Últimos formulários 4 publicados: (acesso, cik_emissor, link do índice)."""
        xml = self.obter(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=only&count={quantidade}&output=atom")
        saida = {}
        for e in ET.fromstring(xml).iter(f"{ATOM}entry"):
            link = e.find(f"{ATOM}link").get("href")
            acesso = link.rsplit("/", 1)[-1].replace("-index.htm", "")
            saida[acesso] = link
        return saida

    def formulario(self, link_indice):
        pasta = link_indice.rsplit("/", 1)[0]
        itens = json.loads(self.obter(pasta + "/index.json"))["directory"]["item"]
        xml = next((i["name"] for i in itens if i["name"].endswith(".xml")), None)
        return self.obter(f"{pasta}/{xml}") if xml else None


def _cargo(diretor, executivo, titulo, dono10):
    t = (titulo or "").lower()
    if "chief executive" in t or "ceo" in t.split():
        return "ceo"
    if "chief financial" in t or "cfo" in t.split():
        return "cfo"
    if "president" in t:
        return "presidente"
    if executivo:
        return "executivo"
    if diretor:
        return "diretor"
    if dono10:
        return "dono10"
    return None


def _v(no, caminho):
    x = no.find(caminho)
    return (x.text or "").strip() if x is not None and x.text else ""


def compras_do_xml(xml_bytes, data_publicacao, acesso):
    """Compras no mercado aberto (código P) num formulário 4. Planos automáticos (10b5-1) ficam de fora."""
    raiz = ET.fromstring(xml_bytes)
    if _v(raiz, "aff10b5One") in ("1", "true"):
        return None
    ticker = _v(raiz, "issuer/issuerTradingSymbol").upper()
    rel = raiz.find("reportingOwner/reportingOwnerRelationship")
    sim = lambda k: _v(rel, k) in ("1", "true") if rel is not None else False
    cargo = _cargo(sim("isDirector"), sim("isOfficer"), _v(rel, "officerTitle") if rel is not None else "", sim("isTenPercentOwner"))
    dono = _v(raiz, "reportingOwner/reportingOwnerId/rptOwnerCik")
    valor = 0.0
    precos = []
    for t in raiz.iter("nonDerivativeTransaction"):
        if _v(t, "transactionCoding/transactionCode") != "P" or _v(t, "transactionAmounts/transactionAcquiredDisposedCode/value") != "A":
            continue
        try:
            qtd, px = float(_v(t, "transactionAmounts/transactionShares/value")), float(_v(t, "transactionAmounts/transactionPricePerShare/value"))
        except ValueError:
            continue
        valor += qtd * px
        precos.append(px)
    return _filtrar({"acesso": acesso, "data": data_publicacao, "ticker": ticker, "cargo": cargo, "dono": dono, "valor": valor,
                     "preco": min(precos) if precos else 0.0})


def _filtrar(e):
    ok = (e["cargo"] and e["valor"] >= config.INSIDER_VALOR_MINIMO and e["preco"] >= config.INSIDER_PRECO_MINIMO
          and e["ticker"].isalpha() and 1 <= len(e["ticker"]) <= 5)
    return e if ok else None


def compras_do_dataset(caminho_zip):
    """Mesmo filtro, sobre o arquivo trimestral da SEC (para o backtest)."""
    z = zipfile.ZipFile(caminho_zip)
    ler = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), "utf-8", errors="replace"), delimiter="\t")
    sub = {r["ACCESSION_NUMBER"]: r for r in ler("SUBMISSION.tsv") if r["DOCUMENT_TYPE"] == "4" and r["AFF10B5ONE"] not in ("1", "true")}
    donos = {}
    for r in ler("REPORTINGOWNER.tsv"):
        if r["ACCESSION_NUMBER"] in sub and r["ACCESSION_NUMBER"] not in donos:
            rel = r["RPTOWNER_RELATIONSHIP"]
            donos[r["ACCESSION_NUMBER"]] = (r["RPTOWNERCIK"], _cargo("Director" in rel, "Officer" in rel, r["RPTOWNER_TITLE"], "TenPercentOwner" in rel))
    soma = {}
    for r in ler("NONDERIV_TRANS.tsv"):
        a = r["ACCESSION_NUMBER"]
        if a not in sub or r["TRANS_CODE"] != "P" or r["TRANS_ACQUIRED_DISP_CD"] != "A":
            continue
        try:
            q, p = float(r["TRANS_SHARES"]), float(r["TRANS_PRICEPERSHARE"])
        except ValueError:
            continue
        v = soma.setdefault(a, [0.0, []])
        v[0] += q * p
        v[1].append(p)
    saida = []
    for a, (valor, precos) in soma.items():
        s = sub[a]
        dono, cargo = donos.get(a, ("", None))
        e = _filtrar({"acesso": a, "data": datetime.strptime(s["FILING_DATE"], "%d-%b-%Y").date().isoformat(),
                      "ticker": s["ISSUERTRADINGSYMBOL"].strip().upper(), "cargo": cargo, "dono": dono, "valor": valor, "preco": min(precos)})
        if e:
            saida.append(e)
    return sorted(saida, key=lambda e: e["data"])
