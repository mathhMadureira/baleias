# Relatório: o Cérebro v4, o robô de mais lucro — método, por que se destacou, limites e plano de melhoria

Data: 13/11/2026. Pedido do dono: "troca o cérebro de todos pelo do robô com mais lucro... vamos estudar qual método, conceitos,
estratégia o robô mais lucrativo usou... fazer um backup dele e começar a estudar uma maneira de aperfeiçoá-lo."
Todos os números abaixo saem de arquivos do projeto (citados). Nada foi inventado.

## 1. O que ele é

O Cérebro v4 é um modelo **LightGBM** (árvores de decisão em gradient boosting, 92 árvores) treinado uma vez só, em 11/11/2026,
com velas de 15 minutos de 33 moedas da Binance, de maio/2025 a novembro/2026 (hipótese H30 do laboratório). Ele responde a uma
pergunta por moeda a cada vela fechada: **a próxima vela de 15 minutos fecha acima ou abaixo?** e devolve uma probabilidade p.

- Entradas (16 medidas, `lab/minerador.py`, NOMES): retornos normalizados pela volatilidade de 1, 4, 16 e 96 velas (`r1 r4 r16 r96`);
  distância normalizada às médias de 20 e 200 velas (`z20 z200`); amplitude da vela em relação à média de 20 (`amplitude`); corpo da
  vela (`corpo`); volume relativo à média de 96 velas e ao mesmo horário dos 20 dias anteriores (`vol96 vol_hora`); RSI de 14
  (`rsi14`); distância à máxima e à mínima de 96 velas (`d_max96 d_min96`); o retorno de 4 velas do Bitcoin e a força da moeda contra
  o Bitcoin (`btc_r4 forca_btc`); e a **hora UTC** (categórica).
- Parâmetros fixados antes do teste (`lab/lgbm.py`): 63 folhas, taxa 0,03, mínimo de 2.000 amostras por folha, 80% de amostragem,
  parada antecipada pela validação.
- Aposta: p ≥ 0,53 compra, p ≤ 0,47 vende (|p − 0,5| ≥ 0,03). Contrato **binário** simulado a 0,51 por 1, 2% da conta por aposta,
  no máximo 6% da conta por vela (`executor/cerebro_v4_nuvem.py`, `baleias/mesa.py` EXPOSICAO_VELA).
- O modelo **não aprende ao vivo**: é o mesmo arquivo do teste (`lab/modelos/lgbm_v4.txt`), para que o placar julgue exatamente o
  que foi testado.

## 2. Como ele pensa (o que as árvores usam)

Importância por ganho no treino (`dados/lab/lgbm_resultado.json`): **hora** 57.633, **btc_r4** 52.868, **corpo** 28.581, **r1** 27.176,
z20 10.221, z200 7.723, r4 6.864, r96 5.784, amplitude 5.744, forca_btc 5.560, r16 5.287, rsi14 4.935, d_max96 4.801, d_min96 4.056,
vol_hora 3.617, vol96 2.836.

Lido em português: o v4 decide sobretudo por **(a)** a hora do dia, **(b)** o que o Bitcoin fez na última hora, **(c)** o formato da
última vela (corpo) e **(d)** o último retorno. Volume quase não pesa. Ou seja, ele é um modelo de **microestrutura e sazonalidade
intradiária**, não de tendência longa.

## 3. Por que ele se destacou

| cérebro | como aprende | carteira em 13/11 16:10 | nas 24 h do desafio |
|---|---|---|---|
| v4 (LightGBM) | treinado uma vez em 18 meses, fixo | **16,57** | 12,11 |
| v2 | sinapses + rede, online, "cérebro humano" | 10,34 | 12,84 |
| v1 | sinapses + rede, online | 8,09 | 12,86 |
| v3 | v1 + humor do mercado | 7,91 | 12,24 |
| cérebros de 1 min por moeda (Rápido) | online, 1 min | 4,91 | 7,47 |

Quatro razões, todas verificáveis:

1. **Treino longo e juiz duro antes de ir ao vivo.** H30: 175.921 apostas de teste fora da amostra, acerto 53,9%, t = 17,3, positivo
   nos 3 blocos (55,9 / 52,5 / 53,2). Os cérebros online (v1–v3) nunca passaram por um teste desse tamanho; aprendem com poucas
   centenas de apostas e ficam reféns do período recente (o cérebro de 1 min aprendeu "tudo cai" em 16 h de queda).
2. **Modelo fixo = sem deriva.** Ao vivo, de 11/11 18:45 a 13/11 18:30 UTC: **2.399 apostas, 53,8% de acerto (IC 95%: 51,8–55,8%)**,
   igual ao laboratório. Compra 53,6%, venda 54,0%. Por bloco de tempo: 48,9% / 60,1% / 52,4%. Por dia UTC: 11/11 36% (319 apostas,
   as primeiras horas), 12/11 59% (1.006), 13/11 55% (1.074).
3. **Muitas apostas pequenas, em muitas moedas.** 13,9 apostas por vela em média, 2% da conta cada, teto de 6% por vela. A lei dos
   grandes números trabalha a favor: 54% em 2.400 apostas vira lucro estável; 54% em 20 apostas é sorte.
4. **O contrato certo para a vantagem que ele tem.** A vantagem do v4 é de **direção**, não de tamanho do movimento. O contrato binário
   paga quase 1 para 1 pela direção, então 54% basta. No perpétuo, o mesmo acerto não paga a taxa (seção 5).

Resultado líquido por aposta ao vivo: +0,110% da conta (soma +2,648 em fração da conta, aposta de 2%).

## 4. Onde ele acerta mais (estudo H36, parte 1, fora da amostra, sem retreinar)

`lab/v4_estudo.py` → `dados/lab/v4_estudo.json`, 170.519 apostas de teste.

| confiança \|p − 0,5\| | apostas | acerto | blocos | perpétuo líquido (0,12% ida e volta) |
|---|---|---|---|---|
| 0,03–0,05 | 92.456 | 52,6% | 53,7 / 51,4 / 52,6 | −0,115%/op |
| 0,05–0,08 | 54.273 | 54,1% | 56,2 / 52,9 / 53,0 | −0,108%/op |
| 0,08–0,12 | 19.887 | 57,5% | 60,8 / 55,9 / 54,9 | −0,065%/op |
| ≥ 0,12 | 3.903 | **65,5%** | 70,9 / 60,4 / 60,3 | +0,070%/op (só o 1º bloco positivo) |

Este é o único achado robusto: **quanto mais confiante, mais acerta, nos 3 blocos.** Os outros cortes não passaram do critério
pré-registrado (≥ 2 pontos e mesma direção em 2 de 3 blocos): hora UTC 18–23 é a pior (53,0% contra 54,2–54,3%), sábado é o melhor
dia (55,4%), compra e venda empatam (53,9%), e o ranking de moedas do teste (PEPE, ONE, CYBER 60–62%) **não se repetiu ao vivo**
(PEPE e CYBER estão entre as piores ao vivo: 34/69 e 32/67).

## 5. Limites (o que ele NÃO faz)

- **Não paga o perpétuo com taxa de tomador.** H30: −0,098%/op; H31 (limiares 0,06 / 0,08 / 0,10): vantagem só no 1º bloco. H36: mesmo
  a faixa ≥ 0,12 é positiva só no 1º bloco. O movimento médio de 15 min é pequeno demais para 0,12% de custo.
- **O lucro dele é em contrato binário**, cujo mercado real (Polymarket) está bloqueado no Brasil e cobra 0,07 × p × (1 − p) por ação
  (3,5% a 0,50; ponto de equilíbrio 52,75%). A carteira de 16,57 é pesquisa, não dinheiro na sua conta.
- **Ao vivo ele oscila por dia** (36% → 59% → 55%): uma semana ruim é normal e não prova que quebrou.

## 6. O que foi feito hoje com ele

- **Backup:** `backups/cerebro_v4_2026-11-13.tar.gz` (modelo, código de treino, medidas, executor, resultados H30/H31, estado da nuvem) e
  etiqueta git `cerebro-v4-2026-11-13`. SHA-256 do modelo: `37af66ad…430412`.
- **Cérebro de todos:** Rápido 1 min e Scalper passam a seguir as apostas do v4 (`mesa.sinais_v4`). Dois robôs novos na nuvem, 24 h,
  independentes da máquina que dorme: **Rápido nuvem** (todas as apostas do v4) e **Rápido nuvem seletivo** (só |p − 0,5| ≥ 0,12),
  ambos no perpétuo simulado com as regras do Rápido (US$ 25 a 10×, stop 1%, lucro realizado +US$ 0,50, fim da vela). Hipótese H37.
  O Minerador não tem cérebro (é a regra H26) e continua. O robô do testnet da Binance já seguia o v4 (agora em todas as apostas).
- **Previsão registrada antes de ligar:** pelo laboratório, o Rápido nuvem agressivo deve perder ≈ 0,10%/op (≈ US$ 0,025 por operação
  de US$ 25) e o seletivo ficar perto de zero. Se os dois perderem, o caminho do perpétuo com o v4 é só com taxa de maker.

## 7. Como aperfeiçoar (plano, em ordem de evidência)

1. **Cortar a taxa** (o maior ganho possível, já em teste): com taxa de maker (0,04% ida e volta) a faixa 0,08–0,12 ficaria ≈ +0,015%/op
   e a ≥ 0,12 ≈ +0,15%/op. O robô do testnet mede quantas ordens maker executam de verdade (até agora: 2 de 4 entradas; as outras
   foram a mercado depois de 60 s).
2. **Apostar mais onde ele é mais confiante** (binário): tamanho proporcional à confiança, com teto. É o achado da H36. Precisa ser
   pré-registrado e testado no laboratório antes de mudar a conta do v4.
3. **Retreino mensal com a mesma receita** (H36 parte 2, walk-forward): treina até o mês M, testa no mês M+1; passa se melhorar em 2 de
   3 meses. Responde se o modelo fixo envelhece.
4. **Medidas novas que já gravamos** (H36 parte 3): funding, juros em aberto, desequilíbrio do livro (o gravador salva a cada 5 min).
   Mesmo juiz da H30; só entra se vencer o v4 atual no total e em 2 de 3 blocos.
5. **Alvo diferente para o perpétuo:** em vez de "sobe ou desce", prever "sobe mais que o custo" (|movimento| > 0,15%). É o único
   jeito de o modelo aprender a evitar as velas paradas, que são as que perdem no perpétuo.

O que **não** fazer: escolher moedas ou horas pelo resultado ao vivo (não se repete, seção 4); mexer nos parâmetros do modelo depois
de ver o placar; trocar o v4 por um cérebro online sem teste de 100 mil apostas.
