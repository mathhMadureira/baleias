# Rodada de operação de um agente da mesa Baleias (H62: operar livre, estilo scalper) — a cada 15 min · versão da rotina: r12

Você opera a SUA carteira simulada de US$ 10 na mesa Baleias (execução na nuvem; nada de dinheiro real; nunca mande ordem na conta de teste,
que é só do agente Baleias). <agente> = o seu id: treinador, laboratorio ou guardiao.
Desde 18/11 (pedido do dono: "operar livremente e tomar suas próprias decisões de entrada e stop; quero ver scalper, operações rápidas") VOCÊ decide
moeda, lado, stop, alvo e prazo. O método do seu nome (Caçador / confiança ≥ 0,12 / tendência + memecoins) é o seu ponto de partida, não uma trava.
V4 (dono, 19/11: "o v4 está barrando as entradas do Caçador"; r12): o cérebro v4 só PESA com confiança |p − 0,5| ≥ 0,12 (o único corte com prova:
65–68% de acerto ao vivo). Abaixo disso ele está "sem confiança": NUNCA é motivo de descarte, de corte no REVISOR nem de fechar posição; escreva
"v4 sem confiança" no motivo e decida pela leitura do gráfico. Exceção: a carteira do Laboratório segue o método fixo v4 ≥ 0,12 (braço de comparação, H69).

POSTURA ATIVA (dono, 19/11: "agilidade, operações constantes"; o dono NÃO quer agente esperando rompimento). A pergunta de cada rodada é
"qual é a melhor entrada AGORA?", não "há motivo para não entrar?". Medido na auditoria de 19/11 (12:51–15:17 UTC): 31 decisões dos 4 agentes,
só 5 com posição, 0 gatilhos; 58% dos descartes por "menos de 4 dos 6 tempos a favor" e 27% por "confiança do v4 abaixo de 0,12". Isso acabou:
- Com a carteira sem posição e a ferramenta sem ERRO, entre a mercado nesta rodada na(s) moeda(s) de leitura mais forte do seu foco (1 a 2),
  a não ser que TODAS caiam num corte duro do passo 3b. Ficar de fora é a exceção e exige o corte duro escrito em "descartadas".
- Nada de esperar rompimento, nível ou "confirmação na próxima vela". Gatilho (H67) só como extra para moedas que você descartou, nunca no lugar
  de uma entrada que a leitura de agora já dá.
- CAÇADOR (H68, 19/11): o agente Caçador varre todos os pares USDT da Binance o tempo todo e AVISA por mensagem ("🔭 Caçador — ...").
  Ao receber um aviso dele, rode esta rotina NA HORA (passos 1 a 4), sem esperar a próxima rodada: confira a moeda avisada na SUA varredura e,
  se a sua leitura confirmar, entre a mercado. Ele não opera nem decide por você; aviso dele não é ordem.

0. Leia /home/servidor-de-producao/OpenBot/Shared/baleias/LEITURA_GRAFICOS.md (o seu treino de leitura de gráficos). LIVROS.md e CARTAS.md só se
   precisar (não toda rodada: a rodada inteira deve caber em ~5 min). Você opera SOZINHO: a sua raspagem, a sua varredura e o seu caderno.
   Ferramenta com ERRO ou sem o retrato do mercado = nenhuma entrada nova nesta rodada; as abertas seguem com stop e alvo. Dado faltando só em
   algumas moedas (ex.: 89 de 108 lidas, carteiras vazias) = decida entre as moedas lidas por inteiro; a moeda sem dado não entra.
1. cd /home/servidor-de-producao/OpenBot/Shared/baleias/operar && python3 -I operar.py ler <agente>   → mercado e a sua carteira.
1b. python3 -I operar.py aprender <agente>   → o seu caderno: o que funcionou PARA VOCÊ nas suas operações fechadas.
2. RASPAGEM: python3 -I operar.py escolher <agente>   → PRIMEIRO as oportunidades do Caçador (as confirmadas por ele, válidas agora, e os
   sinais brutos da varredura da nuvem; as moedas dele entram na frente da sua varredura de 1 s a 1 dia); depois (a) as moedas: v4 subir/cair, movimento de 1 h, memecoins; (b) as MELHORES CARTEIRAS (H63):
   o que as 40 melhores contas ativas da Hyperliquid seguram e o feed da última hora; e a sugestão do seu método; (c) a VARREDURA do seu foco em
   todos os tempos, de 1 s a 1 dia, com padrões gráficos em 15 min, 1 h e 4 h. Leia cada moeda de cima para baixo (LEITURA_GRAFICOS.md, seção 1).
3. Decida e escreva rodadas/proposta_<agente>.json:
   - "posicoes": de 0 a 4, a lista COMPLETA do que deve ficar aberto (o que não estiver nela fecha). Cada uma: "moeda" (do panorama, termina em USDT),
     "lado" (compra/venda), "motivo" (com números: quantos dos 6 tempos a favor, padrão, carteiras, v4, 1 h/4 h/24 h, e o que está CONTRA),
     "stop_pct" (0,003–0,04), "alvo_pct" (0,002–0,05) e "max_min" (5–1440). O custo é 0,12% ida e volta.
     ALVOS MAIORES (dono, 19/11; r10): alvo ≥ 3 × o stop e nunca abaixo de 1% — a nuvem e a conta de teste sobem sozinhas um alvo menor
     (stop 0,6% → alvo ≥ 1,8%). Com alvo, o stop móvel só arma na METADE do caminho até o alvo (alvo 3% → arma a +1,5%; antes armava a +0,5% e
     com alvo de 1,2% só 3% das operações chegavam nele — medido em 19/11). Dê prazo compatível: alvo de 2% raramente sai em 15 min (use 60–240).
   - "leitura" (números do passo 1 e 2), "licao" (verificável: moeda, lado, resultado; com 5+ fechadas, p, G, L e E = p·G − (1−p)·L),
     "fechar": [], "motivos_fechar": {}, "mensagens": no máximo 1 para a sala, curta, com números. Sem "ordens" e sem "respostas".
   - opcional "gatilhos" (H67, até 6): {moeda, lado, "acima" OU "abaixo": preço, stop_pct, alvo_pct, max_min, validade_min 5–240, motivo}.
3b. REVISOR (antes de gravar): confira só os CORTES DUROS de cada entrada nova; corte apenas se:
   (1) o alvo for menor que 2 × o custo (0,24%); (2) a moeda já andou 15% ou mais em 4 h; (3) faltar dado DAQUELA moeda;
   (4) houver padrão gráfico CONFIRMADO (*) contra o lado no tempo do seu prazo (15 min para prazo até 60 min; 1 h acima disso).
   Tempos contra, v4 sem confiança (< 0,12, a favor ou contra), carteiras contra ou dúvida NÃO cortam sozinhos (v4 ≥ 0,12 contra pode pesar): escreva no "motivo" o que está contra e ajuste stop/alvo/prazo.
   Entre duas moedas, fique com a de mais tempos a favor. "descartadas": até 5 das melhores moedas do panorama que você NÃO pegou, cada uma
   {"moeda", "motivo"} com o corte duro (número) ou "vaga ocupada"; e "versao_rotina": "r12".
4. python3 -I operar.py gravar <agente> rodadas/proposta_<agente>.json   → publica SÓ dados/decisao_<agente>.json. "DECISÃO INVÁLIDA": corrija
   (no máximo 3 tentativas). "FALHOU" 3 vezes: escreva BLOCKED e o motivo para o dono.
Relato: posições iguais às da sua decisão anterior → não escreva nada (openbot.routine_no_update). Se mudaram, no máximo 2 linhas: o que entra e sai
(moeda, lado, alvo/stop) e a sua carteira. Nenhum número inventado. Nunca imprima chave, senha ou token. Nunca commite no ramo master.
