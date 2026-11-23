"""Regras da mesa Baleias em código — a mesma fonte de REGRAS.md (versão R1, 19/11/2026). Usado por operar.py gravar, chefe/gravar.py e cacar.py.

Stop, alvo e prazo vêm da EXECUÇÃO (executor.robo_claude_nuvem.parametros e executor.stop_movel.armar_em), para que texto e código nunca divirjam.
"""
import sys

sys.path.insert(0, "/home/servidor-de-producao/baleias")
from executor.robo_claude_nuvem import LIMITES, parametros  # noqa: E402,F401
from executor.stop_movel import GUARDA, armar_em  # noqa: E402,F401

VERSAO = "R2"
ESTICADA_4H = None                       # R2 (dono, 23/11: "mude todas"): C2 e C3 deixam de cortar; só C1 (sem dado)
CAMPOS = ("stop_pct",)                  # R2: só o stop é obrigatório; alvo e prazo são opcionais (sem prazo: 24 h)


def prazo_sugerido(alvo_pct):
    """Prazo sugerido pelo alvo efetivo (conduta igual para operadores e Caçador): até 1,5% → 60 min; até 3% → 120; acima → 240."""
    return 60 if alvo_pct <= 0.015 else 120 if alvo_pct <= 0.03 else 240


def tempo_do_prazo(max_min):
    """C3 olha o padrão no tempo do prazo: 15 min para prazo até 60 min; 1 h acima disso."""
    return "15m" if (max_min or 60) <= 60 else "1h"


def faltam_campos(pos):
    return [k for k in CAMPOS if not isinstance(pos.get(k), (int, float))]


def cortes_duros(lado, max_min, leitura):
    """Cortes duros de REGRAS.md §3 para uma entrada NOVA. leitura = item da varredura de multitempo.py (ou None = sem leitura).
    Devolve a lista de cortes (vazia = pode entrar). C1 (sem leitura) só é devolvido quando leitura is None."""
    if not leitura:
        return ["C1: sem leitura de 1 s a 1 dia desta moeda"]
    out = []
    if ESTICADA_4H is None:                                  # R2: C2/C3 viram informação no motivo, não corte
        return out
    v4h = (leitura.get("var") or {}).get("4h")
    if isinstance(v4h, (int, float)) and abs(v4h) >= ESTICADA_4H:
        out.append(f"C2: andou {v4h:+.1f}% em 4 h (≥ {ESTICADA_4H:.0f}%)")
    t = tempo_do_prazo(max_min)
    contra = "baixa" if lado == "compra" else "alta"
    for q in leitura.get("padroes") or []:
        if q.get("tempo") == t and q.get("confirmado") and q.get("sentido") == contra:
            out.append(f"C3: {q.get('padrao')} confirmado contra o lado em {t}")
            break
    return out


def conferir_decisao(posicoes, abertas, varredura):
    """Para gravar.py/operar.py: erros de REGRAS.md nas posições NOVAS (as já abertas não são cortadas).
    varredura = lista de leituras do multitempo anexada à decisão (só confere C2/C3 das moedas que estão nela; C1 é conduta)."""
    por = {x.get("par"): x for x in varredura or []}
    erros = []
    for p in posicoes or []:
        par = str(p.get("moeda", "")).upper()
        if par in (abertas or {}):
            continue
        falta = faltam_campos(p)
        if falta:
            erros.append(f"{par}: posição nova sem {', '.join(falta)} (REGRAS §5: stop em toda entrada)")
        if par in por:
            for c in cortes_duros(p.get("lado"), p.get("max_min"), por[par]):
                erros.append(f"{par}: {c} (REGRAS §3)")
    return erros
