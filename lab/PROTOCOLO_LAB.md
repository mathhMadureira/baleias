# Laboratório: protocolo da hipótese 1 (seguir tendência), escrito em 2026-11-06 ANTES de baixar qualquer dado

## Pergunta
Ficar comprado num ativo quando o retorno dos últimos L dias é positivo (e fora, ou vendido, quando é negativo) rende mais, ajustado ao risco, do que só comprar e segurar, depois do custo?

## Dados
- Cripto (Binance, diário, pares USDT, desde a listagem): BTC, ETH, BNB, XRP, ADA, DOGE, LTC, LINK, TRX, SOL.
- Fundos americanos (Yahoo, diário, desde 2007): SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, SLV, USO, DBC, VNQ. Fonte não oficial.

## Cofre
- Tudo a partir de **2024-11-06** é cofre. O código recusa calcular no cofre sem a opção `--abrir-cofre`, que só funciona uma vez e grava o registro em `lab/cofre_aberto.json`.

## Mecânica (sem olhar o futuro)
- O sinal é calculado com o fechamento do dia t e aplicado ao retorno de t para t+1.
- Custo: 0,10% por lado em cripto e 0,05% por lado nos fundos, cobrado sempre que a posição muda.
- Carteira: peso igual entre os ativos disponíveis no dia, por universo.

## Tentativas (todas contam na correção)
- L ∈ {20, 60, 120, 250} dias × modo ∈ {comprado/fora, comprado/vendido} = **8 tentativas**.
- Escolha no período de desenvolvimento: a combinação com maior Sharpe médio entre os dois universos.

## Critério para abrir o cofre
- Sharpe Deflacionado (Bailey e López de Prado, 2014) da escolhida, nas 8 tentativas, **≥ 0,95** em pelo menos um universo. Se não passar, a hipótese cai sem abrir o cofre.

## Critério de aprovação no cofre (uma única avaliação)
Nos dois universos, ao mesmo tempo:
1. retorno anual depois do custo > 0;
2. Sharpe maior que o de comprar e segurar a mesma carteira;
3. maior queda (drawdown) menor que a de comprar e segurar.
Aprovada → vai para o simulado ao vivo. Reprovada → descartada; nada de reajustar e testar de novo no mesmo cofre.

---

# Hipótese 2: tendência de 20 dias só em cripto, testada AO VIVO (registrada em 2026-11-06, antes de qualquer dado novo)

Motivo: a hipótese 1 foi reprovada no cofre (falhou nos fundos), mas em cripto passou. O cofre de cripto já foi visto, então não prova nada; a prova tem de vir de dados que ainda não existem.

## Regra (fixa, sem ajuste durante o teste)
- Ativos: BTC, ETH, BNB, XRP, ADA, DOGE, LTC, LINK, TRX, SOL (pares USDT da Binance, fechamento diário UTC).
- No fechamento de cada dia d: se fechamento(d) / fechamento(d − 20) − 1 > 0, o ativo fica comprado no dia seguinte; senão, fica fora (caixa).
- Peso fixo de 1/10 por ativo (o que está fora vira caixa, rendendo zero).
- Custo de 0,10% sobre o peso que muda de posição.
- Comparação: comprar e segurar os mesmos 10 ativos com peso igual.

## Período e critérios
- O primeiro dia contado é **2026-11-07** (fechamento de 06/11 define a primeira posição). Antes de 180 dias, nenhuma conclusão.
- Aprovada aos 180 dias se, ao mesmo tempo: retorno acumulado > 0; Sharpe maior que o de comprar e segurar; maior queda menor que a de comprar e segurar.
- Se não passar aos 180 dias, segue até 365 dias; se falhar de novo, é descartada. Aprovada não significa dinheiro automático: o dono decide.

---

# Hipótese 3: receber funding (comprado à vista + vendido no perpétuo), Hyperliquid (registrada em 2026-11-06, antes de baixar o histórico)

## Regra (fixa, sem grade de parâmetros)
- Moedas: BTC (à vista UBTC), ETH (UETH), HYPE, SOL (USOL).
- A cada hora, por moeda: **entra** se a média do funding das últimas 72 h for positiva e, mantida por 14 dias, pagar o custo de ida e volta; **sai** se a média das últimas 72 h ficar negativa.
- Custos (documentação oficial, nível base): à vista 0,070% e perpétuo 0,045% por lado → 0,23% ida e volta. Funding conforme a documentação: pago a cada hora, sem taxa.
- Capital: cada moeda tem 1/4 do capital; posição com o perpétuo a 1x de margem, então cada US$ 1 de exposição usa US$ 2 de capital (metade à vista, metade de margem). Retornos são sobre o capital total.
- Não entram na conta: diferença de preço entre o à vista e o perpétuo (base), risco de o token à vista (UBTC, UETH, USOL) descolar do ativo original, e risco de liquidação. São riscos reais e ficam registrados como limites.

## Avaliação
- Backtest em todo o histórico disponível, só descritivo (a regra não foi ajustada a ele): retorno anual depois do custo, % de dias positivos, maior queda, e comparação com deixar o capital parado (zero).
- Teste ao vivo a partir de 2026-11-07, contabilizando o funding realmente pago hora a hora. Avaliação aos 90 dias: aprovada se o resultado acumulado for positivo e a maior queda for menor que 2% do capital.

---

# Hipótese 4: modelos de IA prontos (Chronos-Bolt, depois Kronos) preveem o BTC melhor que o acaso? (registrada em 2026-11-06, antes de rodar)
- Dados: velas de 1 min do BTCUSDT na Binance, últimos 7 dias. A cada 15 min, o modelo recebe as 512 velas anteriores (só passado) e prevê o fechamento 15 min à frente (mediana da previsão).
- Medida principal: R² fora da amostra do retorno de 15 min contra prever zero (o mesmo critério que reprovou o modelo atual, que teve −0,036 nesse horizonte).
- Secundárias: acerto de direção; resultado de operar só quando |previsão| > 0,2% (custo), comprado ou vendido, segurando 15 min.
- Passa se o R² for positivo **e** o resultado das operações for positivo depois do custo. Uma única rodada por modelo, sem ajuste.

---

# Hipótese 5: IA generativa (Gemini) lendo notícias e preço prevê o BTC em 4 h? (registrada em 2026-11-06, antes de rodar; autorizada pelo dono a usar a chave do Gemini do Gauss)
- Só daqui para frente: o modelo pode ter lido sobre o passado no treino, então backtest não vale.
- Às 00, 04, 08, 12, 16 e 20 h UTC, o modelo `gemini-3.8-flash` (temperatura 0) recebe: preço atual do BTC, retornos de 1 h, 4 h, 24 h e 7 dias, volume relativo, funding da Hyperliquid e até 12 manchetes das últimas 12 h (Google News). Responde em JSON: direção (alta/queda), confiança (0,5 a 1) e retorno esperado em %.
- Resolução: fechamento de 1 min da Binance 4 h depois. A previsão é gravada antes, com o preço da hora.
- Medidas: acerto de direção (intervalo de Wilson) contra 50% e contra "sempre alta"; resultado de operar só quando |retorno esperado| > 0,2% (custo), na direção prevista, por 4 h.
- Avaliação com 300 previsões (~50 dias): passa se o limite inferior do acerto for > 50% **e** a soma das operações depois do custo for positiva. Sem troca de prompt nem de modelo no meio; mudança zera a contagem.
- As manchetes são texto de terceiros: o modelo só devolve JSON, sem ferramentas; nada do que ele escreve é executado.
- 2026-11-06, ajuste antes da primeira previsão (a pedido do dono, "períodos menores também"): a cada 15 min UTC, uma única consulta pede três previsões: 15 min, 1 h e 4 h. Cada prazo é avaliado à parte, com o mesmo critério (300 previsões resolvidas, limite inferior do acerto > 50% e soma das operações acima do custo > 0). O preço de referência é o do momento em que a resposta chega, não o de quando a pergunta saiu, para não dar ao modelo o tempo que ele levou para pensar. Também entram no contexto os retornos de 5 e 15 min.

---

# Hipótese 5b: Gemini com as lições dos grandes traders (registrada em 2026-11-06, antes de rodar)
Base: reports/Maiores traders e metodologias.md. A versão 1 (hipótese 5) segue intocada; a 5b roda em paralelo, no MESMO contexto de cada consulta (comparação pareada).
- Instrução nova: pode se abster ("sem_posicao") quando não houver vantagem clara; a operação só faz sentido se o movimento esperado superar o custo de 0,2%; prioriza teses de horas, não de minutos; diz o que invalidaria a tese.
- Mesmos prazos (15 min, 1 h, 4 h), mesma resolução, mesmo critério (300 previsões resolvidas não abstidas por prazo; limite inferior do acerto > 50% e soma das operações acima do custo > 0). Também se compara com a v1 nas mesmas consultas.

# Robô: versões de prazo maior no aprendizado (2026-11-06)
As versões passam a combinar lado (compra/venda) × previsão mínima {0, 0,10, 0,25%} × segurar {5, 15, 30, 60, 240 min} = 30 versões. 0,25% = custo de 0,2% mais margem; 60 e 240 min seguem o padrão dos vencedores (horizontes mais longos). Versões antigas (0,05%, 0,20%) deixam de ser escolhidas; o histórico delas fica guardado.

---

# Hipótese 3b: funding com alavancagem — quanto dá para alavancar sem ser liquidado? (registrada em 2026-11-06, antes de rodar)
Motivo: o dono quer resolver a alavancagem. Ela só faz sentido sobre uma estratégia com vantagem medida; a única até agora é a 3 (funding).

## Modelo
- Mesma regra de entrada e saída da hipótese 3 (média de 72 h, recuperar o custo em 14 dias), mesmas 4 moedas, mesmos custos.
- Alavancagem L do perpétuo vendido ∈ {1, 2, 3, 5, 10}. Capital por US$ 1 de exposição = 1 (à vista) + 1/L (margem). Margem de manutenção **suposta** de 1,25% (metade da inicial a 40x; não conferida na documentação).
- A cada hora, com a MÁXIMA da vela de 1 h: se o preço subiu desde o último reequilíbrio a ponto de consumir metade da distância até a liquidação, reequilibra (vende à vista para repor a margem), pagando 0,07% sobre o valor movido e voltando ao L original. Se a máxima da hora atingir o preço de liquidação antes disso, conta como LIQUIDAÇÃO: perde a margem de manutenção, paga o custo de reentrada (0,23%) e reabre.
- Não modela: base entre à vista e perpétuo, descolamento do token à vista, atraso de execução no reequilíbrio, risco de a corretora quebrar.

## Medidas
Retorno anual sobre o capital, % de dias positivos, maior queda, número de liquidações e de reequilíbrios, por nível de L. Também a fração de Kelly estimada (média/variância diária) como referência.

## Uso
Escolher para o teste ao vivo o MAIOR L com zero liquidações em todo o histórico E maior queda menor que 2%; o resultado é descritivo (sem cofre), porque o histórico já foi visto na hipótese 3.

### Resultado da H3b (2026-11-06)

Máximas horárias: Hyperliquid nas últimas ~5000 h, Binance antes disso (outra bolsa, suposição). 4152 de 87536 horas posicionadas ficaram sem vela (HYPE antes de 30/05/2025), e nelas a liquidação não foi checada.

| L | ao ano | dias + | maior queda | liquidações | 2026 |
|---|---|---|---|---|---|
| 1x | +6,12% | 84% | −0,16% | 0 | +1,60% |
| 2x | +8,23% | 84% | −0,21% | 0 | +2,13% |
| 3x | +9,22% | 84% | −0,26% | 1 | +2,39% |
| 5x | +10,09% | 84% | −0,47% | 3 | +2,65% |
| 10x | +10,31% | 83% | −0,75% | 10 | +2,88% |

Pela regra pré-registrada, o escolhido é **2x**, que entra no ao vivo simulado junto com a H3 (mesmo início, 2026-11-07). A primeira rodada mostrava zero liquidações em todos os níveis, mas só porque faltavam velas antes de 2025. Esse erro foi corrigido antes desta tabela.

### H5/H5b: troca de modelo (2026-11-06, antes da 1ª previsão)

Nenhuma previsão foi gravada: todas as chamadas ao `gemini-3.8-flash` falharam (503 e depois 429, cota da chave esgotada). O modelo passa a ser `gemini-2.5-flash`, que respondeu no teste. Prompt, horizontes, regras e critérios continuam iguais. A contagem começa na primeira previsão gravada.

## Hipótese 6: padrões de vela e de mercado (pré-registrada em 2026-11-06, antes de qualquer cálculo)

**Pergunta:** depois de um padrão de vela ou de mercado no BTC, a chance de alta ou queda nos 15 min, 1 h e 4 h seguintes é diferente o bastante de uma moeda ao ar para pagar o custo?

- **Dados:** BTCUSDT da Binance em velas de 15 min, de 2020-01-01 até hoje. **Treino:** 2020 a 2023. **Teste:** 2024-01-01 até hoje, aberto uma única vez depois do treino.
- **Padrões (decididos no fechamento da vela, sem olhar à frente):**
  - vela: engolfo de alta, engolfo de baixa, martelo, estrela cadente, doji, três soldados, três corvos, inside bar, marubozu de alta, marubozu de baixa;
  - mercado: tendência de alta (EMA20 > EMA50 e preço acima), tendência de baixa, rompimento da máxima de 20 velas, rompimento da mínima de 20 velas, RSI14 < 30, RSI14 > 70, volume > 3× a média de 96 velas, vela de alta forte (> 3 desvios) e vela de queda forte.
- **Medidas:** para cada padrão e horizonte (1, 4 e 16 velas): número de casos sem sobreposição (um caso novo só depois de passado o horizonte do anterior), chance de alta, retorno médio e estatística t.
- **Passa** quem cumprir as três condições:
  1. no treino, |retorno médio| > 0,2% (custo de ida e volta) e |t| > 3,2 (correção para cerca de 57 testes);
  2. no teste, o mesmo sinal, com |retorno médio| > 0,2% e |t| > 2;
  3. pelo menos 30 casos em cada período.
- **Uso:** a tabela de cada padrão ativo vai para o contexto da versão 2 do Gemini, com os números de treino e de teste e a marca passou/não passou. O robô só usa padrões que passaram. Se nenhum passar, o resultado é esse, e ele fica registrado.
