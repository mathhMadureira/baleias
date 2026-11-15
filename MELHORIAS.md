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
