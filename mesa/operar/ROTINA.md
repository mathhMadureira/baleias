# Rodada de operação de um agente da mesa Baleias (H62: operar livre, estilo scalper) — a cada 15 min · versão da rotina: r14

Você opera a SUA carteira simulada de US$ 10 na mesa Baleias (execução na nuvem) e a SUA conta de demonstração (passo 5). Nada de dinheiro real;
nunca mande ordem na conta de teste da Binance, que é só do agente Baleias, nem na conta de outro agente. <agente> = o seu id: treinador, laboratorio ou guardiao. VOCÊ decide moeda, lado, stop, alvo e prazo.

REGRAS: siga /home/servidor-de-producao/OpenBot/Shared/baleias/REGRAS.md (fonte única desde 19/11, versão R2). Postura ativa, os 3 cortes duros
(R2, 23/11: só C1 sem dado corta; C2 e C3 viram informação no motivo), o papel do v4, stop/alvo/prazo, tamanho e Caçador estão só lá; esta rotina não os repete.
Leia o REGRAS.md no começo de cada rodada. A ferramenta (operar.py gravar) recusa o que fere as regras marcadas [ferramenta].
Aviso do Caçador ("🔭 Caçador — ...") por mensagem = rode esta rotina NA HORA (passos 1 a 5) e confira a moeda na SUA leitura.

0. Leia REGRAS.md e /home/servidor-de-producao/OpenBot/Shared/baleias/LEITURA_GRAFICOS.md (o treino de leitura de gráficos). LIVROS.md e CARTAS.md
   só se precisar: a rodada inteira deve caber em ~5 min. Você opera SOZINHO: a sua raspagem, a sua varredura e o seu caderno.
   Ferramenta com ERRO ou sem o retrato do mercado = nenhuma entrada nova nesta rodada; as abertas seguem com stop e alvo.
1. cd /home/servidor-de-producao/OpenBot/Shared/baleias/operar && python3 -I operar.py ler <agente>   → mercado e a sua carteira.
1b. python3 -I operar.py aprender <agente>   → o seu caderno: o que funcionou PARA VOCÊ nas suas operações fechadas.
2. RASPAGEM: python3 -I operar.py escolher <agente>   → primeiro as oportunidades do Caçador; depois as moedas (v4 com confiança, movimento de 1 h,
   memecoins), as MELHORES CARTEIRAS (H63) e a VARREDURA do seu foco de 1 s a 1 dia com padrões gráficos. Leia cada moeda de cima para baixo
   (LEITURA_GRAFICOS.md, seção 1).
3. Decida e escreva rodadas/proposta_<agente>.json:
   - "posicoes": de 0 a 8, a lista COMPLETA do que deve ficar aberto (o que não estiver nela fecha). Cada uma: "moeda" (termina em USDT), "lado"
     (compra/venda), "motivo" (números: tempos a favor, padrão, carteiras, v4 só se confiança ≥ 0,12, aviso do Caçador, e o que está CONTRA),
     "stop_pct" (obrigatório em entrada nova); "alvo_pct" (0,2% a 50%), "max_min" e "movel": false são opcionais (REGRAS.md §5, R2).
   - "leitura" (números do passo 1 e 2), "licao" (verificável: moeda, lado, resultado; com 5+ fechadas, p, G, L e E = p·G − (1−p)·L),
     "fechar": [], "motivos_fechar": {}, "mensagens": no máximo 1 para a sala, curta, com números. Sem "ordens" e sem "respostas".
   - opcional "gatilhos" (H67, até 6): {moeda, lado, "acima" OU "abaixo": preço, stop_pct, alvo_pct, max_min, validade_min 5–240, motivo}.
   - "descartadas": até 5 das melhores moedas que você NÃO pegou, cada uma {"moeda", "motivo"} com o motivo (C1 com o número, "vaga ocupada" ou a sua leitura)
     ou "vaga ocupada"; e "versao_rotina": "r14".
4. python3 -I operar.py gravar <agente> rodadas/proposta_<agente>.json   → publica SÓ dados/decisao_<agente>.json. "DECISÃO INVÁLIDA": corrija
   (no máximo 3 tentativas). "FALHOU" 3 vezes: escreva BLOCKED e o motivo para o dono.
5. A SUA CONTA DE DEMONSTRAÇÃO (H71; dinheiro fictício): depois do "ok" do passo 4, rode python3 -I corretora.py <agente>  → concilia a sua conta na
   corretora (laboratorio: Gate Futures TestNet; treinador: Bybit Demo; guardiao: BingX VST), executa a SUA decisão com ordem a mercado, stop e alvo
   guardados na corretora, e grava SÓ dados/corretora_<agente>.json. Linha começando com "PARE" porque a corretora ainda não foi validada: siga sem
   ela (não é erro da rodada; diga no relato só na primeira vez). "PARE" por outro motivo (endereço, BINANCE_REAL): não rode de novo e avise o dono.
   Linha com 🚨: avise o dono. Nunca rode com outro <agente> que não o seu.
Relato: posições iguais às da sua decisão anterior e nada novo na corretora → não escreva nada (openbot.routine_no_update). Se mudaram, no máximo
2 linhas: o que entra e sai (moeda, lado, alvo/stop), a sua carteira e, na corretora, as ordens com os ids do stop e do alvo. Nenhum número inventado. Nunca imprima chave, senha ou token. Nunca commite no ramo master.
