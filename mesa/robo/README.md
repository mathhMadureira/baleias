# Robô único (24/11/2026)

Uma execução para todas as estratégias, com os limites no código (`robo.py`, `LIMITES`): só velas fechadas, dado velho = não faz nada,
alavancagem bruta ≤ 1×, perda do dia ≥ 3% = zera e para (só o dono religa), opera só a diferença, custo de 0,06% por lado.
A estratégia (`estrategias/<nome>.py`) só devolve pesos de −1 a +1. Modo papel; conta de demonstração só com estratégia aprovada no laboratório.

| estratégia | hipótese | estado |
|---|---|---|
| `ma_5x60` | H79 — médias de 5 × 60 dias, BTC + ETH | papel, juízo em 23/02/2027 |

Rodar: `python3 -I mesa/robo/robo.py passo ma_5x60` (uma vez por dia, depois das 00:00 UTC). Estado: `dados/robo_ma_5x60.json`.
