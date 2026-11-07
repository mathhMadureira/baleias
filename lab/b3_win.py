"""Mini índice (WIN) negócio a negócio do arquivo público diário da B3 → velas de 1 min (H6-WINb e coletor diário)."""
import datetime as dt
import io
import json
import time
import urllib.request
import zipfile

from baleias import config

PASTA = config.RAIZ / "lab" / "win"
URL = "https://arquivos.b3.com.br/rapinegocios/tickercsv/{}"
ABRE, FECHA = "090000000", "182500000"   # pregão regular (horário de Brasília)


def _linhas(z):
    nome = z.namelist()[0]
    with z.open(nome) as f:
        for b in io.TextIOWrapper(f, encoding="latin-1"):
            if ";WIN" in b[:20]:
                yield b.rstrip("\n").split(";")


def velas_do_dia(dia):
    """Velas de 1 min do contrato WIN mais negociado no dia; None se o arquivo não existe ou está vazio."""
    arq = PASTA / f"{dia}.json"
    if arq.exists():
        return json.loads(arq.read_text())
    tmp = PASTA / f"{dia}.zip"
    PASTA.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL.format(dia), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
    try:
        if tmp.stat().st_size == 0:
            return None
        z = zipfile.ZipFile(tmp)
        volume, cancelados = {}, set()
        for c in _linhas(z):
            if len(c[1]) != 6:
                continue
            if c[2] != "0":
                cancelados.add(c[6])
            else:
                volume[c[1]] = volume.get(c[1], 0) + int(c[4])
        if not volume:
            return None
        contrato = max(volume, key=volume.get)
        barras = {}
        for c in _linhas(z):
            if c[1] != contrato or c[2] != "0" or c[6] in cancelados or not (ABRE <= c[5].zfill(9) < FECHA):
                continue
            h = c[5].zfill(9)
            minuto = int(h[:2]) * 60 + int(h[2:4])
            px, q = float(c[3].replace(",", ".")), int(c[4])
            b = barras.get(minuto)
            if b is None:
                barras[minuto] = [px, px, px, px, q]
            else:
                b[1], b[2], b[3], b[4] = max(b[1], px), min(b[2], px), px, b[4] + q
        base = int(dt.datetime.strptime(dia, "%Y-%m-%d").replace(tzinfo=dt.timezone(dt.timedelta(hours=-3))).timestamp() * 1000)
        saida = {"contrato": contrato, "velas": [[base + m * 60_000, *barras[m]] for m in sorted(barras)]}
        arq.write_text(json.dumps(saida))
        return saida
    finally:
        tmp.unlink(missing_ok=True)


def coletar(dias=35):
    feitos = []
    hoje = dt.date.today()
    for k in range(dias, 0, -1):
        d = hoje - dt.timedelta(days=k)
        if d.weekday() >= 5:
            continue
        try:
            r = velas_do_dia(d.isoformat())
        except Exception as e:
            print(d, "falhou", type(e).__name__, str(e)[:80], flush=True)
            continue
        if r:
            feitos.append(d.isoformat())
            print(d, r["contrato"], len(r["velas"]), "velas", flush=True)
        time.sleep(1)
    return feitos


if __name__ == "__main__":
    coletar()
