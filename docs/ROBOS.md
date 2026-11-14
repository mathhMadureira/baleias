# Remapeamento dos robôs — missão, cérebro, onde erraram, o que muda

14/11/2026, 12:00 (Brasília). Números das operações fechadas até agora (arquivos `dados/robo_*.json` locais e do ramo `estado`).
Pergunta do dono: "os robôs têm cérebro mesmo? Se têm, precisam de ajuda, como uma criança aprendendo a andar de bicicleta."

## 1. Quem tem cérebro e quem só obedece

| peça | aprende sozinha? | como |
|---|---|---|
| **Cérebro v4** (LightGBM) | **não** ao vivo | treinado uma vez (11/11) em 18 meses de velas; é o cérebro de todos os robôs do perpétuo. "Ensinar" = retreinar com dados novos e julgar (H41, em andamento) |
| Cérebros v1, v2, v3 (nuvem, pesquisa) | sim | sinapses que ganham/perdem peso a cada aposta; sinapses novas nascem em observação e só votam se provarem (≥ 150 previsões). Em 12/11 entraram 12 fórmulas dos grandes traders (H33) |
| Cérebros de 1 min por moeda (Rápido local) | sim | mesma mecânica; autoanálise mostrou acerto de 23–27% onde previam 54–56%: deixaram de decidir entradas (só o v4 decide) |
| Robôs (Rápido nuvem, Caçador, Testnet, Scalper, Minerador) | não | executam regras fixas de entrada/saída sobre o que o cérebro diz |

Ou seja: **os robôs não têm cérebro próprio; o cérebro é o v4, e ele hoje não aprende enquanto opera.** Os que aprendem (v1–v3) são pesquisa.

## 2. Onde cada um errou (operações fechadas)

| robô | ops | ganhos | total | o que os números mostram |
|---|---|---|---|---|
| Rápido 1 min (local, zerado hoje) | 160 | 25% | −5,19 | 34 stops de 4N em 1 min = −4,46; 126 das 160 ops no horário 18–23 UTC = −5,53 (as outras 34 deram +0,34); compras −3,62, vendas −1,57 |
| v4 Testnet (nuvem, zerado hoje) | 58 | 24% | −5,06 | BTC preso 17 h com a máquina dormindo = −1,68; direção certa só em 31%; 18–23 UTC = −3,69; entradas que falharam como maker e foram a mercado = −2,83 em 8 ops |
| Rápido nuvem (v4, todas as apostas) | 38 | 29% | −1,13 | direção certa em 42% (antes do custo); as apostas de confiança ≥ 0,12 acertaram só 8/20 ao vivo (o laboratório dizia 65%); compras −0,97, vendas −0,16; 27 das 38 ops em 18–23 UTC = −0,84 |
| Caçador (v4, 2 compras + 2 vendas) | 7 | 29% | −0,08 | poucas ops (ficou 12 h travado, ver 3); direção certa em 4/7 |
| Minerador (H28) | 97 | 48% | −1,18 | vendas depois de alta sem volume: +1,01 em 34 ops; compras depois de queda: −2,19 em 63 ops; 2 stops de 2% = −1,06; 00–05 UTC = −1,34 |
| Scalper (local) | 416 | 36% | −1,70 | "lucro realizado +0,5%" deu +1,64 em 54 ops; "fim da vela" deu −2,06 em 291 ops; 284 das 400 ops em 18–23 UTC |
| Funding (carry) | 7 | — | 0,00 | recebe funding; quase não mexe |

Três padrões se repetem em robôs diferentes:

1. **Horário 18–23 UTC (15h–21h de Brasília)** concentra as perdas de todos. Em parte porque foi quando mais operaram (máquina acordada, dono
   olhando); em parte porque o laboratório já apontava essa faixa como a pior do v4 (53,0% contra 54,2% nas outras). Ao vivo foi muito pior
   que isso. Dois dias não bastam para concluir; fica anotado e medido.
2. **Comprar perdeu mais que vender** em todos (Rápido 1 min, Rápido nuvem, Minerador, Scalper). O mercado destes dias caiu; o v4 aposta nos
   dois lados e não tem um "humor do mercado" para pesar o lado (o v3 tem).
3. **Perdas de infraestrutura, não de previsão:** BTC preso 17 h (máquina dormiu), 32 ordens órfãs (robô caía e remandava), Rápido nuvem e
   Caçador travados 12 h por posições em moedas que saíram do universo (SOXSB, RWUSD) e por 15 rodadas com gravação rejeitada na nuvem.
   Tudo isso foi consertado em 13–14/11. Essas perdas não dizem nada sobre o cérebro.

## 3. O que muda agora (feito em 14/11)

- Carteiras do Rápido 1 min e do v4 Testnet **zeradas em US$ 10** (históricos guardados). Os dois voltaram a operar.
- Rápido local: as entradas pela varredura dos cérebros de 1 min foram desligadas (ele entrou duas vezes em ZEC às 11:45 por elas e perdeu
  1,08 em dois minutos). Só o v4 decide.
- Rápido nuvem e Caçador: posição em moeda que saiu do universo agora busca as velas dela e fecha; não trava mais a margem.
- Nuvem: cada fluxo grava só os próprios arquivos por cima do estado mais novo; rodadas a cada 20 min.

## 4. Notícias, calor do mercado e conhecimento novo (resposta direta)

- **Notícias do dia:** os robôs **não** leem. Foi testado (H9: tom das notícias do GDELT, grátis, 2025) e não previu o BTC: reprovado. O
  módulo existe (`baleias/noticias.py`) e alimenta só o monitor antigo. Ligar notícias no cérebro sem evidência seria inventar.
- **Calor do mercado:** parcialmente. O v3 pesa o "humor" (quanto o mercado subiu); o v4 vê o retorno do Bitcoin e a hora; o gravador salva
  funding, juros em aberto e livro a cada 5 min desde 12/11 (ainda sem meses de histórico para treinar). Amplitude do mercado (quantas
  moedas sobem) existe no painel, mas nenhum cérebro usa. É o item 3 da H36 (medidas novas), pré-registrado e ainda não rodado.
- **Buscar conhecimento na internet:** os robôs não fazem; **eu faço por eles**: quatro relatórios de pesquisa (previsibilidade em cripto,
  maiores traders, fórmulas práticas, mineração), e as 12 fórmulas dos grandes traders já estão dentro dos cérebros em observação (H33).
  O que a pesquisa encontrou de sólido em cripto (revisado por pares) está em `docs/RELATORIO_CEREBRO_V4.md` e nos relatórios.
- **Corrigir os trades perdedores:** o que já existe é a autoanálise (geladeira de 24 h para a moeda em que mais perde; exigir mais certeza
  no lado em que mais erra) nos cérebros que aprendem. Para o v4, "corrigir por moeda" foi testado (H36) e **não se repete** no tempo
  (PEPE e CYBER eram as melhores no teste e as piores ao vivo): corrigir pelo último erro é perseguir ruído. A correção honesta é o
  **retreino com juiz (H41)**: o v4.1 aprende com os dados até hoje e só substitui o v4 se acertar mais nos últimos 30 dias, em 2 de 3 blocos.

## 5. Missão de cada robô, daqui para a frente

| robô | missão | critério de aprovação (mesa) |
|---|---|---|
| Rápido nuvem | operar todas as apostas do v4, as mais confiantes primeiro, 24 h (teste "agressivo" da H37) | ≥ 30 ops, carteira ≥ 11, sem passar de US$ 5 |
| Caçador | sempre posicionado: 2 compras e 2 vendas por vela, as maiores confianças do v4 (H37) | idem |
| v4 Testnet | provar na conta de teste da Binance, com ordens reais, o que as simulações mostram | idem |
| Minerador | a única regra de minutos que pagou custo no laboratório; continua como está | idem |
| Scalper / Rápido 1 min (locais) | seguem o v4 enquanto a máquina está acordada; servem de comparação | idem |
| Cérebros v1–v3 | pesquisa: provar ao vivo as sinapses dos grandes traders (H33) | promoção por sinapse |
| v4 → v4.1 | aprender com os dados novos (H41, retreino mensal com juiz) | acerto maior no holdout em 2 de 3 blocos |
