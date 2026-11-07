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
