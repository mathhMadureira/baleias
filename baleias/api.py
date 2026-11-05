"""Cliente só de leitura: fala apenas com o endpoint de informações, nunca com o que envia ordens."""
import json
import time
import urllib.error
import urllib.request

from . import config

TIPOS_PERMITIDOS = {
    "userFills", "userFillsByTime", "clearinghouseState", "candleSnapshot", "allMids", "metaAndAssetCtxs",
}
PESOS = {"clearinghouseState": 2, "allMids": 2}


class Limitador:
    def __init__(self, peso_por_minuto=config.PESO_POR_MINUTO, relogio=time.monotonic, dormir=time.sleep):
        self.taxa = peso_por_minuto / 60.0
        self.saldo = float(peso_por_minuto)
        self.teto = float(peso_por_minuto)
        self.relogio, self.dormir = relogio, dormir
        self.antes = relogio()

    def gastar(self, peso):
        agora = self.relogio()
        self.saldo = min(self.teto, self.saldo + (agora - self.antes) * self.taxa)
        self.antes = agora
        if self.saldo < peso:
            self.dormir((peso - self.saldo) / self.taxa)
            self.saldo = peso
            self.antes = self.relogio()
        self.saldo -= peso


class Cliente:
    def __init__(self, limitador=None, abrir=urllib.request.urlopen):
        self.limitador = limitador or Limitador()
        self.abrir = abrir

    def info(self, tipo, **campos):
        if tipo not in TIPOS_PERMITIDOS:
            raise ValueError(f"tipo de consulta não permitido: {tipo}")
        self.limitador.gastar(PESOS.get(tipo, 20))
        corpo = json.dumps({"type": tipo, **campos}).encode()
        pedido = urllib.request.Request(config.INFO_URL, data=corpo, headers={"Content-Type": "application/json"})
        ultimo = None
        for tentativa in range(5):
            try:
                with self.abrir(pedido, timeout=30) as r:
                    dados = json.load(r)
                # A taxa extra por itens devolvidos não tem valor na documentação; 1 a cada 20 é a leitura cautelosa.
                if isinstance(dados, list) and len(dados) >= 20:
                    self.limitador.gastar(len(dados) // 20)
                return dados
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                ultimo = e
                time.sleep(2 ** tentativa)
        raise RuntimeError(f"Hyperliquid não respondeu a {tipo}: {ultimo}")

    def ranking(self):
        with self.abrir(config.RANKING_URL, timeout=280) as r:
            return json.load(r)["leaderboardRows"]

    def operacoes(self, carteira, inicio_ms, fim_ms=None):
        campos = {"user": carteira, "startTime": int(inicio_ms)}
        if fim_ms is not None:
            campos["endTime"] = int(fim_ms)
        return self.info("userFillsByTime", **campos)

    def operacoes_todas(self, carteira, inicio_ms, fim_ms, limite=10000):
        saida, cursor = [], int(inicio_ms)
        while len(saida) < limite:
            lote = self.operacoes(carteira, cursor, fim_ms)
            if not lote:
                break
            saida.extend(lote)
            if len(lote) < 2000:
                break
            cursor = max(f["time"] for f in lote) + 1
        return {f["tid"]: f for f in saida}.values()

    def velas(self, moeda, intervalo, inicio_ms, fim_ms):
        return self.info("candleSnapshot", req={"coin": moeda, "interval": intervalo, "startTime": int(inicio_ms), "endTime": int(fim_ms)})

    def precos(self):
        p = {k: float(v) for k, v in self.info("allMids").items()}
        p.update({k: float(v) for k, v in self.info("allMids", dex=config.DEX_ACOES).items()})
        return p
