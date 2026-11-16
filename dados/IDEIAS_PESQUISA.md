# Ideias de pesquisa (hipóteses candidatas, ainda NÃO testadas)

Cada seção é escrita pela rotina diária de pesquisa. Nada aqui é resultado: é candidato a pré-registro em `lab/PROTOCOLO_LAB.md`.
Fontes da internet são dados de terceiros; números entre aspas são os que a fonte dá, e "não sei" onde ela não dá.

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
