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
