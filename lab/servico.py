"""Serviço das tarefas lentas (Gemini, SEC, funding, tendência), separado do monitor das baleias para não atrasá-lo."""
import time

from baleias import banco, saude


def rodar():
    from baleias.insider_vivo import Rotina
    from lab import generativa
    c = banco.abrir()
    rotina = Rotina(c)
    while True:
        inicio = time.monotonic()
        partes = []
        try:
            g = generativa.ciclo(c)
            partes.append(f"gemini {g}")
        except Exception as e:
            partes.append(f"gemini falhou {type(e).__name__}")
            print(time.strftime("%F %T"), "IA generativa falhou:", type(e).__name__, str(e)[:150], flush=True)
        try:
            partes.append(f"rotina {rotina.rodar()}")
        except Exception as e:
            partes.append(f"rotina falhou {type(e).__name__}")
            print(time.strftime("%F %T"), "rotina falhou:", type(e).__name__, str(e)[:150], flush=True)
        saude.bater(c, "pesquisa", " | ".join(partes))
        time.sleep(max(1, 30 - (time.monotonic() - inicio)))


if __name__ == "__main__":
    rodar()
