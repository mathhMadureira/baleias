"""Guarda do dia (H54, regra do dono 16/11: "nenhum robô deve terminar as 24 h no prejuízo").

Nenhuma regra impede o mercado de cair; o que dá para obrigar é o robô NÃO DEVOLVER um dia que ficou positivo:
  - o dia é o dia UTC (vira às 21:00 de Brasília); resultado do dia = patrimônio agora − patrimônio na primeira rodada do dia;
  - se o resultado do dia chegou a +GATILHO e voltou a DEVOLVE do pico (ainda no lucro), o robô fecha todas as posições no preço da rodada
    e não abre mais nada até o dia seguinte. É compatível com a regra 11 (só para no lucro e sem operação aberta) e com a regra 5
    (não há trava de perda: no dia negativo o robô segue operando).
Medido antes de ligar (16/11, 36 dias-robô da mesa): dias positivos 7 → 11 e soma −45,54 → −26,40 com GATILHO 0,25 (lab/PROTOCOLO_LAB.md, H54).
"""
import time

GATILHO, DEVOLVE = 0.25, 0.5
META = 12.0          # H57: meta do dono (17/11: "ninguém conseguiu fazer mais de 10"). A de +0,50 passou no teste mas segurava quem ganhava;
                     # a de 12 não mudou nada nos dados antigos. Quem protege o lucro do dia é a guarda (GATILHO/DEVOLVE).


def _hoje(agora):
    return time.strftime("%Y-%m-%d", time.gmtime(agora))


def checar(e, agora=None):
    """Atualiza e["guarda_dia"] com o patrimônio da última rodada. Devolve "normal", "fechar" (fechar tudo agora e travar) ou "travado"."""
    agora = agora or time.time()
    pat = float(e.get("patrimonio", e.get("caixa", 10.0)) or 0)
    d = e.get("guarda_dia")
    if not d or d.get("data") != _hoje(agora):
        d = {"data": _hoje(agora), "inicio": round(pat, 4), "pico": 0.0, "travado": False}
    res = pat - d["inicio"]
    d["resultado"], d["pico"] = round(res, 4), round(max(d["pico"], res), 4)
    e["guarda_dia"] = d
    if d["travado"] and not d.get("por") and res > d["pico"] * DEVOLVE and res < META:   # trava antiga pela meta de 0,50: destrava
        d["travado"] = False
    if d["travado"]:
        return "travado"
    if res >= META or (d["pico"] >= GATILHO and res <= d["pico"] * DEVOLVE):
        d["travado"], d["travado_em"], d["por"] = True, int(agora), "meta" if res >= META else "guarda"
        return "fechar"
    return "normal"


def motivo(e):
    d = e.get("guarda_dia") or {}
    if d.get("resultado", 0) >= META:
        return f"meta do dia: +{d.get('resultado', 0):.2f} (meta +{META:.2f}); dia garantido no lucro"
    return f"guarda do dia: chegou a +{d.get('pico', 0):.2f} e voltou a +{d.get('resultado', 0):.2f}; dia garantido no lucro"


def texto(nome, e):
    d = e.get("guarda_dia") or {}
    return f"🔒 {nome}: dia garantido no lucro (+{d.get('resultado', 0):.2f}; pico +{d.get('pico', 0):.2f}). Fechou tudo e volta às 21:00 de Brasília."
