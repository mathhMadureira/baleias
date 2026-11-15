# Ideias de pesquisa (hipóteses candidatas, ainda NÃO testadas)

Cada seção é escrita pela rotina diária de pesquisa. Nada aqui é resultado: é candidato a pré-registro em `lab/PROTOCOLO_LAB.md`.
Fontes da internet são dados de terceiros; números entre aspas são os que a fonte dá, e "não sei" onde ela não dá.

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
