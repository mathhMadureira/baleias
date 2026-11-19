# Como ler o gráfico de cada moeda (manual de treino dos agentes da mesa Baleias, 18/11/2026)

Fontes: os 10 livros (LIVROS.md), a cartilha da mesa (docs/CARTILHA_ROBO_CLAUDE.md) e o que o laboratório já mediu (lab/PROTOCOLO_LAB.md).
Cada agente lê SOZINHO: a sua raspagem (`operar.py escolher`), a sua varredura (o seu foco) e o seu caderno (`operar.py aprender`). Não copie a posição de
outro agente; se chegar à mesma moeda, que seja pela sua leitura.

## 1. De cima para baixo (um tempo de cada vez, nesta ordem)
1. **1 dia e 4 h — o pano de fundo.** Preço acima ou abaixo da média de 20 velas (↑/↓ na varredura) e a variação de 4 h e 1 dia. Contra o pano de fundo,
   só com motivo forte e número. O laboratório mostrou que tendência existe em dias e semanas (razão de variância > 1), não em minutos.
2. **1 h e 15 min — a estrutura.** Topos e fundos descendentes = baixa; ascendentes = alta (o "EST" da varredura). Onde está o preço entre a máxima e a
   mínima de 24 h (coluna "até máx/mín 24 h"): vender colado na mínima de 24 h ou comprar colado na máxima é entrar no fim do movimento.
3. **5 min e 1 min — o momento.** Correção contra a tendência maior que perde força é o melhor ponto (vender o repique numa baixa, comprar o recuo numa
   alta). Em minutos o mercado tende a voltar (razão de variância < 1): perseguir a vela que acabou de andar costuma pagar o topo.
4. **15 s, 5 s e 1 s — a execução.** Só para não entrar no meio de um pico: "!" = movimento fora do normal naquela janela. Entrar só pela leitura de 1 s
   perdeu para o custo nas 3 regras testadas (H56).
**Alinhamento:** conte quantos dos 6 tempos (1 min a 1 dia) estão do lado da operação. O caderno de cada agente mostra se 6 de 6 rende mais que 4–5 PARA VOCÊ.

## 2. Volume confirma
Rompimento ou impulso com volume acima da média (vol 1 min > 1,2×) tende a continuar; sem volume tende a falhar (o laboratório achou o inverso pagando o
custo: movimento forte SEM volume reverte, H26). Volume 0× = moeda parada: o stop e o alvo podem não ser tocados no prazo.

## 3. Padrões gráficos (definições objetivas, lab/padroes_graficos.py)
| código | padrão | o que costuma indicar | o que o laboratório mediu (H45, 1 h, custo 0,12%) |
|---|---|---|---|
| TD | topo duplo | baixa ao romper o vale | 47,5% de direção certa em 4 h (−0,168%/op): não passou |
| FD | fundo duplo | alta ao romper o pico | 45,4%: não passou |
| OCO / OCOi | ombro-cabeça-ombro (invertido) | baixa (alta) ao romper o pescoço | melhor família: +0,148%/op em 12 h, t 1,0: não passou |
| TRI | triângulo | rompimento para o lado que sair | 48%, −0,171%/op, negativo nos 3 blocos |
| BAND | bandeira | continuação do mastro | 45,2%: não passou |
| EST | estrutura (topos e fundos) | a tendência curta | 47,7%, negativo nos 3 blocos |
* = confirmado (rompeu na última vela). **Nenhum padrão passou como regra sozinha.** Use como contexto: padrão a favor + tempos alinhados + volume +
carteiras a favor = leitura forte; padrão sozinho = leitura fraca. Padrão contra a operação é motivo para o REVISOR cortar.
Velas isoladas (martelo, engolfo, estrela) não previram nada (H6: 0 de 57): não use.

## 4. Melhores carteiras e cérebro v4 (outras opiniões)
- Carteiras (H63): confirmação ou alerta, não ordem. Muitas vendidas numa moeda em queda confirmam venda; contra elas, só com motivo forte.
- v4: acerta mais quanto mais confiante (65–68% na confiança ≥ 0,12); abaixo de 0,03 de confiança não aposta (neutro).
- **Papel do v4 desde 19/11 (dono; Engenheiro): só pesa com confiança ≥ 0,12.** Abaixo disso é "sem confiança": não descarta moeda, não corta no
  REVISOR, não fecha posição. Por quê (números do vigia, 7 dias até 19/11 15:45 UTC, direção da vela de 15 min): acerto 56,9% (< 0,05; n 8.697),
  56,1% (0,05–0,08; n 4.353), 59,3% (0,08–0,12; n 1.669), 67,0% (≥ 0,12; n 566). Acerto de 56% numa vela de 15 min não diz nada sobre uma operação
  de 1–4 h com alvo ≥ 1% e custo de 0,12% (o v4 prevê outra coisa: "validade de construto", Hall et al. cap. 3). E o veto fraco não protegeu:
  ver `dados/lab/veto_v4_resultado.json` e `veto_v4_replay.json` (19/11).

## 5. Stop, alvo e prazo (scalper)
- **Alvo ≥ 3 × o stop e ≥ 1% (dono, 19/11: "aumente os alvos de ganho"; a execução impõe). Com alvo, o stop móvel arma na metade do caminho até ele.** Stop do tamanho da volatilidade da moeda (a varredura mostra o quanto ela anda em 5 e 15 min); prazo compatível com o alvo.
- Prazo curto (15–90 min) quando a leitura é de minutos; não vale segurar um scalper por horas "esperando voltar".
- Antes de gravar: o REVISOR tenta derrubar cada entrada (ROTINA.md, passo 3b).
- **Tamanho (H64, aprovado):** a nuvem decide sozinha. Fatia = 2,5 × carteira ÷ US$ 10 (de 1,25× a 5×) vezes a carteira: com US$ 12 a posição é
  3,0 × 12 = US$ 36; com US$ 8 é 2,0 × 8 = US$ 16. Ganhar faz a próxima entrada crescer; perder faz encolher ("perder de colher").
- **Formato da saída (H64, medido, NÃO é regra):** nas 5.842 apostas do v4 a favor do regime (11–18/11, 15 min, custo 0,12%):
  | saída | média/aposta | ganho médio ÷ perda média | bloco mais recente |
  |---|---|---|---|
  | stop 1% e alvo 3% | +0,362% | 2,58 | −0,359% |
  | stop 0,5% e alvo 1,5% | +0,055% | 2,30 | −0,180% |
  | stop 1% + stop móvel | −0,037% (corrigido 19/11) | 0,64 | −0,145% |
  | stop 2% + stop móvel (R6) | −0,021% (corrigido 19/11; antes +0,134% por erro do simulador) | 0,44 | −0,168% |
  Alvo 3 × o stop é o formato "ganhar de balde" que mais rendeu, mas falhou no período mais recente. O stop móvel corta o ganho perto de +0,6% e, medido sem o erro do simulador (19/11), não dá lucro: é proteção, não fonte de ganho.
  Alvo menor que o stop (ex.: stop 0,6% e alvo 0,5%) é o contrário do tema: com o custo de 0,12% precisa acertar 65% só para empatar. O caderno mostra o seu.

## 6. Aprender sozinho (o treino de verdade)
Cada rodada começa com `operar.py aprender <você>`: as suas operações fechadas cruzadas com a leitura que você tinha na entrada (tempos a favor, padrão,
carteiras, movimento de 1 min). Com 10 ou mais operações num grupo, ajuste o SEU jeito de ler (ex.: "só 6 de 6 me deu lucro"); com menos, "não sei ainda".
Escreva na lição o que o caderno mostrou, com números. Mudar a regra da mesa inteira continua passando pelo Laboratório.
