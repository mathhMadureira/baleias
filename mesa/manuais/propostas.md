# Propostas do Treinador (uma mudança por vez; o Laboratório julga)

## P1 — Caçador só entra em aposta do v4 da vela mais nova (18/11/2026 ~19:45 UTC)

**O que muda (uma coisa):** em `executor/v4_perp_nuvem.passo`, a lista de candidatos à entrada passa a aceitar só apostas de `pendentes`
cuja vela do sinal (`p["t"]`) é a última vela de 15 min fechada (idade ≤ 15 min na rodada). Tudo o mais (ranking K=2, R6, stop 2%,
regime, guarda do dia, H58) fica igual. O mesmo código roda Rápido nuvem e Scalpers B–D: a correção vale para eles sem escolha de robô.

**Por quê (o defeito):** `pendentes` do `dados/cerebro_v4.json` guarda apostas antigas de moedas que pararam de ser previstas
(agora: 79 apostas, 26 da vela mais nova, as outras de 1 h a ~5 dias; ex. RWUSD, SOXSB, BABAB de 13/11 20:15; HEMI de 15/11 13:45).
O Caçador entra nelas com o preço (`px`) e a hora (`entrada_t`) da vela antiga, e o stop móvel/stop 2% é conferido nas velas de 1 min
**do passado**. Ex.: HEMI aberta no estado em 16/11 21:57, com entrada 15/11 14:00 a 0,00348 e saída pelo stop 2% em 15/11 14:41
(−0,530). É uma operação que ninguém poderia executar (regra 9 do dono: tudo feito para dinheiro real). Além disso, no ranking, uma aposta
velha de confiança alta ocupa a vaga de uma aposta nova.

**Números (operações fechadas desde o zero de 16/11 21:53 UTC até 18/11 19:30 UTC; `origin/estado` 8d0382f2):**
atraso = (1ª rodada em que a posição aparece em `abertas` no histórico do ramo `estado`) − `entrada_t`. Os dois grupos não se misturam:
limpas 0,0–0,2 h; velhas 2,1–99,7 h.

| robô | todas: n / soma US$ / fator | velhas (atraso > 30 min): n / soma | limpas: n / soma / fator |
|---|---|---|---|
| Caçador (`robo_v4_cacador.json`) | 48 / +1,969 / 1,69 | 7 / −0,055 | 41 / +2,024 / 1,89 |
| Scalper B (`robo_scalper_b.json`) | 101 / +1,030 / 1,19 | 29 / +1,064 | 72 / −0,035 / 0,99 |
| Rápido nuvem (`robo_v4_perp.json`) | 45 / +0,711 / 1,23 | 17 / +0,523 | 28 / +0,187 / 1,09 |

Operações limpas em 3 blocos iguais de tempo (16/11 21:53–17/11 13:05–18/11 04:18–18/11 19:30 UTC, pela hora de abertura real):

| robô | bloco 1 | bloco 2 | bloco 3 |
|---|---|---|---|
| Caçador | 14 ops +1,067 | 17 ops +0,388 | 10 ops +0,570 |
| Scalper B | 54 ops +0,955 | 11 ops −0,377 | 7 ops −0,612 |
| Rápido nuvem | 17 ops +0,838 | 11 ops −0,651 | 0 ops |

Leitura: o Caçador continua no lucro sem as velhas (3 blocos positivos). O lucro inteiro do Scalper B veio das velhas.

**Onde o Caçador ganha e perde (41 limpas, custo 0,12% já no resultado):**

| motivo de saída | n | ganhos | soma US$ | média %/op |
|---|---|---|---|---|
| stop móvel | 28 | 28 | +4,027 | +0,516 |
| guarda do dia (H54) | 7 | 2 | −0,362 | −0,173 |
| tendência de 24 h virou | 4 | 1 | −0,348 | −0,307 |
| stop 2% | 2 | 0 | −1,293 | −2,120 |

| recorte | grupo: n / soma US$ / fator |
|---|---|
| lado | compra 25 / +0,756 / 1,44 · venda 16 / +1,268 / 3,16 |
| confiança do v4 | <0,12: 3 / −0,387 / 0,40 · 0,12–0,15: 24 / +1,023 / 1,73 · ≥0,15: 14 / +1,388 / 7,02 |
| hora UTC da entrada | 00–06: 9 / −0,374 / 0,71 · 06–12: 10 / +0,570 / 2,51 · 18–24: 22 / +1,829 / 3,96 (12–18: 0) |
| tempo segurando | <30 min: 22 / +2,537 / 13,6 · 30 min–2 h: 11 / +0,481 / 1,83 · ≥2 h: 8 / −0,993 / 0,34 |

Nas velas de 1 min da Binance (à vista, as mesmas do `stop_movel`): 30 das 41 armaram o stop móvel (+0,5%), 21 delas em ≤ 30 min;
as 11 que nunca armaram somam −2,33. Testei "sair se não armar em T min" (3 tentativas, dentro da amostra): soma 2,024 → T 30: 1,571 ·
T 60: 1,967 · T 120: 2,483. O sinal troca com T: **sem evidência, não proponho**. Os recortes acima têm amostra pequena: só informação.

**Como testar:** não é regra de estratégia nova, é tirar da simulação o que não é executável; a H52 (que aprovou a R6) já entra na vela
do próprio sinal. Proposta de verificação para o Laboratório:
1. Reproduzir o atraso de cada operação (scripts em `Shared/baleias/treinador/P1/`: `historico_aberturas.py` percorre o ramo `estado`;
   `treinador_tab.py` faz as tabelas) e confirmar os números acima.
2. Confirmar no código que `entrada`/`entrada_t` vêm de `p["px"]`/`p["t"]` sem checar a idade (linhas 159–184 de `v4_perp_nuvem.py`).
3. Depois da mudança aplicada pelo Baleias: 30 operações novas do Caçador, custo 0,12%, 3 blocos de tempo.

**Critério de aprovação:** (a) itens 1 e 2 confirmados → a mudança entra (operação com preço de mais de 30 min antes da abertura não é
executável); (b) ao vivo, nas 30 operações seguintes, zero operações com atraso > 30 min. O resultado ao vivo do Caçador depois disso
não aprova nem reprova a P1 (não sei qual será); ele é a nova base do torneio. Sugestão ao juiz do torneio (H50/H52): contar só
operações limpas — com isso o Scalper B fica com fator 0,99 (72 ops) e o título de campeão fica com o Caçador (1,89 em 41 ops).

**Não sei:** por que as velhas do Scalper B e do Rápido deram lucro e as do Caçador não (7 a 29 ops; pode ser acaso). Não conferi o Scalper C e D
nem o Robô Claude/testnet (a H59 lê `ultima`, não `pendentes`).

**Veredito do Laboratório (18/11/2026 ~21:30 UTC): APROVADA como correção de simulação, com uma emenda.** Registro completo em
`lab/PROTOCOLO_LAB.md` (seção "P1 do Treinador", commit 428d6592). Script de verificação: `lab/atraso_entrada.py`.

- **(a) cumprido.** Atrasos reproduzidos por outro método: a hora do evento "ENTROU" da rodada menos `entrada_t`, em todas as revisões do
  `estado` até 8d0382f2. Caçador 48 / 41 limpas (+2,024, fator 1,89) / 7 velhas; Rápido 28 / 17. Os dois batem exatamente. No Scalper B,
  uma operação muda de grupo (73/28). O código confirma: linhas 159–184 não olham a idade, e `stop_movel.conferir` começa em `entrada_t`.
- **Achado a mais:** as "limpas" também olham o passado. A rodada roda de 0 a 20 min (mediana ~5) depois da vela, e o stop móvel é conferido
  nesses minutos. 7 das 41 limpas do Caçador saíram antes de o robô abrir (+0,983 dos +2,024). Scalper C: 7 (+0,555); Rápido: 3 (+0,384).
- **Emenda (mesma razão: tirar o que não é executável):** além de só aceitar a vela mais nova, a entrada vai para o preço e a hora da rodada,
  e o stop/stop móvel só confere minutos a partir dela.
- **(b) substituído:** nas próximas 30 operações de cada robô afetado, zero operações com atraso > 30 min **e** zero com saída antes da abertura,
  medido com `lab/atraso_entrada.py`.
- **Torneio:** "contar só as limpas" não é aceito, porque as limpas também estão infladas. Os placares e os juízes ao vivo dos robôs do v4
  (H49, H52, H50/H51) contam só operações abertas depois da correção. Os números de antes não decidem campeão.
- Enviado ao Baleias para aplicar.
