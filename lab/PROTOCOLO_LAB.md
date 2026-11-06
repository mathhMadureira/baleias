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
