"""Telegram se configurado; sempre grava em arquivo. O token vem do ambiente e nunca vai para o banco nem para logs."""
import json
import os
import time
import urllib.parse
import urllib.request

from . import config


def texto(sinal, media, desvio, n, histo=""):
    return (f"🐋 {sinal['lado'].upper()} {sinal['moeda']} ({sinal['tipo']})\n"
            f"Carteira {sinal['carteira'][:8]}…  posição US$ {sinal['nocional']:,.0f}\n"
            f"Preço no alerta: {sinal['px']}  |  atraso: {sinal['atraso_s']:.0f}s\n"
            f"Esperado em 4 h, depois dos custos: {media:+.2f}% (±{desvio:.2f}), com {n} sinais aprendidos\n"
            f"{histo}Teste, não recomendação. Pode perder tudo.")


def enviar(mensagem):
    config.RAIZ.mkdir(parents=True, exist_ok=True)
    with open(config.RAIZ / "alertas.log", "a") as f:
        f.write(json.dumps({"t": int(time.time()), "msg": mensagem}, ensure_ascii=False) + "\n")
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    corpo = urllib.parse.urlencode({"chat_id": chat, "text": mensagem}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=corpo, timeout=15):
            return True
    except OSError as e:
        # A URL contém o token: registra só o tipo do erro.
        print(f"telegram falhou: {type(e).__name__}", flush=True)
        return False
