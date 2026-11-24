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

## Hipótese 34: primeira meia hora do dia prevê a última (pré-registrada em 2026-11-12, antes de rodar)

- **Fonte:** Shen, Urquhart & Wang (2022), previsibilidade intradiária em cripto: o retorno da primeira meia hora (00:00–00:30 UTC) prevê o da última (23:30–24:00 UTC).
- **Dados:** 33 moedas, 15 min, maio/2025–nov/2026 (os mesmos da H26/H30). Teste no período inteiro, dividido em 3 blocos.
- **Regra A:** às 23:30 UTC, compra se r(00:00–00:30) > 0, vende a descoberto se < 0; sai às 24:00. **Regra B:** idem, mas só quando |r(00:00–00:30)| > 0,5%. Duas tentativas, contadas.
- **Custo:** 0,12% ida e volta. **Passa** com média líquida > 0, t ≥ 2 (agrupado por dia) e média > 0 em 2 dos 3 blocos.

### Resultado da H34 (2026-11-12): reprovada
- A (sempre): 558 dias, −0,129%/dia, t = −7,4, negativa nos 3 blocos. B (|r| > 0,5%): 554 dias, −0,150%/dia, t = −6,2, negativa nos 3 blocos.
- Leitura: o efeito da primeira meia hora não aparece nas 33 moedas em 2025–26; o resultado é ≈ o custo, ou seja, previsão nula.

## Hipótese 35: swing trade com as regras diárias de melhor evidência (pré-registrada em 2026-11-12 19:45 BRT, antes de rodar)

- **Por quê:** o dono definiu a meta como "robô acertivo em swing trade e day trade" (12/11). A pesquisa (relatórios "Previsibilidade em cripto"
  e "Ensinamentos práticos para robôs", seção 11) só encontrou evidência revisada por pares em cripto para regras de 1 dia ou mais:
  momentum semanal (Liu & Tsyvinski 2021, RFS), média móvel variável de 20 dias (Grobys, Ahmed & Sapkota 2020, FRL) e seguir tendência
  como classe (Hurst et al.; Tartaruga). Nada em minutos pagou custo até agora (H24, H25, H31, H32, H34).
- **Dados:** velas diárias das 33 moedas do robô, últimos 2200 dias (o que existir por moeda), avaliadas de 2020-01-01 até ontem. Três blocos
  de tempo iguais.
- **Regras (como estão escritas, sem ajuste):** A) R7 = C[t]/C[t−7] − 1: > 0 compra, < 0 vende, na abertura seguinte, segura 7 dias.
  B) MM20 com banda de 1%: C > MM20×1,01 comprado, C < MM20×0,99 vendido, entre as bandas fora; muda na abertura seguinte.
  C) Tartaruga 20/10: compra no rompimento da máxima de 20 dias, sai na mínima de 10; vendido simétrico.
  Todas com stop de 2×ATR20 (conferido na mínima/máxima do dia; sai no stop ou na abertura se abriu além).
- **Custo:** 0,06% por lado (tomador), 0,12% ida e volta. Uma unidade por moeda; a carteira do dia é a média das moedas vivas.
- **Passa** se: média do retorno líquido por dia > 0, t ≥ 2 (agrupado por dia) e média > 0 em 2 dos 3 blocos. Três tentativas contadas
  (A, B, C, compra e venda). As versões "só compra" são leitura e não contam para aprovar.
- **Se passar:** vira robô "Swing" na nuvem (uma decisão por dia, no fechamento UTC), com carteira de US$ 10 na mesa, tamanho do dono
  (US$ 25 a 10×) e as mesmas regras do teste. Se nenhuma passar, fica registrado e nada entra na mesa.

### Resultado da H35 (2026-11-12 19:55 BRT): reprovada (nenhuma das três passa)
- Referência "mercado sempre comprado" nas mesmas 33 moedas (sobreviventes): +0,204%/dia, t 2,3, blocos [+0,40, +0,16, +0,05] ≈ +53%/ano.
- A (momentum 7d, compra e venda): 6723 op., 38% certas, +0,089%/dia, t 1,5, blocos [+0,20, +0,01, +0,06] → não passa (t < 2).
- B (MM20 ±1%, compra e venda): 7115 op., 26% certas, +0,107%/dia, t 1,6, blocos [+0,17, +0,07, +0,08] → não passa.
- C (Tartaruga 20/10, compra e venda): 1792 op., 34% certas, +0,083%/dia, t 1,5, blocos [+0,18, +0,02, +0,05] → não passa.
- Leitura (não conta): as versões "só compra" dão +0,115 a +0,133%/dia com t 2,4–3,2, mas TODAS ficam abaixo de simplesmente
  ficar comprado nas mesmas moedas (+0,204%/dia). Ou seja: o que parece lucro das regras é a alta das moedas que sobreviveram
  até hoje (viés de sobrevivência), não a regra. Primeira rodada do teste tinha um erro (fechamento na abertura contava o trade
  inteiro de novo: +577%/ano); corrigido antes de qualquer decisão. Arquivo: dados/lab/swing_resultado.json. Nada entra na mesa.

## Hipótese 33: as fórmulas dos grandes traders como sinapses dos cérebros (pré-registrada em 2026-11-12 22:58 BRT, antes de ligar)

- **Pedido do dono:** "coloca esses cérebros para aprender as metodologias dos maiores traders" (12/11) e "aperfeiçoe todos os cérebros, vá atrás
  de mais conhecimento para eles" (12/11, noite).
- **Fonte:** relatório "Ensinamentos práticos para robôs" (research_notes/.../formulas_dos_grandes_traders.md, seção 16, lista ranqueada).
  Entram só as regras que fazem sentido em velas de minutos (as diárias foram testadas na H35 e reprovadas): Holy Grail (Raschke), Turtle Soup
  (Raschke/Connors), TD Setup 9 (DeMark), Williams %R(10) com espera de 5 velas, barra 80-20 (Connors/Raschke) e rompimento de volatilidade
  (Williams). Cada uma nos dois sentidos = 12 sinapses (`baleias/cerebro.py`, `SINAPSES_TRADERS`, `medidas_traders`).
- **Como são julgadas:** entram em OBSERVAÇÃO (peso 0, não votam) em todos os cérebros (v1, v2, v3 da nuvem, cérebros por moeda do Rápido).
  A regra de promoção já existente decide: com ≥150 previsões, promove se o limite inferior do intervalo de Wilson (95%) ficar acima da base
  (50% no v1/v2; o humor do mercado `base_sobe` no v3/Rápido); poda se o acerto ficar abaixo da base − 2 pontos. Nada é promovido à mão.
- **Passa (por sinapse):** promovida ao vivo por essa regra. **Reprovada:** podada. O resultado de cada uma fica no diário do cérebro
  (`dados/cerebro*.json`, "diario") e será copiado aqui quando houver ≥150 previsões.
- **Observação honesta:** a evidência pública dessas seis é anedótica ou fraca (o relatório marca [NV]/[S]); o teste ao vivo é o juiz.

## Hipótese 36: estudar e aperfeiçoar o Cérebro v4, o robô de mais lucro (pré-registrada em 2026-11-13 16:40 BRT, antes de rodar)

- **Pedido do dono (13/11):** trocar o cérebro de todos os robôs pelo do robô com mais lucro (o v4, LightGBM), deixá-los na nuvem,
  fazer backup, estudar o método dele e começar a aperfeiçoá-lo.
- **Backup feito:** `backups/cerebro_v4_2026-11-13.tar.gz` (modelo `lab/modelos/lgbm_v4.txt`, código de treino `lab/lgbm.py`, medidas
  `lab/minerador.py`, executor `executor/cerebro_v4_nuvem.py`, resultados H30/H31, estado da nuvem) e etiqueta git `cerebro-v4-2026-11-13`.
- **Troca de cérebro:** Rápido 1 min e Scalper passam a seguir as apostas do v4 (`mesa.sinais_v4`, |p − 0,5| ≥ 0,03); novo robô
  "Rápido nuvem (v4)" (`executor/v4_perp_nuvem.py`) opera o v4 no perpétuo simulado na nuvem, 24 h, com as regras do Rápido
  (US$ 25 a 10×, stop 1%, lucro realizado +US$ 0,50, fim da vela). O Minerador não tem cérebro (é a regra H26) e continua.
- **Parte 1 (descritiva, `lab/v4_estudo.py`):** no teste fora da amostra da H30 (25% finais), com o modelo salvo e sem retreinar,
  medir acerto no binário e líquido no perpétuo por: faixa de hora UTC (0–5, 6–11, 12–17, 18–23), dia da semana, faixa de confiança
  (0,03–0,05, 0,05–0,08, 0,08–0,12, ≥0,12), lado e moeda, no teste inteiro e nos 3 blocos. **Conta como achado** um corte com
  ≥ 5.000 apostas no teste, acerto ≥ 2 pontos acima (ou abaixo) do total E na mesma direção em ≥ 2 dos 3 blocos. Um achado vira
  filtro só depois de passar como hipótese própria (H37) ao vivo ou em dados novos; nada é aplicado só por este estudo.
- **Parte 2 (planejada, ainda não rodada):** retreino mensal com a mesma receita (walk-forward: treina até o mês M, testa no mês
  M+1), para medir se o acerto no mês seguinte melhora em relação ao modelo fixo de 11/11. Passa se melhorar em ≥ 2 de 3 meses.
- **Parte 3 (planejada):** medidas novas que o gravador já grava (funding, juros em aberto, desequilíbrio do livro) como colunas
  extras, com o mesmo juiz da H30. Passa só se vencer o v4 atual no teste inteiro E em 2 dos 3 blocos.

### Resultado da H36, parte 1 (2026-11-13 16:50 BRT): um achado, a confiança
- Teste fora da amostra (170.519 apostas): acerto 53,9% [blocos 56,0 / 52,6 / 53,1]; perpétuo −0,103%/op.
- **Confiança |p − 0,5| (achado, nos 3 blocos):** 0,03–0,05: 52,6% (92.456); 0,05–0,08: 54,1% (54.273); 0,08–0,12: 57,5% (19.887;
  blocos 60,8 / 55,9 / 54,9); ≥0,12: 65,5% (3.903; blocos 70,9 / 60,4 / 60,3). No perpétuo a 0,12% ida e volta: 0,08–0,12 dá −0,065%/op
  (+0,002 / −0,099 / −0,115) e ≥0,12 dá +0,070%/op (+0,176 / −0,001 / −0,076): positivo só no 1º bloco, como na H31.
- Hora UTC: 18–23 é a pior (53,0% contra 54,2–54,3% nas outras), diferença de 1,2 ponto: abaixo do corte de 2 pontos, não é achado.
  Dia da semana: sábado 55,4% (+1,5 ponto): não é achado. Lado: compra 53,9%, venda 53,9%. Moedas: PEPE/ONE/CYBER 60–62% no teste,
  mas ao vivo PEPE e CYBER estão entre as piores → ranking de moeda não se repete; não é achado.
- Leitura: o v4 acerta a DIREÇÃO de forma robusta e tanto mais quanto mais confiante, mas o tamanho do movimento em 15 min é pequeno
  demais para pagar 0,12% no perpétuo. Com taxa de maker (0,04% ida e volta) a faixa 0,08–0,12 ficaria ≈ +0,015%/op e a ≥0,12
  ≈ +0,15%/op — por isso o robô do testnet tenta entrar como maker. Arquivo: dados/lab/v4_estudo.json.

## Hipótese 37: v4 no perpétuo, agressivo contra seletivo, ao vivo na nuvem (pré-registrada em 2026-11-13 16:52 BRT, antes de ligar)

- Dois robôs iguais (`executor/v4_perp_nuvem.py`, US$ 25 a 10×, 0,06% por lado, stop 1%, lucro realizado +US$ 0,50, fim da vela,
  carteira de US$ 10 cada): **Rápido nuvem** (todas as apostas do v4, |p − 0,5| ≥ 0,03, pedido do dono: agressividade) e
  **Rápido nuvem seletivo** (só |p − 0,5| ≥ 0,12, o achado da H36).
- **Passa** o que, com ≥ 200 operações, tiver resultado líquido > 0 e acerto com limite inferior de Wilson acima de 50%. Previsão
  registrada antes: pelo laboratório, o agressivo deve perder ≈ 0,10%/op (≈ US$ 0,025 por operação) e o seletivo ficar perto de zero.

## Hipótese 38: LightGBM com alvo de LUCRO no perpétuo (pré-registrada em 2026-11-13 17:05 BRT, antes de rodar)

- **Pedido do dono (13/11):** "quero lucros, quero operações com lucro". O v4 acerta direção (53,9%) mas o movimento de 15 min não paga o custo.
- **Mudança:** dois modelos LightGBM (mesmos dados, 16 medidas, cortes e parâmetros da H30) aprendem "próxima vela fecha ≥ +0,15%" e
  "≤ −0,15%" — movimentos que pagam 0,12% de custo e sobram. Operação: compra se P(alta) − P(baixa) ≥ d, vende se P(baixa) − P(alta) ≥ d,
  d ∈ {0,05, 0,10, 0,15} (três tentativas, contadas). `lab/lgbm_alvo.py`.
- **Passa** (por d): média líquida > 0, t ≥ 2 agrupado por instante, média > 0 em 2 dos 3 blocos, ≥ 1.000 operações no teste.
- **Se passar:** vira o cérebro dos robôs do perpétuo (Rápido nuvem, testnet) no lugar do v4, no d aprovado. Se nenhum passar, fica registrado:
  o laboratório não encontrou operação de 15 min que pague o custo no perpétuo com estes dados.

### Resultado da H38 (2026-11-13 16:50 BRT): reprovada nos três d
- Modelos: alta 214 árvores (33,7% das velas sobem ≥ 0,15%), baixa 220 árvores (34,5%). Medidas mais usadas: btc_r4, hora, corpo, vol_hora, r1.
- d = 0,05: 198.385 op., −0,103%/op, acerto 53,4%, blocos −0,072 / −0,120 / −0,117. d = 0,10: 83.094 op., −0,085%/op, acerto 55,1%,
  blocos −0,031 / −0,105 / −0,120. d = 0,15: 34.170 op., −0,050%/op, acerto 57,8%, blocos **+0,028** / −0,082 / −0,117 (t −1,9).
- Leitura: mudar o alvo para "movimento que paga o custo" não resolve: a vantagem continua só no 1º bloco (maio–jul/2025) e some
  depois, como na H30/H31/H36. Com estes dados e estas 16 medidas, **nenhuma operação de 15 min no perpétuo paga 0,12% de custo**
  de forma estável. Modelos salvos em lab/modelos/lgbm_alvo_{alta,baixa}.txt; resultado em dados/lab/lgbm_alvo_resultado.json.

## Hipótese 39: pegar a tendência de horas e segurar (pré-registrada em 2026-11-13 17:00 BRT, antes de rodar)

- **Pedido do dono (13/11):** "BMT teve uma alta de 01:00 até 13:00, por que nenhum robô entrou e ficou comprado segurando a subida?";
  idem QNT. Nenhum robô atual segura além de uma vela de 15 min.
- **Regra (como escrita, sem ajuste):** a cada vela de 15 min fechada, r4h = C[t]/C[t−16] − 1 normalizado pelo desvio-padrão dos
  retornos de 4 h dos últimos 20 dias (z); volume das últimas 4 h ÷ média do volume de 4 h dos últimos 20 dias (vol). Entra COMPRADO
  se z ≥ 2 e vol ≥ 1,5 (VENDIDO se z ≤ −2 e vol ≥ 1,5), ao fechamento da vela. Sai no stop móvel (extremo desde a entrada ∓ k × ATR20
  de 15 min, conferido na mínima/máxima da vela seguinte usando o extremo até a vela anterior), no stop fixo de 2% ou no tempo máximo.
- **Três tentativas, contadas:** A) k = 2, máximo 48 velas (12 h), compra e venda; B) k = 3, máximo 96 velas (24 h), compra e venda;
  C) = A só compra. Custo 0,12% ida e volta. Uma posição por moeda.
- **Dados:** 33 moedas, 15 min, maio/2025–nov/2026 (dados/lab/minerador_15m.npz), 3 blocos iguais.
- **Passa** se: média líquida por operação > 0, t ≥ 2 agrupado por dia de entrada, média > 0 em 2 dos 3 blocos, ≥ 300 operações.
- **Se passar:** vira robô "Tendência" na nuvem (15 min, 33 moedas, carteira de US$ 10, US$ 25 a 10×) com a regra aprovada.

### Resultado da H39 (2026-11-13 17:15 BRT): reprovada nos três braços
- A (k = 2, 12 h, compra e venda): 14.307 op. em 530 dias, acerto 32,1%, −0,115%/op (t −6,8), blocos −0,081 / −0,154 / −0,106; 85% das saídas no stop móvel, segura 9 velas em média.
- B (k = 3, 24 h, compra e venda): 11.142 op., acerto 31,6%, −0,060%/op (t −4,0), blocos +0,126 / −0,175 / −0,094.
- C (k = 2, 12 h, só compra): 7.415 op., acerto 32,7%, +0,006%/op (t −3,5), blocos +0,031 / −0,083 / +0,057 (média ≈ zero, t negativo por dia).
- Leitura: entrar depois de um movimento forte de 4 h com volume e segurar com stop móvel PERDE na média nas 33 moedas em 2025–26.
  As subidas de horas que o dono vê (BMT, QNT) existem, mas são raras; as entradas iguais a elas que não continuam pagam stop atrás de
  stop (85% das saídas). Nada entra na mesa. Arquivo: dados/lab/tendencia_horas_resultado.json.

### H37, emenda (2026-11-13 17:30 BRT, antes de qualquer operação do braço trocado)
- Pedido do dono: "não quero ver nenhum robô esperando aparecer oportunidade; quero eles caçando a própria entrada, na venda ou na compra".
- O braço "Rápido nuvem seletivo" (|p − 0,5| ≥ 0,12; 0 operações até aqui) é substituído pelo **Caçador** (`V4P_MODO=ranking`, K = 2):
  a cada vela, entre todas as moedas do universo, as 2 com maior probabilidade de subir (compra) e as 2 com maior de cair (venda), pelo v4;
  sempre posicionado. Mesmas regras de tamanho, stop, alvo e saída. Juiz igual ao da H37. Estado: dados/robo_v4_cacador.json.
- Previsão registrada: pelo laboratório (H36), o Caçador opera nas faixas de confiança mais altas disponíveis em cada vela (com 135 moedas,
  em geral ≥ 0,08), onde o perpétuo ficou entre −0,065% e +0,07%/op: esperado perto de zero, melhor que o agressivo.

## Hipótese 40: alvo dinâmico por ATR nas apostas do v4 (pré-registrada em 2026-11-14 00:20 BRT, antes de rodar)

- **Origem:** análise externa trazida pelo dono (14/11): o lucro realizado fixo de US$ 0,50 (= +2% em US$ 25) quase nunca é atingido numa
  vela de 15 min; um alvo proporcional à volatilidade da moeda (múltiplo do ATR) capturaria o extremo da vela em vez de sair no fechamento.
- **Dados e modelo:** teste fora da amostra da H30 (25% finais), modelo salvo `lab/modelos/lgbm_v4.txt`, apostas com |p − 0,5| ≥ 0,03,
  entrada no fechamento da vela do sinal (como nas simulações da nuvem), saída dentro da vela seguinte. ATR14 = média do true range das
  14 velas de 15 min anteriores ao sinal. Custo 0,06% por lado. Stop fixo de 1% conferido na mínima/máxima; se stop e alvo caberiam na
  mesma vela, conta o stop (conservador).
- **Braços (três tentativas, contadas):** alvo = entrada ± 1,0 × ATR14; ± 1,5 × ATR14; ± 2,0 × ATR14. Se a vela não toca o alvo nem o
  stop, sai no fechamento. **Referências (não contam):** R1 = sair sempre no fechamento (o que o v4 faz hoje); R2 = R1 com stop de 1%
  (o Rápido nuvem de hoje).
- **Passa** o braço com média líquida > 0, t ≥ 2 agrupado por instante, média > 0 em 2 dos 3 blocos E média acima da referência R2.
  Também é relatado o mesmo corte só nas apostas de confiança ≥ 0,12.
- **Se passar:** o alvo do Rápido nuvem, do Caçador e do testnet passa a ser o múltiplo aprovado do ATR14 em vez de US$ 0,50 fixos.

### Resultado da H40 (2026-11-14 10:55 BRT): reprovada nos três braços
- Referências: R1 (sair no fechamento) −0,1048%/op; R2 (fechamento + stop 1%) −0,1038%/op. Braços: alvo 1,0×ATR14 −0,1042%; 1,5×ATR14
  −0,1032%; 2,0×ATR14 −0,1030%/op (187.115 apostas; blocos todos negativos, t ≈ −42). Só nas apostas de confiança ≥ 0,12: R2 +0,022%,
  alvos +0,023 / +0,026 / +0,028%/op — ganho de 0,006 ponto, dentro do ruído.
- Leitura: o alvo fixo de US$ 0,50 não era o gargalo (quase nunca é tocado, e trocá-lo por um múltiplo do ATR não muda a média). O que
  decide é a direção e o tamanho do movimento em 15 min, não a regra de saída. Arquivo: dados/lab/v4_alvo_atr.json.

## Hipótese 41: ensinar o v4 com os dados novos — retreino com juiz (pré-registrada em 2026-11-14 11:50 BRT, antes de rodar)

- **Pedido do dono (14/11):** os robôs têm cérebro? Precisam de ajuda para aprender. O v4 é fixo (treinado em 11/11 com dados até o fim do
  teste); a forma honesta de "ensiná-lo" é retreinar com a mesma receita incluindo os dados mais novos e JULGAR se ficou melhor, em vez de
  supor.
- **Dados:** 33 moedas, 15 min, 2025-05-01 até hoje (download novo). **Holdout** = últimos 30 dias (nenhum modelo treina neles), dividido
  em 3 blocos de 10 dias.
- **Modelo novo (v4.1):** mesma receita da H30 (16 medidas, parâmetros, parada antecipada), treino = 2/3 e validação = 1/3 do período
  anterior ao holdout. **Modelo velho:** `lab/modelos/lgbm_v4.txt` como está (o holdout fica dentro do antigo período de teste dele; ele
  nunca treinou nesses dias).
- **Medidas no holdout, para os dois:** acerto binário nas apostas |p − 0,5| ≥ 0,03 e ≥ 0,12; resultado líquido no perpétuo (0,12%)
  nas mesmas faixas; tudo no total e por bloco.
- **Passa (v4.1 substitui o v4):** acerto binário (≥ 0,03) maior que o do v4 velho no holdout inteiro E em ≥ 2 dos 3 blocos, com ≥ 20.000
  apostas no holdout. Se não passar, o v4 fica e o retreino é repetido daqui a 30 dias com a mesma regra.
- **Não conta como aprovação:** melhora só no perpétuo ou só na faixa ≥ 0,12 (são relatadas como leitura).

### Resultado da H41 (2026-11-14 15:40 BRT): PASSOU — v4.1 substitui o v4
- Dados até 14/11 14:30 UTC (54.011 velas × 33 moedas). Holdout 2026-10-15 → 2026-11-14 (3 blocos de 10 dias); o novo treinou de 2025-05-03 a 2026-10-15 (78 árvores).
- |p − 0,5| ≥ 0,03: velho 52.97% / **novo 53.46%** em 34600 apostas; blocos velho [53.0, 51.3, 54.7] novo [54.1, 51.4, 54.9]; perpétuo velho -0.120% / novo -0.119%/op.
- |p − 0,5| ≥ 0,12 (leitura): velho 62.0% (669) / novo 58.4% (639); perpétuo velho -0.053% / novo -0.076%/op.
- O v4.1 vira `lab/modelos/lgbm_v4.txt` (o anterior fica em `lgbm_v4_anterior.txt`). A partir daqui o retreino é automático e semanal (`.github/workflows/retreino.yml`), sempre com este juiz.

## Hipótese 42: o humor do mercado como filtro de lado para o v4 (pré-registrada em 2026-11-14 15:45 BRT, antes de rodar)

- **Pedido do dono (14/11):** "o BTC caiu muito e um robô deveria ter operado em short; hoje subiu e deveriam ter operado em long". Ao vivo,
  comprar perdeu mais que vender em todos os robôs enquanto o mercado caía. O v4 aposta nos dois lados sem olhar o humor do mercado todo.
- **Humor:** a cada vela, a média entre as 33 moedas do retorno normalizado de 4 velas (r4) e de 16 velas (r16) — o mesmo cálculo das
  medidas do v4, sem dado novo. Positivo = mercado subindo; negativo = caindo.
- **Braços (três tentativas, contadas), no teste fora da amostra da H30 com o modelo salvo:** A) só apostas do v4 alinhadas com o sinal do
  humor r4 (compra se humor > 0, venda se < 0); B) idem com o humor r16; C) = A, só quando |humor r4| ≥ 0,3 (mercado decidido).
  Referência: todas as apostas (−0,103%/op no perpétuo; 53,9% de acerto).
- **Passa** o braço com líquido no perpétuo (0,12%) > 0, t ≥ 2 agrupado por instante, > 0 em 2 dos 3 blocos e ≥ 20.000 apostas; o acerto
  binário é relatado como leitura. **Se passar:** o Rápido nuvem, o Caçador e o testnet só entram alinhados com o humor aprovado.

### Resultado da H42 (2026-11-14 16:00 BRT): reprovada nos três braços
- Referência (todas as apostas): 170.519, acerto 53,92%, perpétuo −0,103%/op. A (alinhado com o humor r4): 51.810, 53,67%, −0,084%/op
  (blocos −0,047 / −0,107 / −0,101). B (humor r16): 62.232, 53,30%, −0,095%/op. C (A e |humor| ≥ 0,3): 26.124, 52,46%, −0,087%/op.
- Leitura: apostar CONTRA o humor acerta mais (54,03%) e perde mais no perpétuo (−0,111%/op): quando o mercado cai, as apostas de venda
  acertam mas o movimento é pequeno; as de compra erram mais. Seguir o humor reduz a perda em 0,02 ponto e não a vira em lucro.
  "O BTC caiu, deveria ter vendido" é verdade para o dia; em velas de 15 min o filtro não paga. Arquivo: dados/lab/v4_humor.json.

## Hipótese 43: Robô Claude — o Claude decide as posições lendo o mercado, de hora em hora (pré-registrada em 2026-11-14 21:50 BRT, antes de ligar)

- **Pedido do dono (14/11):** "quero usar o Claude dentro do baleia para operar para mim; se o mercado está em tendência de baixa entra vendido,
  em alta entra comprado; segura a tendência". Hoje o BTC caiu 6,2% com 94% das moedas caindo e os robôs de 15 min perderam (−7,5 em 6 h).
- **Como funciona:** a cada rodada da nuvem, `executor/mercado_agora.py` escreve o retrato do mercado (BTC 1 h/4 h/24 h, amplitude, líderes
  de 4 h, apostas mais confiantes do v4, estado do próprio robô e suas lições). De hora em hora uma rotina do Claude Code na nuvem da Anthropic
  (assinatura do dono) lê o retrato e a cartilha `docs/CARTILHA_ROBO_CLAUDE.md` e grava `dados/decisao_claude.json` (posições desejadas,
  fechamentos, uma lição). `executor/robo_claude_nuvem.py` executa no perpétuo simulado: US$ 25 a 10×, até 4 posições, stop 1,5% nas
  mínimas/máximas, tempo máximo 24 h, custo 0,06% por lado, carteira de US$ 10. Só dados públicos da Binance.
- **O que é diferente dos outros robôs:** horizonte de horas em vez de 15 min, lado decidido pela tendência do dia, e um "operador" que
  lê as próprias operações e escreve lições. **O que não muda:** o juiz. A rotina pode mudar o próprio raciocínio, nunca as regras de risco.
- **Passa** pelo critério da mesa: ≥ 30 operações, carteira ≥ US$ 11, sem passar de US$ 5. Comparação declarada: contra o Caçador e o Rápido
  nuvem no mesmo período. Previsão registrada antes: não sei. Não há teste histórico possível de uma decisão discricionária; o placar ao vivo é o juiz.
- **Custo:** usa a cota da assinatura do dono (24 decisões por dia). Se a cota acabar, o robô fica sem decisão nova e as posições fecham por stop ou tempo.

## Hipótese 44: regra do dono — regime de tendência nos robôs automáticos (registrada em 2026-11-15 09:30 BRT, antes de ligar)

- **Decisão do dono (14–15/11, repetida várias vezes):** "se o mercado está em tendência de baixa, entra vendido; se está em alta, entra
  comprado; segura a tendência". O laboratório já mediu algo próximo (H42: alinhar as apostas de 15 min com o humor reduziu a perda de
  −0,103% para −0,084%/op, sem virar lucro), mas a regra aqui é outra — regime pela amplitude de 24 h e 4 h e posição segurada — e a decisão
  é do dono; o placar ao vivo julga.
- **Regime** (`executor/regime.py`): baixa = ≤ 30% das moedas do universo subindo em 24 h e ≤ 60% em 4 h; alta = ≥ 70% e ≥ 40%; senão neutro.
- **Nos robôs:** Rápido nuvem e testnet só entram no lado do regime; o Caçador, na baixa, abre as 4 vendas mais confiantes do v4 (na alta,
  as 4 compras); no neutro, como antes. **Segurar:** no fim da vela, se o regime continua e o v4 aposta no mesmo lado da posição, ela não é
  fechada (passa para a vela seguinte, sem pagar saída e entrada). Stop de 1% e lucro realizado de +US$ 0,50 continuam valendo.
- **Juiz:** critério da mesa (≥ 30 operações, carteira ≥ US$ 11, sem passar de US$ 5), comparando com os resultados antes da regra.
  Carteiras do Rápido nuvem, do testnet e do Rápido 1 min zeradas em US$ 10 no mesmo momento (históricos guardados).
- **Emenda (15/11 09:40, antes de qualquer operação com a regra):** o regime passa a ser só pela amplitude de 24 h (baixa ≤ 30%, alta ≥ 70%);
  o filtro de 4 h saiu porque deixava os robôs fora durante repiques fracos dentro da baixa (às 09:10, 88% das moedas subindo em 4 h com o
  volume do BTC a 0,76× a média). A cartilha do Robô Claude foi alinhada: repique de 4 h sem volume numa baixa de 24 h é ponto de venda.

## Hipótese 45: padrões gráficos clássicos (figuras geométricas) em 1 h (pré-registrada em 2026-11-15 17:00 BRT, antes de rodar)

- **Pedido do dono (15/11):** "manda ele ler o livro de day trade, para aprender os padrões de mercado, as figuras geométricas". Não há acesso
  aos livros pagos; as definições usadas são as clássicas, escritas como regras objetivas em `lab/padroes_graficos.py` (topo/fundo duplo,
  ombro-cabeça-ombro e invertido, triângulos simétrico/ascendente/descendente, bandeiras, virada de estrutura de topos e fundos).
- **Dados:** 33 moedas, velas de 15 min de 2025-05 a 2026-11 (`dados/lab/minerador_15m.npz`) agregadas em 1 h. Evento = padrão CONFIRMADO
  (rompimento) no fechamento de uma vela de 1 h; entrada no fechamento; resultado no sentido do padrão em 4 h e em 12 h, menos 0,12% de custo.
- **Juiz, por família de padrão e horizonte (7 famílias × 2 horizontes = 14 tentativas, contadas):** média líquida > 0, t ≥ 2 agrupado por
  dia, média > 0 em 2 dos 3 blocos de tempo, ≥ 200 eventos. Com 14 tentativas, um t perto de 2 sozinho pode ser sorte: o resultado
  publica o t de cada uma para o leitor descontar.
- **Uso:** o detector já entra no retrato do Robô Claude como informação (o que está formado e o que confirmou na última hora); a cartilha
  manda dar peso só às famílias aprovadas aqui, e o resultado de cada família vai junto no retrato (`lab/resultados/padroes_graficos.json`).

### Resultado da H45 (2026-11-15 17:10 BRT): reprovada nas 14 tentativas
- 33 moedas, 1 h, mai/2025–nov/2026; evento = rompimento confirmado; custo 0,12%. Nenhuma família passou. Direção certa abaixo de 50% em quase
  todas: topo duplo 47,5% (4 h, −0,168%/op, t −4,5), fundo duplo 45,4%, OCO invertido 44,4%, bandeira 45,2%, triângulo 48,0% (−0,171%/op,
  negativo nos 3 blocos), virada de estrutura 47,7% (6.861 eventos, −0,108%/op, t −4,3, negativa nos 3 blocos). A melhor foi ombro-cabeça-ombro
  em 12 h (+0,148%/op, 52,9%, t +1,0, 711 eventos): longe do critério.
- Leitura: em cripto de 1 h, seguir o rompimento das figuras clássicas perde para o acaso. Triângulo e virada de estrutura erram de forma
  consistente (os 3 blocos negativos): operar CONTRA eles pode ser uma ideia, mas é achado depois de ver o dado e precisa de hipótese nova.
  No retrato do Robô Claude os padrões ficam só como informação (a cartilha só dá peso a família aprovada). Arquivo: lab/resultados/padroes_graficos.json.

## Hipótese 46: o v4 piora das 18 às 24 h UTC — deriva ao vivo ou acaso? (pré-registrada em 2026-11-15 17:55 BRT, antes de olhar os dados novos)

- **Origem:** vigia do v4 (`executor/vigia_v4.py`, monitoramento do livro "Machine Learning for High-Risk Applications", cap. 3). Nas apostas
  ao vivo de 11/11 18:45 a 15/11 19:00 UTC (12.673 apostas, 359 velas): 18–24 h UTC acertou 44,2% (3.762 apostas); 00–06 h 58,6%, 06–12 h
  56,9%, 12–18 h 52,2%. No laboratório (H36) a faixa 18–23 h acertava 53,0% contra 54,2% das outras: a diferença ao vivo é muito maior.
  Como o achado saiu destes dados, eles **não servem para testá-lo** (seria p-hacking): o teste é só com apostas posteriores.
- **Teste (prospectivo):** apostas conferidas de 16/11 00:00 a 22/11 24:00 UTC. Erro-padrão por vela (moedas da mesma vela andam juntas).
- **Juiz:** a faixa 18–24 h UTC acerta < 50% com z ≤ −2 contra 50%, e as outras faixas juntas acertam ≥ 52%. Uma tentativa só.
- **Se passar:** os robôs do v4 deixam de abrir posições novas das 18 às 24 h UTC (vira regra fixa, como a do stop). **Se não passar:** nada
  muda e o achado de 11–15/11 fica registrado como acaso ou deriva passageira.
- **Cuidado anotado (confusão):** compras 48,1% × vendas 57,8% no mesmo período não é achado: o mercado caiu nesses dias, e lado e queda do
  mercado estão misturados ("Analytical Skills for AI and Data Science", cap. 2, confundidores). Não vira hipótese sem separar o regime.

## Hipótese 47: Robô Livre — sem regras de decisão, só custo real e liquidação (registrada em 2026-11-15 18:20 BRT, antes de ligar)

- **Pedido do dono (15/11):** "crie um robô livre dessas regras e vamos ver como ele se comporta, se ele avança mais rápido".
- **Regra (`executor/robo_livre_nuvem.py`):** lado = maioria das 140 moedas em 24 h (a referência que ganhou do v4 ao vivo no vigia: 53,3% ×
  52,7%); entra nas 4 moedas mais fortes desse lado, carteira inteira a 20×, lucro reinvestido; sai quando a maioria vira ou a moeda sai das
  8 líderes; sem stop nem tempo máximo; liquidação a 4,5% contra (perde a margem da posição). Custo de 0,06% por lado na conta; o resultado
  sem custo aparece ao lado. Não obedece ordens do chefe. Não passou por teste de laboratório (é o ponto do pedido).
- **Medida:** carteira a cada rodada, desde US$ 10. Em 24 h (até 16/11 21:30 UTC) e em 7 dias: carteira com custo, carteira sem custo,
  número de liquidações. Nenhum número de expectativa é dado antes: não há teste que sustente um.

## Hipótese 48: trava de lucro no Robô Claude (registrada em 2026-11-15 19:10 BRT, antes de ligar)

- **Queixa do dono (15/11):** "quando estão positivos, entram em outras operações e começam a perder; não saem do lugar".
- **Medido (403 operações fechadas dos robôs da nuvem, velas de 1 min de cada uma):** depois de um ganho a operação seguinte NÃO é pior
  (Caçador −0,011 × −0,023 depois de perda; Minerador +0,006 × −0,027). O que existe é **devolver o lucro aberto**: no Robô Claude 8 de 9
  operações chegaram a +0,5% e terminaram no zero ou no negativo (devolução média de 3,5% do pico); nos robôs do v4 (15 min) só 0–9%.
- **Simulação (3 tentativas: armar a +0,3%, +0,5%, +1%; guardar metade):** Robô Claude melhora nas 3 (−3,19 → −0,76 / −0,58 / −0,38);
  nos robôs do v4 o efeito troca de sinal entre versões e entre metades do período (ex.: Caçador −3,35 → −1,55 a 0,3%, → −4,02 a 1%):
  **sem evidência, não muda**. Escolhida a de +1% para o Robô Claude (coerente com stop de 1,5–4%). Só 9 operações: amostra pequena.
- **Regra ligada:** chegou a +1% a favor (máxima/mínima de vela de 15 min fechada) → a saída sobe para +0,5%.
- **Juiz ao vivo (até 30 operações do Robô Claude ou 29/11):** as saídas pela trava somam mais do que essas mesmas operações somariam com a
  saída sem trava (recalculado com as velas). Se não, a trava sai.

## Hipótese 49: stop móvel em todos os robôs da nuvem (registrada em 2026-11-15 19:40 BRT, antes de ligar; substitui a H48)

- **Pedido do dono (15/11):** "eles devem realizar lucro e ir subindo o stop, acompanhando o movimento".
- **Simulação** nas mesmas 403 operações da H48 (velas de 1 min de cada uma; custo de 0,12% mantido; 5 tentativas, que somam 8 com as 3 da
  H48): arma quando o lucro aberto chega a A; a saída fica em G × o maior lucro já visto, subindo junto, nunca descendo. Resultado em US$:
  A 0,3%/G 50% −8,25 → −1,53 · A 0,5%/G 50% → −2,32 · A 1%/G 50% → −4,61 · **A 0,5%/G 70% → −0,51** · A 1%/G 70% → −3,67.
  Escolhida A 0,5%/G 70%: melhora nas duas metades (−5,40 → +0,20; −2,85 → −0,71) e em todos os robôs (Caçador −3,35 → −0,40, Robô Claude
  −3,19 → +0,95, Minerador −2,14 → −1,61, Rápido nuvem +0,45 → +0,56, Scalper −0,02 → −0,00). É resultado dentro da amostra: o juiz é ao vivo.
- **Ligado em:** Robô Claude, Caçador, Rápido nuvem, Scalper nuvem, Minerador (`executor/stop_movel.py`, minuto a minuto, junto com o stop
  de segurança na ordem real dos preços). Fora: testnet (ordens na corretora de teste, outro fluxo) e Robô Livre (sem regras, a pedido do dono:
  serve de comparação).
- **Juiz ao vivo (até 22/11):** a soma das saídas pelo stop móvel é maior que a soma dessas mesmas operações com a saída antiga (recalculada
  com as velas). Se não for, o stop móvel sai.

## Hipótese 50: torneio — campeão × desafiantes do Scalper (registrada em 2026-11-15 19:05 BRT, antes de ligar)

- **Missão do dono (15/11):** "ver qual robô performa melhor e aperfeiçoá-lo, inclusive suas habilidades".
- **Placar em 15/11 22:00 UTC** (operações fechadas de cada robô): Scalper nuvem fator de lucro 1,24 (25 ops, carteira 10,21) · Rápido nuvem
  0,90 (25) · Minerador 0,75 (178) · Caçador 0,69 (183) · Testnet 0,19 (22) · Robô Claude 0 (9) · Robô Livre: 2 liquidações em 41 min
  (carteira 3,80). Nenhum robô tem fator de lucro > 1 com 30 operações ou mais: o melhor é o Scalper, com amostra pequena.
- **Desafiantes (uma mudança cada, 2 tentativas):** Scalper B = sem o alvo fixo de +0,5% (o stop móvel da H49 leva o lucro);
  Scalper C = só apostas do v4 com |p − 0,5| ≥ 0,08 (a confiança foi o único achado robusto da H36).
- **Juiz (`executor/torneio.py`, a cada rodada):** depois de 30 operações do desafiante, fator de lucro maior que o do Scalper E soma maior,
  ambos medidos no mesmo período. O vencedor é anunciado na sala e vira a nova versão do Scalper.

## Hipótese 51: Scalper D — focar onde o Scalper ganha, só com prova (registrada em 2026-11-15 19:30 BRT, antes de ligar)

- **Pedido do dono (15/11):** "o Scalper na nuvem tem que focar onde ele está positivo".
- **Medido (29 operações do Scalper, carteira 10,58):** ganha nas saídas por lucro realizado (9 ops, +0,855) e stop móvel (2 ops, +0,197);
  perde nas saídas no fim da vela (15 ops, −0,381; contra a tendência 3 ops, −0,090). A saída não é escolhível na entrada. Segurar as 18 operações
  do fim da vela até alvo/stop/4 h daria −0,518 (real −0,471): não melhora. Segmentos de entrada com 29 operações se contradizem (18–24 h UTC
  +0,63 no Scalper e o pior horário do v4 inteiro no vigia): escolher agora seria ajustar ao acaso.
- **Regra:** o Scalper D é igual ao Scalper e evita, a cada rodada, os segmentos de entrada (lado, faixa de 6 h UTC, confiança ≥/< 0,08) em
  que o Scalper original perde com ≥ 50 operações e z ≤ −2 (`executor/torneio.py` escreve `dados/foco_scalper.json`). Nunca exclui os dois lados.
- **Juiz:** o do torneio (H50): depois de 30 operações, fator de lucro e soma maiores que o Scalper no mesmo período.

## Hipótese 52: novas rotas de saída para as apostas do v4 — sair do "fim da vela de 15 min" (pré-registrada em 2026-11-15 20:05 BRT, antes de rodar)

- **Pedido do dono (15/11):** "esse negócio de 15 minutos, de esperar vela de 15, de fechar antes, não tem sido bom. Reveja as fórmulas e rotas,
  com novos cálculos probabilísticos". Medido antes: no Scalper, as saídas no fim da vela somam −0,47 em 18 operações.
- **Dados:** TODAS as apostas do v4 conferidas ao vivo (`dados/cerebro_v4.json`, 11/11–15/11, ~12.800 apostas em ~140 moedas), com as velas de
  15 min da Binance de cada moeda. Entrada no fechamento da vela do sinal (como os robôs). Custo 0,12% ida e volta. Dentro de uma vela, se o
  stop e a saída de lucro couberem, conta o stop (conservador); o pico do stop móvel só vale a partir da vela seguinte.
- **Rotas (8 tentativas, contadas):** R0 atual (fim da vela seguinte, stop 1%) · R1 horizonte 1 h, stop 1% · R2 horizonte 4 h, stop 2% ·
  R3 stop móvel (arma +0,5%, guarda 70%) + stop 1%, máx. 4 h · R4 stop móvel + stop 2%, máx. 24 h · R5 alvo +2% e stop 1% (2 para 1), máx. 24 h ·
  R6 = R4 só nas apostas a favor do regime de 24 h (≤ 30% / ≥ 70% das moedas subindo) · R7 = R4 só com confiança |p − 0,5| ≥ 0,08.
- **Cálculo probabilístico publicado para cada rota:** acerto p, ganho médio G, perda média L, expectativa E = p·G − (1 − p)·L − custo, e o
  acerto de empate p* = (L + custo) ÷ (G + L).
- **Juiz:** média líquida por aposta > 0, z ≥ 2,50 (Bonferroni para 8 tentativas, 5% unilateral) com erro-padrão por vela de entrada, e média > 0
  nos 3 blocos de tempo. Só a rota aprovada substitui o fim da vela nos robôs do v4; se nenhuma passar, a melhor fica registrada e nada muda.
- **Limite honesto:** são 4 dias de mercado (quase todo em queda e depois repique). Uma rota aprovada aqui ainda precisa repetir ao vivo.

### Resultado da H52 (2026-11-15 20:40 BRT): R6 aprovada no juiz pré-registrado; robustez fraca

13.179 apostas do v4 (217 moedas, 11/11 18:45–15/11), velas de 15 min, custo 0,12%:

| rota | média/aposta | z (por vela) | blocos | acerto | G | L | empate p* |
|---|---|---|---|---|---|---|---|
| R0 atual: fim da vela, stop 1% | −0,145% | −6,55 | −0,131 −0,125 −0,158 | 42,7% | 0,58% | 0,47% | 56,5% |
| R1 1 h, stop 1% | −0,098% | −3,59 | −0,242 −0,192 −0,019 | 39,4% | 1,14% | 0,71% | 44,7% |
| R2 4 h, stop 2% | −0,100% | −1,38 | −0,100 −0,192 −0,051 | 41,2% | 2,21% | 1,52% | 43,9% |
| R3 móvel + stop 1%, 4 h | −0,106% | −4,03 | −0,180 −0,107 −0,092 | 56,5% | 0,75% | 0,95% | 62,8% |
| R4 móvel + stop 2%, 24 h | −0,090% | −3,33 | −0,269 −0,173 −0,011 | 71,7% | 0,78% | 1,87% | 75,1% |
| R5 alvo 2% / stop 1%, 24 h | −0,067% | −1,52 | −0,046 −0,131 −0,037 | 35,5% | 1,90% | 0,97% | 37,8% |
| **R6 = R4 a favor do regime de 24 h** | **+0,225%** | **+2,71** | **+0,296 +0,276 +0,193** | 83,5% | 0,78% | 1,85% | 74,9% |
| R7 = R4 confiança ≥ 0,08 | +0,203% | +0,77 | só 37 apostas | 70,3% | 0,55% | 0,20% | 43,2% |

- **Juiz pré-registrado: R6 APROVADA** (média > 0, z ≥ 2,50, 3 blocos positivos). R0, a rota em uso, é a pior das 8.
- **Robustez (feita depois, informativa):** as posições da R6 duram horas e se sobrepõem; agrupando por blocos de 6 h o z cai para +0,30
  (13 de 17 blocos positivos), e por 12 h +1,02 (7 de 9). 4.333 das 4.492 apostas da R6 são vendas na queda de 11–15/11: um único episódio.
  Contra o regime: −0,307% (2 de 9 blocos de 12 h positivos); regime neutro: −0,119%.
- **Decisão (pelo protocolo):** R6 substitui o fim da vela no Rápido nuvem e no Caçador (`V4P_ROTA=r6`, stop 2%). Os Scalpers ficam como estão
  (torneio). **Juiz ao vivo até 29/11:** Rápido e Caçador com R6 precisam de média por operação > 0 em 30+ operações; senão voltam ao fim da vela.

## Hipótese 53: Robô LBank — SOL, memecoins e Robinhood (HOOD) no perpétuo da LBank, simulado (registrada em 2026-11-15 21:30 BRT, antes de ligar)

- **Pedido do dono (15/11):** "faz o robô simulado da LBank" (day trade em memecoins, Solana e Robinhood).
- **Moedas (perpétuos da LBank):** SOL, DOGE, SHIB, PEPE, WIF, BONK, FLOKI, BRETT, POPCAT, FARTCOIN, PNUT, PENGU e HOOD (ação da Robinhood
  tokenizada; o perpétuo custa o mesmo que o HOODX à vista). Preços públicos da LBank (`marketData` do perpétuo; velas de 1 min da API à vista).
- **Regra (rota da H52 adaptada):** lado = regime da amplitude do mercado (140 moedas da Binance, H44): baixa → vende as até 4 moedas que mais caem
  em 24 h (≤ −1%); alta → compra as que mais sobem (≥ +1%); neutro → segue a tendência de 24 h da própria moeda quando |variação| ≥ 3%.
  Saídas: stop móvel (arma +0,5%, guarda 70%, minuto a minuto), stop de segurança de 2%, lado contra o regime (ou, no neutro, a moeda virar),
  24 h. US$ 25 a 10× por posição, até 4, carteira de US$ 10, piso de US$ 5, 0,06% por lado. Funding não entra na conta (anotado).
- **O que não sei:** a regra nunca foi testada nestas moedas nem na LBank; o neutro (|24 h| ≥ 3%) não tem teste nenhum.
- **Juiz (torneio, H50):** fator de lucro e soma depois de 30 operações; comparação com o Rápido nuvem (mesma rota R6) no mesmo período.

### H53 — adendo (16/11/2026, antes de ligar): universo do Robô LBank = todo o perpétuo da LBank

- **Pedido do dono (16/11):** "o robô da LBank olhe todas as moedas e todas as memecoins igual na Binance, não restrinja ele de ver".
- **Mudança única:** a lista fixa de 13 moedas (SOL, 11 memecoins, HOOD) vira todas as moedas USDT do perpétuo da LBank com volume ≥ US$ 1 mi
  em 24 h (mesmo corte de `lab/universo.py`; em 16/11 18:45 BRT: 312 de 845). Regra de entrada e saída, tamanho e custo não mudam.
- Moeda sem par à vista de mesmo nome não tem velas de 1 min: o stop de 2% é conferido no preço de cada rodada (15 min).
- **Até aqui (lista antiga):** 39 operações, carteira US$ 6,32, fator de lucro 0,42. **Juiz:** as próximas 30 operações com o universo novo,
  comparadas com essas 39 (soma e fator de lucro); sem ajuste depois de ver o resultado.

### Banco da mesa (16/11/2026) — medida que decidiu o desenho

- Pedido do dono: um robô que coordene as carteiras como um banco, sem dar crédito nem emprestar (tudo será dinheiro real).
- Medido antes de decidir (estado da nuvem de 16/11, 112 janelas de 30 operações, passo 10, todos os robôs): depois de 30 operações no lucro, as
  30 seguintes deram em média −0,557 (n 37); depois de 30 no prejuízo, −0,435 (n 75); correlação −0,136. **Lucro recente não se repete** →
  o banco NÃO move dinheiro para quem ganhou. Ele é tesoureiro (soma, margem, exposição consolidada, robôs em lados opostos na mesma moeda) e
  refaz essa medida a cada rodada (`executor/banco.py`, `dados/banco.json`).

## Hipótese 54: Guarda do dia — não devolver dia positivo (registrada em 16/11/2026 ~19:00 BRT, antes de ligar)

- **Regra do dono (16/11):** "nenhum robô deve terminar as 24 h no prejuízo". Nenhuma regra impede o mercado de cair; o que se pode obrigar
  é não devolver um dia que ficou positivo.
- **Regra:** dia UTC; resultado do dia = patrimônio − patrimônio na 1ª rodada do dia. Se chegou a +US$ 0,25 e voltou a metade do pico,
  fecha tudo no preço da rodada e não abre nada até 00:00 UTC (`executor/guarda_dia.py`). Dia negativo segue operando (regras 5 e 11).
  Em todos os robôs da nuvem (Rápido, Caçador, Scalpers A–D, Minerador, LBank, Claude, Livre); testnet fica fora (outro fluxo).
- **Medida antes de ligar** (estado de 16/11, 36 dias-robô, operações fechadas por dia de saída, sem as posições abertas no momento da
  trava): sem trava 7 dias positivos, soma −45,54; gatilho +0,15 → 10 e −27,95; **+0,25 → 11 e −26,40**; +0,50 → 8 e −33,75.
  3 gatilhos tentados; escolhido 0,25 depois de ver (0,15 e 0,25 dão quase o mesmo). Amostra pequena.
- **Juiz ao vivo (17/11 a 23/11):** fração de dias-robô positivos e soma por dia-robô, contra os 36 dias-robô anteriores (7/36 = 19%;
  −1,27 por dia-robô). Passa se as duas melhorarem.

## Hipótese 55: Não perseguir o movimento de 15 min (registrada em 16/11/2026 ~19:40 BRT, antes de ligar)

- **Pedido do dono (16/11):** "tire esse negócio de rompimento de entrada, acho que isso tá atrapalhando; analisar a moeda em todos os tempos gráficos".
- **Medido antes** (`estado-antes-do-zero-2026-11-16`, 1455 operações fechadas de 10 robôs com velas da Binance; tendência de cada tempo
  gráfico = último fechamento acima/abaixo da média das 20 velas fechadas antes da entrada; resultado por posição de US$ 25):
  todos os 5 tempos (15m, 1h, 4h, 1d, 1w) a favor: n 171, −0,054/op; ≥4 a favor: n 431, −0,053; <4: n 1024, −0,013 → exigir todos os
  tempos a favor PIORA. Isolado, 15 min a favor (perseguir): n 395, −0,070; contra: n 1060, −0,008. 3 blocos de tempo: a favor −0,046 /
  −0,043 / −0,111; contra −0,020 / +0,012 / −0,014 (3/3). 1 tentativa principal (5 tempos) + leitura por tempo gráfico; o de 15 min foi
  escolhido depois de ver os 5.
- **Regra:** nenhum robô abre compra com o preço acima da média de 20 velas de 15 min, nem venda abaixo dela (`executor/sem_perseguir.py`).
  Vale para todos (Rápido, Caçador, Scalpers, Minerador, Claude, Livre, LBank), sem escolher robô depois de ver (Caçador e Minerador foram
  melhores a favor no recorte por robô; não são excluídos).
- **Juiz ao vivo (17/11 a 23/11):** média por operação da mesa contra −0,0175/op (média das 1455 operações antes). Passa se for maior nos
  3 terços da semana.

## Hipótese 56: Radar de oportunidades a partir de 1 segundo, em todos os tempos gráficos (registrada em 16/11/2026 ~20:00 BRT, antes de rodar)

- **Pedido do dono (16/11):** "o que importa é a visão de oportunidade; se encontrar, entra comprado ou vendido; não importa o tempo gráfico;
  todos lendo o mercado a partir de 1 segundo e operando em todos os tempos gráficos".
- **Dados:** velas de 1 s da Binance à vista (data.binance.vision, arquivos diários), 12 moedas líquidas (BTC, ETH, SOL, XRP, DOGE, BNB,
  ADA, PEPE, SUI, LINK, AVAX, TRX), 3 dias = 3 blocos: 13/11, 14/11, 15/11/2026.
- **Leitura:** em cada segundo, para cada janela w ∈ {5 s, 15 s, 1 min, 5 min, 15 min, 1 h, 4 h}: z_w = retorno da janela ÷ (desvio dos retornos
  de 1 s na última hora × √w). Oportunidade = |z_w| ≥ 4 em alguma janela (a de maior |z| decide o lado). Volume da janela ÷ volume médio da
  mesma janela na última hora = vol_w.
- **3 regras (3 tentativas, todas contadas):** R1 reversão (entra contra o movimento); R2 continuação (entra a favor); R3 reversão só com
  vol_w ≤ 1 (a regra H28 do Minerador, que passou, generalizada para todos os tempos).
- **Execução simulada:** US$ 25 por posição, 0,06% por lado; uma posição por moeda; saída por stop móvel (arma +0,5%, guarda 70%), stop 1%,
  alvo +2% (US$ 0,50), ou 1 h; 60 s de espera após sair.
- **Aprovação:** média por operação > 0 depois do custo nos 3 dias, com ≥ 30 operações em cada dia. Sem ajuste depois de ver.
- **Resultado H56 (16/11, `lab/radar_1s.py`, 12 moedas × 13–15/11, velas de 1 s): REPROVADA nas 3 regras.** R1 reversão: 1036 ops,
  −0,0289 US$/op (dias −0,034 / −0,039 / −0,014), acerto 58%. R2 continuação: 1015 ops, −0,0261 (−0,032 / −0,020 / −0,028), 56%.
  R3 reversão sem volume: 456 ops, −0,0169 (−0,017 / −0,030 / −0,002), 61%. Custo por operação US$ 0,03: antes do custo R1 +0,001,
  R2 +0,004, R3 +0,013 por operação — a leitura de 1 s quase empata e o custo leva tudo. Decisão do dono: o Radar (R3) entra na mesa
  SIMULADO, como comparação ao vivo (como o Robô Livre na H47), marcado como reprovado no laboratório.
- **H55 REVOGADA pelo dono (16/11, ~20:40 BRT), antes de ter resultado ao vivo:** "a decisão não deve ser limitada por tempo". Saiu de todos
  os robôs. Junto saíram os outros limites de 15 min: a rodada da nuvem não espera mais a vela (começa 1 min depois da anterior); Scalpers
  A–D passam à rota R6 da H52 (sem saída no fim da vela; mantêm o alvo deles); Minerador sai por stop móvel, stop de 2% ou 24 h, não mais
  no fim da vela seguinte (a regra H28 foi testada saindo na vela seguinte: a saída nova não foi testada). O v4 continua prevendo em velas de
  15 min (é como foi treinado).

## Hipóteses 57 e 58: meta do dia e reinvestir % da carteira (registradas em 17/11/2026, antes de rodar; ideias dos vídeos do "Grok bot")

- **H57 meta do dia:** quando o resultado do dia (patrimônio − patrimônio na 1ª rodada do dia UTC) chega a +META, o robô fecha tudo e trava
  até 00:00 UTC (soma-se à guarda do dia H54). META testadas: US$ 12 (meta do dono), US$ 1 e US$ 0,50 — 3 tentativas.
- **H58 reinvestir:** o tamanho da posição deixa de ser fixo (US$ 25) e passa a ser proporcional à carteira: nocional = 2,5 × patrimônio
  realizado no momento da entrada (igual a US$ 25 com US$ 10; cresce com o lucro e encolhe com a perda). Variante do vídeo: margem = 60% do
  caixa livre (nocional = 6 × caixa livre a 10×) — 2 tentativas.
- **Dados:** operações fechadas da etiqueta `estado-antes-do-zero-2026-11-16` (robôs da mesa menos testnet), na ordem real de entradas e
  saídas; resultado em % do nocional preservado.
- **Aprovação:** carteira final somada dos robôs maior que a regra atual E maior fração de dias-robô positivos (H57) / sem robô abaixo do
  piso de US$ 5 que não estava antes (H58).
- **Resultado H57/H58 (17/11, contrafactual nas operações da etiqueta, 9 robôs, 34 dias-robô):** atual 78,45 (9/34 dias positivos, 1 robô
  < US$ 5). H57 meta 12: 78,45 (nenhum dia chegou) — sem efeito; meta 1: 78,65, 9/34 — reprovada (dias não melhoram); **meta 0,50: 82,58,
  11/34 — aprovada**. **H58 proporcional 2,5×: 81,91, 0 robôs < US$ 5 — aprovada**; 60% do caixa (vídeo): 70,26, 7/34, 2 < US$ 5 —
  reprovada. Aproximação: depois da trava, as posições abertas seguem até a saída real. Ligadas em 17/11 (`executor/guarda_dia.py` META,
  `executor/tamanho.py`) em Rápido, Caçador, Scalpers, Minerador, LBank, Claude e Radar (Livre já usa a carteira inteira).
- **H57 alterada pelo dono (17/11):** com a meta de +0,50, 8 robôs passaram de US$ 10 (10,11 a 10,86) e ficaram travados ("ninguém
  conseguiu fazer mais de 10"). META volta a US$ 12 (meta do dono; no contrafactual, igual a não ter meta); a guarda H54 continua. Travas
  antigas pela meta de 0,50 são soltas. Robô LBank só entra em moeda com velas de 1 min na LBank (SPACE1 −11% e AIOT −7% com stop de 2%:
  sem velas de 1 min o stop só era conferido a cada rodada).

## Hipótese 59: Chefe OpenBot no testnet — as decisões do chefe executadas com ordens reais e stop na corretora (registrada em 17/11/2026 ~22:00 BRT = 18/11 01:00 UTC, antes de ligar)

- **Pedido do dono (17/11):** o chefe da mesa (agente OpenBot, rotina de 30 min) passa a operar a conta de TESTE de futuros da Binance
  (`testnet.binancefuture.com`, dinheiro fictício) no lugar do robô "v4 Testnet", com ordens de verdade. Nenhum dinheiro real.
- **Entrada:** as posições da decisão do chefe (`posicoes` do `dados/decisao_claude.json` que ele mesmo gravou, válida por 75 min), as mesmas
  do Robô Claude simulado: moeda, lado (compra/venda), até 4 ao mesmo tempo. Executa a mercado na rodada da rotina, logo depois de gravar a
  decisão (o simulado entra no fechamento de 15 min da rodada seguinte da nuvem). Moeda que não existe nos futuros do testnet, ou cujo nocional
  mínimo passa de 1,5 × o tamanho da posição, não entra (anotado).
- **Proteção na corretora:** toda entrada sai junto com um STOP_MARKET reduce-only guardado na corretora (máquina dormindo não deixa posição
  sem stop; 13/11: −1,68 por isso). Stop inicial = o do Robô Claude: 2 × amplitude média de 1 h (24 h de velas de 15 min do testnet), entre 1,5% e 4%.
  Se o stop não for aceito, a posição é fechada na hora. **Stop móvel:** a cada rodada (30 min), com as velas de 1 min do testnet desde a última
  conferência: se o pico a favor chegou a +0,5%, o stop da corretora sobe para entrada ± 70% do pico (nunca desce). Diferença declarada para o
  simulado: o simulado confere o stop móvel minuto a minuto; aqui ele só sobe a cada 30 min (entre rodadas vale o último stop guardado).
- **Saídas:** stop da corretora (segurança ou móvel); moeda fora da lista de posições da decisão, ou lado invertido (a mercado, reduce-only);
  24 h sem nova decisão; guarda do dia (H54: chegou a +0,25 no dia UTC e voltou à metade → fecha tudo e trava até 00:00 UTC); meta do dia de
  US$ 12 (H57). Sem trava de perda diária; sem pausa no prejuízo ou com operação aberta; piso de US$ 5.
- **Tamanho:** carteira própria de US$ 10 (contabilidade do robô dentro da conta de teste, que tem ~US$ 4.983); nocional = 2,5 × carteira
  realizada (H58), alavancagem 10×, margem = nocional ÷ 10.
- **Custo e resultado:** o resultado de cada operação é o da corretora: `realizedPnl` menos `commission` das execuções (`/fapi/v1/userTrades`),
  inclusive a taxa da entrada. Preços e execuções são os do testnet (o livro do testnet não é o da Binance real; anotado como limite).
- **Ao voltar de uma pausa da máquina:** antes de qualquer decisão, confere na corretora posições, stops executados e ordens; o que a corretora
  fechou entra nas fechadas com o resultado dela. Ordem ou posição na conta que o estado não conhece é cancelada/fechada (conta só deste robô).
- **Estado:** `dados/robo_openbot_testnet.json` no ramo `estado` (gravado só por este robô); na EQUIPE como "Chefe OpenBot (testnet)".
- **Juiz (uma avaliação, sem ajuste depois de ver):** ao completar 30 operações fechadas OU 7 dias (25/11/2026, o que vier primeiro).
  1. **Passa** se o resultado líquido somado for > 0 e o fator de lucro > 1.
  2. **Comparação declarada:** contra as operações do Robô Claude simulado com `decisao_t` no mesmo período (as mesmas decisões): diferença
     de resultado por operação = custo real de execução (taxas, escorregamento, stop móvel de 30 min). Relatada, não aprova nem reprova.
  Previsão registrada antes: não sei (o Robô Claude tem 7 operações; amostra pequena).

### H59 — emenda (17/11/2026 ~22:40 BRT = 18/11 01:40 UTC, antes de qualquer ordem pela regra nova): a escolha passa a vir do universo inteiro pelo v4
- **Pedido do dono (17/11):** "operar no testnet olhando TODAS as moedas"; analisar a cada rodada a probabilidade do v4 de cada moeda, o regime de
  24 h, volume e movimento de 1 h/4 h/24 h, e escolher as melhores oportunidades nos dois lados.
- **Muda só como o chefe escolhe as `posicoes`** (que valem para o Robô Claude simulado E para o testnet, como antes). Script `universo.py` do chefe:
  ordem = confiança do v4 no lado, |p − 0,5| (o único achado robusto, H36). **Entra** só com confiança ≥ 0,08 (faixa de 57,5% e 65,5% de acerto
  no laboratório), no lado do regime de 24 h (H44; neutro = os dois lados), fora de moeda com |4 h| ≥ 15% (esticada, cartilha), que exista nos
  futuros do testnet com nocional mínimo ≤ 1,5 × a posição, no máximo uma de BTC/ETH, até 4 posições. **Mantém** a aberta enquanto o regime não
  virar contra e o v4 não apontar o lado oposto com confiança ≥ 0,03; senão ela sai da lista (fecha). Fonte: `ultima` do `dados/cerebro_v4.json`
  (se a rodada mais nova da nuvem trouxer < 50 moedas, usa a mais nova com o universo completo de até 15 min). Memecoins: o preço do perpétuo da
  LBank é lido só para comparação; ordens só no testnet da Binance.
- **Execução, proteção, tamanho, custo e juiz:** os da H59 (stop STOP_MARKET reduce-only na corretora em toda entrada, guarda do dia, meta 12, 24 h,
  2,5 × carteira a 10×, resultado da corretora; 30 operações ou 25/11; passa com soma > 0 e fator de lucro > 1). As 2 operações abertas antes da
  emenda (ZEC e RENDER, 18/11 01:04 UTC) contam no juiz e são relatadas à parte. **Comparação declarada (não decide):** Robô Claude (mesmas posições,
  execução simulada) e Caçador (também escolhe pela confiança do v4) no mesmo período. Previsão: não sei; pelo laboratório (H31/H36), entrar por
  confiança do v4 e sair em 15 min não paga o custo; aqui a saída é pelo stop móvel/24 h (como a R6, H52), o que não foi testado com esta seleção.

## Hipótese 60: alavancagem na carteira — posição de 3,75× ou 5× a carteira, a 20× (registrada em 17/11/2026 ~23:05 BRT = 18/11 02:05 UTC, antes de rodar)

- **Pedido do dono (17/11):** "a mesa se saiu muito mal, não consegue passar de 11 dólares... eu quero alavancagem na carteira". Hoje (H58) cada
  posição tem nocional = 2,5 × a carteira realizada, a 10× (margem = 25% da carteira; 4 posições = carteira inteira em margem, 10× de exposição).
- **Braços (3 tentativas, contadas):** A) nocional = 3,75 × carteira; B) nocional = 5 × carteira; C) nocional = 5 × carteira só enquanto o robô está
  no lucro com prova no momento da entrada (carteira > US$ 10 e fator de lucro > 1 em ≥ 30 operações fechadas até ali), senão 2,5 × (regra decidível
  ao vivo, sem olhar o futuro). Nos três a alavancagem da corretora sobe para 20× (margem = nocional ÷ 20, para as 4 posições caberem). Com 20×, a
  liquidação fica a ~5% contra; todos os stops da mesa ficam entre 1% e 4%. Perda de uma operação limitada à margem (liquidação) nos braços.
- **Dados (dois conjuntos independentes):** (1) operações fechadas da etiqueta `estado-antes-do-zero-2026-11-16`; (2) operações fechadas desde o zero
  de 16/11 até agora. Robôs que usam o tamanho da H58: Rápido nuvem, Caçador, Scalpers A–D, Minerador, Robô Claude, Robô LBank, Radar (Livre tem
  tamanho próprio; testnets ficam fora). Resultado de cada operação em % do nocional preservado (já com o custo de 0,12%); entradas e saídas na ordem
  real; nocional calculado na entrada com a carteira realizada daquele momento; abaixo do piso de US$ 5 o robô não entra mais. Guarda do dia e
  posições que não caberiam na margem não são simuladas (anotado).
- **Passa** o braço que, nos DOIS conjuntos: (a) a soma das carteiras finais for maior que a da regra atual (2,5×) e (b) nenhum robô terminar abaixo
  do piso de US$ 5 sem estar abaixo também na regra atual. Entre os aprovados, vale o de maior soma no conjunto (2). Vale para todos os robôs da lista
  (não se escolhe robô depois de ver). Se nenhum passar: nada muda e o resultado fica registrado.
- **Contexto já medido (não decide):** o Banco mediu que o lucro de 30 operações não se repete nas 30 seguintes (correlação −0,14; 16/11), e o Robô
  Livre (carteira inteira a 20×) quebrou em 1 dia (4 liquidações, carteira 0,90).

### Resultado da H60 (18/11 02:10 UTC, `lab/alavancagem.py` → `dados/lab/alavancagem_resultado.json`): reprovada nos três braços
| braço | antes do zero: soma (9 robôs) | robôs < US$ 5 | desde o zero: soma (10 robôs) | robôs < US$ 5 |
|---|---|---|---|---|
| atual 2,5× a 10× | 60,93 | — | 95,04 | — |
| A 3,75× a 20× | 48,89 | Caçador, Claude, Rápido | 96,53 | Radar |
| B 5× a 20× | 42,63 | os 9 | 96,52 | Radar |
| C 5× só no lucro com prova | 58,58 | — | 94,21 | — |
- Conferência: o braço atual reproduz as carteiras reais desde o zero (Caçador 12,00 × 11,97; Claude 8,85 × 8,85; Radar 5,80 × 5,85).
- Leitura: alavancar multiplica o resultado dos dois lados. Antes do zero (mesa perdendo) o 5× levaria os 9 robôs ao piso; desde o zero o Caçador
  iria a 14,26 e o Scalper B a 11,76, mas o Radar cairia abaixo de US$ 5. Alavancar só quem está no lucro com prova (C) perde nos dois conjuntos:
  o lucro não se repete (como o Banco já mediu). O gargalo é a vantagem por operação, não o tamanho. Nada muda.

### H54 REVOGADA e LBank com memecoins primeiro (decisão do dono, 18/11/2026 ~16:45 BRT = 19:45 UTC)
- **Dono:** "pode destravar todos eles, eu quero ver eles operando igual em wall street, caçando oportunidades e fazendo entradas seja em short ou em
  long, mesmo que seja scalper. quero ver o lbank operando em memecoins também." A guarda do dia (H54) sai de todos os robôs antes do fim do juiz
  dela (17–23/11); as travas feitas por ela são soltas. Ficam a meta de US$ 12 (H57), o piso de US$ 5 e os stops. O juiz da H54 não será feito
  (registrado como não julgado). Regime de 24 h (H44) continua decidindo o lado; no neutro os robôs operam compra e venda.
- **H53, adendo 2 (LBank):** memecoins (lista em `executor/robo_lbank_nuvem.py`; 11 com volume e velas de 1 min na LBank em 18/11: DOGE, SHIB, PEPE,
  WIF, FLOKI, FARTCOIN, PENGU, PEOPLE, CHILLGUY, USELESS, PUMP) vão na frente da fila de entradas e, no regime neutro, entram a favor da tendência
  de 24 h da própria moeda a partir de 1% (as outras seguem pedindo 3%). Não testado no laboratório; o juiz é o do torneio (H50): fator de lucro e
  soma das próximas 30 operações, comparadas com as 23 anteriores (soma −4,26, fator 0,47).

## P1 do Treinador: entrada em aposta velha do v4 (julgada em 18/11/2026 ~21:30 UTC; proposta em `Shared/baleias/propostas.md`)

- **Defeito alegado:** `executor/v4_perp_nuvem.passo` (Caçador, Rápido nuvem, Scalpers A–D) escolhe candidatos em `pendentes` do
  `cerebro_v4.json` sem olhar a idade. Uma moeda que sai da previsão deixa a aposta lá para sempre (`cerebro_v4_nuvem.passo` só apaga
  quando a moeda volta a ser prevista). A entrada usa `p["px"]` e `p["t"]` da vela antiga.
- **Conferido no código:** linhas 159–184 (`entrada = p["px"]`, `entrada_t = (p["t"] + 15 min)`, sem teste de idade), e
  `stop_movel.conferir`/`preparar`, que confere o stop e o stop móvel nas velas de 1 min **a partir de `entrada_t`**, não da rodada que abriu.
- **Reproduzido** com um método diferente do do Treinador (`lab/atraso_entrada.py`; atraso = hora do evento "ENTROU" da rodada − `entrada_t`,
  juntando os eventos de todas as revisões do ramo `estado` até 8d0382f2; todas as fechadas casadas):

| robô | todas: n / soma / fator | velhas (> 30 min): n / soma | limpas: n / soma / fator | limpas que saíram ANTES da rodada que abriu |
|---|---|---|---|---|
| Caçador | 48 / +1,969 / 1,69 | 7 / −0,055 | 41 / +2,024 / 1,89 | 7 / +0,983 |
| Rápido nuvem | 45 / +0,711 / 1,23 | 17 / +0,523 | 28 / +0,187 / 1,09 | 3 / +0,384 |
| Scalper | 83 / +0,619 / 1,19 | 27 / +0,567 | 56 / +0,052 / 1,02 | 1 / −0,030 |
| Scalper B | 101 / +1,030 / 1,19 | 28 / +1,094 | 73 / −0,065 / 0,99 | 3 / +0,126 |
| Scalper C | 93 / +0,141 / 1,03 | 13 / +0,260 | 80 / −0,119 / 0,97 | 7 / +0,555 |
| Scalper D | 83 / +0,619 / 1,19 | 27 / +0,567 | 56 / +0,052 / 1,02 | 1 / −0,030 |

  Caçador e Rápido batem exatamente com os números do Treinador; no Scalper B, uma operação muda de grupo (72/29 dele, 73/28 aqui).
  Atraso das limpas: mediana de ~5 min, máximo de 13–20 min. Atraso das velhas: de 2,1 a 99,7 h.
- **Achado a mais (não estava na P1):** mesmo na vela mais nova, a rodada roda de 0 a 20 min depois do fechamento. A entrada fica no preço do
  fechamento e o stop móvel é conferido nesses minutos, que já passaram. 7 das 41 limpas do Caçador saíram pelo stop móvel antes de o robô
  "entrar" (+0,983 de +2,024; fator 29). Também não é executável.
- **Veredito: P1 APROVADA como correção de simulação** (não é estratégia, então não há juiz de lucro). Ela vem com uma emenda pela mesma razão:
  1. só entra a aposta cuja vela do sinal é a última vela de 15 min fechada (P1);
  2. a entrada é no preço e na hora da rodada que abre, e o stop/stop móvel só confere minutos a partir dela (emenda do Laboratório).
- **Verificação ao vivo (substitui o critério b da P1):** nas próximas 30 operações de cada robô afetado, `lab/atraso_entrada.py` tem de dar zero
  operações com atraso > 30 min e zero com saída antes da rodada que abriu. Se falhar, a correção volta ao Baleias.
- **Consequência para os juízes ao vivo** (decidida agora, antes de ver qualquer número depois da correção): as operações abertas antes da
  correção ficam como registro e não servem de prova. H52 (Rápido e Caçador): 30 operações abertas depois da correção (o prazo de 29/11 se
  estende até elas existirem). H49: as mesmas operações pós-correção (≥ 30) no lugar da janela até 22/11. Torneio H50/H51 e H53 (só no LBank,
  outro código, não afetado): placares dos robôs do v4 recomeçam na correção. O pedido de "contar só as limpas" não é aceito, porque as limpas
  também olham até 20 min do passado.
- **Não conferido:** Robô Claude simulado (entra no "fechamento de 15 min da rodada seguinte", então pode ter o mesmo defeito), Minerador, Radar, LBank.
  O Chefe OpenBot no testnet usa ordens reais, então não tem esse defeito.

## Hipótese 61: os agentes do OpenBot operam no lugar dos robôs (registrada em 18/11/2026 ~17:00 BRT = 20:00 UTC, antes de ligar)
- **Dono (18/11):** "a partir de agora quem opera são vocês no lugar dos robôs. Retire os robôs do painel e coloque no lugar deles os agentes do
  OpenBot". Os robôs (Rápido, Caçador, Scalpers A–D, Minerador, LBank, Livre, Radar) saem do laço da nuvem e do painel (`ROBOS_APOSENTADOS` em
  `baleias/equipe.py`; `radar.yml` desligado); as carteiras deles ficam congeladas como estão (histórico). Cérebro v4, vigia, retrato, torneio e banco seguem.
- **Quem opera (carteira simulada de US$ 10 cada, mesma execução do Robô Claude: até 4 posições, stop pela volatilidade 1,5–4%, stop móvel H49,
  24 h, 2,5 × a carteira a 10×, custo 0,06%/lado, meta de US$ 12, piso de US$ 5):** ⚓ Baleias (chefe; método H59: v4 com confiança ≥ 0,08 no
  lado do regime, e a conta de TESTE com ordens reais), 🎯 Treinador (método do Caçador: as apostas mais confiantes do v4 — regime de baixa 4 vendas,
  alta 4 compras, neutro 2 + 2), 🔬 Laboratório (só v4 com confiança ≥ 0,12, o achado H36, no lado do regime) e 🛡 Guardião (tendência de 24 h decide
  o lado; as moedas que lideram o movimento, memecoins primeiro; neutro: |24 h| ≥ 3%, memecoins ≥ 1%). Todos mantêm a posição enquanto o regime e o
  sinal do próprio método não virarem contra; nenhuma moeda esticada (|4 h| ≥ 15%). A escolha é a do script `operar.py` (regra fixa); o agente
  escreve leitura e lição, não troca moedas por opinião. Decisão a cada 30 min por agente; vale 75 min.
- **Juiz (torneio H50, ao vivo):** depois de 30 operações de cada agente, fator de lucro > 1 e carteira > US$ 10; campeão entre os aprovados.
  Comparação declarada (não decide): resultado dos robôs aposentados que faziam o mesmo método (Caçador, LBank) até 18/11. Previsão: não sei.
- **P1 aplicada pelo agente Baleias (18/11 ~20:25 UTC; hora exata = início da rodada da nuvem anotada em MELHORIAS.md):** (b) no executor que hoje roda
  TODOS os agentes (`executor/robo_claude_nuvem.py`): entradas e saídas por decisão no fechamento da última vela de 1 min fechada na hora da rodada
  (`stop_movel.precos_da_rodada`), `entrada_t` = hora da rodada, stop de 15 min só em velas que começam depois da entrada. (a)+(b) também em
  `executor/v4_perp_nuvem.py` (só aposta da última vela fechada; entrada no preço e na hora da rodada), que está parado desde a H61 (robôs aposentados):
  vale se os robôs voltarem. Testes `P1EntradaNaRodada`.

## Hipótese 62: agentes operam livres, estilo scalper (decisão do dono, registrada em 18/11/2026 17:37 BRT = 20:37 UTC, antes de ligar; nuvem com o código novo desde a rodada 44393086663, 20:38 UTC)
- **Dono:** "põe os robôs para operar livremente e tomar suas próprias decisões de entrada e stop. Quero ver eles fazendo scalper, operações rápidas."
  Os operadores são os agentes do OpenBot (H61). A escolha das moedas deixa de ser a regra fixa do `operar.py`/`universo.py` (vira sugestão e panorama):
  cada agente decide moeda, lado e, por posição, `stop_pct` (0,3–4%), `alvo_pct` (0,2–5%, realiza o lucro) e `max_min` (5–1440 min).
- **Execução:** a nuvem (`executor/robo_claude_nuvem.py`) confere stop, alvo e stop móvel minuto a minuto e fecha no prazo; reabre só na próxima decisão
  do agente (a cada 30 min). Na conta de teste o chefe guarda na corretora o stop E o alvo (TAKE_PROFIT_MARKET reduce-only); o prazo é conferido a cada
  rodada dele. Custo 0,06%/lado, tamanho 2,5 × carteira a 10×, até 4 posições, meta de US$ 12, piso de US$ 5 continuam.
- **O que o laboratório já sabe (não decide; o dono decidiu):** saídas curtas de scalper perderam para o custo em 5 min (H24, todos os pares alvo/stop),
  rompimento de 5 min perdeu (H25) e nenhuma regra de 1 min pagou 0,12% (H32). Previsão registrada: não sei para decisões discricionárias; o histórico
  aponta perda por operação perto do custo.
- **Juiz (torneio H50):** por agente, depois de 30 operações abertas a partir desta hora: fator de lucro > 1 e carteira > US$ 10. As operações de antes
  desta hora (H61) ficam separadas.

## Hipótese 63: raspagem das melhores carteiras da Hyperliquid ("monitor fomo") como sinal para os agentes (registrada em 18/11/2026 ~18:40 BRT = 21:40 UTC, antes de rodar)
- **Pedido do dono (18/11):** "os agentes façam uma raspagem pelas moedas e também nas melhores carteiras, tipo um monitor fomo, e comecem a operar
  depois dessa raspagem em scalper". Referências buscadas antes: bots que copiam o ranking da Hyperliquid (ranking 1×/dia, posições a cada poucos
  minutos, posição nova = sinal), o fomo.family (feed do que os melhores traders compram e vendem) e o aviso de que perto do topo do ranking há
  carteiras que só copiam as 10 primeiras. O teste 1 deste projeto (copiar carteiras grandes da Hyperliquid, saída em 4 h) parou com 18 sinais:
  +0,239% [−0,655; +1,132], sem conclusão.
- **Raspagem das carteiras (fixa):** ranking público `stats-data.hyperliquid.xyz/Mainnet/leaderboard`, renovado a cada 24 h. Entram contas com
  valor ≥ US$ 50 mil, lucro > 0 no mês, na semana e no total, ROI do mês ≥ 5% e giro do mês (volume ÷ conta) ≥ 10 (trader ativo, não quem só segura);
  as 40 de maior ROI do mês. A cada rodada da nuvem (~4 min), as posições abertas delas (`clearinghouseState`, API pública) e os preços de meio de
  livro (`allMids`). Moeda da Hyperliquid vira o par USDT da Binance (kPEPE → PEPE). Arquivo: `dados/carteiras_top.json`.
- **O que os agentes recebem (descritivo, não decide sozinho):** por moeda, quantas das 40 estão compradas e vendidas, o valor líquido, e o "feed":
  posições abertas ou fechadas por elas na última hora. A raspagem das moedas (v4, movimento, memecoins) continua. Os agentes decidem livres (H62).
- **Teste automático do sinal (o juiz desta hipótese):** cada abertura nova (moeda, lado) por uma das 40 vira um evento com o preço de meio da hora;
  é resolvido entre 60 e 75 min depois: retorno no lado da carteira menos 0,12% de custo. Rodadas que perderem a janela não resolvem (evento descartado).
  **Passa** com ≥ 300 eventos resolvidos: média > 0, t ≥ 2 com erro-padrão por hora de abertura (aberturas da mesma hora andam juntas) e média > 0 em
  2 dos 3 blocos de tempo. Leitura extra, não decide: o mesmo para eventos em que 2+ das 40 abriram o mesmo lado na mesma moeda em 1 hora.
  Uma tentativa só; o filtro das 40 não muda depois de ver.

## Hipótese 64: "perder de colher e ganhar de balde" — entrada que cresce com o ganho e saída com stop pequeno e lucro grande (registrada em 18/11/2026 19:35 BRT = 22:35 UTC, antes de rodar)
- **Pedido do dono (18/11):** "com os ganhos, faça eles aumentarem a porcentagem de valor de entrada. O tema central é: perder de colher e ganhar de
  balde — perder pouco e ganhar muito." E: "o que eu quero é melhorar a autonomia dos agentes, fazendo eles ganharem muito mais dinheiro."
- **Medido antes (não decide):** desde a H61 o chefe ganha em média US$ 0,053 e perde 0,103 por operação (o contrário do tema); as decisões dele
  usam stop 0,6% e alvo 0,5%. Na H52 a única rota aprovada (R6) ganha de colher (G 0,78%) e perde de balde (L 1,85%) com acerto de 83,5%; a rota
  2 para 1 (R5) deu −0,067%. Na H60, crescer a posição só no lucro com prova (braço C) perdeu nos dois conjuntos.
- **Parte T — tamanho (1 tentativa):** fator = 2,5 × carteira realizada ÷ US$ 10, limitado a [1,25; 5]; nocional = fator × carteira realizada
  (com US$ 12 → 3,0×; com US$ 8 → 2,0×: cresce no ganho, encolhe na perda). Alavancagem da corretora 10× com fator ≤ 2,5 e 20× acima (as 4 margens
  cabem; perda limitada à margem). Contrafactual igual ao da H60 (`lab/alavancagem.py`): conjunto 1 = etiqueta `estado-antes-do-zero-2026-11-16`;
  conjunto 2 = robôs da H60 e os 3 agentes desde o zero de 16/11 até agora. **Passa** se, nos DOIS conjuntos, a soma das carteiras finais for maior
  que a da regra atual (2,5×) e nenhum robô terminar abaixo do piso de US$ 5 sem estar abaixo também na regra atual.
- **Parte S — saída (4 tentativas, contadas):** todas as apostas do v4 conferidas ao vivo (`dados/cerebro_v4.json`) A FAVOR do regime de 24 h
  (≤ 30% das moedas subindo = só vendas; ≥ 70% = só compras; o regime é contado nas próprias moedas dos dados), velas de 15 min da Binance, entrada
  no fechamento da vela do sinal, custo 0,12%, stop conta primeiro dentro da vela, pico do stop móvel só a partir da vela seguinte, máximo 24 h:
  S1 stop 0,5% e alvo 1,5% · S2 stop 0,5% + stop móvel (arma +0,5%, guarda 70%), sem alvo · S3 stop 1% + stop móvel, sem alvo · S4 stop 1% e alvo 3%.
  Referência (não conta): R6 recalculada nos mesmos dados. **Passa** a rota com média líquida > 0, z ≥ 2,24 (Bonferroni para 4, 5% unilateral,
  erro-padrão por vela de entrada), média > 0 nos 3 blocos de tempo e ganho médio ≥ 2 × perda média (a definição do tema). Entre as aprovadas vale a
  de maior média.
- **O que entra:** parte T aprovada → o tamanho novo vale para os agentes da nuvem e para a conta de teste. Rota S aprovada → vira a forma obrigatória
  das posições dos agentes (stop até o da rota; alvo ≥ 3 × stop ou sem alvo, deixando o stop móvel levar o lucro); o `operar.py` e o `gravar.py`
  recusam decisão fora dela. O que não passar não entra e fica registrado; o dono recebe os números.
- **Juiz ao vivo do que entrar (até 02/12):** por agente, em 30+ operações: ganho médio ≥ 2 × perda média e carteira > US$ 10.

### Resultado da H64 (18/11 22:50 UTC, `lab/colher_balde.py` → `dados/lab/colher_balde_resultado.json`): parte T aprovada; parte S reprovada
**Parte T (tamanho que cresce com o ganho): PASSOU.**
| conjunto | soma atual (2,5×) | soma H64 | abaixo do piso só na H64 |
|---|---|---|---|
| antes do zero (9 robôs) | 60,93 | 63,40 | — |
| desde o zero (12 robôs e agentes) | 116,92 | 117,47 | — |
- Leitura: ajuda sobretudo quando a carteira cai (a posição encolhe: o Robô Claude antes do zero 5,85 → 6,40; o Radar 5,88 → 6,47). Com lucro a
  diferença é pequena (+0,55 na soma desde o zero). Entra na nuvem e na conta de teste.

**Parte S (saída colher/balde): nenhuma rota passou.** 24.891 apostas do v4, 5.842 a favor do regime, 236 moedas (1ª rodada do script perdeu 46
moedas por erro de rede e símbolo; refeita com nova tentativa e velas do à vista quando o perpétuo não tem o símbolo, mesma regra):
| rota | média/aposta | z | blocos | acerto | G | L | G ÷ L |
|---|---|---|---|---|---|---|---|
| S1 stop 0,5% alvo 1,5% | +0,055% | +1,04 | +0,197 +0,152 −0,180 | 33,0% | 1,38% | 0,60% | 2,30 |
| S2 stop 0,5% + móvel | +0,017% | +0,44 | +0,091 +0,047 −0,085 | 50,8% | 0,60% | 0,59% | 1,03 |
| S3 stop 1% + móvel | +0,084% | +1,60 | +0,229 +0,056 −0,028 | 68,0% | 0,61% | 1,03% | 0,59 |
| S4 stop 1% alvo 3% | +0,362% | +3,27 | +1,176 +0,299 −0,359 | 37,4% | 2,76% | 1,07% | 2,58 |
| R6 (referência) stop 2% + móvel | +0,134% | +1,94 | +0,336 +0,070 +0,006 | 80,4% | 0,61% | 1,80% | 0,34 |
- S4 é a melhor e é "colher/balde" (ganha 2,6 × o que perde), mas perdeu no bloco mais recente (−0,359%): não passa. O stop móvel corta o ganho
  em ~0,6% (G 0,60–0,61% em S2, S3 e R6): com ele não há balde. Nada vira obrigação; os números vão para o manual dos agentes como informação.

### Resultado da H20 (juízo diário, 19/11/2026 09:00 BRT = 12:00 UTC; `lab/juizo_h20.py`, `origin/estado` 12850e8c): REPROVADA
Critério pré-registrado (ajuste 2, 10/11): ≥ 500 apostas ao vivo e limite inferior de Wilson (95%) do acerto > 51%. Medido sem ajuste em
`dados/cerebro.json` (`operacoes` com `t` ≥ `inicio_ao_vivo` = 10/11 03:30 UTC; apostas de 10/11 13:45 a 19/11 05:45 UTC). 1 tentativa.
| apostas ao vivo | acertos | acerto | Wilson 95% | capital simulado |
|---|---|---|---|---|
| 563 | 297 | 52,8% | [48,6%; 56,8%] | 960,54 → 1269,65 |
- Limite inferior 48,6% < 51%: reprovada. O acerto fica acima do equilíbrio do contrato (51%), mas sem prova.
- Blocos de tempo (só informação, não fazem parte do critério): 166 apostas 54,8% · 185 apostas 47,6% · 212 apostas 55,7%.
- O que muda: nada (o v1 roda só no binário simulado; não decide nenhuma carteira). H21 (v2 × v1) segue: v2 com 266 de 300 apostas.

## Hipótese 65: métodos de fora com evidência publicada — fluxo agressor (scalper de 15 min), momento semanal comprado e vendido, e alavancagem pela volatilidade (registrada em 19/11/2026 ~11:00 BRT = 14:00 UTC, antes de baixar os dados)
- **Pedido do dono (19/11):** "vá atrás de um método lucrativo de scalper e de alavancagem (GitHub, Hugging Face, livros, YouTube, artigos); os robôs
  precisam acumular lucro, eu preciso dobrar o capital."
- **Pesquisa (19/11):** nenhum scalper público com lucro líquido verificável depois do custo (repositórios freqtrade e testes independentes de
  estratégias do YouTube ficam perto de 40–50% de acerto). O que tem evidência publicada e AINDA NÃO foi testado aqui:
  (1) desequilíbrio do fluxo agressor (volume comprador × vendedor) prevendo o retorno curto em cripto: sinal fraco e curto (Bieganowski & Ślepaczuk,
  arXiv 2602.00776; arXiv 2608.21888 acha reversão com AUC 0,54); (2) momento entre moedas COMPRADO E VENDIDO de 1–4 semanas (Liu, Tsyvinski & Wu,
  Journal of Finance 2022: ~3%/semana bruto, mais forte nas moedas grandes; a H15 testou só compra e top 5); (3) alavancagem inversa à volatilidade
  (Moreira & Muir, NBER w22208; Harvey et al., volatilidade-alvo em 60+ ativos reduz os extremos) e Kelly fracionado (½ Kelly).
- **Dados:** perpétuos USDT da Binance, velas com o volume agressor comprador (coluna "taker buy" das klines). Universo FIXO = as 60 moedas de maior
  volume em US$ nas últimas 24 h na hora de rodar (viés de sobrevivência anotado). Custo 0,12% ida e volta. Sem funding (anotado).
- **F — fluxo de 15 min (2 tentativas):** I = 2 × volume comprador ÷ volume − 1 da vela; z = (I − média) ÷ desvio das 96 velas anteriores da mesma
  moeda. Sinal com |z| ≥ 2,5. F1 segue o fluxo, F2 vai contra; entra no fechamento da vela do sinal, sai no fechamento 4 velas (1 h) depois.
  Últimos 60 dias.
- **M — momento semanal comprado e vendido (1 tentativa):** toda segunda 00:00 UTC, ordena as moedas com 21+ dias de histórico pelo retorno dos 21
  dias anteriores; compra os 20% de cima e vende os 20% de baixo, pesos iguais, segura 7 dias; custo 0,12% por perna por semana (giro inteiro,
  conservador). Velas diárias, últimos 730 dias.
- **Juiz (F1, F2, M; 3 tentativas):** média líquida > 0, t ≥ 2,13 (Bonferroni para 3, 5% unilateral; erro-padrão agrupado pela vela de entrada em F,
  pela semana em M) e média > 0 nos 3 blocos de tempo.
- **L — alavancagem pela volatilidade (só se F ou M passar; não conta tentativa):** exposição = 1 × (volatilidade-alvo ÷ volatilidade das 4 semanas
  anteriores da própria estratégia), limitada a 3×, alvo = a volatilidade média do treino (primeira metade). Passa se, na segunda metade, tiver
  Sharpe maior E queda máxima menor que a exposição fixa. Kelly e ½ Kelly calculados como informação.
- **O que entra:** método aprovado vira robô/regra na mesa simulada e na conta de teste, com o tamanho H64; alavancagem só pela L aprovada. Nada
  aprovado = registrado e o dono recebe os números.

### Resultado da H65 (19/11 ~14:20 UTC, `lab/metodos_fora.py` → `dados/lab/metodos_fora_resultado.json`): reprovada nas 3 tentativas
| tentativa | eventos | média líquida | t | blocos | acerto |
|---|---|---|---|---|---|
| F1 segue o fluxo agressor (15 min, 1 h) | 4.828 | −0,132% | −5,66 | −0,100 −0,166 −0,127 | 40,9% |
| F2 contra o fluxo agressor | 4.828 | −0,108% | −4,66 | −0,140 −0,074 −0,113 | 40,4% |
| M momento semanal comprado e vendido | 100 semanas | +0,241%/semana | +0,34 | −0,085 +0,900 −0,082 | 54,0% |
- Leitura: no fluxo, seguir e ir contra perdem quase exatamente o custo (0,12%): antes do custo o sinal vale ~0,01%, nada. O momento semanal tem
  média positiva só por causa de um bloco; queda máxima −48%. A parte L (alavancagem pela volatilidade) não roda porque nada passou; como informação,
  no momento semanal ela PIOROU (Sharpe 0,004 → −0,023; queda −48% → −51%). Nada entra na mesa.

## Hipótese 66: busca computacional em milhares de variações, com reserva intocada (registrada em 19/11/2026 ~11:40 BRT = 14:40 UTC, antes de baixar os dados)
- **Pedido do dono (19/11):** "crie um método onde a gente consiga dobrar esse capital; comece fazendo variações de testes, cálculos computacionais."
- **Risco conhecido:** testar milhares de regras sempre acha alguma que "deu certo" por sorte. Defesa pré-registrada: três trechos de tempo em ordem,
  e a reserva final só é usada UMA vez, pela regra escolhida pelo programa (sem eu olhar a reserva antes).
- **Dados:** velas de 1 h dos perpétuos USDT da Binance, as mesmas 60 moedas fixas da H65 (`dados/lab/h65_cache.json`), últimos 365 dias.
  Treino = primeiros 60% do tempo; validação = 20% seguintes; reserva = últimos 20% (~73 dias). Custo 0,12% ida e volta. Sem funding (anotado).
- **Variações (4.896 = 34 sinais × 2 filtros × 72 saídas):**
  sinais (entrada no fechamento da vela do sinal; "segue" ou "contra"): rompimento da máxima/mínima de N velas (N 12, 24, 48, 168);
  retorno de L velas com z ≥ k contra o desvio de 30 dias (L 1, 4, 24; k 2, 3); cruzamento da média de M velas (M 20, 50, 200);
  IFR de 14 nos extremos (20/80, 30/70); volume ≥ k × a mediana de 48 velas (k 3, 5) no lado da vela.
  Filtros: nenhum, ou só a favor do regime de 24 h (≤ 30% das 60 moedas subindo = só vendas; ≥ 70% = só compras).
  Saídas: stop 0,5/1/2/3%; alvo nenhum, 2× ou 3× o stop; stop móvel (arma +0,5%, guarda 70%) sim ou não; prazo 6, 24 ou 72 h.
  Dentro da vela, stop conta antes do alvo; o pico do stop móvel só vale da vela seguinte.
- **Escolha (automática):** no treino, as variações com ≥ 200 entradas, ordenadas pelo t (erro-padrão agrupado pela hora de entrada) da média
  líquida; as 20 melhores vão para a validação; fica a de maior t na validação entre as que tiverem média > 0 e t ≥ 2. Nenhuma = para aqui.
- **Juiz na reserva (1 tentativa):** média líquida > 0, t ≥ 2 e média > 0 nas duas metades da reserva. Também a carteira simulada de US$ 10 com o
  tamanho da H64 (até 4 posições) na reserva e um sorteio de Monte Carlo (10.000 ordens das operações da reserva) da chance de dobrar antes de
  cair ao piso de US$ 5 — informação, não decide.
- **Se passar:** vira robô na mesa simulada e na conta de teste, com juiz ao vivo de 30 operações; dinheiro real continua sendo decisão do dono.

### Resultado da H66 (19/11 ~15:30 UTC, `lab/busca_dobrar.py` → `dados/lab/busca_dobrar_resultado.json`): reprovada na reserva — e um erro de simulação achado
- **1ª rodada INVÁLIDA (erro do simulador):** as 20 melhores eram todas "stop 3% + stop móvel" e a reserva deu +0,386%/op, t 8,4. Controle feito
  antes de aceitar: entradas SORTEADAS ao acaso com a mesma saída davam +0,21% (comprando +0,19%, vendendo +0,20%) — impossível. Causa: quando a
  vela anterior já tinha FECHADO abaixo do nível do stop móvel, o simulador saía no nível (um preço que já tinha passado). Corrigido: sai no
  fechamento anterior (a abertura). Depois da correção o controle aleatório dá −0,108% (≈ o custo), como deve.
- **2ª rodada (simulador corrigido; mesma regra, mesma reserva — a reserva tinha sido usada uma vez com o simulador errado; a escolha é automática):**
  as 20 melhores do treino são quase todas "retorno de 24 h com z ≥ 2 a favor (segue), stop 3%, prazo 72 h, sem stop móvel". Escolhida pela
  validação: ret24h z ≥ 3, segue, filtro de regime, stop 3%, alvo 9%, 72 h (validação +2,9%/op, t 6,9).
  **Reserva: 1.304 entradas, média −0,246%, t −1,26, metades +0,133% e −0,485% → REPROVADA.** Monte Carlo: 10% de chance de dobrar antes do piso.
  Leitura: o que brilha na validação era a tendência daquele trecho; não se repetiu. O t agrupado por hora fica inflado com posições de 72 h que se
  sobrepõem (anotado).
- **Consequência do erro para as aprovações antigas (re-medido com a correção, `lab/colher_balde.py --so-s`, 27.910 apostas do v4):**
  | rota | antes (com o erro) | corrigido |
  |---|---|---|
  | R6 stop 2% + móvel, a favor do regime | +0,134%/aposta (H64) · +0,225% (H52, aprovada) | **−0,021%**, blocos +0,208 −0,099 −0,168 |
  | S3 stop 1% + móvel | +0,084% | −0,037% |
  | S2 stop 0,5% + móvel | +0,017% | −0,060% |
  | S4 stop 1% alvo 3% (sem móvel; não muda) | +0,362% | +0,309%, último bloco −0,472% |
  A aprovação da R6 (H52) e a do stop móvel (H49, também simulada em velas fechadas) estavam infladas por este erro. O stop móvel continua ligado
  (é proteção, não fonte de lucro), mas `executor/stop_movel.py` passa a sair no fechamento anterior quando ele já passou do nível (velas de 1 min
  agora trazem o fechamento). Lucro "pelo stop móvel" nas carteiras simuladas dos agentes até hoje (8 saídas, +0,80) pode estar inflado.

## Hipótese 67: gatilhos armados — os agentes deixam níveis de entrada que a nuvem confere minuto a minuto (decisão do dono, registrada em 19/11/2026 ~13:00 BRT = 16:00 UTC, antes de ligar)
- **Dono (19/11):** "os agentes estão demorando muito para operar… preciso de mais agilidade, operações constantes, varredura contínua; no tempo em
  que um agente está parado, várias oportunidades aparecem e passam despercebidas."
- **Execução (`executor/robo_claude_nuvem.py`):** além de "posicoes", cada decisão pode ter até 6 "gatilhos" {moeda, lado, acima OU abaixo, stop_pct,
  alvo_pct, max_min, validade_min 5–240 (padrão 120), motivo}. A cada rodada da nuvem (~3 min) cada gatilho é conferido nas velas de 1 min desde que
  foi armado; no primeiro minuto em que o preço cruza o nível, a posição abre no nível (ou no fechamento do minuto anterior se ele já tinha passado:
  sem olhar o futuro), com o tamanho da H64, até 4 posições. Nível que o preço já passou na hora de armar não é armado. Decisão nova substitui os
  gatilhos. Vale para as carteiras simuladas dos 4 agentes; a conta de teste do chefe continua entrando só nas rodadas dele (o stop tem de nascer
  junto com a entrada na corretora, H59).
- **O que o laboratório já sabe (não decide; o dono decidiu):** rompimentos de 5 min e de 1 h não pagaram o custo como regra fixa (H25, H66).
- **Juiz (até 03/12):** por agente, operações abertas por gatilho × abertas na rodada, em 30+ de cada: média por operação e fator de lucro.

## Hipótese 70 (registrada como "H68" em 3e5ea591; renumerada em 19/11 ~20:10 UTC porque a H68 do Caçador já estava no código): saída das posições com alvo do agente — o stop móvel não pode fechar antes do alvo (registrada em 19/11/2026 ~16:00 BRT = 19:00 UTC, antes de rodar; pedido do agente Engenheiro, auditoria de 19/11)
- **Medido antes (não decide):** controle de 4.000 entradas SORTEADAS no código da nuvem (`executor/stop_movel.conferir`, 10 moedas, 3 dias de velas
  de 1 min; script do Engenheiro `medir/controle_aleatorio.py`). Com stop 0,6% e alvo 1,2% em 120 min (o que o chefe usa), a média foi −0,117% (≈ o custo:
  o simulador está limpo). As saídas foram 1.896 pelo stop móvel, 1.638 pelo stop, 339 pelo prazo e **127 pelo alvo (3%)**. O stop móvel (arma +0,5%,
  guarda 70%) fecha antes de qualquer alvo acima de 0,5%. Na H64 já se via que G ≈ 0,6% com o móvel. A rota sem móvel (S4 stop 1% alvo 3%) foi a
  melhor, mas perdeu no último bloco.
- **Entradas (reais):** todas as apostas do v4 conferidas ao vivo (`dados/cerebro_v4.json`, `ops` com prob) com confiança |p − 0,5| ≥ 0,08, nos dois
  lados, de 16/11 21:53 UTC até a hora de rodar. Entrada como a nuvem faz depois da P1: fechamento da vela de 1 min que fecha 5 min depois do fim da vela
  do sinal (atraso mediano medido na P1). Velas de 1 min do perpétuo da Binance (à vista quando o perpétuo não tem o símbolo). Custo 0,12%.
- **Saídas (simuladas pelo próprio `stop_movel.conferir` da nuvem, nas velas de 1 min):** duas geometrias × três formas:
  - geometria G1: stop 0,6%, alvo 1,2%, prazo 120 min (a do chefe); G2: stop 1%, alvo 3%, prazo 24 h (a S4 da H64);
  - A0 (referência, a regra de hoje): stop móvel armando a +0,5% e guardando 70%, junto com o alvo;
  - A1: sem stop móvel quando a posição tem alvo;
  - A2: o stop móvel só arma quando o lucro chega à metade do alvo (G1 a +0,6%, G2 a +1,5%), guardando 70%.
  São **4 tentativas** (A1 e A2 nas duas geometrias), contadas.
- **Controle obrigatório (antes de olhar o resultado das entradas reais):** as mesmas 6 combinações com entradas sorteadas (mesmas moedas, mesmos
  instantes, lado sorteado). Cada combinação tem de dar média = −0,12% ± 3 erros-padrão. Se alguma sair disso, o simulador está errado: a rodada é
  inválida e nada é julgado.
- **Juiz (por tentativa):** diferença pareada (Ax − A0, mesma entrada) com média > 0, z ≥ 2,24 (Bonferroni para 4, 5% unilateral; erro-padrão
  agrupado pela vela de 15 min do sinal) e diferença > 0 nos 3 blocos de tempo iguais. Também é relatada a média absoluta de cada forma, mas ela não decide.
  Entre as aprovadas da mesma geometria vale a de maior diferença.
- **Se passar:** a forma aprovada vira a regra da nuvem para posições COM `alvo_pct` maior que 0,5% (`executor/robo_claude_nuvem.py`/`stop_movel.py`,
  quem aplica é o Baleias). Posições sem alvo, ou com alvo até 0,5%, seguem com o móvel de hoje. Juiz ao vivo: 30 operações com alvo > 0,5% depois de ligada,
  com a soma pela regra nova maior que a soma das mesmas operações pela A0 (recalculada). **Se não passar:** nada muda, e a ROTINA (r9, passo 3)
  continua avisando que com alvo acima de 0,5% quem fecha é o stop móvel.
- **Previsão registrada:** não sei. Com entradas sem vantagem a saída não muda a média, como mostrou o controle (−0,117% / −0,100% / −0,117%). Só muda se
  as apostas do v4 tiverem continuação além de +0,5%.

## Hipótese 69: rotina r9 (postura ativa, só cortes duros) × r8 — juiz ao vivo (registrada em 19/11/2026 ~16:00 BRT = 19:00 UTC, antes de qualquer operação r9 ser medida)
- **O que mudou (Engenheiro, auditoria de 19/11, a pedido do dono: "agilidade, operações constantes"):** `Shared/baleias/operar/ROTINA.md` r8 → r9.
  O REVISOR deixa de cortar por "menos de 4 dos 6 tempos a favor", "v4 abaixo de 0,12", "carteiras contra" e "dúvida". Ficam só os cortes duros
  (alvo < 0,24%, |4 h| ≥ 15%, dado faltando, padrão CONFIRMADO contra no tempo do prazo). Com carteira vazia, o agente entra a mercado na leitura mais forte.
  Medido antes pelo Engenheiro (12:51–15:17 UTC): 31 decisões, 5 com posição; 58% dos descartes por tempos, 27% pelo v4 < 0,12.
- **Veredito do Laboratório sobre a natureza:** é mudança de **prompt**, não de regra de estratégia. Desde a H62 os agentes decidem livres, e o REVISOR
  nunca foi pré-registrado nem testado. O único teste parecido (H55) mediu que exigir todos os tempos a favor PIORAVA, e o v4 ≥ 0,12 não tinha passado no
  perpétuo (H31/H36; só no 1º bloco). Então não volta para a r8. O que a r9 muda é a quantidade de entradas, e isso é medido aqui.
- **Versão de cada operação:** `versao_rotina` da decisão cujo `t` = `decisao_t` da operação (histórico do ramo `estado`, `dados/decisao_*.json`).
  Decisão sem o campo = "antes da r8". Operação aberta por gatilho (H67) conta na versão da decisão que armou o gatilho.
- **Controle (o mesmo para as duas versões):** para cada operação real, a mesma moeda, o mesmo instante de entrada, o mesmo stop/alvo/prazo e o lado
  SORTEADO (média dos dois lados), simulado em `stop_movel.conferir` nas velas de 1 min. Excesso da operação = resultado real em % do nocional − controle.
  O controle tira o efeito do mercado do período: r8 e r9 são de dias diferentes.
- **Juiz (por agente e no total dos 4; 1 tentativa):** com ≥ 30 operações r9 e ≥ 30 r8 (r6/r8 juntas se a r8 sozinha não chegar a 30):
  a r9 **fica** se o excesso médio da r9 for ≥ o da r8 (no total dos 4) **e** o fator de lucro da r9 for > 1. Se não, o REVISOR volta à r8
  (cópia do Engenheiro em `backup-2026-11-19/ROTINA.md`). Também se relatam, sem decidir, média por operação, fator de lucro, operações por dia e a carteira de cada agente.
- **Prazo:** quando o total dos 4 agentes tiver 30 operações r9 fechadas ou até 03/12, o que vier primeiro. Se faltar r8, a comparação fica com o controle:
  a r9 precisa de excesso médio > 0 com t ≥ 2, com erro-padrão agrupado pela rodada de decisão.
- **Adendo (19/11 ~19:20 UTC, antes de medir qualquer operação r9): a carteira do Laboratório fica de fora da r9, por escolha do Laboratório, não da rotina.**
  Ela continua com o método fixo da H61: só v4 com confiança ≥ 0,12, no lado do regime. Por isso a decisão das 15:34 UTC cortou BONK venda
  (6 de 6 tempos a favor, confiança < 0,12). Motivo: é a única carteira de regra fixa, sem leitura discricionária, e serve de braço de comparação
  para a H69. Ela não entra no total dos 4 do juiz da r9 (o total passa a ser dos outros 3 agentes) e é relatada à parte. Custo dessa escolha, medido:
  0 operações desde 18/11 (a confiança ≥ 0,12 no lado do regime quase não aparece). Se em 03/12 ela ainda tiver menos de 10 operações, o braço
  não mediu nada e o Laboratório passa a seguir a r9 como os outros (fica registrado aqui, sem ajuste depois de ver).
- **Previsão registrada:** mais operações por dia. Por operação, perto do controle (≈ −0,12%), a não ser que a leitura dos agentes tenha vantagem;
  nenhum teste do laboratório mostrou vantagem em leitura discricionária até aqui (H43, H62: não sei).

## Hipótese 68: o Caçador — varredura contínua de oportunidades na nuvem, com juiz automático (registrada em 19/11/2026 ~13:10 BRT = 16:10 UTC, antes de ligar)
- **Dono (19/11):** "quero um agente caçador… ele não opera, apenas caça as oportunidades e avisa os agentes que operam… leitura e análises 24 h,
  constantemente… criptos e memecoins… na Binance a todo momento uma vela explode para cima ou para baixo, tendências se formam." Desenho aprovado
  pelo chefe (Baleias); engenharia do Engenheiro.
- **Onde roda:** `executor/cacador_nuvem.py`, a cada rodada do laço de `cerebro.yml` (~3 min), grava só `dados/oportunidades.json`. O agente
  Caçador do OpenBot lê esse arquivo, confere o gráfico e avisa os operadores; não opera.
- **Universo (limite declarado):** a nuvem do GitHub não alcança a API de futuros da Binance (bloqueio regional; não será contornado). Varre TODOS
  os pares USDT à vista em negociação da Binance (`data-api.binance.vision`, os mesmos preços que a execução da nuvem usa), com volume de 24 h
  ≥ US$ 500 mil, sem estáveis, fiduciárias, ações tokenizadas e alavancados (filtros de `lab/universo.py`). Memecoins primeiro na ordem.
  Listagem nova = par USDT que aparece no `exchangeInfo` (relido a cada 60 min) e não estava na lista anterior. Memecoins de DEX (DexScreener
  token-profiles + tokens, GeckoTerminal new_pools da Solana; APIs públicas sem chave) = só informação, sem juiz (filtros: liquidez ≥ US$ 50 mil,
  idade ≥ 30 min, ≥ 10 compras e ≥ 10 vendas em 1 h, volume de 1 h ≥ US$ 25 mil; maiores detentores: não disponível nessas APIs → "não sei").
- **Sinais (fixos; entrada = fechamento do último minuto fechado; lado sugerido; nível de invalidação):**
  E1/E5/E15 explosão de vela: retorno da janela de 1, 5 ou 15 min com |z| ≥ 3 (z = log-retorno ÷ (desvio dos retornos de 1 min dos 120 min
  anteriores à janela × √minutos)) E volume da janela ≥ 3 × o volume médio por minuto da base × minutos; lado = o do movimento (segue);
  invalidação = o preço de antes da janela.
  T tendência se formando: fechamento acima (abaixo) da MM20 em 15 min, 1 h e 4 h (4 h agregado de velas de 1 h) e a vela de 15 min anterior do
  outro lado da MM20 dela (acabou de cruzar); invalidação = MM20 de 15 min.
  R rompimento de 24 h: preço acima da máxima (abaixo da mínima) das 96 velas de 15 min anteriores, com a última vela de 15 min fechada ainda
  dentro; invalidação = a máxima/mínima rompida.
  P15/P60 padrão gráfico CONFIRMADO de `lab/padroes_graficos.detectar` em 15 min / 1 h (alta = compra); invalidação = mínima (máxima) da última vela.
  T, R e P são lidos nas candidatas da rodada (todas com sinal de 1 min, memecoins, as 20 de maior |24 h|, as 20 de maior |1 h|, as perto da
  máxima/mínima de 24 h; até 80). Força 0–100 = mín(100, 12·|z| maior + 15·tempos da MM20 a favor (0–3) + 8·mín(5, volume relativo) + 10 se memecoin).
  O mesmo (moeda, sinal, lado) não vira evento novo antes de 30 min. Até 25 eventos por rodada (os de maior força).
- **Juiz automático (uma avaliação por sinal e horizonte; 7 sinais × 2 horizontes = 14 tentativas, contadas):** cada evento é resolvido pelo
  fechamento do minuto 15 e do minuto 60 depois da entrada (velas históricas de 1 min; rodada atrasada não perde evento): retorno no lado sugerido
  − 0,12%. **Controle de entradas aleatórias obrigatório:** para cada evento real, um evento de controle no mesmo instante, moeda sorteada entre as
  lidas e lado sorteado, resolvido igual. **Passa** o par (sinal, horizonte) com ≥ 300 eventos, média > 0, t ≥ 2,69 (≥ 2 pedido pelo chefe e
  Bonferroni para 14, 5% unilateral; erro-padrão agrupado pela hora da entrada) e média > 0 em 2 dos 3 blocos de tempo (horas em ordem, terços).
  **Validade:** o juiz só vale se o controle do mesmo horizonte der média dentro de −0,12% ± 2 erros-padrão (senão há erro de simulação e nada passa).
  Placar no próprio `dados/oportunidades.json` (`juiz_h68`).
- **O que entra:** nada muda nas regras dos operadores por esta hipótese: eles recebem os avisos e decidem livres (H62). Sinal aprovado → o
  Caçador passa a marcá-lo como "aprovado no juiz" nos avisos; sinal reprovado ou sem prova → "sem prova" (informação).
- **Execução (mudança de encanamento, não de estratégia):** a nuvem passa a abrir posição de agente em moeda fora das velas do v4 quando tem o
  preço de 1 min da rodada (antes a entrada era recusada), para que as oportunidades fora das 108 moedas do v4 possam ser operadas.
- Previsão registrada antes: não sei. O laboratório já viu rompimentos de 5 min e de 1 h, regras de 1 s e fluxo agressor perderem para o custo
  (H25, H56, H65, H66): a previsão mais provável é média perto de −0,12%.

### Decisão do dono (19/11/2026 ~16:30 BRT = 19:30 UTC): alvos de ganho maiores para todos os agentes
- **Dono:** "aumente os alvos de ganhos, repasse isso para todos os agentes, os alvos maiores."
- **Execução:** `executor/robo_claude_nuvem.parametros` (nuvem) e `chefe/testnet.py` (conta de teste, mesma função): alvo ≥ 3 × o stop e ≥ 1%
  (limite de cima 5%); alvo menor é subido sozinho; com stop e sem alvo, o alvo passa a ser 3 × o stop. Com alvo, o stop móvel só arma na metade do caminho até ele (`stop_movel.armar_em`; antes +0,5% cortava quase tudo: com alvo 1,2% só 3% chegavam, medido pelo Engenheiro). Rotina r10 e manual seção 5.
- **O que o laboratório já sabe (não decide):** na H64, "stop 1% e alvo 3%" foi a melhor saída medida (+0,309%/aposta corrigido, ganho ÷ perda
  2,58), mas perdeu no bloco mais recente (−0,472%). Alvo maior = acerto menor (36%). **Juiz ao vivo (até 03/12):** por agente, em 30+ operações
  com a regra: ganho médio ≥ 2 × perda média e média por operação > 0.

### H70 e H69, adendo (19/11 ~20:00 UTC, antes de rodar a H70 e de medir qualquer operação r9/r10): alvos maiores por decisão do dono
- **Dono (19/11):** "aumente os alvos de ganhos, repasse isso para todos os agentes, os alvos maiores." O agente Baleias ligou (commits 3b51fc4d e
  1de5b148): alvo ≥ 3 × o stop, nunca abaixo de 1% (teto de 5%). Com alvo, o stop móvel só arma na metade do caminho até ele (`stop_movel.armar_em`).
  Rotina r10. É, na prática, a forma **A2** da H70, ligada **antes** do teste, por decisão do dono.
- **H70 continua como está, sem mudar critério nem tentativas.** Passa a medir a regra que já está ligada. Se a A2 for reprovada (diferença contra a A0 sem
  z ≥ 2,24 ou negativa em algum bloco), o Laboratório não desliga: o resultado vai ao dono, que decidiu. Se a A1 (sem móvel) passar e a A2 não, isso também vai ao dono.
- **H69:** a r10 muda a saída, não a postura de entrada. O controle já usa, em cada operação, o mesmo stop, alvo e prazo e a regra de saída em vigor
  naquele momento. Assim o efeito da saída sai do excesso. **r9 e r10 contam juntas** como "postura ativa" contra a r8, e a r10 é relatada também à parte.
  Juiz, prazo e a exclusão da carteira do Laboratório (adendo anterior): iguais.

### H69, adendo 3 (19/11, antes de medir qualquer operação r9/r10/r11): rotina r11
- O Engenheiro passou a ROTINA para a r11. Ela muda só a informação de entrada: o passo 2 mostra primeiro as oportunidades do Caçador (H68,
  `dados/oportunidades.json`) e um aviso do Caçador faz a rotina rodar na hora. Stop, alvo, revisor e postura são os da r10.
- **r9, r10 e r11 contam juntas** como "postura ativa" contra a r8. O controle de lado sorteado usa o mesmo instante, então a mudança de horário
  pelo aviso também sai do excesso. Relatado à parte (não decide): as entradas em moeda avisada pelo Caçador na última hora antes da decisão, contra as outras.

### H69, adendo 4 (19/11 ~20:45 UTC, antes de medir qualquer operação r9–r12): rotina r12
- O Engenheiro, a pedido do dono ("o v4 está barrando as entradas do Caçador; reestruture"), passou ferramenta e prompt para a r12: o v4 só pesa com
  confiança ≥ 0,12 (`operar.py`, `chefe/universo.py` 0,08/0,03 → 0,12). A carteira do Laboratório mantém o método fixo, inclusive o "contra" de 0,03 que fecha
  posição. **A r12 conta junto com r9–r11** como "postura ativa"; o controle de lado sorteado não muda.
- **Medição do veto do v4 (Engenheiro, `lab/veto_v4.py`, fe1ca5fa; só descritiva, não é pré-registro):** no replay de 2 dias (3.970 explosões do Caçador) e
  ao vivo (226 sinais em 19/11), o v4 fraco contra ou a favor não tem efeito de sinal consistente (troca de sinal entre replay e ao vivo). Não vira
  hipótese de filtro: a evidência não sustenta, e testar a mesma ideia de novo nesses dados seria ajustar ao que já foi visto. As explosões perderam
  mais que o sorteio no replay (−0,180% × −0,124% em 15 min). Isso é para o juiz da H68, que já está pré-registrado e não muda.

## Hipótese 71: uma conta de demonstração por operador — as decisões de cada agente executadas com ordens reais numa corretora de teste (registrada em 20/11/2026 ~00:10 BRT = 03:10 UTC, antes da primeira ordem)
- **Dono (19/11):** "vamos dar uma carteira para cada um". Cada operador passa a executar a PRÓPRIA decisão (`dados/decisao_<agente>.json`) numa conta de
  demonstração de uma corretora (dinheiro fictício), como o chefe faz na Binance testnet (H59). Nunca dinheiro real; duas contas nunca no mesmo robô.
  Mapa: Laboratório → Gate Futures TestNet (`api-testnet.gateapi.io`); Treinador → Bybit Demo Trading (`api-demo.bybit.com`); Guardião → BingX VST
  (`open-api-vst.bingx.com`). A ferramenta fala só com esses endereços e PARA em qualquer outro. Chaves só no cofre do OpenBot, nunca no repositório.
  Bybit e BingX ficam travadas até uma validação só de leitura passar (a chave salva da Bybit é da conta real e não é usada; a BingX recusa o IP).
- **Execução (`OpenBot/Shared/baleias/operar/corretora.py <agente>`, máquina local, no fim da rotina de operar):** segue as `posicoes` da decisão do
  agente (válida 75 min, a mesma da carteira simulada): moeda fora da lista ou de lado invertido fecha a mercado; moeda nova abre a mercado com stop
  (gatilho reduce-only) e alvo (gatilho reduce-only) guardados na corretora, nos valores efetivos de REGRAS.md §5 (`robo_claude_nuvem.parametros`).
  Stop recusado = fecha na hora. Stop móvel: a cada rodada, com o pico desde a entrada (velas de 1 min da própria corretora), arma em máx(0,5%, alvo ÷ 2)
  e sobe o stop para entrada ± 70% do pico (nunca desce). Prazo (`max_min`) e 24 h conferidos a cada rodada. Cada moeda entra no máximo uma vez por
  decisão. Moeda que não existe na corretora, ou cujo lote mínimo passa de 1,5 × a posição, não entra (anotado). Antes de tudo, concilia a conta
  (posições e gatilhos executados enquanto a máquina dormia; ordem ou posição desconhecida é cancelada/fechada: a conta é só daquele agente).
- **Tamanho:** carteira própria de US$ 10 dentro da conta de demonstração (contabilidade do robô, como na H59), nocional pela H64 sobre a carteira
  realizada, alavancagem 10× até 2,5× e 20× acima (rebaixada se a corretora recusar). A conta tem mais dinheiro (ex.: Gate 1.000 USDT), mas o robô usa só
  a própria carteira, para comparar com a carteira simulada do mesmo agente.
- **Resultado:** o da corretora (execuções da entrada e da saída menos as taxas cobradas). Estado em `dados/corretora_<agente>.json` no ramo `estado`
  (só a ferramenta grava). Os preços são os da corretora de teste (livro diferente do mercado real: limite anotado).
- **Juiz (comparação, não aprova estratégia):** por agente, ao completar 30 operações fechadas na corretora ou em 7 dias (27/11): diferença por
  operação entre a conta de demonstração e a carteira simulada do mesmo agente nas mesmas decisões (`decisao_t`) = custo real de execução (taxa,
  escorregamento, stop móvel por rodada). Relatada ao dono. Previsão: não sei.

## Hipótese 72: escala — o que "lucros maiores" custa em risco (registrada em 21/11/2026 ~23:20 UTC, antes de rodar)
- **Dono (21/11):** "todos os agentes estão operando em busca de pequenos lucros, por centavos de dólar; eu não quero centavos, quero lucros significantes e maiores."
- **Dados:** as operações FECHADAS reais no ramo `estado` na hora de rodar, sem baixar dado novo: a carteira simulada dos 4 agentes (`robo_claude.json`,
  `agente_laboratorio.json`, `agente_treinador.json`, `agente_guardiao.json`) e a conta de teste do chefe (`robo_openbot_testnet.json`). O retorno de cada
  operação é o realizado em % do nocional (`resultado_usd / nocional`), que já inclui taxas e custo. O tamanho muda; o fio por operação, não.
- **Duas alavancas, medidas separadas:**
  - **A — capital:** carteira por agente de US$ 10 → 50, 100, 500 e 1.000, com a regra de tamanho da H64 inalterada (fator 2,5 × carteira ÷ 10 em [1,25; 5],
    10× até fator 2,5 e 20× acima) e o piso em 50% da carteira inicial.
  - **B — alavancagem:** carteira de US$ 10 e 100 com 20× e 50× fixos; perda de uma posição para na margem (`pct ≥ −1 ÷ alavancagem`, como no código).
- **Medida:** sequência real de fechamento, carteira realizada; final, mínima, queda máxima em % da carteira, liquidações. Monte Carlo de 10.000 ordens
  sorteadas das operações (com reposição) por braço: mediana do final, chance de dobrar antes de cair ao piso.
- **Critério (1 tentativa, sem ajustar depois):**
  1. **Portão do fio:** se a média por operação em % do nocional não for > 0 com t ≥ 2 em NENHUM dos dois conjuntos, a escala NÃO entra: alavanca não
     multiplica fio que não existe. O resultado vai ao dono com o capital necessário para o lucro que ele pediu, dado o fio atual.
  2. Se o fio passar: **A** passa se o resultado em US$ crescer ~proporcional à carteira e a queda máxima em % não piorar mais de 1 ponto percentual;
     **B** passa se o resultado em US$ dobrar com queda máxima ≤ 1,5× a atual e liquidação em ≤ 2% das operações.
  3. Relatado sem decidir: operações e dias para +US$ 100 e o capital necessário para US$ 1 e US$ 10 por dia com o fio de hoje.
- **Se reprovar:** nada muda nas carteiras nem na alavancagem; o dono recebe o número e decide sobre capital (dinheiro fictício das contas de demonstração
  é decisão dele, não da rotina).
- **Previsão registrada:** o fio deve ficar perto de zero (a H64 já mostrou +0,55 na soma com a escala; a conta de teste está negativa) e o teste deve
  reprovar no portão. Escala maior deve aumentar o tamanho dos dois lados (ganho e perda), não a proporção.

### Resultado da H72 (21/11/2026 ~23:30 UTC, `lab/escala_capital.py` → `dados/lab/escala_capital_resultado.json`): REPROVADA no portão do fio
| conjunto | operações | fio por operação | t |
|---|---|---|---|
| carteira simulada (4 agentes) | 136 | +0,0547% do nocional | 0,72 |
| conta de teste (chefe) | 38 | −0,1327% do nocional | −0,53 |
- O portão pedia média > 0 com t ≥ 2 em algum conjunto: nenhum. A alavanca (capital ou alavancagem) multiplica o fio; com fio sem prova, multiplica ruído. **Nada muda** nas carteiras nem na alavancagem.
- Mesmo sem decidir, o número do dono (com o fio de hoje, regra H64, 30,6 operações/dia): US$ 1 por operação exige carteira de **US$ 731**; US$ 10/dia exige **US$ 239**; US$ 100/dia, **US$ 2.390**; na carteira de US$ 10 seriam **7.313 operações** para +US$ 100 (~239 dias).
- Custo da escala no risco: com a regra H64 o fator satura em 5× já com carteira de US$ 50, e a queda máxima simulada sobe de 17,9% (US$ 10) para 35,7% (US$ 50 ou mais) na carteira simulada, e de 22,6% para 44,9% na conta de teste. Alavancagem de 50× na carteira de US$ 10: +0,54 US$ a mais no total, 2 liquidações na sequência real.
- Na conta de teste o braço maior termina **abaixo** do capital em todos os tamanhos (8,52 de 10): escalar ali aumentaria a perda em dólares.

## Hipótese 73: tamanho maior com perda maior — autorizado pelo dono (registrada em 22/11/2026 ~00:50 UTC, antes de rodar)
- **Dono (22/11):** "pode aumentar o tamanho da perda também." Depois de saber que a H72 reprovou a escala por falta de fio provado e que US$ 10/dia exigiria US$ 239 de carteira,
  o dono autoriza posição maior aceitando perda maior por operação. Dinheiro fictício (carteira simulada e conta de teste); nada de dinheiro real.
- **Braços na mesma sequência real de fechadas** (136 dos 4 agentes; 38 da conta de teste), carteira de US$ 10, regra H64 mantida como referência:
  - **atual:** nocional = 2,5 × carteira, 10× (margem 0,25 × carteira por posição; risco ≈ US$ 0,25 por operação com stop de 1%).
  - **A:** nocional = 5 × carteira, 20× (margem 0,25 × carteira; risco ≈ US$ 0,50).
  - **B:** nocional = 10 × carteira, 50× (margem 0,20 × carteira; risco ≈ US$ 1,00; 4 posições usam 80% da carteira de margem).
  - Perda de uma posição para na margem (`pct ≥ −1 ÷ alavancagem`), como no código; liquidação custa a margem inteira.
- **Juiz (1 tentativa):** o braço maior entra se, na sequência real e no Monte Carlo de 10.000 ordens: (a) o resultado em US$ por operação crescer ao menos proporcionalmente ao tamanho;
  (b) a chance de bater no piso de US$ 5 ficar ≤ 25%; (c) liquidação em ≤ 5% das operações. Entre os que passarem, vale o de maior resultado em US$.
- **O que muda se passar:** `tamanho()` em `executor/robo_claude_nuvem.py` (a nuvem dos 4 agentes e a conta de teste usam a mesma função). Testes e commit.
- **Previsão registrada:** o fio não muda (continua perto de zero); o que muda é o tamanho dos dois lados. Em 50×, qualquer stop acima de 2% vira liquidação da margem; espero que o braço B perca em dólares na conta de teste, que já tem fio negativo.

### Resultado da H73 (22/11/2026 ~01:10 UTC, `lab/escala_capital.py` → `dados/lab/escala_capital_resultado.json`): fator 5 a 20× entra nas carteiras simuladas; 10 a 50× reprovada
| braço (carteira US$ 10) | simulação real, final | queda máx. | piso (MC) | liquidações | conta de teste, final | piso (MC) |
|---|---|---|---|---|---|---|
| atual 2,5× a 10× | 10,29 | 17,9% | 0,01% | 0 | 8,52 | 0,01% |
| **fator 5 a 20×** | **10,53** | 35,7% | **14,3%** | 0 | 6,96 | 30,1% |
| fator 10 a 50× | 4,55 | 54,5% | 41,8% | 2 | 4,92 | 57,0% |
- Critério: resultado maior, piso ≤ 25%, liquidação ≤ 5%. O fator 5 passa na carteira simulada (149 operações; fio +0,0254%, t 0,36) e reprova na
  conta de teste (fio −0,1327%), onde o braço maior bateria no piso em 30,1%. Por isso: **nuvem dos 4 agentes a 5 × a carteira, 20×; conta de teste
  na H64 (2,5 ×, 10×)**. O fator 10 termina abaixo do piso na sequência real — reprovado.
- O fio não mudou (segue perto de zero, t 0,36): o tamanho dobra, a vantagem não. O que dobra é o sobe-e-desce: queda máxima 17,9% → 35,7%.

## Juízo diário de 23/11/2026 (~22:00 UTC; atrasado: o juízo de 22/11 não rodou). Ramo `estado` 080d2bb6

### Resultado da H46 (`lab/juizo_h46.py`): REPROVADA — nada muda
| faixa UTC | acerto | apostas | velas | erro-padrão |
|---|---|---|---|---|
| 00–06 h | 54,72% | 7.769 | 168 | 1,61% |
| 06–12 h | 53,83% | 6.792 | 149 | 1,65% |
| 12–18 h | 56,09% | 7.096 | 139 | 2,02% |
| **18–24 h** | **57,48%** | 7.627 | 162 | 1,78% |
| 00–18 h juntas | 54,89% | 21.657 | 456 | 1,01% |
- 29.284 apostas de 16/11 00:00 a 22/11 24:00 UTC; acerto = líquido > 0 (conta do vigia); erro-padrão por vela. 1 tentativa.
- 18–24 h acertou **acima** de 50% (z +4,20): a primeira condição falha. As outras ≥ 52%: sim. O achado de 11–15/11 (44,2%) fica registrado como acaso ou deriva passageira; os robôs do v4 não ganham regra de horário.

### H47 (Robô Livre, descritivo, prazo 22/11 21:20 UTC): só registro
- Estado em `dados/robo_livre.json` (última gravação 18/11 00:01 UTC; robô parado desde que quebrou e aposentado na H61).
- Carteira com custo **US$ 0,90**; sem custo US$ 1,84 (de US$ 10). 25 operações fechadas, **4 liquidações** (−4,5% a 20×), custo pago US$ 0,93. Quebrou (`quebrou: true`).
- Leitura: sem regras de decisão e a 20× com a carteira inteira, perdeu 91% em menos de 2 dias; o custo explica só US$ 0,93 dos US$ 9,10 perdidos.

### Resultado da H70 (`lab/juizo_h70.py`, ramo `estado` 4ae07584): REPROVADA nas 4 tentativas — controle válido
- 3.699 apostas do v4 com confiança ≥ 0,08 desde 16/11 21:53 UTC, 200 moedas (velas: 184 perpétuo, 16 à vista). G1: 3.699 conferidas; G2: 3.491 (208 com prazo aberto).
- Controle (lado sorteado), todos dentro de −0,12% ± 3 EP: G1 −0,118 / −0,116 / −0,121%; G2 −0,131 / −0,184 / −0,137% (A0/A1/A2).

| tentativa | média da diferença | EP | z | blocos | veredito |
|---|---|---|---|---|---|
| G1 A1 − A0 | +0,020% | 0,021% | +0,98 | −0,006 / +0,068 / −0,000% | reprovada |
| G1 A2 − A0 | +0,004% | 0,005% | +0,88 | +0,002 / +0,005 / +0,006% | reprovada (z < 2,24) |
| G2 A1 − A0 | −0,054% | 0,073% | −0,74 | −0,142 / +0,114 / −0,133% | reprovada |
| G2 A2 − A0 | +0,011% | 0,042% | +0,26 | −0,065 / +0,083 / +0,014% | reprovada |
- Média absoluta (relato): G1 A0 −0,077%, A1 −0,057%, A2 −0,073%; G2 A0 −0,089%, A1 −0,143%, A2 −0,078%. Todas negativas depois do custo.
- Conforme o adendo de 19/11: a A2 já está ligada por decisão do dono; o Laboratório **não desliga**. O resultado vai ao dono: a forma da saída não muda a
  média de modo detectável (como previsto); nenhuma forma tem vantagem. A A1 (sem móvel) também não passou.
- Ajuste no script antes de rodar: o download desiste de uma fonte após 4 falhas de rede (antes era laço infinito); download em paralelo (8), mesmo código de medida.

## Hipótese 74 (P2 do Treinador): os agentes só compram com alerta `explosao_*` de compra do Caçador ainda válido (registrada em 23/11/2026 ~22:45 UTC, antes de rodar)
- **Proposta:** `Shared/baleias/propostas.md`, P2. Na amostra do Treinador (225 operações, 17/11–23/11), as compras sem alerta perdem (59 operações, −US$ 8,29, fator 0,19)
  e as com alerta ganham (13, +0,335, fator 1,47). Esses números saíram dos mesmos dados: **não servem de teste**.
- **Teste fora da amostra (decide agora; 1 tentativa):** todos os alertas `explosao_*` de COMPRA do Caçador, remontados do histórico de `dados/oportunidades.json`
  no ramo `estado` (cada commit, de 19/11 16:00 a 23/11 22:23 UTC). O mesmo (moeda, sinal, lado) dentro de 30 min conta uma vez só (a regra de repetição do Caçador).
  Quase nenhum desses alertas virou operação de agente, então eles não se confundem com as 13 da descoberta.
  - Entrada: fechamento da primeira vela de 1 min que fecha depois da hora do alerta. Velas de 1 min do perpétuo da Binance, ou do mercado à vista quando o perpétuo não tem a moeda.
  - Saída: stop, alvo e prazo do próprio alerta (`sugestao`), pelo `executor/stop_movel.conferir` com a regra em vigor (móvel arma em max(+0,5%, alvo/2)). Custo de 0,12%.
  - Controle de validade: mesmas moedas e instantes, lado sorteado. A média tem de ficar em −0,12% ± 3 erros-padrão; se não ficar, a rodada é inválida.
  - Relatado, sem decidir: os alertas de VENDA medidos do mesmo jeito.
- **Juiz (a):** média líquida > 0 com z ≥ 2 (erro-padrão agrupado pela hora do alerta) **e** > 0 em cada um de 3 blocos de tempo iguais. Exijo z além dos 3 blocos
  que o Treinador pediu, porque com milhares de alertas a média só ser positiva nos 3 blocos pode ser ruído.
- **Se (a) passar:** a regra vai ao Baleias (o `operar.py` recusa compra sem alerta válido). O juiz ao vivo é o (b) do Treinador: das 30 primeiras compras recusadas,
  gravadas e simuladas do mesmo jeito, a soma tem de ser < 0 com fator < 1 em 2 dos 3 blocos; se não for, a regra sai. **Se (a) falhar:** nada muda.
- **Previsão registrada:** reprova. O juiz automático da H68 nunca deu prova a nenhum sinal do Caçador, e entrar depois de uma explosão de 1 a 15 min tende a pegar
  o fim do movimento. A perda das compras sem alerta pode ser só o mercado em queda nesses dias (o mesmo da H42).

### Resultado da H74 (23/11/2026 ~23:00 UTC, `lab/juizo_h74.py`, ramo `estado` 3dc14328): REPROVADA — nada muda
- 1.599 commits de `oportunidades.json`; 3.903 alertas `explosao_*` depois da regra de 30 min (1.905 compra, 1.998 venda); 24 fora (prazo aberto ou sem velas). Velas: 236 perpétuo, 19 à vista.

| grupo | n | média líquida | EP | z | acerto | fator | blocos |
|---|---|---|---|---|---|---|---|
| controle (lado sorteado) | 3.879 | −0,096% | 0,023% | −4,07 | 41,2% | 0,84 | −0,134 / −0,097 / −0,053% |
| venda (relato) | 1.983 | +0,011% | 0,103% | +0,10 | 43,6% | 1,02 | +0,106 / −0,002 / −0,105% |
| **compra (juiz a)** | **1.896** | **−0,146%** | 0,082% | **−1,78** | 39,6% | 0,78 | −0,375 / −0,005 / −0,160% |
- Controle dentro de −0,12% ± 3 EP: rodada válida. A compra no alerta perde nos 3 blocos e fica **abaixo** do lado sorteado: comprar só com o alerta não protege as compras.
  As 13 compras com alerta da P2 (+0,335) foram acaso de amostra pequena. Como previsto. A perda das compras sem alerta continua sem explicação testada (o mercado em queda é a candidata).

## Hipótese 75 (pedido do dono, 23/11): "orquestra" — um maestro coordena as carteiras em vez de cada agente sozinho (H61) (registrada em 23/11/2026 ~23:15 UTC, antes de rodar)
- **Pedido:** o dono quer os agentes "como uma orquestra sincronizada". Maestro = o chefe (decisão do dono). Proposta: raspagem única e fresca, papéis diferentes
  (tendência, reversão, memecoins), quadro da rodada (quem pega qual moeda), Guardião como risco do conjunto, rotinas em sequência e placar comum.
- **O que dá para testar nos dados (a parte que muda decisão):** três regras do maestro, fixadas agora, aplicadas em ordem de entrada às operações fechadas
  das 4 carteiras simuladas de agente (`robo_claude`, `agente_guardiao`, `agente_laboratorio`, `agente_treinador`; ramo `estado` 3fa38ccf). A conta de teste do
  chefe fica de fora: copia a decisão do `robo_claude`.
  - R1 sem duplicar: entrada recusada se outra carteira já tem a mesma moeda no mesmo lado aberta naquele instante (entre as mantidas).
  - R2 exposição: entrada recusada se a mesa já tem 6 ou mais posições mantidas abertas no mesmo lado.
  - R3 perda do dia: entrada recusada se a soma das mantidas fechadas antes, no mesmo dia UTC, está em −US$ 1,00 ou pior.
- **Medida:** resultado_usd por operação. Base = todas; filtro = as mantidas. Controle (placebo): 2.000 sorteios que recusam o MESMO número de operações ao acaso.
- **Juiz:** (a) média das mantidas acima de 97,5% dos sorteios **e** (b) média das recusadas < 0 **e** (c) média das mantidas ≥ média da base em 2 de 3 blocos de
  tempo iguais (pela hora de entrada). 1 tentativa, sem trocar os números depois.
- **Se passar:** a orquestra entra nas rotinas, e o juiz ao vivo são as 60 primeiras operações: as recusadas (gravadas e simuladas) têm de somar < 0. Se não somarem, as regras saem.
  **Se reprovar:** as regras R1–R3 não entram. Proponho ao dono só a parte de infraestrutura (raspagem única e fresca, rotinas em sequência, placar comum), que não muda decisão.
- **Previsão registrada:** reprova no placebo. A amostra é pequena (~180 operações) e a perda pode ser só o mercado em queda (H42/H74); R1 e R2 devem recusar poucas.

### Resultado da H75 (23/11/2026 ~23:25 UTC, `lab/juizo_h75.py`, ramo `estado` 3fa38ccf): REPROVADA — R1–R3 não entram
- 184 operações (17/11 12:18 a 23/11 22:33 UTC); o maestro manteria 118 e recusaria 66 (R1 25, R2 11, R3 30).

| grupo | n | soma US$ | média US$ |
|---|---|---|---|
| base (todas) | 184 | −3,078 | −0,0167 |
| mantidas | 118 | −5,664 | −0,0480 |
| **recusadas** | 66 | **+2,587** | +0,0392 |

- Placebo: as mantidas ficam acima de só 0,4% dos sorteios (precisava de 97,5%). Blocos: mantidas abaixo da base nos 3 (−0,038/−0,024/−0,087 contra +0,003/+0,009/−0,083).
- As recusadas ganharam: o freio do dia (R3) corta as operações que recuperam, e as duplicadas (R1) não eram as piores. Previsão (reprova) confirmada, mas pior que o esperado:
  coordenar por essas regras **piora**. Segue a parte de infraestrutura (raspagem única e fresca, rotinas em sequência, placar comum), que vai ao dono como proposta.

### Decisão do dono (23/11/2026 ~23:40 UTC): REGRAS R2 — soltar as travas ("mude todas")
- Pedido: "algumas regras estão limitando a liberdade dos agentes operar… as oportunidades passam diante deles" → "mude todas".
- Muda: C2 e C3 não cortam (só C1); alvo opcional 0,2–50% (sem 3 × stop nem mínimo de 1%); prazo opcional (sem prazo: 24 h); stop móvel desligável por posição
  (`"movel": false`, padrão ligado); até 8 posições com 4/8 do tamanho cada (exposição total igual). Fica: stop obrigatório (0,3–4%), tamanho H73/H64, piso US$ 5.
- Sem teste prévio, por decisão do dono. Dados a favor: H75 (as entradas que os freios cortariam somaram +US$ 2,59). Dados contra: H74 (comprar nas explosões
  que o C2 cortava perdeu −0,146% por operação, 1.896 alertas).
- **Juiz ao vivo (registrado agora):** as 60 primeiras operações fechadas das 4 carteiras de agente depois da R2 contra as 60 últimas antes dela (resultado_usd
  por operação). Se a média depois for menor que a de antes **e** a soma depois for < 0, volto ao dono com os números para decidir se a R2 fica.

### Juízo de 24/11/2026 (~20:30 UTC, `lab/juizo_h59_h62.py`, ramo `estado` 88e39602): H59 e H62 pelo critério escrito, sem ajuste
- **H59 (Chefe OpenBot no testnet): REPROVADA.** As 30 primeiras operações fechadas (18/11 01:04 a 20/11 13:51 UTC), resultado da corretora
  (realizedPnl − commission): soma −US$ 1,834, fator de lucro 0,615, acerto 33,3%, t da média −0,93. Precisava de soma > 0 e fator > 1.
  À parte: ZEC −0,970 e RENDER −0,794 (abertas antes da emenda); sem as duas a soma ainda é −0,070. Comparação (não decide): Robô Claude com
  `decisao_t` no mesmo período, 37 operações, soma −0,798, fator 0,78. Todas as 56 fechadas até hoje: soma −2,960, fator 0,589.
- **H62 (agentes livres, 30 operações abertas desde 18/11 20:37 UTC; carteira = 10 + todas as fechadas até a saída da 30ª):**

| agente | n | soma US$ | fator | acerto | t | carteira na 30ª | veredito |
|---|---|---|---|---|---|---|---|
| Baleias (`robo_claude`) | 30 | +0,387 | 1,168 | 56,7% | +0,38 | 9,526 | REPROVADO (carteira ≤ 10) |
| Treinador | 30 | −0,488 | 0,822 | 43,3% | −0,49 | 9,684 | REPROVADO |
| Guardião | 30 | −0,034 | 0,987 | 60,0% | −0,03 | 10,292 | REPROVADO (fator ≤ 1) |
| Laboratório | 25 | — | — | — | — | — | não julgável (faltam 5) |

  Baleias: a carteira começou a H62 em US$ 8,889 (herdada do Robô Claude, 16 fechadas antes); pelo critério escrito reprova. As 30 operações da H62
  sozinhas somaram +0,387 (fator 1,17), mas com t +0,38 isso não se distingue de zero. Sem campeão. Nada muda no código.
- **H49 (stop móvel):** não julgada. Desde a H62 cada agente põe alvo e prazo, e desde a R2 (23/11) o móvel é desligável; a "saída antiga" escrita
  (regra do robô sem o móvel) não existe para essas operações. Fica registrada como não julgável; a pergunta foi respondida nos dados pela H70 (reprovada em 23/11).
- **R2 (juiz ao vivo):** 12 de 60 operações abertas depois de 23/11 23:40 UTC; não venceu.

## Hipótese 76 (proposta do Caçador, 24/11): "hora_22utc" — comprar BTC às 22:00 UTC e vender às 00:00 UTC (registrada em 24/11/2026 ~21:00 UTC, antes de baixar os dados)
- **Fonte:** Padyšák e Vojtko, "Seasonality, Trend-following, and Mean reversion in Bitcoin" (SSRN 4081000): Gemini 2015–2021, 33% ao ano, Sharpe 1,58, custo não informado.
  Conta do Caçador: 33%/365 ≈ 0,09% por dia, abaixo do custo de 0,12%.
- **Regra:** uma operação por dia, só compra. Entrada na abertura da vela de 1 h das 22:00 UTC; saída na abertura da vela das 00:00 UTC.
- **Dados (fora da amostra do artigo):** velas de 1 h de BTCUSDT à vista da Binance, de 01/01/2022 a 23/11/2026. Custo de 0,12% por operação.
- **Controle de validade:** no mesmo dia, uma janela de 2 h que começa numa hora sorteada entre 00 e 21 UTC. A média tem de ficar em −0,12% ± 3 erros-padrão; se não ficar, a rodada é inválida.
- **Juiz (1 tentativa, só BTC):** n ≥ 300 dias, média líquida > 0, t ≥ 2,69 (o que o Caçador sugeriu) e > 0 em **cada** um de 3 blocos de tempo iguais.
  Uso a regra dos 3 blocos do laboratório, mais dura que os 2 de 3 propostos. ETHUSDT, na mesma janela, só é relatado.
- **Se passar:** vai ao Baleias como sinal informativo para os agentes (não ordem automática). **Se falhar:** nada muda.
- **Previsão registrada:** reprova. A vantagem publicada é menor que o custo.
