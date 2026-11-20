# REGRAS da mesa Baleias — fonte única (versão R1, 19/11/2026)

Pedido do dono (19/11): "ainda há muitos conflitos de decisões entre os agentes e o Caçador, conflitos de regras". Este é o ÚNICO lugar das regras
de entrada, corte, stop, alvo e prazo. Rotinas, ROTINA.md, a rotina do chefe, o Caçador e o manual LEITURA_GRAFICOS.md mandam seguir este arquivo
e não repetem as regras. A opinião continua livre: cada operador decide sozinho (H62). Mudança de estratégia só com pré-registro no Laboratório,
e aí este arquivo muda junto com o código (`/home/servidor-de-producao/OpenBot/Shared/baleias/regras.py`).

Marcas: **[código]** = a execução impõe (escrever outro valor não muda nada) · **[ferramenta]** = `operar.py gravar`, `chefe/gravar.py` e
`cacar.py publicar` recusam · **[conduta]** = o agente aplica.

## 1. Quem faz o quê
- Operadores (Treinador, Guardião, chefe Baleias): decidem moeda, lado, stop, alvo e prazo. O método do nome é ponto de partida, não trava.
- Laboratório: método fixo, v4 com confiança ≥ 0,12 no lado do regime (braço de comparação da H69). É a única exceção às seções 2 e 4.
- Caçador: não opera. Só avisa oportunidades que passam nestas MESMAS regras (seção 7). Aviso dele não é ordem.

## 2. Postura [conduta]
- Ativa: a pergunta é "qual a melhor entrada AGORA?". Sem posição e sem ERRO de ferramenta, entre a mercado na leitura mais forte (1 a 2 moedas).
  Ficar de fora só por um corte duro da seção 3, escrito em "descartadas".
- Não espere rompimento nem confirmação na próxima vela. Gatilho (H67) só como extra para moeda descartada.
- Aviso do Caçador = rodar a rotina de operar na hora e conferir na própria leitura.
- Entre duas moedas que passam nos cortes, fique com a de mais tempos a favor.

## 3. Cortes duros — os ÚNICOS motivos para não entrar em moeda nova
| corte | regra | quem confere |
|---|---|---|
| C1 | falta dado daquela moeda (sem leitura de 1 s a 1 dia / sem preço) | [conduta]; [ferramenta] no Caçador |
| C2 | a moeda já andou 15% ou mais em 4 h (para cima ou para baixo) | [ferramenta] quando a moeda está na varredura anexada |
| C3 | padrão gráfico CONFIRMADO (*) contra o lado, no tempo do prazo: 15 min se o prazo é de até 60 min; 1 h acima | [ferramenta] idem |
Nada mais corta: tempos contra, v4 sem confiança, carteiras contra, dúvida ou alvo "pequeno" vão escritos no motivo.
Posição já aberta não é cortada por C1–C3 (sai por stop, alvo, prazo ou pela decisão do agente).

## 4. v4
- Só pesa com confiança |p − 0,5| ≥ 0,12. Abaixo disso é "sem confiança": nunca descarta, nunca corta, nunca fecha posição [código em
  `operar.py` e `chefe/universo.py`: sugestões e manutenção usam 0,12].
- v4 ≥ 0,12 contra o lado pode pesar na decisão (opinião, não corte duro). Medido em 19/11: o veto fraco não teve efeito consistente
  (`auditorias/veto_v4_*.json`).

## 5. Stop, alvo e prazo [código: `executor/robo_claude_nuvem.parametros`, o mesmo na conta de teste]
- Toda entrada NOVA traz `stop_pct`, `alvo_pct` e `max_min` [ferramenta].
- stop: 0,3% a 4% (valor fora é encostado no limite).
- alvo efetivo = mín(5%, máx(alvo pedido, 3 × stop, 1%)). Com stop acima de 1,67% o alvo fica em 5%, que é menos de 3 × o stop.
- prazo: 5 a 1.440 min. Prazo sugerido pelo alvo efetivo (operadores e Caçador iguais) [conduta; código na sugestão do Caçador]:
  alvo até 1,5% → 60 min · até 3% → 120 min · acima de 3% → 240 min.
- Stop móvel [código, `executor/stop_movel.armar_em`]: arma quando o lucro chega a máx(0,5%, alvo ÷ 2) e devolve no máximo 30% do pico (guarda 70%).
- Custo: 0,06% por lado (0,12% ida e volta) [código].

## 6. Tamanho e carteira [código]
- Fatia H64: nocional = (2,5 × carteira ÷ US$ 10, entre 1,25 e 5) × carteira; alavancagem 10× até 2,5× e 20× acima.
- Até 4 posições, uma por moeda; piso de US$ 5 (abaixo = eliminado); meta do dia US$ 12.
- Conta de teste (só o chefe): a moeda tem de existir nos futuros do testnet e o nocional mínimo da corretora não pode passar de 1,5 × a posição;
  senão a conta de teste não entra (a carteira simulada do chefe entra). [conduta] O chefe escolhe, de preferência, moedas marcadas ✓ testnet
  no `universo.py`, para as duas carteiras andarem juntas.

- Contas de demonstração dos operadores (H71) [código: `operar/corretora.py`]: cada agente executa a PRÓPRIA decisão na própria conta (Laboratório →
  Gate Futures TestNet; Treinador → Bybit Demo; Guardião → BingX VST), com a carteira própria de US$ 10 e as mesmas regras desta página (stop e alvo
  guardados na corretora; stop recusado = fecha na hora; lote mínimo > 1,5 × a posição = não entra). A ferramenta só fala com o endereço de
  demonstração e PARA em qualquer outro; corretora não validada fica travada (hoje: Bybit e BingX).

## 7. Caçador [ferramenta: `cacar.py publicar`]
- Publica só o que tem leitura de 1 s a 1 dia (C1) e passa em C2 e C3, com stop, alvo e prazo já ajustados pela seção 5.
- Avisa os operadores só com força ≥ 70 ou com o sinal aprovado no juiz H68; validade de 15 a 60 min; a mesma moeda e lado no máximo 1 vez em 30 min.

## 8. Não é regra (informação)
- As tabelas medidas do manual (LEITURA_GRAFICOS.md, seção 5), o placar do juiz H68 e o caderno de cada agente.

## Conflitos resolvidos nesta versão (R1)
| # | onde estava | uma dizia | a outra dizia | agora |
|---|---|---|---|---|
| 1 | ROTINA r12 passo 3b × execução | corta alvo < 0,24% | a execução já sobe o alvo para ≥ 1% (o corte nunca age) | removido; §5 |
| 2 | ROTINA (alvo 0,2–5%) × execução | aceita alvo de 0,2% | alvo efetivo ≥ 1% e ≥ 3 × stop | §5 diz o efetivo |
| 3 | `cacar.py` × execução | recusa alvo < 3 × stop | com stop > 1,67% o teto de 5% obriga alvo < 3 × stop (aviso válido recusado) | o Caçador ajusta pela mesma função da execução |
| 4 | prazo: manual × ROTINA × Caçador | 15–90 min · 60–240 min · 60/120/240 pelo tempo gráfico | — | §5: prazo pelo alvo (60/120/240) |
| 5 | REVISOR dos operadores × do chefe | padrão confirmado contra no tempo do prazo | padrão forte contra E menos de 4 dos 6 tempos | §3 C3 para todos |
| 6 | Caçador × operadores | confirma só com a maioria dos 6 tempos a favor | os operadores não exigem isso desde a r9 | §7: as mesmas C1–C3 |
| 7 | Caçador × REVISOR | avisa explosão e rompimento depois de alta forte | corta a moeda que andou 15% em 4 h | o Caçador não avisa o que C2 cortaria |
| 8 | chefe simulado × conta de teste | a decisão entra no simulado | a conta de teste recusa moeda fora do testnet ou com nocional mínimo > 1,5 × a posição | §6: escolher moedas ✓ testnet |
| 9 | regra "alvo ≥ 3 × stop" × posição sem stop | o alvo depende do stop | sem stop_pct a execução não aplica o 3 × | §5: stop, alvo e prazo obrigatórios em entrada nova |
| 10 | rotina do Guardião × ROTINA | "método fixo" | "ponto de partida, não trava" | §1 |
