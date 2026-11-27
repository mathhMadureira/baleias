"""H88 (27/11/2026): o cético ajuda? Simula o plano de cada ordem VETADA nas velas de 1 min da BingX e compara com as aprovadas que entraram.

Critério (PROTOCOLO_LAB.md, H88): depois de 30 vetadas ou 30 dias, o cético AJUDA se a média simulada das vetadas for < 0 e menor que a
média real (em %) das aprovadas que entraram. Custo 0,12% ida e volta. Stop e alvo na mesma vela = stop.
Uso: python3 -I -m lab.h88_cetico   → imprime e grava dados/lab/h88_cetico.json
"""
import json
import time
import urllib.request
from pathlib import Path

EQUIPE = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/equipe")
CONTA = Path("/home/servidor-de-producao/OpenBot/Shared/baleias/operar/corretoras/laboratorio.json")
SAIDA = Path(__file__).resolve().parent.parent / "dados" / "lab" / "h88_cetico.json"
CUSTO = 0.0012


def simular(lado, ref, plano, velas):
    """velas: [[t, o, h, l, c], ...] a partir da ordem. Devolve o resultado em fração (já com custo)."""
    s = 1 if lado == "compra" else -1
    stop, alvo = float(plano.get("stop_pct") or 0.02), plano.get("alvo_pct")
    arma, guarda = plano.get("movel_arma"), float(plano.get("movel_guarda") or 0.6)
    pico, piso = 0.0, -stop
    for k, (_, o, h, l, c) in enumerate(velas[: int(plano.get("prazo_min") or 240)]):
        fav, contra = ((h if s > 0 else l) / ref - 1) * s, ((l if s > 0 else h) / ref - 1) * s
        if contra <= piso:
            return piso - CUSTO
        if alvo and fav >= float(alvo):
            return float(alvo) - CUSTO
        pico = max(pico, fav)
        if arma and pico >= float(arma):
            piso = max(piso, pico * guarda)
    return ((velas[min(len(velas), int(plano.get("prazo_min") or 240)) - 1][4] / ref - 1) * s - CUSTO) if velas else 0.0


def velas_1m(moeda, t0):
    u = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={moeda[:-4]}-USDT&interval=1m&startTime={int(t0 * 1000)}&limit=1440"
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20))["data"]
    v = sorted(([int(x["time"]) / 1000, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])] for x in d), key=lambda x: x[0])
    return [x for x in v if x[0] >= t0]


def main():
    cet = json.loads((EQUIPE / "cetico.json").read_text()) if (EQUIPE / "cetico.json").exists() else {}
    vet = []
    for oid, c in cet.items():
        if c.get("decisao") == "vetada" and time.time() - c["t"] > 4 * 3600:
            try:
                vet.append({"id": oid, "moeda": c["moeda"], "r": simular(c["lado"], float(c["preco_ref"]), c["plano"], velas_1m(c["moeda"], c["t"]))})
            except Exception as ex:
                print(f"{oid}: sem velas ({type(ex).__name__})")
    aprov = set(k for k, c in cet.items() if c.get("decisao") == "aprovada")
    e = json.loads(CONTA.read_text())
    ent = [f for f in e.get("fechadas") or [] if f.get("ordem") in aprov]
    r_ap = [f["resultado_usd"] / max(1e-9, float(f.get("nocional") or 1)) for f in ent]
    mv = sum(x["r"] for x in vet) / len(vet) if vet else None
    ma = sum(r_ap) / len(r_ap) if r_ap else None
    out = {"t": time.time(), "vetadas": vet, "n_vetadas": len(vet), "media_vetadas": mv, "n_aprovadas": len(r_ap), "media_aprovadas": ma,
           "pronto": len(vet) >= 30, "ajuda": (mv is not None and ma is not None and mv < 0 and mv < ma)}
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"vetadas {len(vet)} média {mv if mv is None else f'{mv:+.3%}'} | aprovadas {len(r_ap)} média {ma if ma is None else f'{ma:+.3%}'} | "
          f"{'veredito: ' + ('AJUDA' if out['ajuda'] else 'NÃO ajuda') if out['pronto'] else 'ainda sem 30 vetadas'}")


if __name__ == "__main__":
    main()
