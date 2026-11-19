# Agenda do Laboratório — hipóteses em teste ao vivo e quando julgar

Feita em 18/11/2026 ~17:00 BRT (20:00 UTC) a partir de `~/baleias/lab/PROTOCOLO_LAB.md` (H1–H60) e do ramo `estado` da nuvem.
Juiz de todas: 🔬 Laboratório, pelo critério escrito no protocolo; nada é julgado antes do prazo e nada é ajustado depois de ver.
"estado:" = arquivo no ramo `estado` (`git show origin/estado:dados/...`). "local" = só na máquina (que dorme). BRT = UTC − 3.

## 1. Julgamentos com data marcada (prioridade)

| # | Hipótese | Critério (pré-registrado) | Prazo | Dados onde medir | Situação em 18/11 |
|---|---|---|---|---|---|
| H46 | v4 pior das 18–24 h UTC | 18–24 h UTC acerta < 50% com z ≤ −2 (erro-padrão por vela) **e** as outras faixas juntas ≥ 52%. 1 tentativa. Passa → v4 não abre posição nova 18–24 h UTC | apostas de 16/11 00:00 a 22/11 24:00 UTC → julgar **23/11 00:00 UTC (22/11 21:00 BRT)** | estado:`dados/cerebro_v4.json` → `ops` por moeda (`[t_vela, resultado, acertou]`, guarda até 3000 por moeda ≈ 31 dias). Não usar `vigia_v4.json` (mistura 11–15/11, os dados da descoberta) | aguardando |
| H49 | stop móvel (arma +0,5%, guarda 70%) | soma das saídas pelo stop móvel > soma com a saída antiga (velas de 1 min) | **sem prazo novo:** os robôs estão parados desde a H61 (18/11 ~19:58 UTC). Julgar nas operações dos agentes (H61) abertas depois da P1 (rodada de 18/11 20:18:18 UTC), ≥ 30 | `fechadas` das carteiras dos agentes (executor `robo_claude_nuvem.py`) | aguardando operações dos agentes |
| H54 | guarda do dia | — | **REVOGADA pelo dono em 18/11 (~19:45 UTC), antes do prazo: não será julgada** | — | fora (registrado em 5aba7100) |
| H59 | Chefe OpenBot no testnet | soma líquida > 0 **e** fator de lucro > 1 (resultado da corretora: realizedPnl − commission). Comparação relatada, não decide: Robô Claude (mesmo `decisao_t`) e Caçador | **30 operações fechadas ou 25/11 01:03 UTC (24/11 22:03 BRT)**, o que vier antes | estado:`dados/robo_openbot_testnet.json` (`fechadas`); comparação `robo_claude.json`, `robo_v4_cacador.json`. ZEC e RENDER (abertas antes da emenda) relatadas à parte | 3 fechadas, 3 abertas |
| H52 | rota R6 no Rápido nuvem e no Caçador | média por operação > 0 em 30+ operações depois da P1 | **suspensa:** robôs parados desde a H61; sem operações novas. Só volta se os robôs voltarem | estado:`robo_v4_perp.json`, `robo_v4_cacador.json` (congelados) | não julgável |
| H50/H51 | torneio do Scalper (B, C, D) | fator de lucro e soma maiores que o Scalper, ≥ 30 operações | **encerrado sem veredito:** robôs aposentados (H61), e as operações de antes da P1 não são executáveis | estado:`dados/torneio.json` | registro apenas |
| H53 | Robô LBank (adendo 2, 18/11: memecoins primeiro) | as próximas 30 operações contra as 23 anteriores (soma −4,26, fator 0,47): fator de lucro **e** soma maiores (juiz do torneio) | **30 operações** depois de 18/11 ~19:45 UTC | estado:`dados/robo_lbank.json` (`fechadas`) | recomeçou a contagem. Nota E |
| H20 | Cérebro v1 no binário simulado | ≥ 500 apostas ao vivo; limite inferior de Wilson do acerto > 51% | 500 apostas → **prazo já atingido** | estado:`dados/cerebro.json` (`operacoes` com `t` ≥ `inicio_ao_vivo`) | **REPROVADA em 19/11 12:00 UTC:** 563 apostas, acerto 52,8%, Wilson [48,6%; 56,8%] < 51% (`lab/juizo_h20.py`, estado 12850e8c) |

## 2. Testes ao vivo longos ou por contagem (sem data próxima)

| # | Hipótese | Critério | Prazo | Dados | Situação em 18/11 |
|---|---|---|---|---|---|
| H21 | v2 × v1 | ambos ≥ 300 apostas ao vivo; v2 vence com resultado **e** acerto maiores | 300 apostas do v2 | estado:`cerebro.json`, `cerebro_v2.json` | v1 563, v2 266 (19/11) |
| H19 | Vórtice invertido | ≥ 300 apostas, Wilson > 51% | 300 apostas | local `dados/h19_vortice.jsonl` | 18 apostas resolvidas |
| H5/H5b | Gemini 15 min, 1 h, 4 h | por prazo: 300 resolvidas (não abstidas na 5b), Wilson > 50% **e** soma das operações > 0 após 0,2% | 300 por prazo | local `dados/baleias.db`: `llm_previsoes`, `llm_previsoes_v2`, `llm_contextos` | 180 consultas gravadas; contagem resolvida não conferida |
| H7 | fluxo antecipa preço | 2000 janelas; R² fora da amostra > 0 (IC sem 0) **e** regra simples com lucro | 2000 janelas | local `dados/leitura_mercado.jsonl` | 572 linhas |
| H2 | tendência 20 d em cripto | aos 180 d: retorno > 0, Sharpe e maior queda melhores que comprar e segurar; senão 365 d | **05/05/2027** | local `baleias.db` → `lab_tendencia` | rodando |
| H3/H3b | receber funding (1× e 2×) | aos 90 d: acumulado > 0 e maior queda < 2% | **04/02/2027** | local `baleias.db` → `lab_funding` | 11 dias contados |
| H10b | Tartaruga só compra | expectativa > 0 e PF > 1,3 | 30 operações ou **05/05/2027** | estado:`robo_tartaruga.json` | 0 operações |
| H28b | Minerador | ≥ 200 operações: média > 0 e t > 2; reprova se média ≤ 0 | 200 operações | estado:`robo_minerador.json` + etiqueta antes do zero | 40 desde 16/11. Saída mudou em 16/11 (sem teste) |
| H37 | Rápido nuvem e Caçador | ≥ 200 operações: líquido > 0 e Wilson > 50% | 200 operações | estado:`robo_v4_perp.json`, `robo_v4_cacador.json` + etiqueta | regras mudaram depois (H44, H52, H54, H57, H58) |
| H43 | Robô Claude | ≥ 30 operações, carteira ≥ US$ 11, nunca abaixo de US$ 5 | 30 operações | estado:`robo_claude.json` + etiqueta | 11 desde 16/11 |
| H33 | sinapses dos traders | regra do próprio cérebro (≥ 150 previsões, Wilson) | automático | `diario` de `cerebro*.json` | copiar para o protocolo quando houver 150 |
| H47 | Robô Livre (descritivo) | carteira com e sem custo, liquidações, em 7 dias | **22/11 21:20 UTC** | estado:`robo_livre.json` | quebrou (carteira 0,90); só registrar |
| H41 | retreino semanal do v4 | juiz da H41, automático | toda semana | `.github/workflows/retreino.yml` | automático |

Fora da agenda: H48 (substituída pela H49), H55 (revogada), H56 Radar e H60 (reprovadas no laboratório; o Radar fica só como comparação).

## H61: os agentes operam no lugar dos robôs (18/11 ~20:00 UTC, commit 10d50818)

| # | Hipótese | Critério | Prazo | Dados | Situação |
|---|---|---|---|---|---|
| H61 | agentes Baleias, Treinador, Laboratório e Guardião operam (US$ 10 cada) | depois de 30 operações de cada agente: fator de lucro > 1 **e** carteira > US$ 10; campeão entre os aprovados | **30 operações por agente** | carteiras dos agentes no ramo `estado` (executor `robo_claude_nuvem.py`) | contam só as operações abertas depois da P1 (rodada de 18/11 20:18:18 UTC). As 4 do Treinador abertas antes ficam à parte. A carteira do Laboratório é julgada por mim mesmo: o critério é o fixado acima, sem ajuste |

## Correção P1 (18/11 ~21:30 UTC, ver `lab/PROTOCOLO_LAB.md`, commit 428d6592)

Aplicada pelo Baleias em 764a98e6, valendo desde a rodada de 18/11 20:18:18 UTC (robôs do v4 **e** o executor dos agentes, que tinha o mesmo defeito na entrada). Os robôs do v4 (Caçador, Rápido nuvem, Scalpers A–D) entravam em apostas velhas e conferiam o stop em minutos que já tinham passado.
Isso foi decidido antes de ver qualquer número depois da correção:
- **H49 e H52:** contam só operações abertas depois que o Baleias aplicar a correção. H52 precisa de 30 por robô (o prazo de 29/11 se
  estende até elas existirem). H49 usa as mesmas (≥ 30) no lugar da janela até 22/11.
- **H50/H51:** os placares dos robôs do v4 recomeçam na correção.
- **Verificação da P1:** nas 30 operações seguintes de cada robô, zero com atraso > 30 min e zero com saída antes da abertura
  (`python3 -m lab.atraso_entrada`).

## Pré-registradas em 19/11 (commit 3e5ea591)

| # | Hipótese | Critério | Prazo | Dados | Situação |
|---|---|---|---|---|---|
| H70 | saída com alvo (era "H68"; alvo ≥ 3× stop e móvel em alvo/2 já ligados pelo dono em 19/11): sem stop móvel (A1) ou móvel só a partir de alvo/2 (A2), em G1 (0,6/1,2/120 min) e G2 (1/3/24 h) | diferença pareada contra a A0 > 0, z ≥ 2,24, > 0 nos 3 blocos. Controle sorteado de cada forma = −0,12% ± 3 erros-padrão; senão a rodada é inválida | rodar no próximo juízo diário (teste nos dados, não ao vivo) | apostas do v4 com confiança ≥ 0,08 desde 16/11 21:53 UTC; velas de 1 min; `stop_movel.conferir` | registrada, não rodada |
| H69 | rotina r9 × r8 | excesso sobre o controle de lado sorteado: r9 ≥ r8 no total dos 4 **e** fator de lucro da r9 > 1. Se faltar r8: excesso da r9 > 0 com t ≥ 2 | 30 operações r9 (total dos 4) ou 03/12 | `fechadas` dos agentes + `versao_rotina` da decisão pelo `decisao_t` | aguardando operações r9 |

## Notas fixadas antes de olhar os resultados (18/11)

- **A (H49), saída antiga:** para Claude, Scalper e Minerador, a saída antiga é a regra do robô sem o stop móvel. Para o Rápido e o Caçador
  com R6, o stop móvel faz parte da rota R4/R6 aprovada na H52. Nesse caso a saída antiga é R6 sem o móvel (stop de 2%, lado contra o
  regime, 24 h), e o resultado é relatado à parte. Guarda do dia e meta valem nas duas contas.
- **B (H54):** a meta do dia mudou durante a janela do teste (H57: 0,50 em 17/11 e depois de volta a 12). O efeito fica relatado à parte,
  sem mudar o critério.
- **C (H52):** se reprovar, o protocolo manda voltar ao "fim da vela", mas a regra 13 do dono (16/11) proibiu o fim da vela. Em caso de
  reprovação, o veredito vai ao dono e ao Baleias com esse conflito declarado.
- **D (H50/H51):** o Scalper D tem os mesmos números do Scalper (83 operações, soma 0,619, fator 1,19). O filtro dele nunca disparou
  (exige ≥ 50 operações e z ≤ −2 num segmento), então o teste do D não mediu nada. Os Scalpers passaram para a R6 em 16/11, no meio do torneio.
- **E (H53):** em 17/11 o LBank passou a entrar só em moedas com velas de 1 min, durante as 30 operações. Isso fica relatado.

## Propostas do Treinador

`propostas.md`: P1 (Treinador, 18/11) aprovada como correção de simulação, com emenda; enviada ao Baleias. Cada proposta nova é pré-registrada no protocolo (regra, dados, custo de 0,12%, critério,
3 blocos, tentativas contadas) antes de rodar, e o veredito fica embaixo dela.
