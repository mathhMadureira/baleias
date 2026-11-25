# Ideias de pesquisa (hipóteses candidatas, ainda NÃO testadas)

Cada seção é escrita pela rotina diária de pesquisa. Nada aqui é resultado: é candidato a pré-registro em `lab/PROTOCOLO_LAB.md`.
Fontes da internet são dados de terceiros; números entre aspas são os que a fonte dá, e "não sei" onde ela não dá.

## 2026-11-25

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/agente_laboratorio.json`, `dados/mercado_agora.json`, 10:18 UTC):

| | |
|---|---|
| Campeão do torneio | **nenhum** (ninguém com carteira > US$ 10 e fator > 1). Melhor fator: **Laboratório 0,81** (27 op, acerto 37%, soma −0,74, carteira 9,26) · Treinador 0,71 (47) · Robô Claude 0,62 (73) · conta de teste 0,59 (56) · Guardião 0,59 (74) |
| Onde o Laboratório perde | **stop de segurança −1%: 7 op, −2,64**; prazo de 120 min: 6 op, −0,85 (stop móvel: 4 op, +1,92). Horário de entrada: **18–24 UTC 19 op, −2,49** (00–06: 2 op +0,70; 12–18: 6 op +1,05). Pelo pregão de Nova York (dias úteis, 15–21 UTC): dentro, vendas 4 op +0,55 e compras 3 op −0,19; fora, vendas 11 op −0,88 e compras 9 op −0,23 |
| Segmento fraco do vigia | 00–06 h UTC 50,9% (8.337) e confiança < 0,05 51,9% (16.762); compras 52,6% × vendas 54,2%. Ao vivo 53,5% × laboratório 53,5% (z +0,03), "dentro do esperado"; confiança ≥ 0,12 acerta 64,2% (858) |

**Mercado hoje** (`dados/mercado_agora.json`): BTC 58.977, −1,71% em 24 h, −0,57% em 4 h, volume de 4 h 1,49× a média; 16,0% das 125 moedas sobem em 4 h
(mediana −1,39%), 17,6% em 24 h (mediana −3,50%). Maior queda de 4 h: NFP −40,5%.

**Já testado ou proposto (fora desta lista):** tudo de 15–24/11 (abaixo), H76–H80; stop por ATR (16/11) — por isso o stop móvel por ATR do
AdaptiveTrend (abaixo) **não** é proposto de novo; stop no fechamento e filtro de Amihud (24/11); filtro de direção de Nova York no Guardião (20/11).

### Ideia 1 — Laboratório: só entrar quando a moeda está em regime de continuação (razão de variâncias ≥ 1)

- **Regra:** para a moeda candidata, VR = Var(r_15min) ÷ (15 × Var(r_1min)), com os retornos de 1 min e de 15 min (não sobrepostos) das últimas
  6 h de velas fechadas. Entrada nova do Laboratório só se VR ≥ 1,0. Compra e venda iguais; stop, alvo e prazo como hoje. Limiar fixado antes =
  1,0 (o ponto teórico, sem ajuste). 1 tentativa.
- **Por quê no Laboratório:** o stop de −1% é onde ele perde (7 op, −2,64, mais que o resultado todo). A teoria diz quando um stop ajuda: com
  retornos sem memória o prêmio do stop é sempre negativo; ele só ajuda com momento (continuação). VR < 1 é reversão à média em minutos: o preço
  bate no −1% e volta (os stops de SOPH 20/11 e BREV 23/11 vieram depois de picos de +0,97% e +0,77%). Barrar essas entradas evita o regime em
  que o stop fixo é caro, sem mexer no stop.
- **Dados:** velas de 1 min do perpétuo da Binance (grátis).
- **Evidência:** Kaminski & Lo, "When Do Stop-Loss Rules Stop Losses?", *Journal of Financial Markets* 18 (2014), pp. 234–254,
  https://dspace.mit.edu/handle/1721.1/114876 — "under the Random Walk Hypothesis … the stopping premium is always negative"; dão condições para
  o stop agregar valor com momento, reversão e troca de regime. Na versão de trabalho (dados mensais 1950–2004) certos stops somam "50 to 100 basis
  points per month" nos períodos de stop (https://ideas.repec.org/p/hhs/sifrwp/0063.html). Para cripto em 1 min, e para o filtro por VR: **não sei**
  (o artigo é de futuros e ações, não de cripto; não achei estudo que filtre entradas por VR).
- **Teste:** entradas tipo Laboratório (H69: v4 com confiança ≥ 0,12, regras de hoje) reconstruídas no histórico de 1 min, saída de hoje, custo
  0,12% ida e volta, 3 blocos de tempo iguais. Passa se, nos 3 blocos, as barradas (VR < 1) tiverem média líquida < 0 e as aceitas média maior que
  o conjunto todo, z ≥ 1,65; e a taxa de saída no stop de −1% das barradas for maior que a das aceitas. Menos de 30 barradas por bloco → "não sei".

### Ideia 2 — Laboratório: lado pelo relógio de Nova York (vende no pregão, compra fora dele)

- **Regra:** em dia útil, de 15:00 a 21:00 UTC (10h–16h de Nova York em horário de inverno; 14:00–20:00 UTC no verão), entrada nova do
  Laboratório só de **venda**; fora dessa janela e no fim de semana, só de **compra**. O sinal do v4 continua escolhendo a moeda e a hora; o filtro só
  veta o lado contrário. Sem parâmetro além do horário oficial da NYSE. 1 tentativa.
- **Por quê no Laboratório:** nas 27 operações, as vendas dentro do pregão deram +0,55 (4 op) e fora −0,88 (11 op); 18–24 UTC é o pior horário
  (19 op, −2,49), com boa parte depois do fechamento de Nova York. Amostra pequena: é só a pista, o teste é no histórico. Difere do filtro de
  20/11 (Guardião, direção do BTC desde 13:30) porque aqui o lado vem do relógio, não do movimento.
- **Dados:** velas de 1 min do perpétuo da Binance e o calendário da NYSE (grátis).
- **Evidência:** estudo com velas de 5 min do BTC de jan/2018 a dez/2023, citado na imprensa sobre o ETF NGHT
  (https://crypto.news/bitcoin-afterdark-etf-targets-btcs-overnight-edge-skips-u-s-hours/): retorno médio de **+0,093%** fora do pregão americano
  contra **−0,029%** dentro (números do resumo de busca; autores e custo: não sei). Quantpedia (https://quantpedia.com/how-to-profitably-trade-bitcoins-overnight-sessions/,
  BTC Gemini por hora, 2015–2024): "most of the BTC returns since 2021 were realized during the nightly sessions"; números por sessão só em
  figura (não sei); sem custos. **Evidência contra:** artigo do *Journal of Risk and Financial Management* 19(9):692 (https://www.mdpi.com/1911-8074/19/9/692,
  BTC e ETH por hora 2016–2025): na reserva 2021–2025 "the BTC training-selected rule underperforms buy-and-hold" (página deu 403; frase do resumo
  de busca). Para altcoins: não sei.
- **Teste:** mesmas entradas reconstruídas da Ideia 1, custo 0,12%, 3 blocos. Passa se, nos 3 blocos, as entradas vetadas (lado contra o relógio)
  tiverem média líquida < 0 e as aceitas média maior que o conjunto todo, z ≥ 1,65 (erro-padrão por hora de entrada). Menos de 30 vetadas por
  bloco → "não sei". Ideias 1 e 2 juntas = 2 tentativas (Bonferroni: z ≥ 1,96).

### Não proposta (anotado para não repetir)

- **Stop móvel por ATR do AdaptiveTrend** (arXiv 2602.11708, pré-publicação; 150+ pares, velas de 6 h, 2022–2024): S_t = max(S_{t−1}, P_t − α·ATR_t),
  α com patamar em 2,0–3,5 (centro 2,5); sem o stop móvel, Sharpe 1,68 e queda máxima −22,4% contra 2,41 e −12,7% com ele; com 12 pb de custo, Sharpe
  1,62. Parâmetros reotimizados todo mês (risco de sobreajuste) e "stop por ATR" já foi proposto em 16/11.
- **Variação dos juros em aberto como sinal de horas:** não achei artigo com teste de previsão; um artigo (arXiv 2310.14973) diz que os juros em aberto
  dos perpétuos de BTC são "systematically misquoted" por algumas das maiores corretoras — cuidado com esse dado.

### O que aprendi hoje sobre o mercado cripto

O BTC voltou a ficar abaixo de US$ 60 mil (58.977 às 10:18 UTC, `dados/mercado_agora.json`) puxado por saída dos ETFs à vista: novembro já soma
saídas de **US$ 4,71 bi**, recorde mensal da categoria, com US$ 569,7 mi na segunda (23/11) e US$ 231,4 mi na terça (24/11), dados da Farside citados
por https://cryptobriefing.com/blackrock-ibit-bitcoin-etf-outflows-november/ e https://coinalertnews.com/news/2026/11/25/bitcoin-etf-outflows-btc-falls
(conferidos só no resumo de busca). As liquidações do dia têm números que não batem entre fontes (US$ 87 mi só em BTC × "mais de US$ 800 mi" no
mercado todo): não sei o valor certo. A queda segue com volume de 4 h 1,49× a média e só 16% das moedas subindo: é venda ampla, guiada pelo fluxo à vista
dos EUA. Isso conversa com o relógio do mercado: desde os ETFs, boa parte da compra e da venda institucional acontece no pregão de Nova York, e os
estudos de praticantes acham que o BTC rendeu mais fora desse horário (+0,093% × −0,029% por sessão, 2018–2023) — mas o teste acadêmico mais
cuidadoso achado diz que a regra do BTC escolhida no passado não ganhou de comprar e segurar em 2021–2025. Lição de método (Kaminski & Lo): um stop
fixo só tem valor esperado positivo se o preço tiver continuação; em ruído puro ele sempre custa. O stop de −1% do Laboratório deve ser julgado junto
com o regime de memória do preço, e não sozinho.

## 2026-11-24

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/agente_laboratorio.json`, `dados/LICOES.md`, 10:18 UTC):

| | |
|---|---|
| Campeão do torneio | **nenhum** (ninguém com carteira > US$ 10 e fator > 1). Melhor fator: **Laboratório 0,83** (25 op, acerto 36%, soma −0,64, carteira 9,36) · Treinador 0,71 (47) · Robô Claude 0,62 (73) · conta de teste 0,60 (54) · Guardião 0,58 (73) |
| Onde o Laboratório perde | **saída no stop de segurança −1%: 7 op, −2,64** (stop móvel: 4 op, +1,92; prazo de 120 min: 5 op, −0,71). Horário: 18–23 UTC 14 op, −0,99 (12–17 UTC +0,56). Lado: compra 12 op −0,42, venda 13 op −0,23. Dois stops (SOPH 20/11, BREV 23/11) vieram depois de pico de +0,97% e +0,77% |
| Segmento fraco do vigia | 00–06 h UTC 51,2% (8.104) e confiança < 0,05 52,4% (16.212); compras 53,0% × vendas 54,3%. Ao vivo 53,8% × laboratório 53,5% (z +0,33), "dentro do esperado" |

**Mercado hoje** (`dados/mercado_agora.json`): BTC 60.000, −2,26% em 24 h, −0,81% em 4 h, volume de 4 h 0,59× a média; 7,9% das 140 moedas sobem em 4 h
(mediana −2,19%). BTC abaixo da MM50 (76.257) e da MM200 (72.291). Medo e ganância 11. Funding (Hyperliquid) neutro: BTC +1,2%/ano, ETH −3,0%/ano.

**Já testado ou proposto (fora desta lista):** tudo de 15–20/11 (ver abaixo), H69, H70, H74, H75; parcial + stop no zero (19/11); stop por ATR (16/11);
stop móvel no fechamento da vela (correção de 19/11, `executor/stop_movel.py`) — a Ideia 1 é sobre o **stop de segurança**, que ainda é por toque.

### Ideia 1 — Laboratório: stop de segurança pelo fechamento da vela de 1 min, com stop de catástrofe de 2% guardado na corretora

- **Regra:** a posição sai no stop de segurança se o **fechamento** de uma vela de 1 min estiver ≥ 1,0% contra a entrada (hoje basta a mínima/máxima
  tocar). Proteção: ordem de stop de 2,0% guardada na corretora (fecha no toque). Nada mais muda (stop móvel, alvo, prazo como hoje). Parâmetros fixos
  antes de rodar: 1,0% e 2,0%. 1 tentativa.
- **Por quê no Laboratório:** o stop de −1% é onde ele perde: 7 das 25 operações, −2,64 (`dados/agente_laboratorio.json`), mais do que todo o resultado
  (−0,64). Se parte desses toques é ruído de pavio de 1 min, o stop no fechamento evita a saída sem mudar a entrada.
- **Dados:** velas de 1 min do perpétuo da Binance (grátis).
- **Evidência:** Hansen, Kim & Kimbrough, "Periodicity in Cryptocurrency Volatility and Liquidity" (arXiv 2109.12142, v2; Binance, Coinbase Pro e
  Uniswap, BTC e ETH, 01/10/2020–01/06/2021), https://arxiv.org/abs/2109.12142 — "a large burst in volatility during the first minute of the hour and
  medium bursts immediately after minutes 15, 30, and 45, and smaller bursts every five minutes"; o efeito é mais forte a cada 4 h (00h…20h, exceto 08h).
  Tamanho do surto em número: não sei (está só em figura). Que o stop no fechamento melhora o resultado: **não achei estudo** — só textos de praticantes
  sem números verificáveis; a única nota mais séria achada (QFX Research, 1 min da BitMEX) diz que stops reduzem a volatilidade do retorno, e a página
  deu 403 (números: não sei). Risco conhecido: a perda média por stop sobe (pode sair a −1,5% ou −2%).
- **Teste:** todas as entradas tipo Laboratório (H69: v4 com confiança ≥ 0,12, regime e regras de hoje) reconstruídas no histórico de 1 min, saídas de
  hoje com os dois stops (toque × fechamento + 2%); custo 0,12% ida e volta; 3 blocos de tempo iguais. Passa se, nos 3 blocos, a média líquida por
  operação com stop no fechamento for maior que com stop no toque, z ≥ 1,65 (pareado por operação), e a pior operação não passar de −2,0% + custo.
  Menos de 30 operações que tocam −1% por bloco → "não sei".

### Ideia 2 — Laboratório: não abrir posição em moeda com iliquidez da última hora ≥ 1,3× a das 24 h anteriores

- **Regra:** para a moeda candidata, I_h = Σ|r_1min| ÷ Σ volume_USD_1min na última hora (Amihud por hora). R = I_h ÷ média de I nas 24 horas
  anteriores. Entrada nova só se R < 1,3. Compra e venda iguais. Limiar fixado antes = 1,3 (o "cerca de 30%" da fonte). 1 tentativa.
- **Por quê no Laboratório:** ele perde de 18 a 23 UTC (14 op, −0,99) e ganha de 12 a 17 (+0,56); na Binance a iliquidez relativa é maior na
  noite da Ásia Oriental. Medir pela moeda (e não pelo relógio) evita repetir filtros de horário já propostos e pega também as horas ruins fora da
  janela. Moeda ilíquida = pavio maior = mais chance do stop de −1% (onde ele perde).
- **Dados:** velas de 1 min com volume em USDT do perpétuo da Binance (grátis).
- **Evidência:** mesmo artigo (arXiv 2109.12142, seção 5.2.1): "For Binance, the relative illiquidity is largest during night time in East-Asia where
  it is about **30% larger** for both Bitcoin and Ether" (medida de Amihud por hora relativa às 24 h anteriores, a mesma deste filtro). Brauneis,
  Mestel & Theissen (2025, citados em 16/11) acham pico de iliquidez em 16–17 UTC. Que o filtro melhore o resultado de operações: não sei (os artigos
  medem liquidez, não lucro). Para altcoins pequenas: não sei (o artigo só tem BTC e ETH).
- **Teste:** mesmas entradas reconstruídas da Ideia 1 (saída de hoje), custo 0,12%, 3 blocos. Passa se, nos 3 blocos, as entradas barradas (R ≥ 1,3)
  tiverem média líquida < 0 e as aceitas média maior que o conjunto todo, z ≥ 1,65; e a taxa de stop de −1% das barradas for maior que a das aceitas.
  Menos de 30 barradas por bloco → "não sei". Ideias 1 e 2 juntas = 2 tentativas (Bonferroni: z ≥ 1,96).

### Não proposta (anotado para não repetir)

- **Spread dos perpétuos ~2 h depois do funding (00/08/16 UTC):** resumo de busca de um artigo do *International Journal of Financial Studies* 14(5):103
  (2026; 26 corretoras, 812 símbolos, nov/2025–jan/2026), https://www.mdpi.com/2227-7072/14/5/103 — a página deu 403, números não conferidos. Nosso
  custo no lab é fixo (0,12%) e o spread não se mede em velas: sem como testar agora.
- **Pulso de 15 min (Kim & Hansen):** já proposto em 15/11 (fluxo agressor na virada do quarto de hora).

### O que aprendi hoje sobre o mercado cripto

O BTC voltou a ficar abaixo de US$ 60 mil hoje (CoinDesk, 24/11 10:08 UTC, "Bitcoin falls below $60,000 as rally on Jensen Huang's Nvidia return fades";
Cointelegraph, 09:25 UTC, liga ao ouro com "worst 60-day loss since 1980s"; manchetes em `dados/mercado_agora.json`) e os ETFs à vista seguem com
saídas ("Bitcoin ETFs keep bleeding", Cointelegraph 07:41 UTC; valor: não sei). Em novembro, o IBIT perdeu US$ 269,7 mi em 11/11, a sétima sessão
seguida de saídas (Crypto Briefing, https://cryptobriefing.com/blackrock-ibit-bitcoin-etf-outflows-4/), e a série de 11 sessões de saídas somou
~US$ 2,35 bi até a primeira entrada em 17/11 (CoinStats, resumo de busca; não conferido no texto). O funding está neutro (BTC +1,2%/ano) com medo
extremo (11): queda sem alavancagem comprada esticada, ou seja, vendas guiadas por fluxo à vista e não por liquidação de comprados. Sobre o relógio do
mercado (Hansen, Kim & Kimbrough, arXiv 2109.12142): a volatilidade do BTC é máxima perto de 16 UTC e mínima perto de 05 UTC; há picos de volume e
volatilidade às 00 h e 16 h (menores às 08 h), as horas de funding da Binance; volume e volatilidade caem no fim de semana, mais no sábado; a
iliquidez na Binance é ~30% maior na noite da Ásia Oriental; e o primeiro minuto de cada hora concentra a maior volatilidade, com surtos menores nos
minutos 15, 30 e 45 — atribuídos a algoritmos e a quem opera por gráfico. Esses padrões, dizem os autores, ficaram mais fortes com os anos.

## 2026-11-20

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/LICOES.md`, 10:18 UTC):

| | |
|---|---|
| Campeão do torneio | **Guardião** (35 op, acerto 62,9%, soma +0,29, fator de lucro 1,11, carteira 10,29) · Laboratório 1,06 (10 op) · Robô Claude 1,00 (41) · Treinador 0,72 (24) · conta de teste 0,64 (25) |
| Onde o Guardião perde | **compras**: 8 op, 50% certas, −0,49 (vendas: 27 op, 67%, +0,78). Perda média 0,203 × ganho média 0,133. 26 das 35 op em 18–23 UTC (−0,03); últimas 24 h −0,40 (12/23). Moedas: TRUMP −0,20 (5 op), DOGE −0,10 (4) |
| Segmento fraco do vigia | compras 52,0% (14.002) × vendas 57,9% (15.689); 18–24 h UTC 52,3% (8.850). Ao vivo 55,1% × laboratório 53,5% (z +1,71), "dentro do esperado" |

**Mercado hoje** (`dados/mercado_agora.json`): BTC 61.805, −3,12% em 24 h, −0,09% em 4 h, volume de 4 h 0,78× a média; só 14,8% das 122
moedas sobem em 24 h (mediana −4,08%). BTC abaixo da MM50 (78.236) e da MM200 (72.694); 12,5% das moedas acima da MM50. Medo e ganância 12.
Funding na Hyperliquid: BTC −6,3%/ano, média das 20 maiores +3,6%/ano.

**Já testado ou proposto (fora desta lista):** H55, H39, H64 (S1–S4), H52/R6, H46, H65 (fluxo agressor, momento semanal, vol), stop por ATR (16/11),
OI × prêmio (16/11), janela FOMC/CPI (17/11), compras só com confiança ≥ 0,12 (18/11), piso de movimento (18/11), veto de queda de 1 h esticada (19/11),
parcial em +0,6% (19/11), funding como direção (19/11, não proposta).

### Ideia 1 — Guardião: compra de memecoin só com o BTC subindo na última hora e nas últimas 4 h

- **Regra:** a compra de memecoin do Guardião só é aceita se r1(BTC) > 0 **e** r4(BTC) > 0 (retorno do BTC perpétuo nas últimas 1 h e 4 h,
  velas de 5 min fechadas). Vendas sem mudança (são onde ele ganha). Sem parâmetro a ajustar: o limiar é zero. 1 tentativa.
- **Por quê no Guardião:** as compras são o lado que perde (8 op, −0,49) e o vigia do v4 mostra o mesmo (compras 52,0% × vendas 57,9%).
  Memecoin é moeda pequena e o BTC transmite o movimento para ela, sobretudo nas quedas: comprar memecoin com o BTC caindo é comprar
  contra quem dá o preço.
- **Dados:** velas de 5 min do BTCUSDT e das memecoins no perpétuo da Binance (grátis).
- **Evidência:** Kurihara & Matsumoto, "Price Transmission from Bitcoin to Altcoins: High-Frequency Evidence and Implications for Trading Strategy",
  *Asia-Pacific Financial Markets* (2026), https://doi.org/10.1007/s10690-026-09589-z — velas de 1 min da Binance; causalidade de Granger
  **só do BTC para as altcoins**; moedas pequenas e de pouca liquidez reagem com atraso de vários minutos; com 2 min de atraso "almost none"
  dos efeitos é significativo. A estratégia deles usa taxa de 0,02% por operação (bem abaixo dos nossos 0,12%): **o ganho deles não vale para nós**;
  só o sentido (BTC conduz) é usado aqui, como filtro e não como gatilho. Santos, Sebastião & Silva, "Bitcoin and Main Altcoins: Causality and
  Trading Strategies", *Notas Económicas* 59 (2025), pp. 7–33 (https://ideas.repec.org/a/gmf/journl/y2025i59p733.html): a causalidade
  BTC → altcoins "more evident in the left tail" (quedas); em alta o BTC é mais receptor. Coeficientes: não sei. Para horizonte de 1 a 4 h: não sei.
- **Teste:** reconstruir as compras tipo Guardião (memecoin, regime de 24 h e regras de entrada de hoje) em todo o histórico de 5 min das memecoins
  do universo; saída igual à de hoje; custo 0,12% ida e volta; 3 blocos de tempo iguais. Passa se, nos 3 blocos, as compras barradas tiverem média
  líquida < 0 e as aceitas tiverem média maior que o conjunto todo, com z ≥ 1,65 (erro-padrão por hora de entrada). Menos de 30 compras barradas
  por bloco → "não sei". 1 tentativa.

### Ideia 2 — Guardião no fim do dia (18–24 UTC): só o lado do BTC desde a abertura de Nova York

- **Regra:** de 19:30 a 24:00 UTC, uma entrada nova do Guardião só é aceita no sentido de rNY = retorno do BTC perpétuo de 13:30 UTC até a vela de
  5 min anterior à entrada (rNY > 0 → só compra; rNY < 0 → só venda; |rNY| < 0,12% → sem filtro). Fora dessa janela, nada muda. Fins de semana
  ficam fora (sem pregão nos EUA). 1 tentativa, limiar = o custo, fixado antes.
- **Por quê no Guardião:** 26 das 35 operações dele são de 18–23 UTC e ali o resultado é −0,03; é também o segmento mais fraco do v4 ao vivo
  (52,3%). É a versão cripto do "a primeira meia hora prevê a última": o fim do pregão americano segue o começo.
- **Dados:** velas de 5 min do BTCUSDT perpétuo (grátis).
- **Evidência:** Shen, Urquhart & Wang, "Bitcoin intraday time-series momentum", *Financial Review* (2022), https://centaur.reading.ac.uk/100181 —
  o retorno da primeira meia hora prevê positivamente o da última; as sessões de maior volume ou volatilidade dão a maior previsibilidade; o motor é
  provisão de liquidez. Coeficientes, R² e custo: não sei (o PDF não abriu neste ambiente). Baur, Cahill, Godfrey & Liu (via Quantpedia,
  https://quantpedia.com/are-there-any-simple-calendar-effects-in-bitcoin-market/): mais atividade quando a bolsa americana está aberta, mas
  efeitos de hora do dia **sem padrão persistente** — evidência contra; por isso 1 tentativa e o veredito pelos 3 blocos.
- **Teste:** reconstruir as entradas do Guardião (memecoins e líderes de 24 h) com hora de entrada de 19:30–24:00 UTC, em dias úteis, em todo o
  histórico de 5 min; saída de hoje; custo 0,12%; 3 blocos. Passa se as entradas contra rNY tiverem média líquida < 0 e as a favor > as contra,
  nos 3 blocos, z ≥ 1,65. Ideias 1 e 2 juntas = 2 tentativas (Bonferroni: z ≥ 1,96).

### Não proposta (anotado para não repetir)

- **BTC como gatilho de 1 min para altcoins (lead-lag):** o atraso é de 1–2 min e a estratégia de Kurihara & Matsumoto foi feita com taxa de 0,02%;
  com 0,12% ida e volta, não paga. Fica só como filtro (Ideia 1).
- **Saída por tempo sem progresso ("time stop"):** não achei estudo revisado; os backtests públicos são de blog e se contradizem (um relata fator de
  lucro de 1,03 para 1,27 ao **remover** a saída de 24 h, em 13 dias: https://dev.to/trendrider/13-days-48-trades-breakeven-then-i-fixed-one-thing-1d6j).
- **Queda de juros em aberto / cascata de liquidação como sinal de repique:** o artigo mais sério achado (arXiv 2607.27070, 7 cascatas do BTCUSDT,
  juros em aberto de 5 min) diz que não observa liquidações diretamente e usa aproximações; resultados de previsão: não sei. Sem base para uma tentativa.

### O que aprendi hoje sobre o mercado cripto

O mercado segue em regime de baixa com medo extremo (índice 12; 14,8% das moedas subindo em 24 h; BTC 61.805, abaixo das médias de 50 e 200 dias;
`dados/mercado_agora.json`). O funding do BTC na Hyperliquid está negativo (−6,3%/ano): os vendidos pagam, sem euforia de compra. Do lado do fluxo,
os ETFs à vista de BTC nos EUA tiveram ~US$ 2,35 bi de saídas líquidas em duas semanas (Crypto Briefing, 18/11/2026,
https://cryptobriefing.com/bitcoin-etf-outflows-anthropic-ipo/); a sequência de saídas começou em 05/11, antes de a Anthropic fixar a faixa de preço do
IPO, e o próprio artigo cita um gestor dizendo que as saídas não vêm do IPO. A manchete da Cointelegraph de 20/11 ("IBIT loses record $541M") não pude
confirmar na busca: número não verificado. A CoinDesk liga o tombo do ouro à fraqueza do BTC (manchete de 20/11; números: não sei). Sobre como o preço se
forma em minutos: o BTC conduz as altcoins e não o contrário (Granger unidirecional, Kurihara & Matsumoto 2026), as moedas pequenas reagem com atraso
de minutos e essa transmissão é mais forte nas quedas (Santos et al. 2025) — o que casa com o Guardião ganhando nas vendas e perdendo nas compras num
mercado que cai.

## 2026-11-19

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/agente_guardiao.json`, 10:18 UTC):

| | |
|---|---|
| Campeão do torneio | **nenhum** (`campeao: null`; mínimo 30 operações, ninguém chegou) |
| Melhor fator de lucro | **Guardião** 2,85 (12 op, acerto 83,3%, soma +0,69, carteira 10,69) · Treinador 2,59 (6 op) · Robô Claude 0,43 (23) · conta de teste 0,40 (13) |
| Onde o Guardião perde | 2 perdas, **as duas em venda de memecoin**: TRUMP −0,277 (stop de segurança −0,8%, posição de US$ 30 a 20×, entrada com 1 h −1,38% e 4 h −2,41%) e SHIB −0,096 (prazo de 90 min). Todas as 12 op foram de 18–23 UTC. Ganho médio 0,106 × perda média 0,186: o alvo fixo de +0,6% limita o ganho abaixo do stop de 0,8% |
| Segmento fraco do vigia | compras 53,0% (12.164) × vendas 57,7% (14.066); 18–24 h UTC 53,4% (7.886). Acerto ao vivo 55,5% contra 53,5% do laboratório, z +2,01 |

**Mercado hoje** (`dados/mercado_agora.json`): BTC 63.797, −1,24% em 24 h, +0,51% em 4 h, volume de 4 h 0,69× a média; 31,8% das 110 moedas
sobem em 24 h (fronteira do regime de baixa) e 59,1% em 4 h (repique sem volume). Medo e ganância 10. Funding médio das 20 maiores na
Hyperliquid +8,9%/ano (BTC −1,4%). Só 5,0% das moedas acima da MM50 diária.

**Já testado ou proposto (fora desta lista):** H55 (não perseguir a vela de 15 min), H39 (entrar esticado), H64 (saída colher/balde, S1–S4), H52/R6,
H46 (18–24 UTC), stop por ATR (16/11), OI × prêmio (16/11), compras só com confiança ≥ 0,12 (18/11), piso de movimento (18/11).

### Ideia 1 — Guardião: não vender memecoin depois de queda de 1 h esticada (reversão de 1 a 4 h)

- **Regra:** para a memecoin candidata à venda, z1 = retorno da última hora ÷ mediana do |retorno de 1 h| das 24 h anteriores (velas de 1 h
  fechadas, Binance). Veto da venda se z1 ≤ −2,5. Espelho na compra: veto se z1 ≥ +2,5. Parâmetro fixo, 1 tentativa (2,5 não é ajustado:
  é escolhido antes de olhar).
- **Por quê no Guardião:** é o único robô com fator de lucro > 1 e as perdas dele são vendas de memecoin. A pior (TRUMP, −0,277 = 1,15 R) entrou
  com −1,38% em 1 h e −2,41% em 4 h, e pegou o repique. A H55 só olha a média de 20 velas de 15 min. Esta regra olha o tamanho da última hora
  em relação à volatilidade da própria moeda. Com alvo de 0,6% e stop de 0,8%, um repique de 1 h basta para tirar a operação.
- **Dados:** velas de 1 h e de 5 min da Binance (grátis).
- **Evidência:** De Nicola, "On the Intraday Behavior of Bitcoin", *Ledger* 6 (2021), pp. 58–80 (https://epub.ub.uni-muenchen.de/97651/):
  "significant negative first-order autocorrelation" dos retornos de 1, 2 e 4 h, e "larger price movements lead to stronger reversals".
  Coeficientes: não sei (texto completo fechado). Contra: Caporale & Plastun (2020, https://link.springer.com/10.1007/s11408-020-00357-1;
  BTC, ETH, LTC, 2015–2019) acham **continuação** na hora dentro de dias anormais. Só BTC/ETH/LTC; para memecoin: não sei.
- **Teste:** reconstruir as entradas tipo Guardião (venda de memecoin a favor do regime de 24 h ≤ 30%; compra no ≥ 70%) em todas as memecoins do
  universo desde o início dos dados de 15 min, saída igual à de hoje (stop 0,8%, alvo 0,6%, stop móvel, 90 min), custo 0,12% ida e volta,
  3 blocos de tempo. Passa se a média líquida por operação com o veto for maior nos 3 blocos e as operações barradas tiverem média < 0
  (z ≥ 1,65 unilateral, erro-padrão por hora de entrada). Se forem barradas menos de 30 operações, o veredito é "não sei". 1 tentativa.

### Ideia 2 — Guardião: realização parcial em +0,6% e o resto com stop no zero (custo incluído)

- **Regra:** metade da posição sai em +0,6% (como hoje). No mesmo instante, o stop da outra metade vai para a entrada + 0,12% (custo pago).
  O alvo dessa metade fica em +1,8% (3 × o stop de 0,6% medido da entrada) ou ela sai no prazo de 90 min, o que vier primeiro. Stop inicial de
  0,8% sem mudança. 1 tentativa.
- **Por quê no Guardião:** a razão ganho ÷ perda dele é 0,57 (0,106 ÷ 0,186). 5 das 10 vitórias pararam no alvo fixo de +0,6%, e picos de até
  +1,26% foram deixados (PUMP vendida, pico +1,26%). Na H64 o stop móvel cortou o ganho em ~0,6% e o alvo de 3% (S4) foi a melhor rota, mas
  perdeu no bloco recente. A parcial guarda o acerto de hoje e abre espaço para o "balde".
- **Dados:** velas de 1 min / 5 min da Binance (para saber o que veio primeiro dentro da vela).
- **Evidência (fraca e CONTRA):** o único backtest público achado (Enlightened Stocktrading, RealTest, sistema de tendência em ações,
  https://enlightenedstocktrading.com/trend-following-profit-targets-do-they-work) diz que "every instance of partial profit taking reduced the
  overall rate of return" e que o retorno ajustado ao risco não melhora de forma estável. Números da tabela: não sei. A favor, só um argumento
  sem backtest (NexusFi, https://nexusfi.com/showthread.php?p=58918): a parcial reduz a sequência de perdas. Não é cripto nem horizonte de 90 min:
  por isso o teste decide.
- **Teste:** mesmas entradas reconstruídas da Ideia 1 (sem o veto), saída de hoje × saída parcial, custo 0,12% em cada metade, 3 blocos. Passa se
  a média líquida for maior nos 3 blocos, z ≥ 1,65, e o ganho médio ÷ perda médio subir. 1 tentativa. Ideias 1 e 2 juntas = 2 tentativas (Bonferroni: z ≥ 1,96).

### Não proposta (anotado para não repetir)

- **Funding como sinal de direção em horas:** a nota da Presto Research (https://prestolabs.io/research/can-funding-rate-predict-price-change; BTC
  perpétuo da Binance desde 2021) dá R² = 12,5% entre a variação do funding e a do preço **na mesma** semana, e **R² ≈ 0 para a semana seguinte**.
  O sinal entre moedas não inclui custo e tem giro "extremely high". He, Manela, Ross & von Wachter ("Fundamentals of Perpetual Futures",
  https://arxiv.org/abs/2212.06888) acham que o retorno passado prevê o desvio do perpétuo em relação ao preço justo (demanda extrapolativa),
  não o retorno futuro. Não vale uma tentativa agora.

### O que aprendi hoje sobre o mercado cripto

O BTC está entre 63 e 64 mil, com cerca de −14% em uma semana. O dado de hoje às 10:18 UTC é 63.797 (`mercado_agora.json`), com 62 mil de suporte
testado de novo hoje cedo (manchete da Cointelegraph no retrato: "Bitcoin retests $62K"). O motor é macro: a ata do Fed mostrou "nearly all
participants" a favor de mais altas de juros, e a chance de alta de 25 pb em dezembro aparece como 90% numa fonte e 97,4% em outra (resumo de
busca: https://www.altcoinbuzz.io/bitcoin-below-63000-fed-rate-hike-december, https://www.coingabbar.com/en/bitcoin-price-forecast-btc-struggles-near-63k-fed-hike-odds-rise;
número oficial: não sei). Os ETFs à vista de BTC tiveram saída líquida de US$ 239,9 milhões em 17/11 e US$ 306,42 milhões em 18/11, com o IBIT
em −148,66 milhões no dia 18, segundo resumo de busca (https://bitcoinworld.co.in/bitcoin-weekly-selloff-etf-outflows/). Esses números não foram
conferidos na Farside. A Cointelegraph de hoje diz que a saída líquida de 2026 passa de US$ 2,5 bilhões. As liquidações divergem entre fontes
(US$ 178,86 milhões em 24 h numa e ~US$ 2 bilhões no fim de semana em outra; não sei qual está certa), com maioria de comprados.

Sobre o relógio: a reversão de 1 a 4 h no BTC (De Nicola 2021) convive com a continuação dentro de dias de choque (Caporale & Plastun 2020).
O que decide é o tamanho do movimento em relação à volatilidade, que é o que a Ideia 1 mede. Com medo e ganância em 10, só 5% das moedas acima da MM50
e o funding das grandes perto de zero (BTC −1,4%/ano), não há comprados lotados para liquidar. A venda de hoje é de fluxo (ETF e macro), não
de alavancagem. Repiques curtos sem volume (4 h com 59% subindo e volume 0,69×) seguem sendo ponto de venda pela cartilha.

## 2026-11-18

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/robo_v4_cacador.json`, 10:19 UTC):

| | |
|---|---|
| Campeão do torneio | **Caçador** (42 op, acerto 78,6%, fator de lucro 1,82, soma +2,03, carteira 11,98) |
| Outros com ≥ 30 op | Scalper B 1,61 (96 op, +2,46; "GANHOU do campeão" do Scalper) · Rápido 1,23 (45) · Scalper 1,19 (83) · Minerador 0,70 (40) |
| Onde o Caçador perde | 9 perdas somam −2,47; **3 stops de segurança de −2% = −1,82 (74%)**: HEMI compra 15/11 14:00, BCH compra 18/11 00:15, PYTH compra 18/11 00:30 |
| Por horário / lado | 00–06 UTC 11 op −0,14; 12–18 UTC 1 op −0,53; 18–24 UTC 25 op +2,11 · compras 26 op +0,77, vendas 16 op +1,25 |
| Segmento fraco do vigia | compras 52,5% (10.864) × vendas 58,3% (12.396); 18–24 h UTC 52,6% (7.043); ≥ 0,12 de confiança 67,9% (414) |

Observação do dado: o Caçador escolhe **moedas estáveis** pela probabilidade do v4. RWUSDUSDT ficou 12,5 h aberta (−0,036, "tempo máximo"),
UUSDT fechou −0,028 em 16/11, e agora há **UUSDT comprada de novo a 1,0003 há 13,6 h** (pico +0,01%), ocupando 1 das 4 vagas
(caixa 6,35 de 12,09). Uma moeda que não se move não paga 0,12% de custo.

**Mercado hoje** (`dados/mercado_agora.json`): BTC 64.599, +0,42% em 24 h, −0,17% em 4 h, volume de 4 h 0,49× a média; 63,8% das 116
moedas sobem em 24 h, só 33,6% em 1 h. Extremos: NFP −66% em 24 h, MMT +115%, ZKC +34,5% em 4 h.

**Já testado ou já proposto (fora desta lista):** stop/alvo por ATR (H40, ideia de 16/11), OI × prêmio (16/11), janela FOMC/CPI e fluxo
agressor na vela (17/11), fluxo do quarto de hora, tamanho por volatilidade, alarme de cascata (15/11), 18–24 h UTC (H46), humor como
filtro de lado (H42), regime de 24 h (H44).

### Ideia 1 — Piso de movimento: não escolher moeda que não paga o custo

- **Regra:** para cada moeda candidata, A = (máxima − mínima) ÷ fechamento das últimas 96 velas de 15 min (24 h). O Caçador (e o Rápido
  nuvem, que usa a mesma escolha) só pode pegar a moeda se A ≥ 2,0% (= o próprio stop de segurança da R6; parâmetro fixo, sem varredura).
  Abaixo do piso, a vaga passa para a próxima da lista do v4. 1 tentativa.
- **Por quê no Caçador:** é um defeito de escolha, não de previsão. Com stop móvel e lucro realizado a +0,50, uma moeda com amplitude
  diária abaixo do custo × alavancagem fica presa até o "tempo máximo (24 h)" ou a virada de tendência, rendendo ≈ 0 menos custo e
  tirando a vaga de uma aposta de 18–24 UTC (onde ganha +2,11). Hoje 1 de 4 vagas está assim (UUSDT).
- **Dados:** velas de 15 min da Binance (grátis); nada novo.
- **Evidência:** interna e aritmética (3 operações em moedas estáveis: −0,028, −0,036 e uma aberta há 13,6 h). Externa, só qualitativa:
  o artigo de pares com aprendizado por reforço (arXiv 2407.16103, https://arxiv.org/pdf/2407.16103) diz que o lucro de alta frequência
  é "sempre significativamente" afetado pelo custo; número para este caso: não sei.
- **Teste:** todas as apostas do v4 conferidas ao vivo (11/11 em diante, 23.260) + histórico do laboratório, simulando a rota R6 do
  Caçador com custo 0,12% ida e volta. Compara a carteira com e sem o piso em 3 blocos de tempo. Passa se a média líquida por vaga-hora
  sobe nos 3 blocos e a soma não cai. 1 tentativa. Risco: poucas moedas estáveis no universo → efeito pequeno; se < 20 apostas forem
  barradas, veredito "não sei".

### Ideia 2 — Compras na abertura de segunda-feira da Ásia; fora dela, compra exige confiança alta

- **Regra:** janela J = domingo 23:00 UTC a segunda 23:59 UTC. Fora de J, o Caçador só abre **compra** se |p − 0,5| ≥ 0,12 (faixa em que o
  vigia mede 67,9%); vendas sem mudança. Dentro de J, compras como hoje (2 compras + 2 vendas). 1 tentativa (limiar 0,12 já é a faixa do
  vigia, não ajustado).
- **Por quê no Caçador:** o lado fraco do v4 ao vivo é a compra (52,5% × 58,3%), e os 3 stops de −2% que fazem 74% da perda do Caçador
  foram **todos compras**. Mercado em sexta semana de queda (CoinDesk, abaixo): comprar com 52% de acerto e stop de 2% é a pior combinação.
  A janela de segunda é onde uma fonte pública acha deriva positiva de tendência.
- **Dados:** velas de 15 min da Binance (grátis) e a probabilidade gravada de cada aposta (já existe no vigia).
- **Evidência:** Concretum Group (Zarattini e coautores), "Seasonality in Bitcoin Intraday Trend Trading" —
  https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/ : 2018–2025, conjunto de modelos de tendência de alta
  frequência com volatilidade-alvo de 20%/ano, Sharpe ≈ 1,6 **bruto de custo** (só comprado ≈ 0,8); retornos "fortemente positivos" de
  domingo ~19:00 ET por ~24 h, alinhados à abertura de Tóquio, efeito "muito mais pronunciado depois de meados de 2020"; domingo de manhã
  nos EUA é negativo. Retorno da janela em %: não sei (a página não dá). Não é artigo revisado; custo não incluído.
- **Teste:** apostas de compra do v4 (ao vivo + laboratório), rota R6, custo 0,12%. Três grupos: compras em J, compras fora de J com
  confiança ≥ 0,12, compras fora de J abaixo de 0,12. Passa se o terceiro grupo tem média líquida < 0 nos 3 blocos de tempo e o filtro
  melhora a soma da carteira nos 3 blocos. 1 tentativa (só há ~1 segunda por semana: se J tiver < 10 segundas, a parte "J" fica "não sei",
  e testa-se só o filtro de confiança da compra).

### O que aprendi hoje sobre o mercado cripto

O BTC está em ~64,5 mil, abaixo da média de 200 semanas (~68 mil, segundo resumo de busca), com o sábado 14/11 tendo ido a ~62 mil e
novembro −17% — sexta perda semanal seguida (CoinDesk, 16/11:
https://www.coindesk.com/tech/2026/11/16/live-news-bitcoin-posts-sixth-weekly-loss-as-tech-stocks-and-metals-slide). O pano de fundo é
macro: treasury de 10 anos a 5,116%, índice do dólar na máxima desde abril/2025, e o mercado precificando 100% de **alta** de juros
de 25 pb na reunião de dezembro do Fed (presidente Kevin Warsh); a ata do Fed é o próximo evento (data: não sei, a página da GuruFocus
deu 403). Liquidações acima de US$ 2 bilhões em 24 h no fim de semana aparecem em resumo de busca; número conferido no texto: não sei.
Sobre o relógio do mercado: Brauneis, Mestel & Theissen (Review of Quantitative Finance and Accounting 64(1), 2025,
https://ideas.repec.org/a/kap/rqfnac/v64y2025i1d10.1007_s11156-024-01304-1.html), 1.940 pares em 38 corretoras: atividade, volatilidade e
**iliquidez** têm pico entre **16:00 e 17:00 UTC**, igual em todas as corretoras; Wątorek et al. (arXiv 2306.17095,
https://arxiv.org/abs/2306.17095, BTC/ETH/DOGE/WIN, 2020–2022, 10 s) acham três fases de atividade (Ásia, Europa, EUA), picos nas horas
cheias e surtos nos anúncios de payroll, CPI e Fed. Para o Caçador: o único stop de 12–18 UTC (HEMI 14:00) caiu na fase de iliquidez
americana, mas 1 operação não prova nada.

## 2026-11-17

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/robo_scalper_nuvem.json`, 08:45 UTC):

| | |
|---|---|
| Campeão do torneio | **Scalper nuvem** (70 op, fator de lucro 1,17, soma +0,43, carteira 10,43) |
| Melhor fator de lucro com ≥ 30 op | Scalper C 1,38 (64 op, soma +0,79; "GANHOU do campeão") · Rápido 1,72 e Caçador 1,94 com < 30 op |
| Onde o Scalper perde | saída **no fim da vela do v4**: 42 op, −1,68 (lucro realizado 24 op +2,28; guarda do dia 4 op −0,17); compras 00–06 UTC 16 op −0,02; 12–18 UTC 2 op −0,20 |
| Segmento fraco do vigia | 18–24 h UTC 49,75% (5.706 apostas) e compras 51,1% (9.539) contra vendas 58,6%; ≥ 0,12 de confiança 70,4% (277) |

Duas observações do dado, sem ação proposta: (1) as 70 operações do Scalper (e as 64 do C) caem todas numa única noite, 16/11 21:45 a
17/11 02:35 UTC; depois disso a guarda/meta do dia travou até 00:00 UTC. O torneio está julgando um episódio só. (2) O Scalper D tem
exatamente os números do Scalper (70 op, 0,432): o foco da H51 ainda não excluiu nada (exige ≥ 50 op e z ≤ −2; o pior segmento tem z −1,42).

**Mercado hoje** (`dados/mercado_agora.json`): BTC 64.507, −0,06% em 24 h, −0,73% em 4 h; 68,2% das 110 moedas sobem em 24 h, mas só
23,6% em 1 h e 31,8% em 4 h; medo e ganância 12; funding médio das 20 maiores da Hyperliquid +2,6%/ano (ontem −6,5%).

**Já testado ou já proposto (fora desta lista):** alvo por ATR (H40), stop por ATR e filtro OI × prêmio (ideias de 16/11), fluxo do quarto
de hora, tamanho por volatilidade e alarme de cascata (15/11), saídas curtas (H24), rotas de saída (H52), 18–24 h UTC (H46, em teste),
primeira meia hora (H34), 1 s (H56). Realização parcial: a única medida pública que achei (Enlightened Stock Trading, 1.432 trades de
tendência em ações) diz que "toda" realização parcial testada reduziu o retorno — não virou ideia.

### Ideia 1 — Janela macro: não abrir posição nova de 30 min antes a 60 min depois de FOMC (comunicado e ata) e CPI dos EUA

- **Regra:** calendário fixo (publicado com meses de antecedência pelo Fed e pelo BLS). Se t ∈ [evento − 30 min, evento + 60 min], os robôs
  do v4 (Scalpers A–D, Rápido, Caçador) não abrem posição; as abertas seguem as saídas normais (regra 11: nada é fechado à força).
  1 tentativa (janela fixa, escrita agora).
- **Por quê no Scalper:** o v4 é um modelo de microestrutura e horário (seção 3.1 do PROJETO), treinado em velas comuns; nos minutos de
  anúncio a volatilidade é outra e a vela do sinal não diz nada do que vem. As saídas "fim da vela" do Scalper (−1,68) são exatamente as
  apostas que não andaram a favor; numa vela de anúncio o movimento é maior e de direção imprevisível. Liga também ao 12–18 UTC
  (horário dos anúncios americanos: 13:30 e 19:00 UTC), onde o Scalper tem 2 op e −0,20 e o vigia 53,0%.
- **Dados:** velas de 15 min e 1 min da Binance (grátis) + datas dos eventos (federalreserve.gov e bls.gov, grátis).
- **Evidência:** Benigno & Rosa, NY Fed Staff Report 1052 — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1052.pdf :
  com dados intradiários, o BTC é "ortogonal" às notícias macro, **exceto o CPI**. Kyriazis, Ofeidis, Palaiokrassas & Tassiulas, "Monetary
  Policy, Digital Assets, and DeFi Activity", arXiv 2302.10252 — https://arxiv.org/abs/2302.10252 : o comunicado do FOMC "afeta fortemente a
  volatilidade" dos ativos digitais, a ata menos, e o efeito "se fortaleceu depois de dezembro de 2021". A razão numérica de volatilidade:
  não sei (o resumo não dá; um resumo de busca fala em "pelo menos duas vezes maior", não conferi no texto). Nenhuma das duas mede lucro de
  robô: a evidência é de volatilidade, não de direção.
- **Teste:** todas as apostas do v4 conferidas ao vivo + histórico do laboratório (v4 desde mai/2025), simulando a rota do Scalper (R6,
  stop 1,5%, realizar +0,125). Custo 0,12% ida e volta. Compara apostas dentro × fora da janela em 3 blocos de tempo. Passa se as apostas
  dentro da janela têm média líquida < 0 nos 3 blocos e < a de fora com z ≤ −2 (erro-padrão por evento, não por aposta). 1 tentativa.
  Risco honesto: são ~8 FOMC e 12 CPI por ano → poucas dezenas de eventos; se der < 20 eventos, o veredito é "não sei".

### Ideia 2 — Confirmação do fluxo agressor na vela do sinal

- **Regra:** f = volume comprador tomador ÷ volume total da vela de 15 min que gerou a aposta (campo "taker buy base volume" das velas da
  Binance). Compra só se f ≥ 0,50; venda só se f ≤ 0,50. 1 tentativa (limiar 0,50 sem ajuste).
- **Por quê no Scalper:** 42 das 70 operações saem no fim da vela sem ter andado (−1,68). Se o v4 aposta contra o fluxo agressor da própria
  vela, é provável que o preço não acompanhe na vela seguinte. O v4 já usa volume relativo, mas não o lado do volume (16 medidas,
  `lab/minerador.py`).
- **Dados:** velas de 15 min da Binance (grátis, histórico longo; o campo já vem em cada vela).
- **Evidência (fraca, por isso 1 tentativa):** Bieganowski & Ślepaczuk, "Explainable Patterns in Cryptocurrency Microstructure", arXiv
  2602.00776 — https://arxiv.org/html/2602.00776v1 : Binance Futures, BTC, LTC, ETC, ENJ, ROSE, 01/01/2022–12/10/2025, 1 s; o desequilíbrio
  de fluxo tem efeito "em grande parte monótono" no retorno. Mas o horizonte é de **3 segundos**, a taxa de tomador usada e o resultado
  líquido não aparecem no texto (não sei); IR* do tomador (bruto) 0,25 no BTC a 8,97 no ETC. Contra: estudo de opções de BTC (arXiv
  2109.02776) acha desequilíbrio horário "sem poder preditivo" para o intervalo seguinte. A H56 (1 s) mostrou que o sinal quase empata
  antes do custo. Não há prova no nosso horizonte: o teste decide.
- **Teste:** apostas do v4 conferidas ao vivo (11/11 até a data) em 3 blocos de tempo, rota do Scalper, custo 0,12%. Passa se as apostas
  mantidas têm média líquida maior que todas as apostas nos 3 blocos E as excluídas têm média < 0 com z ≤ −2 (erro por blocos de 12 h).
  1 tentativa.

### O que aprendi hoje sobre o mercado cripto

O mercado agora é dirigido por juros, não por cripto: a CoinDesk (17/11, citando a Wintermute —
https://www.coindesk.com/markets/2026/11/17/bitcoin-could-slide-into-the-usd50-000s-as-fed-rate-hike-bets-build-wintermute-says ) dá
"cerca de 92%" de chance de **alta** de juros em dezembro depois de inflação de outubro acima do esperado, título de 10 anos acima de 5%,
BTC −15% em novembro e abaixo da média de 200 semanas (~68.000); ETFs à vista com ~US$ 1,9 bi de saída líquida em 2026 (contra US$ 21 bi de
entrada em 2025); a maior posição em opções na Deribit é a venda de 60.000 (> US$ 900 mi de nocional). Níveis citados: 62.000 (mínima de
sábado), 60.000, "pressão para os 50 mil"; a Wintermute muda de ideia se o BTC fechar um dia UTC acima de 68.000 com entrada nos ETFs. Funding
e liquidações de hoje: o artigo não dá. Sobre cascatas: o preprint arXiv 2607.27070 (7 cascatas do BTCUSDT na Binance, mai/2022–out/2025)
achou o sinal de alerta pelo preço significativo em só 4 de 39 configurações e queda média de −24,6% nos juros em aberto durante a cascata
(via https://cryptoslate.com/new-bitcoin-study-shows-the-strongest-recurring-liquidation-warning-signs-cannot-warn-of-an-individual-crash/ ;
não li o PDF). Depois das maiores liquidações, o BTC rendeu 0,78% em 30 dias contra 5,9% típico, mediana −1,1% (K33 via The Block,
https://www.theblock.co/post/372115/whats-next-after-cryptos-fourth-largest-long-liquidation-event-of-2025 ) — horizonte de 30 dias, não serve
para os nossos robôs de horas. Para hoje, o que importa ao robô: semana com ata do FOMC e o mercado sensível a cada número de inflação,
o que pesa na Ideia 1; e o retrato da mesa mostra 68% das moedas subindo em 24 h com só 24% subindo na última hora — repique perdendo força.

## 2026-11-16

**Estado de hoje** (`dados/torneio.json`, `dados/vigia_v4.json`, `dados/LICOES.md`, 10:06 UTC):

| | |
|---|---|
| Campeão do torneio | **Rápido nuvem** (61 op, fator de lucro 0,93, soma −0,37, carteira 9,72; rota R6 da H52, stop 2%) |
| Melhor fator de lucro com ≥ 30 op | Scalper B 1,06 (144 op, soma +0,36) — único > 1 |
| Onde o Rápido perde | stops de segurança: −2% (6 op, −3,18) e −1% (4 op, −1,12) = −4,30 em 10 op; compras 37 op −0,82 (vendas +0,45); 06–11 UTC 12 op −0,66 |
| Segmento fraco do vigia | 18–24 h UTC acerto 46,5% (4.690 apostas; julgado só na H46, 16–22/11) e compras 50,0% (8.011) contra vendas 58,3% |

**Mercado hoje** (`dados/mercado_agora.json`): BTC 64.328, −1,57% em 24 h; 22,0% das 118 moedas subindo em 24 h (regime de baixa pela H44);
medo e ganância 10; funding médio das 20 maiores da Hyperliquid −6,5%/ano.

**Já testado e fora desta lista:** alvo por ATR (H40), saídas curtas de scalper (H24), stop móvel arma 0,5%/guarda 70% (H49, ao vivo),
rotas de saída R0–R7 (H52), humor do mercado (H42), funding extremo (H17), 18–24 h UTC (H46, em teste prospectivo), fluxo do quarto de hora,
tamanho por volatilidade e alarme de cascata (ideias de 15/11, ainda não pré-registradas).

### Ideia 1 — Stop de segurança e stop móvel em múltiplos do ATR, no lugar do stop fixo de 2%

- **Por quê no Rápido:** 10 saídas no stop de segurança custaram −4,30, mais que o resultado total do robô (−0,37). Um stop fixo em % é largo
  demais em moeda calma e curto demais em moeda volátil (as 140 moedas têm volatilidades muito diferentes). A H40 testou o **alvo** por ATR,
  não o stop.
- **Regra:** ATR14 nas velas de 15 min da moeda no momento da entrada. Stop inicial = entrada ∓ α × ATR14. Stop móvel: depois que o lucro
  aberto passa de 1 × ATR14, a saída fica em (melhor preço visto ∓ α × ATR14), só sobe. Mantém o resto da R6 (a favor do regime de 24 h,
  máximo 24 h). Teto de segurança: α × ATR14 nunca maior que 4% (limite de liquidação a 10× está perto de 10%). 3 tentativas: α = 2,0 / 2,5 / 3,0.
- **Dados:** velas de 15 min da Binance (grátis), as apostas do v4 já conferidas (`dados/cerebro_v4.json`).
- **Evidência:** Nguyen (2026), "Systematic Trend-Following with Adaptive Portfolio Construction", arXiv 2602.11708 —
  https://arxiv.org/html/2602.11708v1 . 150+ pares de cripto, fora da amostra jan/2022–dez/2024 (a figura 1 diz até out/2025: conflito no
  próprio texto), custo 4 pb por operação + derrapagem + funding. Com o stop móvel por ATR: Sharpe 2,41, maior queda −12,7%; **sem** o stop
  móvel: Sharpe 1,68, maior queda −22,4%. Faixa boa de α: 2,0 a 3,5 (centro 2,5). Período do ATR e prazo das operações: não sei (não está no
  texto). É preprint, não revisado, e o custo dele (4 pb) é um terço do nosso (12 pb ida e volta).
- **Teste:** apostas do v4 a favor do regime de 24 h, de 11/11 até a data do teste, divididas em 3 blocos de tempo; custo 0,12% ida e volta;
  stop conta primeiro se stop e saída cabem na mesma vela; erro-padrão por blocos de 12 h (a H52 mostrou que por vela superestima o z).
  Passa: média líquida > a da R6 atual nos 3 blocos E soma das perdas no stop menor, z ≥ 2,24 (Bonferroni, 3 tentativas). 3 tentativas.

### Ideia 2 — Filtro de compra: juros em aberto subindo com prêmio do perpétuo caindo = não comprar

- **Por quê no Rápido:** as compras dele perdem (−0,82 em 37 op) e o vigia mostra compras do v4 a 50,0% contra 58,3% nas vendas. Cuidado da
  H46: lado e queda do mercado estão misturados; por isso a regra não é "não comprar", e sim um estado de alavancagem medido por moeda.
- **Regra:** para cada moeda, ΔOI_24h = variação % dos juros em aberto em 24 h; Δprêmio_24h = variação do índice de prêmio (perpétuo − índice)
  em 24 h. Se ΔOI_24h > 0 E Δprêmio_24h < 0 → o Rápido não abre **compra** nessa moeda na vela. Vendas não mudam. 1 tentativa (sem limiar a
  ajustar além do sinal).
- **Dados:** Binance `openInterestHist` (grátis, mas só ~30 dias de histórico; tem de ser gravado daqui para a frente) e velas do índice de
  prêmio `premiumIndexKlines` (grátis, histórico longo).
- **Evidência:** K33 Research (2023), "Paying attention to CME traders can pay off" — https://k33.com/research/articles/paying-attention-to-cme-traders-can-pay-off .
  No dia seguinte a juros em aberto crescendo com base caindo, o BTC rendeu em média "−0,54%" (mediana "−0,31%"); com juros em aberto caindo,
  retorno "quase plano". Dados da CME, horizonte diário, só BTC, sem custo e sem teste de significância informado: é evidência fraca. Número de
  casos: não sei. Por isso o teste é no nosso dado, não na palavra da fonte.
- **Teste:** compras do v4 dos últimos 30 dias (3 blocos de 10 dias) + prospectivo de 17/11 a 30/11. Custo 0,12% ida e volta. Passa: as
  compras bloqueadas têm média líquida < 0 com z ≤ −2 (erro por blocos de 12 h) e as compras mantidas têm média ≥ a de todas as compras, nos
  3 blocos. 1 tentativa.

**Sem evidência sólida hoje (não virou ideia):** retornos em torno do horário do funding (00/08/16 UTC). Hansen, Kim & Kimbrough (Journal of
Financial Econometrics, 2024; arXiv 2109.12142) acham padrões de **volatilidade e volume** por hora e ligam ao funding, mas não de direção;
um estudo na Huobi (AFA) acha spread em U no ciclo de 8 h. Retorno com sinal: não achei estudo. Cascata de liquidação: o preprint de 7 cascatas
(já anotado em 15/11) diz que nenhum sinal avisou todas.

### O que aprendi hoje sobre o mercado cripto

O mercado está em liquidação de alavancagem comprada puxada por saída de ETF. Em 3–4/11/2026 o BTC perdeu US$ 76.000 pela primeira vez desde
meados de setembro, com cerca de US$ 366 milhões liquidados, ~70% de compradores, depois de US$ 398,6 milhões de saída líquida dos ETFs à vista
em 2/11 (IBIT −US$ 405,3 milhões) e queda de 1,1% do Nasdaq (Crypto Briefing, 04/11/2026: https://cryptobriefing.com/bitcoin-below-76000-liquidations/ ).
Hoje o BTC está em 64.328 (−15% desde então, pelo `mercado_agora.json`), a CoinDesk fala em "sexta perda semanal" com ações de tecnologia e
metais caindo, e a maior aposta em opções é "queda abaixo de US$ 60.000" (títulos de 16/11 em `mercado_agora.json`; o valor em aberto: não sei).
Na semana: ata do FOMC e balanço da Nvidia (CoinDesk, "Crypto Week Ahead", 16/11): cripto anda junto com ações de tecnologia, então esses dois
eventos são horários de risco. Funding médio negativo (−6,5%/ano) com medo em 10 diz que a maioria já está vendida: numa cascata, a próxima
pode ser de vendidos para cima (lado da cascata = lado lotado; explicação de mercado, sem número). Sobre o relógio: volatilidade e volume em
cripto têm padrão por hora, dia da semana e dentro da hora, ficando mais fortes com os anos e ligados a algoritmos e ao funding (Hansen, Kim &
Kimbrough, https://arxiv.org/abs/2109.12142 ); isso explica por que um stop fixo em % pega mais em certos horários, mas não diz o lado.

## 2026-11-15

**Mercado hoje** (`dados/mercado_agora.json`, 19:33 UTC): BTC 64.975, −0,91% em 24 h, +0,53% em 4 h; 42,9% das 140 moedas subindo em 24 h
(regime neutro pela H44); volume de 4 h do BTC a 0,52× a média. Não achei notícia datada de hoje que explique o movimento: não sei a causa.

**Já testado e fora desta lista:** primeira meia hora → última (H34), funding extremo (H17), momentum de 7 dias/MM20/Tartaruga (H35),
tendência de 4 h com stop móvel (H39), humor do mercado (H42), reversão de 15 min (H26, só a família sem volume pagou).

### Ideia 1 — Fluxo agressor na virada do quarto de hora prevê 4 a 12 h

- **Evidência:** Kim & Hansen (2026), "The Quarter-Hour Effect", arXiv 2607.09426 — https://arxiv.org/html/2607.09426v2 .
  6 perpétuos USDT da Binance (BTC, ETH, XRP, SOL, DOGE, ADA), jan/2021–out/2024; fora da amostra 2021-07-01 a 2024-10-31.
  O desequilíbrio de ordens nos primeiros 10 s dos minutos :00/:15/:30/:45 prevê o retorno de 4 a 12 h: significativo a 95% em 4 de 6
  contratos em todos os horizontes de 4 a 12 h. Efeito interquartil: "cinco a seis pontos-base" (componente de fluxo defasado) e 9,8 e 16,9 pb
  (componente público) em 8 h e 12 h. Os próprios autores dizem que "o componente previsível é pequeno diante do custo" e **não testam
  estratégia líquida**. Risco claro: 16,9 pb no melhor caso mal passa os 12 pb de ida e volta.
- **Regra:** OI_q = (compra agressora − venda agressora) ÷ volume no 1º minuto de cada quarto de hora (aproximação de 1 min, porque as velas
  de 1 min da Binance trazem o volume comprador agressor; o artigo usa 10 s — com aggTrades de data.binance.vision dá para usar 10 s).
  S = média de OI_q nos 4 quartos de hora da última hora. No fechamento de cada hora: compra se S ≥ quantil 90% do treino, vende se
  S ≤ quantil 10%; segura 8 h (braço A) ou 12 h (braço B). Stop de 1% como na mesa (braço só de leitura).
- **Dados:** velas de 1 min (campo taker buy volume) ou aggTrades, grátis, data.binance.vision. Horizonte: 8–12 h.
- **Teste:** 6 moedas do artigo + 33 do laboratório, 2025-05 a 2026-11 (período posterior ao do artigo = réplica fora da amostra).
  Quantis só no 1º bloco; 3 blocos de tempo; custo 0,12% ida e volta; t agrupado por hora de entrada. Passa: líquido > 0, t ≥ 2,
  > 0 em 2 dos 3 blocos, ≥ 300 operações. 2 tentativas.

### Ideia 2 — Tamanho da posição pela volatilidade (gestão de volatilidade)

- **Evidência:** Grobys, Kolari, Sandretto, Shahzad & Äijö (2025), "Cryptocurrency momentum has (not) its moments", Financial Markets and
  Portfolio Management, doi 10.1007/s11408-025-00474-9 (resumo em https://osuva.uwasa.fi/handle/10024/20018). Momentum semanal em
  moedas grandes: retorno bruto médio "0,90% por semana", não significativo; as versões com gestão de risco elevam o retorno médio semanal
  "em mais de 200%" e têm intercepto significativo a 5%; **não reduzem o risco de cauda** (expoentes de lei de potência iguais).
  Base em ações: Barroso & Santa-Clara (2015), Sharpe "quase dobra"; Moreira & Muir (Journal of Finance). Sharpe em cripto: não sei
  (o texto completo está atrás de login).
- **Regra:** tamanho_i = US$ 25 × min(2; σ_alvo ÷ σ_i), com σ_i = desvio-padrão dos retornos de 1 h da moeda nas últimas 24 h e σ_alvo =
  mediana de σ entre as 140 moedas no treino. Não muda o lado nem a entrada de nenhum robô; só o tamanho. Stop de 1% e piso de US$ 5 iguais.
- **Dados:** velas de 1 h da Binance (grátis). Horizonte: o de cada robô (minutos a horas).
- **Teste:** reaplicar às operações já registradas do Caçador, Rápido nuvem e Minerador (ramo `estado`) e à reserva da H26 (família "movimento
  forte sem volume"): mesma lista de entradas, tamanho fixo × tamanho por volatilidade. 3 blocos de tempo, custo 0,12% sobre o nocional.
  Passa: resultado líquido > o do tamanho fixo em 2 dos 3 blocos E maior queda da carteira menor. 1 tentativa por robô, contadas.

### Ideia 3 — Variância do fluxo agressor como alarme de cascata de liquidação (filtro de risco)

- **Evidência:** Garcia Seuma (2026), arXiv 2607.27070 — https://arxiv.org/abs/2607.27070 . 7 grandes cascatas de liquidação do BTC
  (2022–2025, incluindo 10/10/2025). A **variância do fluxo agressor** foi a única regularidade antes de todas as cascatas com dados; passa
  num placebo de 300 inícios (p combinado de Fisher ≈ 5e-6). O autor avisa: é "precursor de população, não alarme por evento".
  Antecedência e taxa de acerto: não sei (não reportadas no resumo). Amostra pequena (7 eventos).
- **Regra:** f_5m = (2 × compra agressora − volume) ÷ volume do BTC em 5 min; V = variância de f_5m nas últimas 6 h; alarme quando
  V ≥ quantil 95% do treino E tau de Kendall de V nas últimas 6 h > 0. Com alarme: nenhuma entrada nova por 2 h (posições abertas seguem).
- **Dados:** velas de 1 min do BTCUSDT perpétuo com volume agressor (grátis). Horizonte: 2 h.
- **Teste:** aplicar o filtro às entradas do Caçador/Rápido nuvem já registradas e às da regra do Minerador em 2025-05 a 2026-11.
  Passa: menos saídas no stop de 1% e resultado líquido (0,12%) ≥ sem filtro em 2 dos 3 blocos, cortando ≤ 15% das entradas. 1 tentativa.

**Sem evidência sólida (não virou ideia):** juros em aberto × preço — só achei um "odds ratio 1,48" citado de segunda mão, sem artigo
original; e Giagkiozis & Said (Ledger, 2024, https://arxiv.org/abs/2310.14973) mostram que bolsas grandes publicam juros em aberto
errados. A Binance só serve ~30 dias de histórico de juros em aberto pela API; teria de ser gravado a partir de agora.
