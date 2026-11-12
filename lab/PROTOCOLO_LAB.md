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

### Resultado da H6 (2026-11-06)

Passaram **0 de 57** combinações de padrão e prazo. A tabela completa está em `dados/padroes.txt`.

- **Efeitos reais, mas pequenos:** alguns padrões repetem o mesmo efeito no treino e no teste, sempre de reversão curta:
  - três corvos → alta em 15 min: +0,018% (t 4,5) no treino, +0,010% (t 3,6) no teste;
  - martelo → queda em 15 min: −0,014% e −0,009%;
  - três soldados → queda em 15 min: −0,009% e −0,007%;
  - rompimento da mínima de 20 velas → alta em 4 h: +0,10% e +0,06%.
- **Por que ninguém passou:** todos os efeitos ficam entre 4 e 20 vezes abaixo do custo de 0,2%. "Rompimento da máxima", que é o padrão clássico de compra, deu zero.
- **Desdobramento:** a tabela vai para o contexto da versão 2 do Gemini a partir de 2026-11-06 ~20h (horário de Brasília), e a comparação pareada da v2 conta a partir daí. O robô não usa nenhum padrão, porque nenhum passou.
- **Ideia para o futuro, não pré-registrada:** com custo de ordem limitada (maker, ~0,03% ida e volta na Hyperliquid), três corvos em 4 h (+0,044% no teste) ficaria acima do custo. Isso exigiria uma hipótese nova, com simulação de preenchimento de ordem limitada.

## Hipótese 6-WIN: padrões no mini índice (pré-registrada em 2026-11-06, antes de rodar)

- **Mesmos 19 padrões, horizontes e regras da H6**, aplicados ao WIN1! (contrato contínuo do mini índice, B3) em velas de 15 min, rodando no TradingView pelo script `lab/padroes_win.pine`.
- **Dados:** treino na primeira metade das velas que o TradingView liberar e teste na segunda metade. O histórico é bem mais curto que o do BTC (limite de velas da conta), e isso será registrado.
- **Custo assumido:** 15 pontos na ida e volta (1 tick de escorregamento de cada lado, ~10 pontos, mais corretagem e emolumentos). Esse valor ainda não foi conferido nas tabelas da B3 e da corretora, e precisa ser antes de qualquer uso real.
- **Ressalvas:** a rolagem do contrato contínuo cria saltos de preço. Velas que atravessam a noite também entram na conta, e no horizonte de 4 h isso pode misturar dois pregões.

### Resultado da H6-WIN (2026-11-06/07): inconclusivo

- **TradingView:** o script compilou e entrou no gráfico WIN1! 15 min, mas não calculou nada. Tabela, logs e valores da legenda vieram vazios, até um `plot(bar_index)` de teste, e nenhum erro foi mostrado. A causa não foi identificada (talvez limite da conta grátis ou dos dados da B3 para scripts).
- **Substituto (não é o pré-registrado):** Ibovespa à vista (^BVSP, Yahoo), velas de 15 min de 2026-08-12 a 2026-11-06 (1679 velas), metade para treino e metade para teste, custo de 15 pontos (~0,009%). Resultado: **0 de 54 passaram**. Os padrões que pareciam fortes no treino inverteram o sinal no teste (ex.: rompimento da mínima de 20 velas em 4 h: +0,85% no treino, −0,66% no teste). Com 5 a 50 casos por padrão, a amostra é pequena demais para concluir, e o horizonte de 4 h atravessa a noite.
- **Para um teste de verdade:** é preciso um histórico intradiário longo do WIN (anos), de corretora/MetaTrader ou de um fornecedor de dados da B3.

## Hipótese 6-WINb: padrões no índice com dados abertos (pré-registrada em 2026-11-07, antes de rodar)

O TradingView não calculou, e o histórico intradiário do WIN não é gratuito. Para substituir, duas fontes abertas com as mesmas regras da H6 (padrões, |t| > 3,2 no treino e > 2 no teste, mesmo sinal, 30 casos ou mais, efeito acima do custo):

1. **Ibovespa ^BVSP (Yahoo), velas de 1 h, 2023-12 a hoje.** Horizontes de 1, 4 e 7 velas (1 h, 4 h, ~1 pregão). Treino na primeira metade, teste na segunda. Custo de 15 pontos.
2. **WIN real, negócio a negócio, do arquivo público da B3** (`arquivos.b3.com.br/rapinegocios/tickercsv/AAAA-MM-DD`, só os últimos ~20 pregões). Velas de 1 min do contrato mais negociado em cada dia, só no pregão regular. Horizontes de 1, 5 e 15 velas. Treino na primeira metade dos dias, teste na segunda. Custo de 15 pontos.

A partir de agora, um coletor diário guarda as velas de 1 min do WIN, para o histórico crescer e permitir repetir o teste com mais dados.

## Hipótese 7: a "linguagem" do fluxo antecipa o preço? (pré-registrada em 2026-11-07, antes de qualquer dado)

O tradutor do painel ao vivo grava a cada 5 min, para o BTC na Binance, o volume agressor de compra e de venda, as liquidações de comprados e vendidos, o book a ±0,2% e as maiores paredes até ±0,5%, junto com o preço (`dados/leitura_mercado.jsonl`).

- **Pergunta:** o saldo agressor (compra − venda), o desequilíbrio do book e as liquidações de uma janela antecipam o retorno dos 5, 15 e 60 min seguintes?
- **Medida:** regressão fora da amostra (prequencial), como na pesquisa de minutos, com o R² comparado contra prever zero. Também uma regra simples: seguir o sinal do saldo, com custo de 0,2% na ida e volta.
- **Avaliação:** com 2000 janelas (~7 dias contínuos). Passa se o R² fora da amostra for maior que 0 com intervalo que não inclua 0 **e** a regra simples der lucro depois do custo.
- **Enquanto não passar:** as leituras são só descrição, não sinal de entrada.

## Hipótese 8: rede recorrente com memória de longo prazo (LSTM) no BTC (pré-registrada em 2026-11-07, antes de treinar)

- **Dados:** BTCUSDT da Binance, velas de 15 min de 2020 até hoje (o mesmo cache da H6).
- **Entrada:** sequência das últimas 64 velas (16 h). Por vela: retorno, faixa máxima−mínima, corpo, log do volume relativo à média de 96 velas, hora do dia (seno/cosseno) e os 19 padrões da H6 como 0/1.
- **Alvo:** retorno das próximas 1, 4 e 16 velas (15 min, 1 h, 4 h), uma saída para cada.
- **Rede:** LSTM de 2 camadas e 32 unidades, com dropout 0,2, treinada com Adam e erro quadrático, pouca memória porque a máquina tem 3 GB.
- **Divisão no tempo, sem embaralhar:**
  - treino: 2020 a 2022;
  - validação: 2023, usada só para parar o treino cedo;
  - teste: 2024 até hoje, aberto uma única vez.
- **Comparações:** prever zero, e regressão linear com as mesmas entradas da última vela.
- **Passa** se, no teste, cumprir as três condições:
  1. R² fora da amostra > 0, com intervalo bootstrap por blocos de 95% acima de 0;
  2. acerto de direção > 50%, com o intervalo de Wilson acima de 50%;
  3. a regra "operar só quando |previsão| > 0,2%, no sentido previsto" dar lucro depois de 0,2% de custo, com pelo menos 100 operações.

## Hipótese 9: tom das notícias (PLN do GDELT) antecipa o BTC? (pré-registrada em 2026-11-07, antes de baixar)

- **Dados:** o "Average Tone" do GDELT para a busca "bitcoin" (sentimento calculado pelo GDELT sobre notícias do mundo todo), a cada 15 min, nos últimos ~3 meses (a API só guarda isso). Baixado em janelas de 2 dias, com 6 s entre pedidos.
- **Medidas:** o tom e a variação dele em 1 h (4 pontos) contra o retorno do BTC nos próximos 15 min, 1 h e 4 h. Correlação com estatística t, treino na primeira metade e teste na segunda.
- **Passa** com o mesmo sinal nas duas metades, |t| > 3,2 no treino e > 2 no teste, **e** a regra (comprar se o tom subir, vender se cair) dando lucro depois de 0,2%.

### Resultado da H8 (2026-11-07): LSTM não passou

| Prazo | R² no teste [IC 95%] | Linear | Acerto de direção [IC] | Regra (\|prev.\| > 0,2%) |
|---|---|---|---|---|
| 15 min | −0,0010 [−0,0016, −0,0003] | −0,0017 | 50,4% [50,1%, 50,7%] | 0 operações |
| 1 h | −0,0026 [−0,0046, −0,0003] | −0,0004 | 49,9% [49,6%, 50,3%] | 33 op., +0,54% (abaixo do mínimo de 100) |
| 4 h | −0,0099 [−0,0152, −0,0040] | −0,0030 | 50,0% [49,7%, 50,3%] | 1136 op., −0,14% |

- **Treino:** a validação só ficou abaixo de "prever zero" na época 2 (0,31156 contra 0,31240), por 0,3%, e o treino parou na época 5.
- **Teste (2024–2026, ~100 mil velas):** a rede previu pior que zero nos três prazos, com o intervalo inteiro abaixo de 0. É o mesmo resultado do Chronos e da regressão de minutos: o histórico de preço e volume de 15 min do BTC não carrega informação que uma rede recorrente consiga extrair a ponto de pagar o custo.

## Hipótese 10: Tartarugas em cripto, perder pouco e ganhar muito (pré-registrada em 2026-11-07, antes de rodar)

Regras do Sistema 2 das Tartarugas (Dennis/Eckhardt), adaptadas para cripto diário:

- **Universo:** BTC, ETH, BNB, XRP, ADA, DOGE, LTC, LINK, TRX e SOL, em velas diárias da Binance desde a listagem.
- **Volatilidade:** N = ATR de 20 dias (média de Wilder do *true range*).
- **Entrada comprada:** fechamento acima da máxima dos 55 dias anteriores. **Entrada vendida:** fechamento abaixo da mínima dos 55 dias anteriores. Executa na abertura do dia seguinte.
- **Stop inicial:** 2N contra a posição. É a perda pequena, sempre igual a 1R.
- **Saída:** comprado sai quando fecha abaixo da mínima de 20 dias; vendido, acima da máxima de 20 dias. Executa na abertura seguinte. É o que deixa o vencedor correr.
- **Tamanho:** risco de 1% do capital por posição (nocional = 1% × capital ÷ 2N × preço), uma posição por moeda, alavancagem total limitada a 3×.
- **Custos:**
  - 0,10% por lado;
  - 0,02% ao dia sobre o nocional, para os dois lados (financiamento/funding);
  - se o stop é furado na abertura, sai pela abertura.
- **Períodos:** treino de 2018 a 2023, teste de 2024-01-01 até hoje. (Atenção: parte do teste coincide com o cofre da H1, aberto em 2024-11-06, que já mostrou tendência positiva em cripto.)
- **Métricas:**
  - retorno anual, maior queda, % de acertos;
  - ganho médio e perda média em R, expectativa em R, *profit factor*;
  - % de meses positivos e o pior mês.
- **Passa** se cumprir no teste:
  1. expectativa > 0,2R;
  2. *profit factor* > 1,3;
  3. pelo menos 30 operações;
  4. maior queda < 35%;
  5. o treino também com expectativa > 0.

### Resultado da H10 (2026-11-07)

| Variante | Período | Op. | Ao ano | Queda máx. | Acerto | Ganho/perda médios | Expectativa | PF |
|---|---|---|---|---|---|---|---|---|
| Compra e venda (pré-registrada) | treino | 284 | +42,5% | −67,6% | 27% | +9,17R / −0,95R | +1,83R | 3,64 |
| Compra e venda (pré-registrada) | teste | 154 | +11,9% | **−36,8%** | 32% | +2,77R / −0,89R | +0,30R | 1,50 |
| Só compra (**não** pré-registrada) | treino | 160 | +47,0% | −64,9% | 22% | +18,20R / −0,98R | +3,34R | 5,40 |
| Só compra (**não** pré-registrada) | teste | 94 | +14,6% | −32,7% | 29% | +4,33R / −0,96R | +0,56R | 1,83 |

- **Pré-registrada:** **não passou**, só pela queda máxima (−36,8% contra o limite de −35%). Expectativa e PF passaram.
- **Só compra:** cumpre todos os critérios, mas foi escolhida depois de ver os números. Vale como **hipótese nova (H10b)**, a confirmar ao vivo.
- **H10b ao vivo:** carteira simulada de US$ 700, spot, sem alavancagem, 1% de risco por operação, a partir de 2026-11-07 (`dados/tartaruga_vivo.json`, painel /ao-vivo). Avaliação com 30 operações fechadas ou 180 dias. Passa se a expectativa for > 0 e o PF > 1,3.
- **Para lembrar:** a queda máxima histórica de 33–65% é o preço do "ganhar muito". Com 1% de risco por operação e 10 moedas, quedas longas são esperadas.

### Leis medidas (lab/fisica.py, 2026-11-07)

- **Memória por escala (razão de variância de Lo-MacKinlay):**
  - BTC intradiário: VR 0,985 (30 min), 0,967 (1 h, z −2,2), 0,940 (4 h, z −2,2), 0,929 (1 dia, base 15 min). É reversão fraca.
  - Diário, 20/60 dias: BTC 1,09/1,27, ETH 1,08/1,19, SOL 1,16/1,57 (60 d z +2,4). É tendência em semanas.
- **Caudas:** curtose 120 em 15 min e 19 no diário; índice de cauda α 2,7 (15 min) e 4,2 (diário).
- **Previsibilidade fora da amostra (teste 2024+):** volatilidade de amanhã (HAR-RV) R² 0,442; direção de amanhã (AR(1)) R² 0,002.
- **Consequência:** o robô de minutos opera numa escala sem memória aproveitável, contra 0,2% de custo; as 8 operações perderam em média −0,41%. A vantagem possível está em semanas (tendência) e no tamanho da posição (volatilidade previsível).

## Hipótese 11: Tartaruga só compra, spot 1×, com risco ajustado pela volatilidade prevista (pré-registrada em 2026-11-07, antes de rodar)

- **Base:** as regras da H10, só compra, com alavancagem máxima de **1×** (spot, igual ao ao vivo).
- **Variação:** o risco por operação passa a ser 1% × min(1, 20% ÷ σ̂), com σ̂ = volatilidade anualizada da própria carteira (EWMA, λ = 0,94, sobre os retornos diários). Em fase turbulenta arrisca menos; nunca arrisca mais que 1%.
- **Comparação:** a mesma carteira sem o ajuste (H10b a 1×), nos mesmos períodos (treino 2018–2023, teste 2024–hoje).
- **Passa** se, no treino **e** no teste, a maior queda for menor que a da base **e** o retorno/queda (Calmar) for maior que o da base, com a expectativa em R ainda > 0. Se passar, o robô ao vivo usa a versão com ajuste.

### Resultado da H6-WINb (2026-11-07)

- **^BVSP 1 h (dez/2023–nov/2026):** 0 de 54. **BOVA11 1 h:** 0 de 57.
- **WIN real, negócio a negócio da B3:** 15 pregões completos (08/10 a 06/11; os dias incompletos foram descartados), 8453 velas de 1 min. **0 de 57.** Nenhum padrão teve |t| > 1,1 no treino. No teste, os maiores t ficaram em ~2,0–2,3, com sinais opostos aos do treino.
- **Conclusão:** nos dados disponíveis, padrões de vela não mostraram vantagem também no índice, mesmo com custo de ~0,008%. O coletor diário da B3 pode estender a amostra (espera autorização do usuário).

### H10c: as mesmas regras em moedas novas (2026-11-07)

- **Moedas:** as 40 de maior volume em USDT na Binance, fora as 10 originais e as estáveis, com dados desde antes de 2024-06. Sobraram 23 (AAVE, ARB, AVAX, BCH, CELO, CYBER, ENA, FET, GTC, HBAR, INJ, LSK, NEAR, NFP, ONE, PEPE, QNT, SUI, TAO, UNI, WLD, XLM, ZEC), que nunca tinham sido usadas.
- **Regras:** H10b sem nenhuma alteração (só compra, 1×).
- **Resultado no teste 2024–hoje:**
  - 10 originais: 82 op., +12,6%/ano, queda −30,2%, expectativa +0,53R, PF 1,76;
  - 23 novas: 152 op., +27,3%/ano, queda −40,3%, expectativa +0,57R, PF 1,77;
  - todas as 33: 163 op., +25,8%/ano, queda −41,4%, expectativa +0,62R, PF 1,87.
- **Leitura:** a vantagem por operação se repetiu em ativos independentes. Viés: a escolha pelo volume de hoje deixa de fora moedas que morreram (sobrevivência).
- **Decisão:** o robô passa a operar as 33. A queda histórica esperada é de ~40%.

## Hipótese 12: custo em R decide o intervalo (pré-registrada em 2026-11-09, antes de rodar)

- **Motivo, da matemática:** cada operação paga ~0,2% de ida e volta. Medido em unidades de risco (R = distância do stop = 2N), o custo é 0,2% ÷ (2N/preço). No diário, 2N/preço fica em 6–14%, então o custo é 0,02–0,03R. Em 1 h fica em ~0,3%, e o custo chega a ~0,67R.
- **Regra testada:** as mesmas da H10b, mais um filtro: **só entra se 2N/preço ≥ 2%** (custo ≤ 0,1R). O limiar vem da conta acima e não foi ajustado nos dados.
- **Onde:** 4 h, 1 h e 15 min, nas 33 moedas, separando 2024 e 2025–hoje.
- **Passa** um intervalo se, **nos dois períodos**, a expectativa for > +0,2R e o PF > 1,3, com pelo menos 30 operações em cada. O robô rápido ao vivo passa a usar o intervalo aprovado com o filtro. Se nenhum passar, o robô rápido continua só como demonstração.

### Resultado da H12 (2026-11-09): não passou

| Intervalo | Filtro 2N/preço ≥ 2% | 2024 | 2025–hoje |
|---|---|---|---|
| 4 h | não | 200 op, +287%, +1,14R, PF 2,85, queda −39% | 389 op, −24%, +0,00R, PF 1,00, queda −50% |
| 4 h | sim | 198 op, +155%, +0,94R, PF 2,45, queda −36% | 383 op, −14%, +0,05R, PF 1,06, queda −49% |
| 1 h | não | 612 op, −3,9%, +0,10R, PF 1,14, queda −55% | 978 op, +167%, +0,22R, PF 1,30, queda −58% |
| 1 h | sim | 680 op, −22,7%, +0,08R, PF 1,11, queda −65% | 1010 op, +259%, +0,26R, PF 1,37, queda −58% |

- **4 h:** muito bom em 2024 e nulo de 2025 para cá. O filtro não muda o quadro, porque em 4 h o stop já passa de 2% quase sempre.
- **1 h:** positivo por operação nos dois períodos, mas fraco em 2024, e as quedas no caminho são enormes.
- **Nenhum combina** expectativa > 0,2R e PF > 1,3 nos dois períodos. O robô rápido continua como demonstração ao vivo (1 h, sem filtro). O real segue só no diário.
- **15 min:** pendente (download em andamento).

## Hipótese 13: teto de posições abertas (pré-registrada em 2026-11-09, antes de rodar)

- **Motivo:** as moedas são muito correlacionadas, então N posições de 1R funcionam quase como uma posição de N R. As Tartarugas originais limitavam as unidades abertas em mercados correlacionados.
- **Regra:** H10b (só compra, 1×, 33 moedas), com no máximo **6 posições abertas ao mesmo tempo**. Quando há mais sinais que vagas, entram as primeiras da ordem de varredura, sem escolha pelos dados.
- **Períodos:** treino 2018–2023 e teste 2024–hoje, no robô diário.
- **Passa** se, nos dois períodos, a maior queda for menor que a da base **e** o Calmar (retorno anual ÷ maior queda) for maior que o da base. Se passar, o robô diário e o rápido adotam o teto.

### Resultado da H13 (2026-11-09): não passou, por 0,01 de Calmar no teste

| | Treino 2018–23 | Teste 2024–hoje |
|---|---|---|
| Base | +56,3%/ano, queda −64,6%, Calmar 0,87, +2,62R, pior mês −23,7% | +26,3%/ano, queda −41,9%, Calmar 0,63, +0,56R, pior mês −20,4% |
| Teto 6 | +51,0%/ano, queda **−34,6%**, Calmar **1,47**, +2,36R, pior mês −16,2% | +23,8%/ano, queda −38,5%, Calmar **0,62**, +0,74R, pior mês −14,0% |

- **O que melhorou:** a queda caiu nos dois períodos (no treino, quase pela metade). Expectativa, PF e pior mês melhoraram no teste.
- **Por que não passou:** o Calmar do teste ficou 0,01 abaixo da base, e o critério pedia Calmar maior nos dois períodos. Não passou, e o robô continua sem teto.
- **Próximo passo:** a evidência a favor do teto vira candidata a validação **ao vivo**, em paralelo, sem mexer no robô oficial.

## Hipótese 14: reversão probabilística intradiária (pré-registrada em 2026-11-10, antes de rodar)

- **Motivo, da medição física:** a razão de variância é < 1 de 30 min a 1 dia (reversão; z ≈ −2,2 em 1 h e 4 h). Depois de uma queda anormal, parte dela tende a voltar.
- **Sinal:** em velas de 5 min, para cada uma das 33 moedas, z = retorno da última hora ÷ (desvio dos retornos de 5 min nas últimas 24 h × √12). Compra quando **z ≤ −2,5**.
- **Saída:** fechamento depois de **12 velas (1 h)** ou **48 velas (4 h)**, medindo as duas. Custo de 0,2% na ida e volta. Uma operação por moeda de cada vez, sem sobreposição.
- **Dados:** os últimos 60 dias de velas de 5 min (`dados/lab/cripto_5m.json`). **Treino:** primeira metade. **Teste:** segunda metade.
- **Passa** um horizonte se, nas duas metades, o retorno médio líquido for > 0 **e** o t do teste for > 2, com pelo menos 100 operações em cada metade.
- **Se passar:** o robô rápido troca para esta regra, com a probabilidade de acerto atualizada ao vivo (Beta bayesiana) e entrada só quando o ganho esperado líquido for > 0. **Se não passar,** registrar o resultado e não usar.

### Resultado da H14 (2026-11-10): não passou

| Horizonte | Treino | Teste |
|---|---|---|
| 1 h | 652 op., −0,175% líquido, t −2,44, acerto 45% | 845 op., −0,237%, t −4,83, acerto 43% |
| 4 h | 551 op., −0,203%, t −1,85, acerto 45% | 678 op., −0,308%, t −3,09, acerto 47% |

- **Bruto:** a reversão rende de +0,03% (1 h) a −0,1% (4 h) por operação, muito abaixo do custo de 0,2%.
- **Conclusão:** a reversão intradiária medida pela física é real, mas é pequena demais para pagar o custo de ida e volta.

## Hipóteses 15, 16 e 17: vantagens que não dependem de adivinhar a direção (pré-registradas em 2026-11-10, antes de rodar)

**H15 — força relativa (momentum entre moedas), só compra, spot.**
- A cada 7 dias, ordena as 33 moedas pelo retorno dos 28 dias anteriores, pulando o último dia, e fica com as **5 mais fortes**, em pesos iguais.
- Filtro de regime: se o BTC fechar abaixo da média de 100 dias, fica 100% em dólar.
- Custo de 0,1% por lado sobre o que gira.
- Treino 2018–2023, teste 2024–hoje e réplica no grupo 3 (31 moedas menores).
- **Passa** se, no treino e no teste, render mais que comprar e segurar BTC **e** tiver maior queda menor que a do BTC.

**H16 — sazonalidade por hora e por dia da semana.**
- Velas de 1 h das 33 moedas, 2024–hoje. Retorno médio por hora UTC e por dia da semana. Treino 2024, teste 2025–hoje.
- **Passa** uma hora (ou dia) se a média tiver o mesmo sinal nos dois períodos, com |t| > 3 no treino e > 2 no teste, **e** a regra "estar comprado só nessas horas" pagar 0,2% por entrada e saída.

**H17 — funding extremo como sinal contrário.**
- BTC, ETH, SOL e HYPE, com funding de hora em hora da Hyperliquid desde 2023 e preço diário da Binance.
- Sinal: a média de funding das últimas 24 h entre as 10% mais negativas do treino (medo extremo) → compra por 3 dias.
- Treino até 2024-12-31, teste 2025–hoje.
- **Passa** se o retorno médio líquido de 0,2% for > 0 nos dois períodos, com t > 2 no teste e pelo menos 20 sinais em cada.

### Resultados de H15, H16 e H17 (2026-11-10): nenhuma passou

- **H15 (força relativa, top 5 de 28 dias, filtro BTC > MM100):**
  - 33 moedas, treino: +141,6%/ano, queda −51,2% (BTC parado: +21,1%, −81,2%);
  - 33 moedas, teste: +46,9%/ano, **queda −59,5%** (BTC: +20,3%, −53,0%);
  - grupo 3: **−17,3%/ano**, queda −81,7%.
  - Não passou: a queda no teste foi pior que a do BTC, e no grupo de moedas menores perdeu. Repete o padrão das Tartarugas: a vantagem existe nas moedas grandes e some nas pequenas.
- **H16 (sazonalidade):** a primeira medida contou cada moeda em cada hora como observação independente. As moedas se movem juntas, então os t estavam inflados (o próprio critério pré-registrado herdou o erro). Refeito com **um retorno de carteira por dia**: nenhum dia da semana tem |t| ≥ 2 (o maior foi quarta no teste, t +1,51). A regra "comprado só qua/sex/sáb" ficou +0,34%/dia em 2024 (t 1,07) e +0,19%/dia em 2025+ (t 0,88), indistinguível do acaso. Não passou. As horas sofrem da mesma inflação e não serão usadas.
- **H17 (funding extremo negativo → compra por 3 dias):** treino com 84 sinais, +0,87% (t 1,37); teste com 140 sinais, −0,35% (t −0,72). Não passou.

## Hipótese 18: Vórtice + CHOP preveem a próxima vela do BTC? (pré-registrada em 2026-11-10, antes de rodar)

- **Origem:** um artigo que atribui +US$ 319 mil no Polymarket (mercados BTC Sobe/Desce) a esta combinação.
- **Indicadores**, com n = 14:
  - VI⁺ = Σ|Hₜ − Lₜ₋₁| / ΣTR e VI⁻ = Σ|Lₜ − Hₜ₋₁| / ΣTR;
  - CHOP = 100 × log₁₀(ΣTR / (Hmax − Lmin)) / log₁₀(n).
- **Sinal:** quando CHOP < 38,2 (limiar usual), aposta "sobe" se VI⁺ > VI⁻ e "desce" se VI⁻ > VI⁺, sempre para a **próxima vela**.
- **Dados:** BTC 15 min, com treino 2020–2023 e teste 2024–hoje; BTC 5 min, nos últimos 60 dias, divididos em duas metades.
- **Passa** se o acerto de direção for ≥ 53% com o limite inferior de Wilson (95%) > 51% **nos dois períodos**. Num mercado binário pago a ~US$ 0,50–0,52, abaixo disso o spread come o ganho. Com CHOP ≥ 38,2 não há aposta.

### Resultado da H18 (2026-11-10): não passou — o sinal é **anti-preditivo**

| | Apostas | Acerto | IC 95% |
|---|---|---|---|
| 15 min treino 2020–23 | 14.554 | 47,81% | 47,00–48,62% |
| 15 min teste 2024+ | 13.175 | 47,66% | 46,81–48,51% |
| 5 min 1ª metade (60 d) | 2.056 | 46,16% | 44,01–48,32% |
| 5 min 2ª metade | 2.099 | 47,12% | 44,99–49,26% |

- **Leitura:** seguir o Vórtice com CHOP < 38,2 erra mais do que acerta, de forma consistente. É o mesmo fenômeno da razão de variância < 1: reversão em minutos e horas.
- **Sobre o artigo:** o resultado de +US$ 319 mil não vem deste sinal.

## Hipótese 19: Vórtice **invertido** (descoberta depois de ver a H18 — só vale validação daqui para a frente)

- **Regra:** igual à H18, apostando na direção **oposta**. No histórico, isso dá ~52,2–52,3% em 15 min e ~52,9–53,8% em 5 min, mas foi visto depois dos dados e por isso não conta como prova.
- **Validação ao vivo**, desde 2026-11-10: a cada vela de 15 min do BTC fechada, registrar a previsão e conferir na próxima. Fica no painel.
- **Passa** com ≥ 300 apostas ao vivo e acerto com limite inferior de Wilson > 51%.

## Hipótese 20: o cérebro (sinapses + rede neural + criação/poda de rotas) ganha no BTC 15 min? (pré-registrada em 2026-11-10)

- **O que é:** `baleias/cerebro.py`. Sete sinapses iniciais vindas do laboratório (inclui uma MLP 16→12→1 com retropropagação a cada vela) e votação por pesos multiplicativos (Hedge).
- **Rotas novas:** quando o acerto das últimas 200 apostas tem limite superior de Wilson < 52%, nascem novas sinapses em observação. Promoção com ≥ 150 previsões e limite inferior de Wilson > 50%; poda com acerto < 48%.
- **Aposta:** só quando o valor esperado passa do custo de 0,09%. Opera comprado ou vendido, 1×, teto de perda de US$ 100/dia.
- **Aquecimento:** as ~2000 velas anteriores ao início são vividas em sequência (prevendo antes de ver), mas **não contam** para a avaliação.
- **Avaliação ao vivo**, desde 2026-11-10: passa com ≥ 500 apostas ao vivo, retorno líquido médio > 0 com t > 2 **e** acerto com limite inferior de Wilson > 50%.
- **Ajuste antes de qualquer aposta ao vivo (2026-11-10):** no aquecimento, o cérebro não apostou nenhuma vez. Num contrato linear, 15 min mexem ~0,16% e o custo é ~0,09%, o que exigiria ~78% de acerto. O cérebro passa a operar **contratos binários simulados** de 15 min (paga 0,51, recebe 1 se acertar, 2% do capital por aposta), com probabilidade calibrada pelo acerto real de cada sinapse, encolhido em direção a 50% (Beta 20/20). Aposta só com ≥ 53% para um lado. Critério de passagem: ≥ 500 apostas ao vivo, limite inferior de Wilson do acerto > 51%. O acesso ao Polymarket a partir do Brasil não está resolvido (não contornar bloqueio), então fica só em simulação.
- **Ajuste 2 (2026-11-10, ainda com 0 apostas ao vivo):** com o limiar de 53%, o cérebro nunca apostava. A probabilidade calibrada é dominada pela rede neural (52,9% em 1.510, encolhido para ~52,8%). O equilíbrio do contrato a 0,51 é 51%, então o limiar passa a **52%** (1 ponto de margem). A avaliação continua contando só apostas ao vivo a partir daqui.
- **Pausa da máquina (00:00–10:42 BRT de 2026-11-10):** a vela pendente foi conferida com o preço depois da pausa, sem aposta. Corrigido: agora o cérebro revive as velas perdidas em sequência.

## Hipótese 21: os mecanismos do cérebro humano melhoram o cérebro? (v2 contra v1, pré-registrada em 2026-11-10)

- **Base:** `docs/CEREBRO_HUMANO.md`. O v2 acrescenta ao v1:
  - dopamina: reforço pelo erro de previsão de recompensa, com o tamanho do movimento;
  - hipocampo e sono diário: reencena 3000 episódios;
  - homeostase: teto de 40% do voto e compressão no sono;
  - esquecimento: placar com meia-vida de 300;
  - surpresa que acelera o aprendizado;
  - metacognição: abstém-se se o limite superior de Wilson das últimas 60 apostas < 50%.
- **Mesmas condições:** mesmas velas (BTC 15 min), mesmo contrato binário simulado (0,51, 2% por aposta, limiar 52%), rodando lado a lado no GitHub a cada 15 min.
- **Placar ao vivo de cada um** começa no fim do próprio aquecimento: v1 em 2026-11-10 03:30 UTC; v2 na primeira rodada na nuvem.
- **Avaliação:** quando os dois tiverem ≥ 300 apostas ao vivo. O v2 **vence** se o resultado líquido acumulado for maior **e** o acerto também for maior. Se só um dos dois for maior, empate, e continua. Cada um também precisa vencer a referência "sempre sobe" nas próprias apostas.

## Hipótese 22: o cérebro aplicado ao robô rápido (2026-11-10, pedido do dono)

- **O que é:** o robô rápido deixa o rompimento puro e passa a entrar pelo `CerebroRapido`. São as mesmas sinapses do cérebro (rede neural, reversão, padrões, rompimento, rotas criadas), aprendendo com as 33 moedas em velas de 5 min, com previsão de "sobe na próxima 1 h" conferida 12 velas depois.
- **Entrada:** compra se o valor esperado for (2p − 1) × 0,8 × desvio × √12 − 0,2% > 0, nas maiores primeiro, com US$ 5 por operação na conta de US$ 10.
- **Saída:** stop 2N ou 1 h.
- **Aquecimento:** ~880 velas × 33 moedas, que não conta.
- **Avaliação:** pela mesa proprietária (regras da fase 1). Ressalva matemática: com custo de 0,2% e movimento típico de ~0,8%/h, o valor esperado só fica positivo com p ≳ 62%.

## Hipótese 23: método de Oliver Velez (pré-registrada em 2026-11-10, antes de rodar)

- **Fontes:** secundárias (scripts e resumos públicos). O livro "Tools and Tactics for the Master Day Trader" não foi lido.
- **Regras**, com médias simples de 20 e 200 (SMA20, SMA200):
  1. **180 de alta:** vela anterior de baixa, vela atual de alta engolindo o corpo da anterior, e preço > SMA20 > SMA200. **180 de baixa:** o espelho disso.
  2. **Estado estreito com rompimento:** |SMA20 − SMA200| / preço < 1,2%, inclinação da SMA20 (últimas 10 velas) < 0,3%, e vela elefante (amplitude > 2× a média das 20 anteriores) fechando acima (alta) ou abaixo (baixa) das duas médias.
  3. **Vela elefante a favor do quadro:** amplitude > 2× a média de 20, no sentido do quadro de força (alta: fecha acima e preço > SMA20 > SMA200).
  4. **Espaço duplo (contrário):** preço > 3% acima das duas médias → aposta queda; > 3% abaixo → aposta alta.
- **Medidas:** retorno nas 1, 4 e 12 velas seguintes, e acerto de direção.
  - BTC em 15 min: treino 2020–23, teste 2024+.
  - 33 moedas em 5 min: 60 dias, divididos em duas metades.
- **Passa (operar no spot)** com |média| > 0,2% e t > 3,2 no treino, mais o mesmo sinal com > 0,2% e t > 2 no teste.
- **Passa (contrato binário)** com acerto ≥ 53% e limite inferior de Wilson > 51% nos dois períodos.
- **Nos cérebros:** as regras entram nos cérebros como sinapses **em observação**, qualquer que seja o resultado. Só ganham voto se provarem acerto ao vivo.

### Resultado da H23 (2026-11-10)

- **180, vela elefante a favor e estado estreito:** sem vantagem nas duas bases. A média fica ~0%, e o acerto fica abaixo de 50% (em parte porque velas sem movimento contam como erro).
- **Espaço duplo, a 1 h** (contrário: preço > 3% longe das duas médias → volta): **passou no critério binário nas duas bases**.
  - BTC 15 min: 58,0% (562 casos, treino) e 64,5% (110, teste).
  - 33 moedas 5 min: 56,9% (757) e 57,2% (472).
- **No spot, não passou:** a cauda é pesada. Nas moedas, a média no treino foi −0,41%, porque quando o esticamento continua, continua muito.
- **Aplicado:** as 6 regras entraram como sinapses **em observação** nos três cérebros (v1, v2 e o do robô rápido). Elas só ganham voto se provarem ao vivo (≥ 150 previsões, limite inferior de Wilson > 50%). Os cérebros passam a enxergar 220 velas.

### H22 revisada (2026-11-10, pedido do dono): robô rápido nos dois sentidos e com autoconhecimento

- **Perpétuo simulado:** o robô compra ou **vende a descoberto**, o que tiver maior valor esperado, com custo de 0,1% na ida e volta (0,05% por lado). No modo real a venda a descoberto é recusada, porque exige conta de futuros.
- **Autoconhecimento**, a partir das próprias operações fechadas:
  - calibração por faixa de probabilidade, corrigindo a probabilidade com peso 10 para a previsão;
  - lado com ≥ 10 operações e limite superior de Wilson < 50% passa a exigir +0,1% de valor esperado;
  - moeda com ≥ 6 operações e ≤ 20% de acerto vai para a geladeira por 24 h.
- **Avaliação:** pela mesa proprietária.

## Hipótese 24: saídas de scalper (alvo e stop fixos curtos) (pré-registrada em 2026-11-10, antes de rodar)

- **Método** (fontes em `MELHORIAS.md`): alvo fixo pequeno, stop curto e tempo máximo curto. Equilíbrio de acerto = (stop + custo) ÷ (alvo + stop).
- **Entradas testadas:** (a) espaço duplo do Velez (contrário, passou no binário na H23); (b) **aleatória** (comprar ou vender ao acaso, uma a cada 12 velas por moeda), como referência.
- **Saídas:** pares (alvo, stop) de (0,3%, 0,3%), (0,5%, 0,5%), (0,8%, 0,4%) e (1,0%, 0,5%), com no máximo 6 velas (30 min). Se alvo e stop cabem na mesma vela, conta o **stop** (conservador). Custo de 0,1% na ida e volta (perpétuo).
- **Dados:** 33 moedas, velas de 5 min, 60 dias, divididos em duas metades.
- **Passa** um par se o resultado líquido médio for > 0 com t > 2 **nas duas metades**. O robô rápido adota o par aprovado. Se nenhum passar, o resultado fica registrado, e as saídas de scalper são aplicadas só se o dono quiser, sabendo do número.

### Resultado da H24 (2026-11-10): não passou, nenhum par

- **Espaço duplo:**
  - alvo/stop de 0,3/0,3%: −0,24% e −0,22% por operação (acerto 26–30%, empate exige 67%);
  - 0,5/0,5%: −0,21%;
  - 0,8/0,4%: −0,15%;
  - 1,0/0,5%: −0,13%.
- **Aleatória:** de −0,09% a −0,11% em todos os pares (≈ o custo).
- **Leitura:** stop curto mata o sinal de reversão. A moeda esticada ainda dá um último pulo, bate o stop e só depois volta. Com saídas de scalper, a entrada boa fica **pior que a aleatória**.
- **Decisão do dono:** implementar o scalper mesmo assim. Fica como um **robô separado na mesa proprietária**, com conta de US$ 10, as mesmas entradas do cérebro do robô rápido, saídas 1,0%/0,5% (o par menos ruim) e no máximo 30 min. O robô rápido continua igual. A mesa compara os dois ao vivo.

## Hipótese 25: surfar o impulso em 5 min, nos dois sentidos (pré-registrada em 2026-11-10, antes de rodar)

- **Motivo:** o dono viu quedas e altas fortes (−6% a −21% em 1 h) que o robô não acompanhou; o cérebro tende a apostar contra o movimento.
- **Regra:**
  - vende a descoberto quando o fechamento rompe a **mínima** das 55 velas anteriores;
  - compra quando rompe a **máxima**;
  - stop de 2N; sai no canal de 20 velas contrário, ou em no máximo 12 velas.
- **Custo:** perpétuo, 0,1% na ida e volta.
- **Variante "só impulso forte":** exige também vela elefante (amplitude > 2× a média de 20) com volume > 2× a média de 96.
- **Dados:** 33 moedas, 5 min, 60 dias, em duas metades.
- **Passa** com média em R > 0 e t > 2 nas duas metades. Venda e compra são medidas separadas.

### Resultado da H25 (2026-11-10): não passou, nos dois sentidos

| | 1ª metade | 2ª metade |
|---|---|---|
| Rompimento de venda (todas) | 3021 op., −0,23R (t −9,5), acerto 35% | 3744 op., −0,10R (t −4,3) |
| Rompimento de compra (todas) | 3584 op., −0,15R (t −6,2) | 3096 op., −0,27R (t −11,3) |
| Venda só com impulso forte | 1072 op., −0,28R (t −7,1) | 1386 op., +0,03R (t +0,7) |
| Compra só com impulso forte | 1366 op., −0,19R (t −4,4) | 1169 op., −0,31R (t −7,2) |

- **Leitura:** em 5 min, seguir o movimento perde (H25), e apostar contra também perde (H14). As quedas e altas "lindas" só são lindas vistas depois. Na hora do rompimento, a maioria não continua: só ~35% chegam a dar lucro, e os que continuam não pagam os que voltam.
- **Erro operacional meu:** 21 reinícios do painel em 4 h durante o pregão. A partir de agora, mudanças agrupadas, com no máximo um reinício por hora em horário de mercado, exceto correção urgente.

## Hipótese 26: minerador de oportunidades (pré-registrada em 2026-11-11, antes de rodar)

- **Motivo:** pedido do dono. Estudo em `research_notes/Mineração de BTC e oportunidades/mineracao.md`. Como na mineração do Bitcoin, o minerador gera muitas regras candidatas e só aceita as que passam num "alvo de dificuldade" que sobe com o número de tentativas (multiple testing).
- **Alvo do teste:** direção da **próxima vela de 15 min** (o mesmo do Cérebro v3). Aposta binária a 0,51, então o empate é 51%.
- **Dados:** 33 moedas do robô, velas de 15 min com volume, de 2025-05-01 até 2026-11-10. Cortes por tempo:
  - treino: 50% iniciais;
  - validação: 25% seguintes;
  - reserva: 25% finais, olhada uma única vez.
- **Medidas** (16, calculadas só com o passado, em unidades de volatilidade):
  - retornos de 1, 4, 16 e 96 velas;
  - distância das médias de 20 e 200 velas;
  - amplitude da vela ÷ ATR de 20;
  - corpo ÷ amplitude;
  - volume ÷ média de 96 velas;
  - volume ÷ média do mesmo horário nos 20 dias anteriores;
  - RSI de 14;
  - distância da máxima e da mínima de 96 velas;
  - retorno de 4 velas do BTC;
  - força contra o BTC (r4 da moeda − r4 do BTC);
  - hora do dia.
- **Regras candidatas, sempre nos dois sentidos (sobe e desce):**
  - uma medida acima ou abaixo de um quantil (5, 10, 20, 80, 90 ou 95%) do treino;
  - pares de medidas nas caudas de 10% e 90%;
  - cada hora do dia.

  Toda tentativa é contada, inclusive as que falham.
- **Estatística:** em cada instante em que a regra dispara em ≥ 1 moeda, faz-se a média de (acertou − 0,5) entre as moedas. O t é calculado sobre essa série de instantes. Agrupar por instante corrige o fato de as moedas andarem juntas.
- **Alvo de dificuldade (treino):**
  - t ≥ z de Bonferroni para α = 5% unilateral sobre o número total de tentativas;
  - acerto ≥ 52%;
  - ≥ 300 instantes.
- **Validação:** mesmo sentido, com acerto ≥ 51,5% e t ≥ 2.
- **Reserva:** acerto > 51% e t ≥ 1,65. Só as regras que passam nas três etapas são **aprovadas**.
- **Decisão:** as aprovadas entram no Cérebro v3 como sinapses **em observação**. Só votam se provarem acerto ao vivo, pelas regras do próprio cérebro. O resultado médio no perpétuo, com 0,1% de custo, é informado à parte.
- Se nenhuma passar, isso fica registrado e o v3 segue como está.

### Resultado da H26 (2026-11-11): 194 de 1068 tentativas passaram nas três etapas, quase todas a mesma família

- **Alvo de dificuldade:** t ≥ 3,91, por Bonferroni sobre 1068 tentativas. 218 regras passaram no treino; 194 passaram também na validação e na reserva (velas de 15 min, 33 moedas, maio/2025 a nov/2026, 50 min de busca).
- **O que é:** quase todas são **reversão da vela de 15 min**. Vela que fecha muito forte (corpo ou r1 no topo) tende a devolver na próxima, e vice-versa. As melhores acertaram 54–57% na reserva, com t de 13 a 18 e dezenas de milhares de sinais.
- **No binário** (empate em 51%): passam.
- **No perpétuo com 0,1% de custo:** 187 das 194 **perdem** (de −0,03% a −0,12% por operação). Bate com a literatura: o efeito é real, mas pequeno demais para pagar o custo.
- **Exceção que paga o custo (7 regras):** **movimento forte com volume muito baixo reverte**. Quando r1 está na cauda de 10% E o volume está nos 10% mais baixos (da média de 96 velas ou do mesmo horário):

  | | Reserva | t | Perp líquido | Perp no treino | Sinais |
  |---|---|---|---|---|---|
  | Compra | 68% | 12 | +0,19%/op | +0,06% | 999 |
  | Venda | 65% | 11 | +0,19%/op | +0,07% | 1140 |

  Positivo nos dois sentidos e em treino e reserva. Ressalva: em momentos de volume baixo o spread pode ser maior que o custo suposto.
- **Decisão (pré-registrada):** as aprovadas entram no Cérebro v3 em observação. A família "movimento sem volume" vira candidata a robô próprio no perpétuo simulado (H28, a registrar antes de ligar).

## Hipótese 28: robô Minerador — "movimento forte sem volume reverte", ao vivo (pré-registrada em 2026-11-11, antes de ligar)

- **Origem:** H26. É a única família que pagou o custo no perpétuo, nos dois sentidos, no treino (+0,06%/op) e na reserva (+0,19%/op).
- **Regra, em cada vela de 15 min fechada, nas 33 moedas:**
  - r1 = retorno da vela ÷ desvio de 96 velas;
  - vol96 = volume ÷ média de 96 velas;
  - **compra** se r1 ≤ limiar q10 do treino E vol96 ≤ limiar q10;
  - **vende a descoberto** se r1 ≥ limiar q90 E vol96 ≤ limiar q10.

  Os limiares são os números fixos do treino da H26, gravados em `dados/lab/minerador_resultado.json`.
- **Saída:** no fechamento da vela seguinte (15 min, o mesmo alvo medido), com stop de segurança de 2%.
- **Execução:** perpétuo simulado, US$ 5 por posição, margem 5×, 0,05% por lado. Conta de US$ 10 na mesa, no máximo 2 posições no mesmo lado, perda máxima de US$ 1/dia, piso de US$ 5.
- **Passa** com ≥ 200 operações, resultado líquido médio > 0 e t > 2. Reprova se a média for ≤ 0 após 200 operações.

## Mudança 29: saídas largas, custo realista e pausa depois de stop (pré-registrada em 2026-11-11 13:30 BRT, antes de aplicar)

- **Fonte:** `research_notes/Ensinamentos práticos para robôs/`, com dois achados:
  - stop apertado tem prêmio negativo quando o preço reverte (Kaminski & Lo 2014; Lo & Remorov 2017), e em cripto os retornos de curto prazo revertem (autocorrelação negativa, Hurst < 0,5);
  - o custo real no perpétuo é a taxa taker de 0,05%/lado mais o spread e o atraso: ~0,11–0,17% na ida e volta.
- **Robô rápido (1 min):**
  - stop passa de 2N para **4N** (seguro contra catástrofe), saindo como antes no horizonte treinado (12 velas);
  - depois de um stop, a moeda fica **5 velas de fora** (pausa no estilo Freqtrade);
  - custo do cérebro e da simulação: **0,06%/lado** (era 0,05%).
- **Scalper:** stop de −0,5% passa para **−1,5%**. O lucro em +0,5% e a saída no fim da vela do v3 continuam. Custo: 0,06%/lado.
- **Minerador (H28):** fica exatamente como registrado (0,05%/lado), para não mudar um teste em andamento.
- **Avaliação:** a mesa compara o resultado médio por operação **antes e depois** desta mudança (a data fica gravada). Volta atrás se, após 100 operações, a média piorar.
- **Pendência para o real:** mínimos da Binance Futures (US$ 50 no BTC, US$ 20 em ETH, LTC e LINK). Posições de US$ 5 nessas moedas só valem no simulado.

## Hipótese 30: LightGBM como os "olhos" do robô, com juiz duro (pré-registrada em 2026-11-11, antes de rodar)

- **Origem:** post enviado pelo dono (mesa de ETH com LightGBM + juiz em pytest). A ideia do juiz: as chamadas precisam vencer a referência depois dos custos, no total e em pelo menos 2 de 3 blocos.
- **Dados:** os mesmos da H26 (33 moedas, 15 min, maio/2025 a nov/2026) e as mesmas 15 medidas + hora do dia.
- **Alvo:** direção da próxima vela.
- **Modelo:** LightGBM binário com parâmetros fixos antes de ver o teste: 63 folhas, taxa 0,03, até 600 árvores com parada antecipada na validação, mínimo de 2000 amostras por folha, 80% de amostragem.
- **Cortes:** treino 50%, validação 25% (só para a parada antecipada), teste 25% dividido em 3 blocos cronológicos iguais.
- **Regras de aposta no teste:**
  - **binário:** aposta quando p ≥ 0,53 ou p ≤ 0,47;
  - **perpétuo:** opera quando |p − 0,5| ≥ 0,04, com custo de 0,12% na ida e volta.
- **Juiz:**
  - **binário passa** com acerto > 51% e t ≥ 2 (agrupado por instante) no teste inteiro **e** em ≥ 2 dos 3 blocos;
  - **perpétuo passa** com média líquida > 0 e t ≥ 2 no teste inteiro **e** média > 0 em ≥ 2 dos 3 blocos.
- **Decisão:**
  - se passar no binário, vira o **Cérebro v4** na nuvem, ao lado do v3;
  - se passar no perpétuo, vira um **robô LightGBM** na mesa;
  - se reprovar, fica registrado.

## Hipótese 31: v4 no perpétuo só com confiança alta (pré-registrada em 2026-11-11, antes de rodar)

- **Motivo:** na H30 o v4 passou no binário e reprovou no perpétuo operando a partir de |p − 0,5| ≥ 0,04 (−0,098%/op). A pergunta: as apostas mais confiantes pagam o custo?
- **Modelo:** o mesmo arquivo `lab/modelos/lgbm_v4.txt`, sem retreinar. Mesmo período de teste (25% finais) e mesmos 3 blocos.
- **Limiares testados, fixos antes de rodar:** |p − 0,5| ≥ 0,06, 0,08 e 0,10. Custo de 0,12% na ida e volta. Três tentativas, contadas.
- **Passa** o limiar com média líquida > 0 e t ≥ 2 no teste inteiro **e** média > 0 em ≥ 2 dos 3 blocos, com ≥ 1000 operações no teste.
- **Decisão:** se algum passar, o Rápido passa a entrar nas apostas do v4 acima desse limiar (em vez das do v3). Se nenhum passar, o v4 continua só no binário (pesquisa).

### Resultado da H31 (2026-11-11): reprovada nos três limiares

| Limiar | Teste inteiro | Bloco 1 | Bloco 2 | Bloco 3 |
|---|---|---|---|---|
| 0,06 | 52.624 op., −0,075%/op | −0,019% | −0,099% | −0,112% |
| 0,08 | 23.996 op., −0,044%/op | +0,037% | −0,080% | −0,111% |
| 0,10 | 10.708 op., −0,005%/op | +0,085% | −0,048% | −0,101% |

- **Leitura:** quanto mais confiante, melhor, mas a vantagem só existiu no 1º bloco e desapareceu nos dois seguintes. Vantagem direcional no perpétuo é fina e não é estável no tempo. O v4 continua só no binário (pesquisa).
- **Nota de contexto:** a Polymarket, modelo do contrato binário, está em "close-only" para o Brasil (geoblock oficial), e cobra 0,07 × p × (1 − p) por ação do tomador (3,5% do valor a 0,50). Os cérebros v1–v4 passam a ser tratados como pesquisa, não como carteira operável.

## Hipótese 32: minerador de oportunidades em velas de 1 min, para o robô rápido (pré-registrada em 2026-11-11, antes de rodar)

- **Motivo:** o dono delegou aos robôs "encontrar um caminho para lucrar sozinhos". O Rápido opera velas de 1 min com horizonte de 12 velas; nenhuma regra foi minerada nesse tempo gráfico ainda.
- **Dados:** 33 moedas, velas de 1 min, últimos 60 dias até 2026-11-11 00:00 UTC. Mesmas 15 medidas da H26 (janelas em velas), com o "mesmo horário" deslocado em dias de 1440 velas.
- **Alvo:** retorno de 12 velas à frente (o horizonte do Rápido).
- **Candidatas, alvo de dificuldade, cortes e critérios:** idênticos à H26 (Bonferroni sobre todas as tentativas; treino 50% / validação 25% / reserva 25% olhada uma vez). Custo no perpétuo: 0,12% ida e volta.
- **Decisão:** regras aprovadas nas 3 etapas entram nos 33 cérebros do Rápido como sinapses em observação; se alguma pagar o custo no perpétuo, vira entrada direta do Rápido. Se nenhuma passar, fica registrado e o Rápido migra para a regra do Minerador em 15 min.

### Resultado da H32 (2026-11-12): 213 regras aprovadas na direção, ZERO pagam o custo no perpétuo

- 1068 tentativas em velas de 1 min (30 dias, 33 moedas, alvo 12 velas à frente), alvo de dificuldade t ≥ 3,91. 315 passaram no treino, 213 nas três etapas: quase todas reversão (vela forte de 1 min tende a devolver nos 12 min seguintes).
- **Nenhuma** das 213 teve resultado líquido positivo no perpétuo com 0,12% de custo, nem no treino nem na reserva. Em 1 min o movimento típico é menor que o custo.
- **Desafio de 24 h do Rápido (13:35 de 11/11 a 13:35 de 12/11), posições de US$ 25 a 10×:** 106 operações, −US$ 2,94; 90 saídas no fim da vela (≈ 0), 14 stops (≈ toda a perda), 2 realizações. A regra de +US$ 0,50 por posição nunca foi atingida.
- **Decisão pré-registrada:** o Rápido de 1 min não tem regra com vantagem líquida; migra para a regra do Minerador (15 min) ou é desligado, a critério do dono.

### H28b (2026-11-12, decisão do dono): Minerador vira o robô principal do perpétuo
- Tamanho do dono: US$ 25 por posição a 10× (margem US$ 2,50), até 6 no mesmo lado; perda máxima US$ 1/dia e piso US$ 5 mantidos.
- Entra a 2ª família aprovada na H26 (movimento forte com volume ≤ 20% do mesmo horário dos 20 dias anteriores; +0,05–0,06%/op), para operar mais vezes. Custo 0,06%/lado.
- O placar da H28 recomeça daqui (as 11 operações a US$ 5 ficam registradas, não contam para o teste novo).
