# Protocolo do teste (escrito antes de ver qualquer resultado, em 2026-11-04)

Pergunta: copiar entradas de carteiras grandes da Hyperliquid dá lucro **depois dos custos**, com o atraso real de quem recebe o alerta?

## Regras fixas
- Só leitura. O sistema não tem chave nem envia ordem.
- Horizonte principal: sair 4 h depois da entrada. 1 h e 24 h são só registro.
- Custos: taxa taker 0,045% por lado (documentação oficial, nível base) mais slippage **assumido** de 0,01% por lado em BTC/ETH/SOL/HYPE e 0,05% nos demais. O slippage é suposição minha e o funding não entra na conta: os dois podem piorar o resultado real.
- Sem alavancagem no cálculo.
- O modelo só aprende com sinais já resolvidos. Toda previsão é gravada antes de o resultado existir.
- Controle: mesma moeda e mesmo instante, lado sorteado por hash. Um sinal só tem valor se ganhar do controle.

## O que conta como evidência
- Só o resultado **ao vivo** decide. O backtest usa carteiras escolhidas pelo ranking de hoje, que já contém o período testado (viés de sobrevivência): é otimista por construção e nunca libera dinheiro.
- Alertas de "entrada aprovada" só depois de 30 sinais ao vivo resolvidos e com limite inferior da previsão (média − 1 desvio) acima de zero.

## Critério para testar os US$ 10
Todos juntos, medidos ao vivo:
1. Pelo menos 100 sinais aprovados resolvidos.
2. Intervalo de 95% do resultado líquido médio dos aprovados inteiramente acima de zero.
3. Média dos aprovados acima da média do controle.
4. Resultado positivo nas duas metades do período, para não depender de uma única fase do mercado.

## Critério para desistir
Depois de 300 sinais ao vivo resolvidos, se o intervalo de 95% dos aprovados tocar zero ou houver menos de 30 aprovados: a hipótese não se sustentou. Não vale reajustar parâmetros e continuar contando como o mesmo teste. Mudança de regra zera a contagem e é registrada abaixo.

Estes números são escolhas de desenho para evitar autoengano, não verdades de mercado.

## Mudanças de regra
- 2026-11-05, antes de qualquer sinal resolvido (contagem continua em zero): a máquina ficou parada ~18 h e, ao voltar, operações antigas viraram 3 sinais com 3 a 12 h de atraso. Regra nova: grupo detectado mais de 10 min depois da última operação da carteira é descartado e contado como perdido. Os 3 sinais foram marcados como `descartado_atraso` e não entram em nenhuma conta.
- 2026-11-05, ainda com zero sinais resolvidos (contagem segue do zero): o universo passa a incluir ações e índices americanos do mercado xyz da Hyperliquid. Custo dessas: taxa **suposta** no dobro da base (0,09% por lado, valor não conferido) mais 0,05% de slippage. Nova característica `noticia` (manchete do ativo nas 6 h anteriores, Google News); falha de rede vira `desconhecido`, nunca `nao`. Rastro: depois de um alerta, o sistema avisa quando a carteira aumenta ou sai; isso não muda a regra de saída do teste (4 h).

# Teste 2: compras de diretores (SEC, formulário 4), escrito em 2026-11-05 antes de ver resultado

Pergunta: comprar a ação na abertura do dia útil seguinte à publicação de uma compra de diretor ganha do S&P 500 em ~1 mês, depois do custo?

- Entram só compras no mercado aberto (código P, aquisição), de CEO, CFO, presidente, executivo, conselheiro ou dono de 10%, com valor somado ≥ US$ 50 mil, preço ≥ US$ 1, sem plano automático 10b5-1.
- Entrada: abertura do primeiro dia útil depois da data de publicação. Saída: fechamento do 21º dia útil. O de 5 dias é só registro.
- Custo **suposto**: 0,2% por lado, sem câmbio nem IOF de quem compra do Brasil. Controle: SPY no mesmo período.
- Preços: Yahoo Finance, fonte não oficial.
- Alvo do aprendizado: excesso sobre o SPY depois do custo. Alerta só depois de 30 compras resolvidas ao vivo e limite inferior acima de zero.
- O backtest usa os arquivos trimestrais da SEC e só é indicativo: estas regras foram definidas antes dele, mas preços não oficiais e ações deslistadas (sem preço) podem enviesar.
- Mesmo critério de dinheiro e de desistência do teste 1, contado à parte. Cada resultado leva ~1 mês: é um teste lento.
