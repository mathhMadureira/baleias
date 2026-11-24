# Melhorias — lista viva (ler no início de cada sessão)

**Ritual de início de cada sessão:** `python3 checar.py` (tudo tem que dar ✅), depois `git log --oneline -10` e esta lista.

## Princípios (insights da Anthropic aplicados ao projeto, 2026-11-10)
- **Quem propõe não julga:** sinapse nova só ganha voto pelo critério estatístico (código), nunca por opinião minha.
- **Toda estratégia precisa vencer uma referência trivial:** o cérebro mostra "sempre sobe" nas mesmas apostas.
- **Consistência acima de sorte:** exigir que o resultado se repita em vários períodos e moedas (como fizemos com grupos 2 e 3).
- **Sem vazamento:** o aquecimento não conta; teste é sempre em dados que o modelo ainda não viu.
- **Memória pequena e verificada:** o Livro de Métodos e o diário são reconferidos contra os resultados reais; lição velha pode estar errada.
- **Credenciais fora do agente:** chaves só no `.env` digitadas pelo dono; nada de ordem real sem `BINANCE_REAL=1` posto por ele.

Ordem = prioridade. Cada item que mexe em estratégia vira hipótese pré-registrada em `lab/PROTOCOLO_LAB.md` **antes** de testar.

## Em andamento / próximos

0. **[H73 — feito: fator 5 a 20× ligado nas carteiras simuladas]** Tamanho maior com perda maior (dono, 22/11: "pode aumentar o tamanho da perda também"). `lab/escala_capital.py`: fator 5 a 20× (o dobro da H64) passa o juiz na carteira simulada — 10,53 × 10,29 na sequência real, queda 35,7%, sem liquidação, 14,3% de chance de bater no piso; fator 10 a 50× reprovou (termina em 4,55, abaixo do piso). A conta de teste fica na H64 (2,5×) porque com o fio negativo dela o braço maior bateria no piso em 30,1%. O fio por operação não mudou (+0,0254%, t 0,36): o tamanho dobra, a vantagem não. 193 testes.


0. **[H72 — feito: reprovada no portão do fio; nada mudou]** Escala de capital e alavancagem (pedido do dono: "não quero centavos, quero lucros significantes"). Nas 136 operações fechadas dos 4 agentes o fio é +0,0547% do nocional (t 0,72) e na conta de teste −0,1327% (t −0,53): sem prova de vantagem, escala só multiplica ruído. Números para a decisão do dono: US$ 10/dia exige carteira de ~US$ 239 com o fio de hoje; US$ 100/dia, ~US$ 2.390; na carteira de US$ 10 são 7.313 operações para +US$ 100. Com a regra H64 a queda máxima simulada sobe de 17,9% (US$ 10) para 35,7% (US$ 50+). `lab/escala_capital.py`, H72 no protocolo.


1. **[H12 — feito, não passou; falta 15 min]** Custo em R nas velas curtas. Em 1 h o stop 2N fica a ~0,3% do preço e o custo de ida e volta é 0,2% (≈0,67R por operação). Testar um filtro derivado da matemática, não dos dados: só entrar se custo ≤ 0,1R, ou seja, 2N/preço ≥ 2%. Medir em 4 h, 1 h e 15 min, em 2024 e em 2025–hoje.
2. **Robô rápido ao vivo:** depois do H12, escolher o intervalo e o filtro pelo resultado, sem achismo.
3. **[H13 — feito: não passou por 0,01 de Calmar; candidato a teste ao vivo em paralelo]** Risco total máximo: as 33 moedas andam juntas, então 10 posições valem quase uma aposta só. Testar um teto de risco aberto (ex.: 6R) para reduzir a queda máxima de −42%.
4. **Universo dinâmico:** trocar a lista fixa de 33 moedas (que tem viés de sobrevivência) por "as 40 de maior volume dos últimos 30 dias", recalculada todo mês, e medir de novo.
5. **Dinheiro real:** o dono grava a chave (`python3 -m executor.configurar_chave` no Terminal do Ubuntu) e roda `python3 -m executor.verificar`. Depois:
   - [feito 2026-11-10] conciliar ao ligar: posição sumida na corretora → registra pelo stop executado ou fecha no preço atual e avisa;
   - acompanhar de perto a primeira operação real.
6. **Avisos no celular:** configurar os segredos do Telegram no GitHub (`gh secret set TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID`).
7. **[feito 2026-11-09] Gráfico diário ao vivo:** a vela do dia se mexer com o preço, como no gráfico de 1 h.
8. **Fidelidade do teste:** o custo diário de 0,02% (financiamento) não existe no spot; separar spot de perp e incluir escorregamento medido.
9. **Testes ao vivo para avaliar:** H5 (Gemini, ~300 previsões), H7 (fluxo, 2000 janelas), H2/H3 (tendência e funding), **H19 (Vórtice invertido, 300 apostas)**, robô-sombra H13 (teto 6).
10. **Alerta de falha da nuvem:** se o `robo-diario` falhar, avisar no Telegram (o GitHub também manda e-mail).

## Feito (recente)

- 2026-11-21: painel da Mesa ao vivo ganhou cartões de atividade por agente, com situação, carteira, posições e última entrada/saída observada; sem inventar etapas internas que a nuvem não transmite.

- 2026-11-10: **mesa proprietária** (aba 🏦): cada robô em teste tem conta de US$ 10; violação se perder > US$ 1 num dia; eliminado abaixo de US$ 5; aprovado para fase 2 (US$ 50) com ≥ 30 operações, ≥ US$ 11, sem violações, queda < 30%. Robô rápido virou conta nativa de US$ 10 (US$ 5 por operação, máx. 1 h, para no dia com −US$ 1). Cérebro v2 (biologia) competindo com v1.

- 2026-11-10: repositório público; cérebro roda no GitHub a cada 15 min (painel espelha); fluxos acrescentam no ramo `estado`; Livro de Métodos; referência "sempre sobe"; `checar.py`.

- 2026-11-10: H14–H18 testadas e reprovadas (reversão intradiária, força relativa, sazonalidade com contagem corrigida, funding contrário, Vórtice+CHOP). Mapa do mercado inteiro (~170 moedas) e previsor H19 (Vórtice invertido) ao vivo. Robô rápido em 5 min com teto de perda de US$ 100/dia; robô de funding visível.

- 2026-11-10: monitor caía em ciclo com "database is locked" (o Gemini segurava a gravação durante chamadas de rede de até minutos). Commit antes de cada chamada de rede e conexões esperando 30 s. Também confirmado: depois de pausa da máquina, o motor ao vivo se recupera sozinho.
- 2026-11-10: conciliação das posições com a corretora ao ligar (modo real).

- 2026-11-09: robô rápido ao vivo (1 h) com gráfico ao vivo; replay; Bybit; nuvem grátis no GitHub; stops com a máquina desligada; memória do projeto.

- 2026-11-13: **decisões do dono**: todos os robôs com o cérebro v4 (LightGBM) e operando na nuvem; contas de contrato binário fora do placar; linhas e radar de rompimento fora do painel; trava de perda diária do Rápido desligada (só o piso de US$ 5); stop de segurança de 1% no lugar do 4N de 1 min; **universo = todas as moedas da Binance com par USDT e volume ≥ US$ 1 mi (135 moedas, `lab/universo.py`)**. Novos: `executor/v4_perp_nuvem.py` (Rápido nuvem agressivo e seletivo, H37), robô do testnet com modo nuvem (`testnet.yml`, precisa dos segredos BINANCE_TESTNET_API_KEY/SECRET no GitHub), backup do v4 (`backups/`, tag `cerebro-v4-2026-11-13`), relatório `docs/RELATORIO_CEREBRO_V4.md`. Laboratório: H35 (swing diário) reprovada, H36 (estudo do v4: confiança é o achado), H38 (alvo de lucro) reprovada, H39 (tendência de horas) em teste. A máquina local dormiu 17 h (12/11 23:05 → 13/11 16:07); o dono não vai desligar a suspensão: tudo que importa tem de rodar na nuvem.

- 2026-11-14: **o cérebro passa a aprender sozinho, com juiz**: H41 PASSOU (v4.1 retreinado até 15/10 acertou 53,46% contra 52,97% do v4 no holdout de 30 dias, 3 de 3 blocos) e virou o modelo em uso; `retreino.yml` repete isso toda semana (campeão × desafiante). **Diário de lições** (`executor/licoes.py` → `dados/LICOES.md`, cartão no painel): o que cada robô fez e onde perdeu, o que os cérebros promoveram/podaram, últimos vereditos. Universo de 135 moedas; `AGENTS.md`/`CLAUDE.md` com as regras do dono; `GROK_BOT.md` atualizado; `docs/ROBOS.md` (remapeamento). Consertos: gravação do estado na nuvem (15 rodadas perdidas por rebase), posições presas em moedas fora do universo, varredura dos cérebros de 1 min desligada no modo v4, conta de teste limpa (32 ordens órfãs). Reprovadas: H40 (alvo por ATR), H42 (humor do mercado como filtro de lado). Carteiras do Rápido 1 min e do testnet zeradas a pedido do dono.

- 2026-11-15: **Robô Claude consertado e ampliado.** A rotina estava morta das 03:10 às 09:08 (limite do modelo Fable) → agora Opus 5.5, com alarme de rotina parada e histórico de decisões. Regra do dono (H44) nos robôs da nuvem: a tendência de 24 h decide o lado (≤ 30% das moedas subindo = só vendas; ≥ 70% = só compras) e a posição é segurada enquanto o v4 concorda. Robô Claude: posição ajustada para as 4 caberem na carteira (ERA/KAVA não couberam) e stop pela volatilidade (2× amplitude de 1 h, 1,5–4%; as 7 primeiras operações pararam todas no stop de 1,5%). **Retrato do mercado com contexto** (`executor/contexto_mercado.py`): notícias (RSS CoinDesk/Cointelegraph/Decrypt), medo e ganância, funding (Hyperliquid), tendência diária do BTC (MM50/200) e amplitude acima da MM50, padrões gráficos em 1 h (`lab/padroes_graficos.py`, H45 em teste). **Pesquisa diária** (rotina do Claude com busca na internet → `dados/IDEIAS_PESQUISA.md`). **Tudo na nuvem:** Scalper migrado (`Scalper nuvem`), robôs locais desligados por padrão (`BALEIAS_ROBOS_LOCAIS=1` religa). Painel: cartão no topo com as posições ao vivo dos robôs da nuvem e gráfico próprio. Funding (carry) fora do placar.

- 2026-11-15 (noite): **fusão OpenBot + Baleias** (pedido do dono: "um único software com um só propósito"). Propósito: mesa de operadores de IA que opera cripto sozinha na nuvem e conversa com o dono. O OpenBot é um app de desktop (Electron/TypeScript, 243 MB, licença PolyForm Noncommercial) para conversar com agentes de IA; dele vieram as ideias, reescritas em Python puro: agentes persistentes (`baleias/equipe.py`, EQUIPE), sala compartilhada com dono da tarefa (`dados/sala.json`), caixa de entrada do dono (`dados/caixa/<id>.json`, um arquivo por mensagem, enviado pelo painel via `gh api`, sem conflito com a gravação da nuvem), ordens de agente para agente (`dados/ordens.json`, vencem em até 24 h) e gravação atômica. O Robô Claude virou chefe da mesa: a rotina lê `caixa_dono`, `equipe` e `sala_recente` no retrato, responde (`respostas`), dá `ordens` e deixa `mensagens` (cartilha seção 6, rotina atualizada). Caçador, Rápido nuvem, Scalper nuvem e Minerador cumprem as ordens e postam entradas/saídas na sala. Painel: cartão 🐋 Sala de operações no topo (equipe + conversa + caixa de texto). 4 testes novos (116). O app OpenBot em si não é necessário para nada disso; a cópia em `openbot/` fica fora do git.
- 2026-11-15 (noite): **livros da O'Reilly lidos e aplicados** (`docs/LIVROS_OREILLY.md`). Dos 10, 4 servem (risco de modelos, raciocínio analítico, agentes, estatística); nenhum é de trading. Novo **vigia do v4** (`executor/vigia_v4.py`, na nuvem a cada rodada): acerto ao vivo × laboratório com erro-padrão por vela, referências simples nas mesmas apostas e acerto por segmento; vai no retrato do chefe e avisa na sala. Primeiro resultado (12.673 apostas, 11–15/11): 52,5% ao vivo × 53,5% no laboratório (dentro do esperado); 18–24 h UTC 44,2% → **H46 pré-registrada** (teste só com apostas de 16–22/11). O v4 passa a gravar a probabilidade de cada aposta (acerto por faixa de confiança). Cartilha seção 7: autocrítica com dados antes de gravar a decisão. 118 testes.
- 2026-11-15 (noite): **Robô Livre** (H47, pedido do dono): sem regras de decisão; segue a maioria do mercado em 24 h nas 4 moedas líderes, carteira inteira a 20×, reinvestindo, sem stop (só liquidação a 4,5%). Mostra a carteira com e sem custo. Na Sala e no painel como 🦅. 120 testes.
- 2026-11-15 (noite): **trava de lucro no Robô Claude** (H48). Queixa do dono: "quando estão positivos, entram em outras e perdem". Medido em 403 operações: o problema não é a operação seguinte (depois de ganho não é pior); é devolver o lucro aberto — Robô Claude: 8 de 9 chegaram a +0,5% e terminaram ≤ 0. Chegou a +1% → saída sobe para +0,5% (simulação −3,19 → −0,38). Nos robôs do v4 (15 min) a trava não teve efeito consistente: não mudaram. 122 testes.
- 2026-11-15 (noite): **stop móvel em todos os robôs da nuvem** (H49, pedido do dono: "realizar lucro e ir subindo o stop"), no lugar da trava fixa da H48. Arma a +0,5% e guarda 70% do maior lucro, subindo junto, conferido minuto a minuto (`executor/stop_movel.py`, 1 chamada à Binance por posição aberta por rodada). Simulação nas 403 operações: −8,25 → −0,51, melhor nas duas metades e em todos os robôs. Fora: testnet e Robô Livre (comparação). 123 testes.
- 2026-11-15 (noite): **torneio** (`executor/torneio.py`, H50): placar de todos os robôs com as mesmas medidas (fator de lucro, acerto, ganho/perda médios), campeão com ≥ 30 operações, desafiantes julgados no mesmo período e anunciados na sala. Desafiantes do Scalper (melhor fator de lucro hoje, 1,24): **Scalper B** (sem alvo fixo, stop móvel leva o lucro) e **Scalper C** (só apostas confiantes ≥ 0,08). Pesquisa diária reescrita: estuda o campeão, as fraquezas do vigia e como o mercado cripto está operando. Robô Livre: 2 liquidações em 41 min (RARE e ASTER, −4,5% a 20×), carteira 3,80. Rápido nuvem: pico +0,54 às 20:30 UTC → −0,14 (2 stops de −0,28 às 21:30–21:45 e 3 vendas fechadas quando o regime virou para alta). 124 testes.
- 2026-11-15 (noite): **Scalper D (foco)** (H51, pedido do dono: "focar onde ele está positivo"). O Scalper ganha nas saídas por alvo e stop móvel e perde no fim da vela; segurar até o alvo não melhoraria (−0,47 → −0,52). O D evita sozinho os segmentos de entrada em que o Scalper perde com prova (≥ 50 ops, z ≤ −2); hoje nenhum segmento tem prova, então ele opera igual. 125 testes.
- 2026-11-15 (noite): **revisão de engenharia** de todos os robôs da nuvem, prompts e cartilha (pedido do dono). Defeitos corrigidos, cada um com teste: (1) o stop móvel saía antes do alvo do Scalper (tocava +0,5% e saía a +0,35%): o alvo agora é conferido minuto a minuto; (2) Robô Claude: `"posicoes": []` não fechava as abertas — agora toda posição fora da lista fecha; (3) Minerador ainda tinha trava de perda diária de US$ 1 (contra a regra 5): removida; (4) a Sala descartava as mensagens do dono quando os eventos passavam de 600: conversas e eventos agora têm limites separados; (5) a carteira dos robôs do v4 não contava o resultado aberto. Prompt do chefe: lia só 20 KB dos 30 KB do retrato e cortava as linhas da cartilha; agora lê tudo com Read. **O chefe tinha pausado o Rápido às 21:21 UTC "para realizar lucro"** (carteira 10,45), o que o deixou sem entradas enquanto as abertas batiam no stop: cartilha e prompt proíbem pausar para guardar lucro (isso é o stop móvel) e mandam revisar e liberar ordens sem motivo. Cartilha: régua de tendência alinhada (≤ 30%/≥ 70%, antes "80% caindo"). 128 testes.
- 2026-11-15 (noite): **rotas novas (H52)**, pedido do dono: "esse negócio de 15 minutos não tem sido bom". 8 rotas testadas nas 13.179 apostas reais do v4 com cálculo de expectativa (acerto, ganho e perda médios, acerto de empate). A rota em uso (sair no fim da vela de 15 min) é a pior: −0,145% por aposta, z −6,55. Aprovada: **R6** — segurar com stop móvel + stop de 2% até 24 h, só a favor da tendência de 24 h (+0,225%/aposta, z +2,71, 3 blocos positivos; robustez por blocos de 6 h fraca, um episódio de queda). Ligada no Rápido nuvem e no Caçador; Scalpers inalterados para o torneio. 131 testes.
- 2026-11-15 (noite): **conector da LBank, só leitura** (`executor/lbank.py`, pedido do dono). Hora do servidor, preço do BTC (à vista e perpétuo), permissões da chave (recusa chave com saque) e saldos da conta à vista. Nenhuma função de ordem, cancelamento, transferência ou saque existe no arquivo (teste garante). Assinatura (MD5 maiúsculo + HMAC-SHA256) conferida com o exemplo da documentação oficial. A LBank recusa o cliente padrão do Python (403): pedidos vão com User-Agent genérico. Chave: `python3 -m executor.configurar_chave` (opção lbank, não muda a corretora em uso); conferir: `python3 -m executor.lbank`. Saldo do perpétuo: a documentação pública não traz o endereço privado; fica para quando houver. 134 testes.
- 2026-11-15 (noite): **Robô LBank** (H53, simulado, pedido do dono): SOL, 11 memecoins (DOGE, SHIB, PEPE, WIF, BONK, FLOKI, BRETT, POPCAT, FARTCOIN, PNUT, PENGU) e HOOD (Robinhood tokenizada) com os preços públicos do perpétuo da LBank; lado pelo regime de 24 h, segura com stop móvel (velas de 1 min da LBank) e stop de 2%, até 4 posições. Obedece ao chefe; entra no torneio. Nenhuma chave usada. 136 testes.
- 2026-11-16: **Banco da mesa, regras do dono e LBank sem lista.** (1) Torneio: não existe campeão no prejuízo (carteira > US$ 10 e fator > 1).
  (2) Nenhum robô é pausado no prejuízo ou com operações abertas: `equipe.pausa_proibida` recusa a ordem do chefe e anula a pausa em vigor.
  (3) 🏦 Banco (`executor/banco.py`, depois do torneio na nuvem, `dados/banco.json`, linha no placar do painel): tesoureiro do dinheiro real —
  sem crédito e sem empréstimo (pedido do dono); soma as carteiras, margem, exposição bruta × líquida e robôs em lados opostos na mesma moeda.
  Não move dinheiro para quem ganhou porque lucro das 30 operações anteriores não se repetiu nas 30 seguintes (correlação −0,14, 112 janelas).
  (4) Robô LBank vê todas as moedas do perpétuo da LBank com volume ≥ US$ 1 mi (312 hoje; antes 13), adendo da H53. (5) Git local
  corrompido pela VM congelada (7 objetos vazios) deixava o placar do painel vazio: objetos apagados e ramo `estado` baixado de novo.
- 2026-11-16 (noite): **Guarda do dia (H54)**, regra do dono "nenhum robô termina as 24 h no prejuízo": dia que chegou a +0,25 e devolveu
  metade fecha tudo e trava até 21:00 de Brasília, em todos os robôs da nuvem. Medido em 36 dias-robô: dias positivos 7 → 11, soma −45,54 → −26,40.
  O dia que nunca fica positivo segue operando (sem trava de perda). Placar do painel mostra "hoje ±X" e "🔒 dia garantido".
- 2026-11-16 (noite): **Mesa zerada** a pedido do dono (histórico na etiqueta `estado-antes-do-zero-2026-11-16`; testnet não zerado: tem
  ordens na conta de teste). **H55 "não perseguir"** (`executor/sem_perseguir.py`) em todos os robôs: não compra acima da média de 20 velas
  de 15 min, não vende abaixo. Medido em 1455 operações: perseguir −0,070/op × contra −0,008 (3/3 blocos); exigir os 5 tempos gráficos a
  favor deu −0,054 (pior), por isso não virou regra.
- 2026-11-16 (noite): **📡 Radar (H56)**, pedido do dono "ler o mercado a partir de 1 s, em todos os tempos gráficos, entrar onde houver
  oportunidade": teste no laboratório com velas de 1 s (12 moedas, 3 dias) REPROVOU as 3 regras (melhor, R3: −0,017/op; +0,013 antes do
  custo). Entra na mesa SIMULADO como comparação ao vivo (`executor/radar_nuvem.py`, fluxo contínuo `radar.yml`, lê a cada 2 s).
- 2026-11-16 (noite): **Fim dos limites de 15 min** (dono: "a decisão não deve ser limitada por tempo"): H55 revogada; rodada da nuvem
  sem esperar a vela (1 min de intervalo); Scalpers A–D na rota R6 (sem saída no fim da vela, alvo deles mantido); Minerador sai por stop
  móvel, stop 2% ou 24 h.
- 2026-11-17: ideias dos vídeos do "Grok bot", medidas antes: **H57 meta do dia +US$ 0,50** (fecha e trava; carteiras 78,45 → 82,58, dias
  positivos 9 → 11 de 34; meta de +12 nunca foi alcançada) e **H58 posição = 2,5 × carteira** (reinveste o lucro, encolhe na perda; 78,45 →
  81,91, nenhum robô abaixo do piso). O jeito do vídeo (60% do caixa) piorou e ficou fora.
- 2026-11-17: meta do dia volta a **US$ 12** (a de +0,50 travava quem ganhava: 8 robôs entre 10,11 e 10,86 parados); travas da meta antiga
  soltas; a guarda do dia (H54) segue. Robô LBank só entra onde há velas de 1 min (stop de 2% furado em SPACE1 −11% e AIOT −7%).
- 2026-11-17 (noite): **Painel da mesa em tela única** (pedido do dono). Aba "🐋 Mesa ao vivo" lê `/api/painel-mesa` (`mesa.painel_mesa`,
  função pura `montar_painel`, a cada 10 s): placar (carteira, hoje, desde o zero, operações, acerto, fator de lucro, abertas, estado, quando
  o robô gravou), curva da carteira de cada robô desde o zero (SVG), posições abertas com o preço de agora (Binance à vista; LBank para o Robô
  LBank) e há quanto tempo, linha do tempo de entradas e saídas com o motivo, estado (operando, guarda do dia, meta batida, sem dinheiro,
  pausado) e banco (`dados/banco.json`: soma, exposição, conflitos). Conferido número por número contra o ramo `estado` (12 robôs e banco:
  0 diferenças). Sem biblioteca externa (lightweight-charts saiu; velas em SVG próprio). **Tirado do painel por estar desatualizado:** placar
  antigo do desafio de 24 h de 11/11, aba da mesa proprietária (regra de violação de US$ 1/dia, contra a regra 5), robô diário Tartaruga,
  varredura de 33 moedas e Rápido/Scalper locais (desligados em 15/11), cérebros v1–v3 de contrato binário (fora do placar em 13/11; o
  título citava assunto encerrado pela regra 6), previsor H19, robô de funding (fora do placar em 15/11), cartões antigos "robôs operando
  agora", "lucros realizados" desde 11/11, abas sem botão (mapa, replay). Os endereços da API continuam. 149 testes.
  **Achado (não corrigido aqui, é do `executor/`):** depois do zero de 16/11, Caçador, Rápido nuvem e os 4 Scalpers gravaram 4 a 20
  operações abertas e fechadas ANTES do zero (sinais velhos do v4 reprocessados com o estado vazio); estão na carteira (−0,59 a +0,13).
  O painel mostra a contagem em cada robô.
- 2026-11-17 (noite): **Chefe OpenBot no testnet (H59, pré-registrada antes de ligar, commit 12e8c002).** O agente OpenBot que já decide a mesa
  a cada 30 min passa a operar a conta de TESTE de futuros da Binance com ordens de verdade, no lugar do robô "v4 Testnet": `testnet.yml`
  desligado e a rodada viva cancelada; conta conferida vazia (sem posição, sem ordem normal nem condicional, saldo de teste 4.983,17).
  Executa as posições da própria decisão do chefe (as mesmas do Robô Claude simulado), a mercado, e **toda entrada sai com STOP_MARKET
  reduce-only guardado na corretora** (a corretora aceitou pela API de ordens condicionais, `algoOrder`); stop inicial igual ao do Robô Claude,
  stop móvel subindo na corretora a cada rodada, guarda do dia e meta de 12, 24 h, carteira de US$ 10 a 2,5×/10×. Resultado = o da corretora
  (realizedPnl − commission). Ao voltar de uma pausa da máquina, confere primeiro a conta (stops executados, órfãos). O operador
  (`testnet.py`) fica na pasta do agente, fora do repositório; a chave continua só no `.env`. Na EQUIPE como ⚓ "Chefe OpenBot (testnet)",
  estado `dados/robo_openbot_testnet.json` (só ele grava); o painel usa o preço do testnet para este robô. Primeira operação 18/11 01:04 UTC:
  compra de ZEC (0,026 a 961,76, stop 925,33) e RENDER (17,1 a 1,462, stop 1,417). 151 testes.
- 2026-11-17 (noite, 22:45 BRT): **H59, emenda: o chefe escolhe pelo universo inteiro (pedido do dono).** A cada rodada `universo.py` (pasta do agente)
  lê a probabilidade do v4 das ~120 moedas, o regime de 24 h, movimento e volume de 1 h/4 h/24 h, se a moeda existe nos futuros do testnet, e
  compara as memecoins com o perpétuo da LBank; entra só com confiança do v4 ≥ 0,08 (H36), no lado do regime, até 4; mantém as abertas enquanto
  regime e v4 não virarem contra. Primeiras pela regra nova (18/11 01:45 UTC): USTC vendido (v4 0,343; stop 0,004091 na corretora) e SHIB comprado
  (1000SHIB a 0,003864; v4 0,645; stop 0,003797). A tela do testnet é o Demo Trading da Binance (demo.binance.com), mesma conta da API: posições e
  stops (Conditional, reduce-only) aparecem lá. **Achado:** a nuvem às vezes calcula o v4 só nas 33 moedas de reserva (exchangeInfo da Binance
  levou 38 s; 22:30 BRT: 34 moedas); a análise usa então a rodada completa mais nova de até 15 min. Não corrigido em `lab/universo.py` (anotado).
- 2026-11-17 (noite, 23:10 BRT): **H60 alavancagem na carteira — reprovada, nada muda** (pedido do dono: "não passa de 11 dólares, quero
  alavancagem"). Pré-registrada antes de rodar (c5ea773b); contrafactual nas operações reais (`lab/alavancagem.py`): 3,75× e 5× a carteira a 20×
  levam robôs ao piso (antes do zero: os 9 com 5×; desde o zero: o Radar) e alavancar só quem está no lucro com prova perde nos dois conjuntos.
- 2026-11-18 (tarde): **todos os robôs destravados (decisão do dono)**: guarda do dia (H54) revogada em `executor/guarda_dia.py` (GUARDA_LIGADA =
  False; travas antigas soltas na rodada seguinte); ficam a meta de US$ 12, o piso de US$ 5 e os stops. Robô LBank: memecoins primeiro e, no regime
  neutro, a partir de 1% em 24 h (as outras 3%). Regra 12 do AGENTS.md marcada como revogada. 152 testes.
- 2026-11-18 (tarde): **os agentes do OpenBot operam no lugar dos robôs (H61, pedido do dono).** Robôs aposentados do laço da nuvem e do painel
  (`ROBOS_APOSENTADOS`; `radar.yml` desligado; carteiras congeladas). `executor/robo_claude_nuvem.py` virou o executor de qualquer agente
  (RC_AGENTE/RC_ARQ/RC_DECISAO): Baleias (chefe + conta de teste), Treinador (método do Caçador), Laboratório (v4 ≥ 0,12) e Guardião (tendência de
  24 h + memecoins), cada um com US$ 10. Cada agente grava só `dados/decisao_<id>.json` com a ferramenta `OpenBot/Shared/baleias/operar/operar.py`.
  Painel, placar, torneio, banco e diário de lições mostram os agentes. Regime do painel vem do retrato do mercado. 152 testes.
- 2026-11-18 (tarde): **P1 do Treinador aprovada pelo Laboratório e aplicada**: entrada no preço e na hora da rodada (vela de 1 min fechada), não no
  fechamento de uma vela de 15 min passada; no executor dos agentes (`robo_claude_nuvem.py`) e no dos robôs do v4 (com o filtro de aposta velha). 154 testes.
- 2026-11-18 (fim da tarde): **H62 — agentes operam livres, estilo scalper (pedido do dono)**: cada agente escolhe moeda, lado, stop, alvo e prazo de cada
  posição (limites 0,3–4% / 0,2–5% / 5–1440 min); a nuvem confere stop e alvo minuto a minuto; na conta de teste o alvo também fica guardado na corretora
  (TAKE_PROFIT_MARKET). `operar.py escolher` virou panorama (v4 subir/cair, movimento de 1 h, memecoins) + sugestão. 155 testes.
- 2026-11-18 (noite): **H63 — "monitor fomo": raspagem das melhores carteiras (pedido do dono).** Referências buscadas antes (bots que copiam o
  ranking da Hyperliquid, fomo.family, aviso sobre copiadores perto do topo). `executor/carteiras_nuvem.py` na nuvem a cada rodada: ranking público
  da Hyperliquid a cada 24 h → 40 contas ativas e lucrativas (filtro fixo da H63); posições delas e preços de meio (API pública, só leitura);
  feed de aberturas e fechamentos; cada abertura é resolvida em 60–75 min (juiz automático, passa com ≥ 300 eventos e t ≥ 2). Agentes recebem a
  tabela das carteiras e o feed na raspagem (`operar.py escolher`, `universo.py`) e decidem o scalper depois dela (rotina r4). 157 testes.
- 2026-11-18 (noite): **leitura em todos os tempos, de 1 s a 1 dia, e cada agente lendo sozinho (pedidos do dono).** Ferramenta dos agentes
  (`OpenBot/Shared/baleias/operar/multitempo.py`, fora do repositório): variação e z de 1 s, 5 s, 15 s, 1 min, 5 min e 15 min (velas de 1 s), 1 h, 4 h
  e 1 dia; preço contra a MM20 em 6 tempos; volume de 1 min; distância da máxima/mínima de 24 h; padrões gráficos de `lab/padroes_graficos.py` em
  15 min, 1 h e 4 h (a H45 mostrou que nenhum padrão passa sozinho: contexto, não gatilho). Cada agente varre o PRÓPRIO foco e anota num caderno a
  leitura de cada entrada; `operar.py aprender` cruza com as fechadas e mostra o que funcionou para ele. Manual de treino: `LEITURA_GRAFICOS.md`.
  Rotinas r5. Primeira rodada ao vivo (18/11 21:58 UTC) vista na tela do Demo Trading: RUNE, ZEC e AAVE vendidas com stop e alvo na corretora.
- 2026-11-18 (noite): **H64 — "perder de colher e ganhar de balde" (pedido do dono).** `lab/colher_balde.py`, pré-registrado antes de rodar.
  Parte T aprovada: a fatia de cada entrada = 2,5 × carteira ÷ US$ 10 (1,25× a 5×) × a carteira, 10× até 2,5× e 20× acima (as 4 margens cabem;
  perda para na margem). Soma das carteiras 60,93 → 63,40 antes do zero e 116,92 → 117,47 desde o zero. Entrou em `executor/robo_claude_nuvem.py`
  (`tamanho()`) e na conta de teste (com alavancagem rebaixada se a corretora recusar, ex.: KITE). Parte S reprovada: das 4 saídas com stop pequeno e
  lucro grande, a melhor (stop 1%, alvo 3%: +0,362%/aposta, G ÷ L 2,58) perdeu no bloco mais recente; vai como informação no manual dos agentes. 159 testes.
- 2026-11-19: **H65 e H66 — métodos de fora e busca em 4.896 variações (pedido do dono: "dobrar o capital").** H65 (fluxo agressor 15 min,
  momento semanal comprado/vendido, alavancagem pela volatilidade): reprovada. H66 (`lab/busca_dobrar.py`, numpy, treino/validação/reserva):
  reprovada na reserva (−0,246%/op). **Erro achado pelo controle aleatório:** o stop móvel simulado saía num preço que já tinha passado (entradas
  ao acaso davam +0,21%). Corrigido em `executor/stop_movel.py` (velas de 1 min com fechamento) e nos simuladores do lab; com a correção a R6
  (H52) cai para −0,021%. 160 testes.
- 2026-11-19: **H67 — gatilhos armados no executor** (`validar_gatilhos`, `armar`, `disparou`, `conferir_gatilhos` em
  `executor/robo_claude_nuvem.py`; níveis conferidos a cada ~3 min nas velas de 1 min, sem olhar o futuro). O dono não quer agente esperando
  rompimento: a capacidade fica no executor, mas a rotina dos agentes (r8) manda entrar JÁ, a mercado, quando a leitura dá. 162 testes.
- 2026-11-19: **agente Engenheiro criado** (pedido do dono): audita código, dados e prompts a cada 6 h, conserta bugs com teste e manda mudança
  de estratégia ao Laboratório; relatórios em `OpenBot/Shared/baleias/auditorias/`.
- 2026-11-19: **alvos maiores (dono):** alvo ≥ 3 × o stop e ≥ 1% imposto em `parametros()` da nuvem e na conta de teste; rotina r10 e manual; com alvo, o stop móvel arma na metade do caminho até ele.
- 2026-11-19 (tarde): **1ª auditoria do Engenheiro (pedido do dono: "agentes passivos e demorando; quero agilidade, operações constantes").**
  Relatório: `OpenBot/Shared/baleias/auditorias/2026-11-19.md`. Medido no ramo `estado` de 12:51 a 15:17 UTC: 31 decisões dos 4 agentes, só 5 com
  posição (todas MORPHO vendida), 0 gatilhos (H67); dos 155 descartes, 91 (58%) por "menos de 4 dos 6 tempos a favor" do REVISOR e 43 (27%) por
  confiança do v4 < 0,12. Atrasos: fila do OpenBot ("provider-cli-replaced") deixou TODOS os agentes 40 min sem rodar (14:01–14:41 UTC; o chefe 59 min);
  máquina desligada 18/11 23:12 → 19/11 12:51 UTC; da decisão à entrada na nuvem 2,8–4,4 min (rodada mediana de 173 s).
  **Corrigido:** (1) `executor/robo_claude_nuvem.py`: sem o preço da rodada (vela de 1 min) a entrada saía no fechamento de 15 min que já tinha passado;
  agora não entra e avisa; moeda fora das velas também avisa (antes pulava calada). Teste `test_sem_preco_da_rodada_nao_entra_no_fechamento_velho`.
  (2) Fora do repositório (pasta do chefe e `operar/`): decisão gravada pela metade no desligamento (`corrompidos/20261118-231404-decisao.json`, 0 byte)
  derrubava a rodada inteira do `testnet.py`; agora gravação atômica com fsync em `gravar.py`/`testnet.py`, leitura tolerante de decisão, leitura e
  recibo cortados, estado local corrompido recuperado da cópia do ramo, clone corrompido guardado de lado e refeito (`operar.py`); 4 testes novos
  na pasta do Engenheiro (`testes/test_ferramentas.py`). (3) ROTINA dos agentes r9 e rotina do chefe r9: postura ativa (entra a mercado na leitura
  mais forte; ficar de fora só com corte duro escrito), REVISOR só com cortes duros (alvo < 0,24%, |4 h| ≥ 15%, dado faltando, padrão confirmado
  contra). **Controle aleatório** do código da nuvem (4.000 entradas sorteadas em velas reais de 1 min): −0,117%, −0,100%, −0,117% e gatilhos −0,118%
  (≈ custo): sem olhar o futuro. Achado de estratégia mandado ao Laboratório: com alvo de 1,2% o stop móvel fecha 47% e só 3% chegam no alvo. 163 testes.
- 2026-11-19 (tarde): **H68 — o Caçador (pedido do dono: "um agente caçador… não opera, apenas caça as oportunidades e avisa os agentes que operam;
  leitura 24 h; criptos e memecoins").** Pré-registrada antes de ligar (7458b955). Na nuvem, `executor/cacador_nuvem.py` roda a cada rodada do
  `cerebro.yml`, em paralelo às outras etapas (limite de 150 s; 22,7 s na 1ª rodada), e grava só `dados/oportunidades.json`: todos os pares USDT à vista
  da Binance com volume ≥ US$ 500 mil (157 de 525 negociando; a API de futuros não responde na região da nuvem e não foi contornada), explosão de vela
  de 1/5/15 min (z do retorno ≥ 3 e volume ≥ 3×), tendência se formando (MM20 de 15 min, 1 h e 4 h), rompimento de 24 h, padrões confirmados de 15 min
  e 1 h, listagens novas, memecoins primeiro; memecoins de DEX (DexScreener, GeckoTerminal) só como informação, com filtros de segurança. Cada
  oportunidade traz lado, gatilho com números, invalidação, força 0–100 e sugestão de stop/alvo/prazo (alvo ≥ 3 × stop e ≥ 1%). **Juiz automático:**
  cada sinal é resolvido 15 e 60 min depois (−0,12%), com um evento de CONTROLE aleatório no mesmo instante; passa com ≥ 300, t ≥ 2,69 por hora,
  2 de 3 blocos e só se o controle der ≈ −0,12%. A nuvem passa a abrir posição de agente em moeda fora das velas do v4 quando tem o preço de 1 min
  da rodada. Agente **Caçador** no OpenBot (rotina de 5 min: `Shared/baleias/cacador/cacar.py`, confere de 1 s a 1 dia, publica em
  `Shared/baleias/oportunidades_cacador.jsonl` e avisa Treinador, Laboratório, Guardião e o chefe; estudo diário às 06:00). `operar.py escolher`
  mostra as oportunidades do Caçador primeiro e põe essas moedas na varredura do agente; ROTINA r11: aviso do Caçador = rodar a rotina na hora. 170 testes.
- 2026-11-19 (noite): **papel do v4 reestruturado (dono: "o v4 está barrando as entradas do Caçador; o engenheiro deve reestruturá-lo").** Medido antes
  (`lab/veto_v4.py`, descritivo; tabelas em `Shared/baleias/auditorias/veto_v4_*.json`): acerto ao vivo do v4 na vela de 15 min quase igual de < 0,05 a
  0,12 de confiança (56,9% · 56,1% · 59,3%) e só separado em ≥ 0,12 (67,0%, n 566; vigia, 7 dias). Replay de 2 dias das explosões de vela do Caçador
  (3.970 sinais, controle aleatório −0,124%): v4 fraco contra −0,112% × fraco a favor −0,241% em 15 min; ao vivo em 19/11 (226 sinais) o contrário
  (−0,327% × −0,012%). O veto fraco não tem efeito consistente e nenhum grupo paga o custo; as explosões perdem MAIS que o sorteio (−0,180% × −0,124%).
  **Mudou (ferramenta e prompt):** o v4 só pesa com confiança ≥ 0,12 em `operar.py` (rótulo "v4 sem confiança"; não fecha posição nem sugere entrada
  abaixo de 0,12), `chefe/universo.py` (entrada e manutenção 0,08/0,03 → 0,12), ROTINA r12, rotina do chefe r12, rotina do Treinador e
  LEITURA_GRAFICOS.md seção 4. A carteira do Laboratório mantém o método fixo (H69). Livros aplicados ao v4 em `Shared/baleias/LIVROS.md` seção 8.
  Modelo do v4 sem mudança (retreino ou regra nova = pré-registro no Laboratório).
- 2026-11-19 (noite): **prazo total na raspagem do chefe** (achado A16 da auditoria: a rodada das 16:20 UTC passou 27 min só no `universo.py`). `mesa/chefe/universo.py`
  (e a cópia viva na pasta do chefe) tem prazo de 360 s no total (`UNIVERSO_PRAZO_S`): as velas de 15 min param ~150 s antes do fim, e a corretora de teste, a LBank e a
  varredura de 1 s a 1 dia param no que couber. Estourou = a saída diz "⚠️ PARCIAL" com o que faltou; vale só o que foi lido por inteiro (rotina r12); menos de 50 moedas
  continua ERRO. O processo sai sem esperar leituras abandonadas. Teste `UniversoComPrazo`; conferido com prazo de 200 s: 105 de 114 moedas, 144 s, 59 MB. 171 testes.
- 2026-11-19 (noite, 21 UTC): **2ª auditoria do Engenheiro (rotina de 6 h).** Relatório: `OpenBot/Shared/baleias/auditorias/2026-11-19-21.md`. Medido de 15:00 a 21:00 UTC no ramo `estado`: 41 decisões dos 4 agentes, 31 com posição, 46 entradas novas (de manhã: 5 posições em 31 decisões); os 4 agentes e o chefe ficaram ~100 min sem decidir (18:45 → 20:25 UTC) pelo **limite de uso** da conta do provedor (`drain-scheduler` "usage-limit", 6 filas presas a partir de 18:46 UTC), depois de 106 min de máquina suspensa (16:52 → 18:38 UTC). Controle de entradas ALEATÓRIAS refeito no código atual (stop móvel armando na metade do alvo, alvo ≥ 3 × stop): −0,106% a −0,135% em 6 cenários (n 3.102–4.000; ≈ −custo, sem olhar o futuro). **Corrigido (A5 da 1ª auditoria):** `mesa/chefe/ler.py` (e a cópia viva na pasta do chefe) refaz o clone do ramo quando ele está corrompido (guarda o quebrado de lado); com o clone bom e sem rede só para com o erro, sem mexer no clone. Testes `CloneDoChefeQuebrado` (2; falham na versão antiga). 173 testes.
- 2026-11-19 (noite): **REGRAS.md, fonte única de regras (dono: "ainda há muitos conflitos de decisões entre os agentes e o Caçador, conflitos de regras").**
  `Shared/baleias/REGRAS.md` (cópia em `mesa/REGRAS.md`) junta postura, os 3 cortes duros (C1 sem dado, C2 15% em 4 h, C3 padrão confirmado contra no tempo do
  prazo), o papel do v4, stop/alvo/prazo, tamanho e o Caçador, marcando o que o código impõe. `regras.py` usa as mesmas funções da execução
  (`robo_claude_nuvem.parametros`, `stop_movel.armar_em`); `operar.py gravar` e `chefe/gravar.py` recusam entrada nova sem stop/alvo/prazo ou em C2/C3;
  `cacar.py publicar` ajusta stop/alvo/prazo como a execução e não avisa moeda que os operadores cortariam. 10 conflitos resolvidos (tabela no REGRAS.md):
  ex. corte "alvo < 0,24%" que nunca agia (a execução impõe ≥ 1%), Caçador recusando alvo < 3 × stop quando o teto de 5% obriga isso, três prazos
  diferentes (15–90 · 60–240 · por tempo gráfico → pelo alvo: 60/120/240, também em `cacador_nuvem.sugestao`), REVISOR do chefe diferente do dos
  operadores, Caçador exigindo "maioria dos 6 tempos". ROTINA r13 e rotinas do chefe, Treinador, Laboratório, Guardião e Caçador dizem "siga REGRAS.md".
  Placar desde 18/11 (fechadas): chefe simulado 28 op −0,540; conta de teste 22 op −0,953; Treinador 17 op −0,215; Laboratório 7 op +0,362; Guardião
  31 op +0,355 (soma −0,991). Nenhuma regra de estratégia mudou. 175 testes.
- 2026-11-20 (madrugada): **raspagem do chefe dizia "0 de 116 moedas" sem causa** (19/11 ~21:50 UTC, 3 rodadas seguidas; não reproduziu depois: 118/118).
  `velas()` de `mesa/chefe/universo.py` engolia qualquer erro de rede e devolvia lista vazia, sem nova tentativa, e o ERRO saía antes do aviso de PARCIAL.
  Agora: até 3 tentativas por moeda (para logo em HTTP 418/429, limite da Binance), motivo de cada falha contado no ERRO e no PARCIAL ("N × TimeoutError,
  N × HTTP 429, N × prazo da rodada"), e as velas têm sempre pelo menos 2 min do prazo. Teste `UniversoSemErroEngolido`. 176 testes.
- 2026-11-20 (madrugada): **H71 — uma conta de demonstração por operador (dono: "vamos dar uma carteira para cada um").** Pré-registrada antes de qualquer
  ordem (27cb4907). `mesa/operar/corretora.py` (cópia viva em `Shared/baleias/operar/`): o mesmo motor do testnet do chefe (concilia a conta, ordem a
  mercado, stop e alvo como gatilhos reduce-only guardados na corretora, stop recusado = fecha na hora, stop móvel por rodada, prazo, posição/ordem
  desconhecida fechada, trava de arquivo, carteira própria de US$ 10 com o tamanho H64 e as regras do REGRAS.md §5), grava só `dados/corretora_<agente>.json`.
  Laboratório → Gate Futures TestNet (`api-testnet.gateapi.io`; leitura validada: 1.000 USDT de demonstração, sem posição). Treinador → Bybit Demo e
  Guardião → BingX VST ficam TRAVADOS (a chave salva da Bybit é da conta real e é inválida na demo; a BingX recusa o IP); a ferramenta só fala com o
  endereço de demonstração e PARA em qualquer outro. Chaves só no cofre do OpenBot, lidas na hora, nunca impressas. ROTINA r14 (passo 5) e REGRAS §6.
  Testes `CorretoraDemoH71` com corretora falsa. 180 testes.
- 2026-11-20 (13 UTC): **3ª auditoria do Engenheiro (rotina de 6 h; rodada das 03:00 atrasada pela máquina suspensa).** Relatório:
  `OpenBot/Shared/baleias/auditorias/2026-11-20-13.md`. De 19/11 21:00 a 20/11 13:30 UTC a máquina ficou suspensa 22:53 → 02:48 e 03:17 → 13:14 UTC
  (~14 h); antes disso, o **limite de uso** da conta do provedor parou os 4 agentes e o chefe às 22:02 UTC (A17 de novo). 17 decisões, 19 entradas novas
  nas carteiras simuladas. Primeira rodada da Gate (H71) às 13:26 UTC: conciliou, nada a abrir (decisão do Laboratório sem posição), publicou.
  **Corrigido (A22):** nos dois motores de corretora (`mesa/operar/corretora.py` e `mesa/chefe/testnet.py`, com as cópias vivas), erro de rede logo
  depois da ordem a mercado executar (leitura das taxas na Gate, consulta da ordem na Binance) escapava como "entrada falhou": a posição ficava na
  corretora fora do estado e SEM stop até a próxima rodada, que a fechava como desconhecida; e o estado só era salvo no fim da rodada (um erro depois
  de uma entrada perdia a posição). Agora a posição entra no estado assim que a ordem executa (taxa de entrada não lida = lida na saída, não zero),
  a consulta da ordem tenta de novo e, sem confirmação, avisa com 🚨, e a rodada salva o estado mesmo quando cai. Testes `CorretoraDemoH71` (+2) e
  `MotorDoChefeComRedeFalhando` (3); os 5 falham na versão antiga. 185 testes.
- 2026-11-20: **Bybit Demo (Treinador) libera as ordens sozinha quando o saldo de demonstração for > 0** (chave da Demo Trading trocada pelo dono; leitura OK em
  `api-demo.bybit.com`). Com saldo 0 ou sem conseguir ler o saldo, `corretora.py treinador` PARA sem enviar nada; endereço que não é o da demo PARA.
  A ordem a mercado espera a execução no histórico (até 5 consultas). Relógio acertado pelo horário da Bybit (estava 0,6 s adiantado; um pedido deu
  "10002 server timestamp"), janela de 20 s e nova tentativa no 10002. BingX segue travada (IP). Testes `BybitLiberaComSaldo`. 188 testes.
- 2026-11-20: **conta de teste do chefe reabria a moeda que o stop acabara de fechar** (achado da rotina do chefe). A lista "já entrou nesta decisão" era tirada
  das abertas DEPOIS da conciliação; com o stop executado, a moeda sumia dela e voltava na mesma rodada, com stop padrão de −3,3% e sem alvo nem prazo.
  Agora, em `mesa/chefe/testnet.py` e em `mesa/operar/corretora.py`: moeda que saiu por stop, alvo ou prazo depois da decisão não reentra até uma decisão
  nova (a inversão de lado pedida pela decisão continua valendo), e entrada sem `stop_pct`, `alvo_pct` e `max_min` na decisão não acontece (REGRAS §5;
  o stop padrão saiu). **Relógio:** BingX VST recusava por horário ("109400"; máquina 3,85 s atrás, NTP desligado): BingX e Gate passam a usar o horário
  do servidor delas (BingX com recvWindow de 20 s e nova tentativa no 109400); a Binance já usava. BingX validada (leitura OK, 100.000 VST) e liberada
  com a mesma regra da Bybit (ordens só com saldo de demonstração > 0). Testes `SemReentradaESemParametroPadrao` (falham no código antigo). 191 testes.
- 2026-11-20: **brecha no conserto de c8b4c2f5** (achado do chefe): o stop de NEAR executou às 14:21:26 UTC, entre a leitura (14:20) e a publicação da decisão
  (14:23:35); a regra comparava com a hora da publicação e NEAR reabriu. Agora `chefe/gravar.py` e `operar.py gravar` gravam `leitura_t` (hora da leitura/raspagem)
  na decisão, e `testnet.py`/`corretora.py` não reabrem moeda que saiu por stop, alvo ou prazo depois dela (sem `leitura_t`: decisão − 15 min). 192 testes.
- 2026-11-22: **painel: escapar dados da nuvem na atividade dos agentes**. Os nomes de moedas e lados em entradas/posições eram inseridos como HTML sem escape; agora usam `esc()`. Teste de regressão na seção de atividade; 192 testes.
- 2026-11-23 (21 UTC): **4ª auditoria do Engenheiro.** Relatório: `OpenBot/Shared/baleias/auditorias/2026-11-23-21.md`. A máquina ficou parada de 23/11 01:00 a
  21:44 UTC (diário do sistema sem nenhuma linha) e reiniciou às 21:56 UTC: **0 decisões dos 4 agentes nas últimas 6 h**; Treinador e Guardião sem decidir desde
  22/11 00:38 UTC, Claude desde 21:41 e Laboratório desde 21:18. Conta de teste: as 4 posições de 22/11 21:42 (prazo 60 min) ficaram 24 h abertas, protegidas
  pelos gatilhos guardados na corretora; na volta, 3 stops (−0,48) e 1 alvo (+0,37). **Corrigido:** (1) o agendador do GitHub deixou o cérebro 3h20
  (11:03 → 14:23 UTC) e 2 h (20:05 → 22:00 UTC) sem rodada; agora cada rodada dispara a seguinte (`gh workflow run`, `actions: write`, não dispara se
  cancelada à mão). (2) `lab/juizo_h70.py`: erro de rede permanente deixava `baixar()` em laço infinito; agora desiste da fonte depois de 4 falhas seguidas
  (a moeda conta como "sem velas", não como zero). O juiz da H70 morreu no reinício (o registro e o cache estavam em /tmp); rodado de novo, mesmo critério,
  1 tentativa. Testes `CerebroAcordaAProxima` e `JuizoH70SemLacoInfinito` (falham no código antigo). 195 testes.
- 2026-11-24 (03 UTC): **5ª auditoria do Engenheiro.** Relatório: `OpenBot/Shared/baleias/auditorias/2026-11-24-03.md`. A máquina parou de novo de 23/11 23:42
  a 24/11 03:12 UTC (diário sem nenhuma linha, mesmo boot): nesse intervalo nenhum agente decidiu; antes e depois, os 4 decidiram a cada 3–30 min. Conta de
  teste: 7 saídas (5 stops guardados na corretora, 2 fechadas por saírem da lista), patrimônio US$ 7,85 → 7,16, sem 🚨 nem BLOCKED. Código das regras R2
  (09a1f1f5) auditado sem bug. **Corrigido:** `mesa/operar/ROTINA.md` (e a cópia viva) ainda dizia "versão R1" das REGRAS; agora R2. Teste
  `RotinaCitaARegraEmVigor` (a rotina cita só a versão em vigor; falha no texto antigo). 196 testes.
- 2026-11-24 (20 UTC): **6ª auditoria do Engenheiro (rodada das 15:00 UTC atrasada pela máquina congelada).** Relatório:
  `OpenBot/Shared/baleias/auditorias/2026-11-24-20.md`. A máquina virtual congelou de 03:26 a 20:00 UTC (16h34; diário do sistema sem nenhuma linha e
  "Clock change detected" na volta), a 3ª parada em 2 dias: nenhum agente decidiu nesse tempo. Conta de teste: DOGE e TRUMP (decisão de 03:19, prazo
  120 min) ficaram abertas durante a parada, protegidas pelo stop guardado na corretora; na volta, 2 stops (−0,12); patrimônio US$ 7,16 → 7,04.
  **Corrigido:** em `mesa/operar/operar.py` (e a cópia viva), `atualizar()` tratava "fatal: unable to access" (rede caída) como clone corrompido: o clone
  bom do Treinador foi para o lado às 20:08 UTC (`git fsck` limpo) e a rodada clonou de novo pela rede ruim. Agora, como em `mesa/chefe/ler.py`, só refaz
  o clone quando ele não responde a comandos locais; com o clone bom, a rodada para com o erro. Testes `CloneDoAgenteSemRede` (2; o da rede falha no
  código antigo). 199 testes.
