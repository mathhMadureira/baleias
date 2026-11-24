"""Foco da equipe (24/11, dono: "quando eu falar 'hoje a equipe opera na Binance', a equipe inteira foca nisso").

Uma chave central em Shared/baleias/FOCO.json. Toda ferramenta que manda ordem confere aqui ANTES:
- "parado": nenhuma ordem nova em conta nenhuma (stops e alvos já guardados na corretora continuam valendo);
- "binance" | "bybit" | "bingx" | "gate": só a conta de demonstração dessa corretora opera; as outras ficam sem ordem nova;
- "todas": cada agente na própria conta de demonstração (o arranjo antigo);
- "solana_papel": nenhuma corretora; só papel na Solana.
- "lbank": a carteira única de DINHEIRO REAL do dono (24/11: US$ 10), só o operador (Laboratório) manda ordem.

Uso: python3 -I foco.py mostrar | python3 -I foco.py definir <foco> "<motivo>"
"""
import json
import os
import sys
import time
from pathlib import Path

ARQ = Path(os.environ.get("BALEIAS_FOCO", "/home/servidor-de-producao/OpenBot/Shared/baleias/FOCO.json"))
FOCOS = {
    "parado": "ninguém manda ordem nova",
    "binance": "equipe na Binance (conta de teste de futuros)",
    "bybit": "equipe na Bybit Demo",
    "bingx": "equipe na BingX VST",
    "gate": "equipe na Gate Futures TestNet",
    "lbank": "carteira única REAL na LBank (operador: Laboratório)",
    "todas": "cada agente na própria conta de demonstração",
    "solana_papel": "Solana só no papel; nenhuma corretora",
}
CORRETORA_DO_FOCO = {"binance": "binance", "bybit": "bybit", "bingx": "bingx", "gate": "gate", "lbank": "lbank"}


def ler():
    try:
        d = json.loads(ARQ.read_text())
        if d.get("foco") in FOCOS:
            return d
    except (OSError, ValueError):
        pass
    return {"foco": "parado", "motivo": "FOCO.json ausente ou inválido: por segurança, parado", "t": None}


def pode_operar(corretora):
    """corretora = 'binance' | 'bybit' | 'bingx' | 'gate'. Devolve (pode, motivo)."""
    d = ler()
    f = d["foco"]
    if f == "todas" or CORRETORA_DO_FOCO.get(f) == corretora:
        return True, f"foco {f}"
    return False, f"foco da equipe = {f} ({FOCOS[f]}); {corretora} sem ordem nova"


def definir(foco, motivo="", por="dono"):
    if foco not in FOCOS:
        raise SystemExit(f"foco inválido: {foco!r}; use um de {', '.join(FOCOS)}")
    d = {"foco": foco, "descricao": FOCOS[foco], "motivo": motivo, "por": por, "t": time.time(),
         "quando": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    tmp.replace(ARQ)
    return d


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "definir":
        print(json.dumps(definir(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""), ensure_ascii=False))
    else:
        print(json.dumps(ler(), ensure_ascii=False))
