# Baleias — documentação do projeto como ele está agora

Escrita em 13/11/2026 às 18:00 (horário de Brasília), a pedido do dono, para ser lida de ponta a ponta. Tudo aqui vem dos arquivos do
projeto e do que está rodando neste momento. Onde há número, há arquivo de origem. Onde não há evidência, está escrito "não sei".

---

## 1. O que o projeto é

Um sistema de robôs de day trade em criptomoedas, feito para o dono (ex-TI, sem capital no momento) com uma meta: **um agente de
inteligência artificial que opere sozinho, com lucro, na carteira dele na Binance**, em prazos curtos (minutos a horas), comprando e
vendendo (perpétuos). Regras do dono que governam tudo:

- só números reais, nunca inventados; se não se sabe, diz-se "não sei";
- só soluções grátis (dados públicos da Binance, GitHub Actions, Python puro);
- nada de operar sem passar pela mesa (carteiras de teste de US$ 10);
- os robôs devem caçar a própria entrada, na compra e na venda, em **todas as moedas da Binance**, e não ficar esperando;
- sem trava de perda diária (decisão de 12/11); o único limite é o piso de US$ 5 por carteira;
- a máquina local dorme e **não vai deixar de dormir**: tudo que importa tem de rodar na nuvem.

O repositório é público: https://github.com/mathhMadureira/baleias (ramo `master` = código; ramo `estado` = o estado dos robôs da nuvem,
atualizado a cada 15 min). Público porque assim os minutos do GitHub Actions são ilimitados e grátis; em repositório privado a nuvem
pararia em menos de um dia. Não há senha nem chave no repositório: as chaves ficam no `.env` da máquina (não sobe) e no cofre de
segredos do GitHub.

---

## 2. Como as peças se encaixam

```
                 ┌──────────────── NUVEM (GitHub Actions, 24 h) ────────────────┐
 Binance  ─────► │ cérebro.yml (a cada 15 min, rodada viva ~5h40):                │
 (velas 15 min,  │   cerebro_nuvem      → cérebros v1/v2/v3 (pesquisa)           │
  135 moedas)    │   minerador_nuvem    → robô Minerador (H28)                   │ ──► ramo `estado`
                 │   cerebro_v4_nuvem   → Cérebro v4 (LightGBM) aposta por moeda │     (dados/*.json)
                 │   v4_perp_nuvem      → Rápido nuvem (todas as apostas do v4)   │          │
                 │   v4_perp_nuvem      → Caçador (2 compras + 2 vendas por vela) │          │
                 │ testnet.yml (rodada viva ~5h40, salva a cada 5 min):           │          │
                 │   v4_testnet         → ordens REAIS na conta de teste Binance  │          │
                 │ robo.yml (00:10 UTC): Tartaruga diária (executor/diario.py)    │          │
                 └────────────────────────────────────────────────────────────────┘          │
                                                                                            ▼
 ┌──────────── MÁQUINA LOCAL (VirtualBox, dorme) ────────────────────────────────────────────────┐
 │ baleias-painel  → painel http://127.0.0.1:8787 (lê o ramo `estado` + estado local) + Rápido 1 min │
 │                   + Scalper + varredura + gravador de livro/funding/mineração                  │
 │ baleias         → monitor original das baleias (carteiras grandes da Hyperliquid)             │
 │ baleias-robo    → robô diário local (espelho/estratégia antiga de 15 min)                     │
 │ baleias-pesquisa→ tarefas lentas de pesquisa (Gemini, SEC, funding, tendência)                │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Regra prática: **o que decide dinheiro está na nuvem**. A máquina local serve para o painel, os testes do laboratório (que precisam de
numpy/lightgbm, no `.venv-ml`) e dois robôs antigos (Rápido 1 min e Scalper) que só funcionam enquanto ela está acordada.

---

## 3. Os cérebros (quem decide a direção)

### 3.1 Cérebro v4 — o cérebro de todos os robôs (desde 13/11)

- **O que é:** um modelo LightGBM (árvores de decisão em gradient boosting, 92 árvores) treinado uma vez, em 11/11, com velas de 15 min
  de 33 moedas, maio/2025 a nov/2026 (hipótese H30). Arquivo fixo `lab/modelos/lgbm_v4.txt`; não aprende ao vivo.
- **Pergunta que responde, por moeda, a cada vela fechada:** a próxima vela de 15 min fecha acima ou abaixo? Devolve uma probabilidade p.
  Aposta quando p ≥ 0,53 (compra) ou p ≤ 0,47 (venda).
- **O que olha (16 medidas, `lab/minerador.py`):** retornos normalizados de 1, 4, 16 e 96 velas; distância às médias de 20 e 200;
  amplitude e corpo da vela; volume relativo (média de 96 velas e mesmo horário dos 20 dias anteriores); RSI 14; distância à máxima e à
  mínima de 96 velas; retorno de 4 velas do Bitcoin; força da moeda contra o Bitcoin; hora UTC.
- **O que pesa mais nas decisões:** hora do dia, o que o Bitcoin fez na última hora, corpo da última vela e último retorno. Volume quase
  não pesa. É um modelo de microestrutura e horário, não de tendência.
- **Evidência:** laboratório fora da amostra 53,9% de acerto em 175.921 apostas, positivo nos 3 blocos de tempo (H30). Ao vivo, de 11/11
  a 13/11, 2.399 apostas, 53,8% (IC 95%: 51,8–55,8%).
- **O achado mais importante (H36):** quanto mais confiante, mais acerta, nos 3 blocos: 52,6% nas apostas fracas (|p − 0,5| entre 0,03 e
  0,05), 54,1%, 57,5% e **65,5%** nas mais fortes (≥ 0,12).
- **Limite:** o movimento médio de uma vela de 15 min é pequeno. No perpétuo, com custo de 0,12% ida e volta, as apostas do v4 perdem na
  média (−0,10% por operação) em todas as faixas de confiança, menos a mais alta, que ficou perto de zero (H31, H36, H38).
- **Desde 13/11 ele prevê as 135 moedas do universo**, não só as 33 em que foi treinado (fora da amostra de treino: o placar julga).
- Backup: `backups/cerebro_v4_2026-11-13.tar.gz` e etiqueta git `cerebro-v4-2026-11-13`. Relatório completo: `docs/RELATORIO_CEREBRO_V4.md`.

### 3.2 Cérebros v1, v2 e v3 (pesquisa)

`baleias/cerebro.py`. Um "cérebro" é um conjunto de **sinapses** (regras do laboratório e uma rede neural MLP que aprende online) que
votam; os pesos dos votos seguem o algoritmo Hedge (quem acerta ganha peso). Sinapses nascem em observação e só passam a votar se
provarem ao vivo (≥ 150 previsões, limite inferior do intervalo de Wilson acima da base); são podadas se ficarem abaixo. O v2 acrescenta
mecanismos inspirados no cérebro humano (dopamina/erro de recompensa, sono, esquecimento). O v3 compara o acerto de cada sinapse com o
"humor do mercado" (quanto o mercado subiu, em média) para não premiar quem só acerta porque tudo sobe.

- Rodam na nuvem a cada 15 min para o BTC e, em versão por moeda, para 33 moedas. Apostam em contrato binário simulado (pesquisa). **Saíram
  do placar em 13/11** (decisão do dono): a tabela de acerto fica na aba de pesquisa do painel.
- Em 12/11 entraram em observação em todos os cérebros, pré-registradas como H33, 12 sinapses com fórmulas dos grandes traders: Holy Grail e
  Turtle Soup (Raschke), TD Setup 9 (DeMark), Williams %R com espera, barra 80-20 (Connors), rompimento de volatilidade (Williams).
  Nenhuma foi promovida ainda (precisam de 150 previsões cada).
- Os cérebros de 1 minuto por moeda, usados pelo Rápido local, mostraram na autoanálise acerto de 23–27% onde previam 54–56%: por isso o
  Rápido deixou de usá-los e passou a seguir o v4.

---

## 4. Os robôs (quem põe a posição)

Todos na mesa (`baleias/mesa.py`) têm **carteira própria de US$ 10**, começada em 11/11 às 13:35 (o "desafio de 24 h": ninguém dobrou;
a régua continua, e o valor nas 24 h fica guardado em cada cartão). Regras comuns dos robôs do perpétuo: posição de **US$ 25 a 10×**
(margem US$ 2,50), **stop de segurança de 1%**, **lucro realizado a +US$ 0,50**, saída no fim da vela apostada, até 6 posições por
lado, custo de 0,06% por lado, **sem trava de perda diária**, eliminado abaixo de US$ 5.

| robô | onde roda | o que faz | carteira 13/11 18:00 | operações |
|---|---|---|---|---|
| **Rápido nuvem (cérebro v4)** | nuvem | entra em TODAS as apostas do v4, as mais confiantes primeiro, até lotar a carteira (H37, agressivo) | 9,65 | 14 |
| **Caçador** | nuvem | a cada vela, entre as 135 moedas, as 2 com maior chance de subir (compra) e as 2 com maior de cair (venda); sempre posicionado (H37, emenda) | 10,00 (começa agora) | 0 |
| **Minerador (H28)** | nuvem | regra achada pelo minerador de oportunidades: movimento forte (cauda de 10%) com volume muito baixo reverte; entra contra e sai na vela seguinte, stop 2% | 9,70 | 62 |
| **v4 Testnet (Binance)** | nuvem (desde 17:47) | ordens REAIS na conta de teste de futuros da Binance seguindo o v4: tenta maker por 60 s, depois a mercado; stop 1%; ignora moedas sem contrato de futuros | 7,51 | 13 |
| Funding (carry) | nuvem | aprovado no laboratório (ganho pequeno): recebe o funding do perpétuo | 10,00 | 6 |
| Scalper | local | segue as apostas do v4: alvo +0,5%, stop −1,5%, fim da vela | 9,30 | 353 |
| Rápido 1 min | local | seguia os cérebros de 1 min; hoje segue o v4; **eliminado** (4,52, abaixo de US$ 5) | 4,52 | 160 |
| Tartaruga diária | nuvem (00:10 UTC) | rompimento de 55 dias, saída na mínima de 20, só compra; conta separada de US$ 700 | 700 (0 operações desde 07/11) | 0 |

Observações honestas:

- O **Rápido 1 min** perdeu 5,48 em 160 operações. Causas medidas: 34 stops de 4N em 1 minuto custaram 4,46 (sem eles seria −1,94); o
  custo foi 2,11 dos 3,91 perdidos até 12/11; e o cérebro de 1 min errava mais que acertava. Está eliminado pela regra do dono; falta
  decidir se a carteira é zerada.
- O **v4 Testnet** perdeu 1,68 numa posição em BTC que ficou aberta 17 h enquanto a máquina dormia (sem stop conferido). Em 13/11 a conta
  de teste tinha 8 posições e 32 ordens que nenhum robô acompanhava: o robô caía por erro de rede entre mandar a ordem e salvar, reiniciava
  e mandava de novo. Consertado (erro de rede tratado, estado salvo na hora da ordem, conciliação com a conta a cada 5 min), conta limpa, e o
  robô foi para a nuvem.
- O **Minerador** é a única regra de minutos que pagou o custo no laboratório (H26: +0,19% por operação na família volume 96). Ao vivo,
  62 operações, carteira 9,70.

---

## 5. Universo de moedas (desde 13/11)

`lab/universo.py`: **todas as moedas da Binance com par USDT à vista, em negociação, com volume ≥ US$ 1 milhão em 24 h**, fora moedas
estáveis e fiduciárias, ouro tokenizado, ações tokenizadas (NVDAB, TSLAB...) e tokens alavancados (BTCUP, ETHDOWN). As 33 moedas
originais ficam sempre. Hoje: **135 moedas** (BMT e QNT incluídas). Recalculado a cada hora; se a Binance não responder, volta às 33.
Usado por: Cérebro v4, Minerador, Rápido nuvem, Caçador e Testnet. Os cérebros v1–v3 e o painel local continuam nas 33.

---

## 6. O laboratório (como se decide o que vira robô)

Regra fixa desde o começo (`PROTOCOLO.md`, `lab/PROTOCOLO_LAB.md`): **toda ideia é pré-registrada antes de rodar** (dados, regra,
custo, o que conta como "passou"), testada fora da amostra, dividida em 3 blocos de tempo, com custo realista. Passa só o que vence no
total e em 2 dos 3 blocos. O número de tentativas é contado (quem testa 100 regras acha 5 por sorte). Nada é ajustado depois de ver o
resultado. Hipóteses 1 a 5 em `PROTOCOLO.md`; 6 a 39 em `lab/PROTOCOLO_LAB.md`. Placar das aprovadas em `lab/placar.json`.

| hipótese | pergunta | veredito |
|---|---|---|
| H6 / H6-WIN | padrões de vela em cripto e no mini índice | reprovadas |
| H7 | a "linguagem" do fluxo de ordens antecipa o preço | em observação ao vivo |
| H8 | LSTM no BTC | reprovada |
| H9 | tom das notícias (GDELT) | reprovada |
| H10 / H11 | Tartarugas em cripto (diário) | aprovada só compra, nas moedas grandes |
| H12 / H13 | custo em velas curtas; teto de posições | H12 reprovada; H13 por pouco |
| H14 | reversão intradiária | reprovada (pequena demais para o custo) |
| H15–H17 | tamanho, sazonalidade, funding contrário | reprovadas (funding carry aprovado, pequeno) |
| H18 / H19 | Vórtice + CHOP; Vórtice invertido | H18 anti-preditiva; H19 em observação |
| H20–H22 | o cérebro (sinapses + rede) no BTC e no Rápido | em teste ao vivo |
| H23 | método de Oliver Velez | só o "espaço duplo" passou no binário |
| H24 / H25 | saídas de scalper; surfar impulso de 5 min | reprovadas |
| H26 / H28 | minerador de oportunidades → Minerador | **aprovada** (reversão com volume baixo) |
| H30 / H31 | LightGBM (v4); v4 no perpétuo com confiança alta | **v4 aprovado no binário**; perpétuo reprovado |
| H32 | minerador em 1 minuto | 213 regras de direção, 0 pagam o custo |
| H33 | fórmulas dos grandes traders como sinapses | em observação (precisa de 150 previsões) |
| H34 | primeira meia hora prevê a última | reprovada |
| H35 | swing diário (momentum 7 d, MM20, Tartaruga 20/10) | reprovada: nenhuma supera ficar comprado nas sobreviventes |
| H36 | estudo do v4 fora da amostra | achado: confiança (52,6% → 65,5%); hora, dia e moeda não |
| H37 | v4 no perpétuo: agressivo contra Caçador, ao vivo | rodando na nuvem |
| H38 | LightGBM com alvo de lucro (movimento > custo) | reprovada |
| H39 | pegar tendência de horas e segurar | reprovada (85% das saídas no stop) |

**A lição que se repete em todos os testes de minutos:** a direção em 15 min é um pouco previsível (54%), mas o movimento é pequeno
demais para pagar o custo do perpétuo. Toda vantagem encontrada em minutos existiu no 1º bloco de tempo (maio–jul/2025) e sumiu depois.
O que paga custo é raro: a reversão do Minerador e, no diário, seguir tendência só comprado (com viés de sobrevivência).

---

## 7. O painel (http://127.0.0.1:8787)

`baleias/painel.py` + `baleias/terminal.html` (+ `painel.html`, `ao_vivo.html` antigos). Só leitura, só nesta máquina. Seções:

- **Carteiras** (placar): cada robô com carteira atual, valor nas 24 h do desafio, situação. Uma régua só: o mesmo número aparece em
  "lucros realizados".
- **Lucros e perdas realizados:** operações fechadas de cada carteira desde 11/11 13:35, com motivo.
- **Varredura ao vivo** (33 moedas, 1 min): o que os cérebros veem agora.
- **Gráficos ao vivo** (TradingView lightweight-charts): clique na moeda; vela viva a cada segundo. Sem linhas de rompimento (removidas em 13/11).
- **Cérebros (pesquisa):** acerto de v1–v4; sinapses por moeda.
- **Rápido, Scalper, Funding, Diário:** detalhes de cada robô.
- O painel se recarrega sozinho quando o código muda (`/api/versao`). Pontos de dados: `/api/mesa`, `/api/realizados`, `/api/moedas-cerebros`,
  `/api/velas-rapidas`, `/api/versao`.

Limite operacional: no máximo 1 reinício do painel por hora (`systemctl --user restart baleias-painel`), porque ele hospeda o Rápido e o
Scalper locais.

---

## 8. Operação: ligar, desligar, chaves

- **Nuvem:** `gh workflow run cerebro.yml` (cérebros + robôs), `gh workflow run testnet.yml` (robô da Binance), `gh run list --workflow
  cerebro.yml`. Uma rodada fica viva ~5h40; o agendamento de hora em hora acorda a próxima. Para aplicar código novo na hora: cancelar a
  rodada em andamento (`gh run cancel <id>`) e disparar de novo. Estado dos robôs: ramo `estado`, pasta `dados/`.
- **Local:** `systemctl --user status baleias-painel baleias baleias-robo baleias-pesquisa`. Começo de sessão: `cd ~/baleias && python3
  checar.py` (checa serviços, idade dos dados, erros) e ler `MELHORIAS.md`.
- **Botões de parada:** arquivo `~/baleias/PARAR` (robô diário/real) e `dados/PARAR_RAPIDO` (Rápido local). Os robôs da nuvem param
  sozinhos abaixo de US$ 5.
- **Chaves:** nunca no código nem no chat. Testnet: `BINANCE_TESTNET_API_KEY/SECRET` no `.env` (máquina) e nos segredos do GitHub (nuvem).
  Conta real: `python3 -m executor.configurar_chave` num terminal de verdade, depois `python3 -m executor.verificar`, e só então
  `BINANCE_REAL=1`. Chave com permissão de saque é recusada. **Hoje nenhum robô opera dinheiro real.**
- **Testes:** `python3 -m unittest tests.test_baleias` (112 testes, todos passando em 13/11).
- **Variáveis de ambiente principais:** `ROBO_RAPIDO` (intervalo, 1m), `ROBO_RAPIDO_SINAL` (v4), `ROBO_RAPIDO_FONTE` (v4),
  `ROBO_RAPIDO_PERDA_DIA` (0 = sem trava), `ROBO_RAPIDO_STOP` (0,01), `V4P_MODO/V4P_K/V4P_LIMIAR` (Rápido nuvem e Caçador),
  `V4_LIMIAR/V4_CAPITAL/V4_STOP/TESTNET_DURACAO` (testnet), `UNIVERSO_VOLUME_MIN`, `BINANCE_DADOS` (data-api.binance.vision na nuvem),
  `BALEIAS_DADOS`, `CEREBROS_MOEDAS`.

---

## 9. Mapa dos arquivos

- `baleias/` — painel (`painel.py`, `terminal.html`, `terminal_api.py`), mesa (`mesa.py`), cérebros (`cerebro.py`), robôs locais e
  varredura (`tempo_real.py`), monitor original das baleias (`monitor.py`, `sinais.py`, `aprendizado.py`, `banco.py`), notícias, SEC.
- `executor/` — nuvem: `cerebro_nuvem.py`, `cerebro_v4_nuvem.py`, `minerador_nuvem.py`, `v4_perp_nuvem.py`, `v4_testnet.py`,
  `diario.py`; corretoras: `binance.py`, `bybit.py`, `binance_futuros.py` (futuros, só biblioteca padrão), `corretoras.py`;
  Tartaruga: `tartaruga_exec.py`; chaves: `configurar_chave.py`, `verificar.py`.
- `lab/` — protocolo e testes: `PROTOCOLO_LAB.md`, `tartaruga.py` (dados diários, 33 moedas), `minerador.py` (dados de 15 min e
  medidas do v4), `lgbm.py` (treino do v4), `lgbm_alvo.py` (H38), `v4_estudo.py` (H36), `swing.py` (H35), `tendencia_horas.py` (H39),
  `universo.py`, `velez.py`, `lstm.py`, `scalper.py`, `modelos/` (modelos salvos), `placar.json`.
- `dados/` — estado local (`robo_*.json`, `cerebro_*.json`), banco SQLite do monitor (`baleias.db`), gravações (`gravacao/`),
  `lab/` (dados e resultados dos testes), `LIVRO_DE_METODOS.md`.
- `backups/` — backup do Cérebro v4 (13/11). `docs/` — este arquivo, `RELATORIO_CEREBRO_V4.md`, `CEREBRO_HUMANO.md`.
- `.github/workflows/` — `cerebro.yml`, `testnet.yml`, `robo.yml`.
- Fora do repositório, na pasta do usuário: `reports/` e `research_notes/` (pesquisas: previsibilidade em cripto, maiores traders e
  metodologias, ensinamentos práticos para robôs, mineração de BTC).
- Tamanho: ~11.400 linhas de Python; 188 commits.

---

## 10. O que foi decidido em 12 e 13/11 (registro)

1. Trava de perda diária do Rápido desligada ("tirar"); só o piso de US$ 5 elimina.
2. Stop de 4N em 1 minuto trocado por stop de segurança de 1% (medido nos 147 trades).
3. Placar e lucros realizados na mesma régua; a carteira segue depois das 24 h.
4. Todos os robôs com o cérebro v4; Rápido nuvem e Caçador criados na nuvem; backup e relatório do v4.
5. Contas de contrato binário fora do placar; linhas e radar de rompimento fora do painel.
6. Universo = todas as moedas da Binance com volume (135).
7. Robô da Binance para a nuvem (chaves nos segredos do GitHub, gravadas pelo dono); conta de teste limpa; três defeitos consertados.
8. Repositório continua público (minutos ilimitados da nuvem).
9. Testes feitos e reprovados hoje: H35 (swing diário), H38 (alvo de lucro), H39 (tendência de horas).

---

## 11. Pendências

- **Do dono:** decidir a carteira do Rápido local (4,52, eliminado): zerar ou parar. Trocar a chave do testnet que foi colada no chat
  (boa prática; é conta de teste, sem dinheiro).
- **Em observação:** H37 (Rápido nuvem contra Caçador), H33 (sinapses dos grandes traders), robô da Binance na nuvem (primeiras
  execuções reais com o universo de 135 moedas).
- **Próximos testes com alguma chance, pelos dados:** retreino mensal do v4 (H36 parte 2); medidas novas do gravador (funding, juros em
  aberto, livro) como colunas do v4 (H36 parte 3). Ambos pré-registrados, ainda não rodados.
- **Problema aberto, sem solução grátis conhecida:** fazer o acerto de direção do v4 (54%, 65% nas confiantes) virar lucro no perpétuo.
  Hoje a conta não fecha pelo tamanho do movimento em 15 min. O Caçador e o testnet são os testes ao vivo disso.

---

## 12. Glossário curto

- **Perpétuo:** contrato de futuros sem vencimento; permite comprar ou vender (apostar na queda) com alavancagem.
- **10×:** posição de US$ 25 com margem de US$ 2,50; 1% de movimento = 10% da margem.
- **Vela de 15 min:** abertura, máxima, mínima, fechamento e volume de cada 15 minutos.
- **Stop de segurança:** ordem que fecha a posição ao perder 1%.
- **Lucro realizado:** fecha a posição ao ganhar US$ 0,50.
- **Fora da amostra / 3 blocos:** testar numa parte dos dados que o modelo nunca viu, dividida em três períodos: passa só se ganha em dois.
- **Intervalo de Wilson:** faixa de incerteza de um percentual de acerto (54% em 2.400 apostas: entre 52% e 56%).
- **Pré-registro:** escrever a regra e o critério de aprovação antes de rodar o teste, para não escolher o resultado depois.
