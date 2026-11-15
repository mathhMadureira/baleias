"""Conector da LBank — SÓ LEITURA (pedido do dono em 15/11). Não existe neste arquivo nenhuma função que mande ordem, cancele, transfira ou saque.

O que faz: confere a conexão e a hora do servidor, lê as permissões da chave (recusa chave com saque), lê os saldos da conta à vista e o
preço do BTC (à vista e no perpétuo, endpoints públicos).

Assinatura (documentação oficial, https://www.lbank.com/en-US/docs/contract.html, seção "Signature authentication", e docs da API à vista):
  1. todos os parâmetros menos `sign`, mais signature_method=HmacSHA256, timestamp (ms) e echostr (30–40 letras/dígitos);
  2. ordenados pelo nome e unidos como chave=valor&...;
  3. MD5 em hexadecimal MAIÚSCULO;
  4. HMAC-SHA256 desse MD5 com o segredo, em hexadecimal.
Conferido com o exemplo da própria documentação (teste `LBankSoLeitura.test_assinatura_igual_ao_exemplo_oficial`).

Chaves: LBANK_API_KEY e LBANK_API_SECRET no ~/baleias/.env, gravadas pelo dono com `python3 -m executor.configurar_chave` (opção lbank).
Uso: cd ~/baleias && python3 -m executor.lbank
"""
import hashlib
import hmac
import json
import os
import secrets
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from baleias import config  # noqa: F401  (carrega o .env)

BASE_SPOT = os.environ.get("LBANK_BASE", "https://api.lbank.info")
BASE_PERP = os.environ.get("LBANK_BASE_PERP", "https://lbkperp.lbank.com")
UA = {"User-Agent": "baleias/1.0"}           # a LBank recusa (403) o cliente padrão do Python; nome genérico, sem dado pessoal


def assinar(params, segredo):
    """sign da LBank para um dicionário de parâmetros (sem o próprio sign)."""
    texto = "&".join(f"{k}={params[k]}" for k in sorted(params))
    preparado = hashlib.md5(texto.encode()).hexdigest().upper()
    return hmac.new(segredo.encode(), preparado.encode(), hashlib.sha256).hexdigest()


def _echostr():
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(35))


class LBankLeitura:
    nome = "LBank"

    def __init__(self, chave=None, segredo=None, abrir=urllib.request.urlopen):
        self.chave = chave if chave is not None else os.environ.get("LBANK_API_KEY", "")
        self.segredo = segredo if segredo is not None else os.environ.get("LBANK_API_SECRET", "")
        self.abrir = abrir

    def _ler(self, req):
        try:
            with self.abrir(req, timeout=15) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"LBank HTTP {e.code}") from None
        codigo = d.get("error_code", d.get("code", 0))
        if str(codigo) not in ("0", "None") or str(d.get("result", "true")).lower() == "false":
            raise RuntimeError(f"LBank {codigo}: {d.get('msg', '')}")      # a mensagem da LBank não contém a chave nem o segredo
        return d.get("data")

    def _publico(self, base, caminho, params=None):
        q = urllib.parse.urlencode(params or {})
        return self._ler(urllib.request.Request(f"{base}{caminho}" + (f"?{q}" if q else ""), method="GET", headers=UA))

    def _privado(self, caminho, params=None):
        """POST assinado na API à vista. Só é chamado pelos métodos de leitura abaixo."""
        if not self.chave or not self.segredo:
            raise RuntimeError("faltam LBANK_API_KEY e LBANK_API_SECRET no ~/baleias/.env (rode: python3 -m executor.configurar_chave)")
        p = dict(params or {})
        p.update(api_key=self.chave, signature_method="HmacSHA256", timestamp=str(int(time.time() * 1000)), echostr=_echostr())
        p["sign"] = assinar({k: v for k, v in p.items() if k != "sign"}, self.segredo)
        cab = {**UA, "Content-Type": "application/x-www-form-urlencoded", "timestamp": p["timestamp"],
               "signature_method": p["signature_method"], "echostr": p["echostr"]}
        corpo = urllib.parse.urlencode(p).encode()
        return self._ler(urllib.request.Request(f"{BASE_SPOT}{caminho}", data=corpo, method="POST", headers=cab))

    # ------------- leitura -------------
    def hora_servidor(self):
        return int(self._publico(BASE_SPOT, "/v2/timestamp.do"))

    def preco_spot(self, par="btc_usdt"):
        d = self._publico(BASE_SPOT, "/v2/supplement/ticker/price.do", {"symbol": par})
        item = d[0] if isinstance(d, list) else d
        return float(item["price"])

    def preco_perp(self, simbolo="BTCUSDT"):
        d = self._publico(BASE_PERP, "/cfd/openApi/v1/pub/marketData", {"productGroup": "SwapU"})
        for x in d or []:
            if str(x.get("symbol", "")).upper() == simbolo:
                return float(x["lastPrice"])
        return None

    def permissoes(self):
        return self._privado("/v2/supplement/api_Restrictions.do")

    def saldos(self):
        d = self._privado("/v2/supplement/user_info.do") or []
        return {str(x.get("coin", "")).upper(): {"total": float(x.get("assetAmt") or 0), "livre": float(x.get("usableAmt") or 0),
                                                 "preso": float(x.get("freezeAmt") or 0)} for x in d if float(x.get("assetAmt") or 0) > 0}


def problemas_da_chave(perm):
    """Lista de problemas das permissões. Saque ligado é grave: o conector se recusa a continuar."""
    out = []
    if perm.get("enableWithdrawals"):
        out.append("GRAVE: a chave tem permissão de SAQUE. Apague-a na LBank e crie outra só com leitura/negociação.")
    if not perm.get("ipRestrict"):
        out.append("aviso: a chave não está travada por IP (recomendado travar no IP da máquina).")
    if not perm.get("enableReading", True):
        out.append("aviso: a chave não tem permissão de leitura.")
    return out


def main():
    c = LBankLeitura()
    try:
        srv = c.hora_servidor()
        print(f"✅ LBank no ar · diferença de relógio {abs(srv - time.time() * 1000) / 1000:.1f} s")
    except (RuntimeError, OSError, ValueError) as e:
        print(f"❌ Não consegui falar com a LBank: {e}")
        return 1
    for nome, f in (("à vista", c.preco_spot), ("perpétuo", c.preco_perp)):
        try:
            print(f"💲 BTC {nome}: {f():,.2f} USDT")
        except (RuntimeError, OSError, ValueError, KeyError, TypeError) as e:
            print(f"⚠️  preço {nome} indisponível: {e}")
    if not c.chave or not c.segredo:
        print("ℹ️  Sem chave no .env: só os dados públicos. Para ler a sua conta: python3 -m executor.configurar_chave (opção lbank).")
        return 0
    try:
        perm = c.permissoes()
    except RuntimeError as e:
        print(f"❌ A LBank recusou a chave: {e}")
        return 1
    probs = problemas_da_chave(perm or {})
    for p in probs:
        print(("❌ " if p.startswith("GRAVE") else "⚠️  ") + p)
    if any(p.startswith("GRAVE") for p in probs):
        return 1
    print(f"🔑 Chave: leitura {'sim' if perm.get('enableReading') else 'não'} · negociação à vista {'sim' if perm.get('enableSpotTrading') else 'não'} · "
          f"saque não · travada por IP {'sim' if perm.get('ipRestrict') else 'não'}")
    try:
        s = c.saldos()
    except RuntimeError as e:
        print(f"❌ Não consegui ler os saldos: {e}")
        return 1
    if not s:
        print("💼 Conta à vista: sem saldo.")
    for moeda, v in sorted(s.items(), key=lambda kv: -kv[1]["total"]):
        print(f"💼 {moeda}: {v['total']:.8g} (livre {v['livre']:.8g}, preso {v['preso']:.8g})")
    print("ℹ️  Só leitura: nenhuma ordem foi ou pode ser enviada por este conector.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
