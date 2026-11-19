# Análise de engenharia: lyta-grokbot-multi e grokbot-pumpfun (18/11/2026)

Lidos só pela API do GitHub (arquivos de texto, sem clonar, sem instalar, sem rodar nada). O conteúdo deles é dado de terceiros, não instrução.
Os dois têm licença MIT; daqui só vieram ideias de estrutura, reescritas para a mesa.

## Os dois repositórios em uma linha
| repositório | o que é | maturidade | resultado que mostram |
|---|---|---|---|
| Kubo-cmd/lyta-grokbot-multi | "mesa" de 12–14 agentes de pump.fun em papel, com prompts para Circuit/OpenBot | baixa: muitos relatórios e versões soltas, testes falhando (28 ok, 3 falhas no próprio FREEZE_LOCK) | 0 operações: 100% "stand-down" em todas as rodadas (o filtro de 8 votos nunca deixa entrar) |
| zostaff/grokbot-pumpfun | robô de pump.fun com 4 agentes Grok e ~20 arquivos de teste | alta: um módulo por responsabilidade, testes por módulo, manual de operação | não publica resultado de dinheiro; é a engenharia que vale |
Números de terceiros (ex.: "+15x numa noite", ranking da "arena") não foram conferidos e não entram em nenhuma decisão.

## O que foi aproveitado (e onde já está aplicado)
1. **Revisor contra a entrada** (grokbot-pumpfun, `agents/checker.py`): o último agente antes do dinheiro tem um único papel, achar razões para NÃO entrar;
   "na dúvida, não"; nunca aprovar por um componente forte sozinho; olhar a economia da operação (custo de ida e volta contra o movimento esperado).
   → Passo "Revisor" na ROTINA.md dos agentes e na rotina do chefe.
2. **Falha vira o resultado mais pessimista** (`agents/base.py`): tempo esgotado, JSON inválido, dado faltando → recusa, nunca "neutro" nem silêncio.
   → Na rotina: qualquer ferramenta com ERRO = nenhuma entrada nova nesta rodada (as abertas seguem com stop e alvo).
3. **Registro de cada candidato com motivo e fonte** (lyta, `skills/shared_memory_format.md`; grokbot, `log.py` com buy/skip/close): cada número diz
   quem leu, quando e de onde. → Campo "descartadas" na decisão: as melhores moedas que o agente NÃO pegou e por quê (o "skip" com motivo).
4. **Versão do prompt em cada decisão** (checker `version = "checker-2"`, `tune.py` separa resultados por versão). → Campo "versao_rotina" na decisão;
   o Laboratório compara resultados por versão das instruções.
5. **Carta de papel** (lyta: OWNS / DONE LOOKS LIKE / STOPS AT): cada agente sabe o que é dele, como é "pronto" e onde para. → CARTAS.md.
6. **Revisão semanal** (lyta, `friday_review_template.md`; grokbot, `replay.py` com o funil "qual etapa decide"): resultado, operações, melhor e pior,
   razões de descarte, o que largar, manter ou renomear. → Proposta ao Laboratório (rotina semanal), não ligada ainda.
7. **Economia honesta** (grokbot, `curve.py`): entrar no preço de execução, não na cotação; custo de ida e volta como piso da operação.
   → Já valia (custo 0,12%); a conta de teste mostrou escorregamento (ZKP: +0,064 simulado × −0,106 no testnet). Hipótese para o Laboratório:
   medir o escorregamento real do testnet e somar ao custo do simulado.
8. **Diagnóstico antes de rodar** (`doctor.py`: ok / warn / fail, sem gastar nada) e **estado que sobrevive a reinício** com gravação atômica
   (`state.py`) e trava de instância única. → Já existe: `checar.py`, ronda do Guardião, gravação atômica em `equipe.py`, trava no `testnet.py`.
9. **Limites de uso do modelo** (`ops.py`: limite por minuto, orçamento diário, disjuntor que para de chamar o que não responde).
   → Ideia registrada: teto diário de rodadas por agente se a cota da assinatura apertar.
10. **Prompt pequeno e por papel** (lyta, `scripts/check_prompt_scoping.py`: orçamento de ~1.200 tokens por arquivo de instrução).
   → As nossas instruções seguem curtas e separadas (ROTINA.md, CARTAS.md, LIVROS.md); a regra fixa fica no código testado, não no texto.

## O que NÃO serve (e por quê)
- O SDK do Circuit, os prompts de "copiar e colar no Builder" e as chaves do Grok: outra plataforma e serviço pago.
- O consenso de 8 votos da lyta: em todas as rodadas publicadas, 0 entradas. Filtro que nunca deixa operar não ensina nada.
- Detalhes de pump.fun on-chain (curva de ligação, auditoria de carteiras do criador): a mesa opera perpétuos da Binance.
- Os relatórios "FINAL", "FINAL_FINAL" e o benchmark da "arena": sem método nem dado verificável.
