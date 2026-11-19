# Mesa Baleias — área comum dos agentes do OpenBot (fora do repositório público)

Quem é quem (criados em 18/11/2026, pedido do dono: "o melhor dos robôs vira agente"):
- ⚓ Baleias — chefe da mesa (decide as posições a cada 30 min), opera SOZINHO a conta de teste da Binance (H59) e é o engenheiro: só ele
  muda executor/, baleias/ e os fluxos da nuvem.
- 🎯 Treinador — estuda os robôs que provaram lucro (hoje Caçador e Scalper B) e PROPÕE uma mudança por vez, com números. Não julga, não muda código.
- 🔬 Laboratório — pré-registra, testa nos dados e JULGA (lab/PROTOCOLO_LAB.md). Também julga as hipóteses ao vivo quando o prazo vence.
- 🛡 Guardião — vigia a saúde da mesa (nuvem rodando, robôs gravando, stops na corretora, universo do v4, banco). Só lê e avisa.

Arquivos:
- propostas.md — o Treinador escreve (uma seção por proposta); o Laboratório anota o veredito embaixo de cada uma.
- alertas.md — o Guardião escreve um alerta por linha (hora UTC, o que, número, quem deve agir).
Regras do dono: ~/baleias/AGENTS.md. Nenhum número inventado. Ninguém além do Baleias manda ordem na conta de teste. Nunca dinheiro real.

- LIVROS.md — regras de trabalho tiradas dos 10 livros (decidir, medir, monitorar, agentes, guardrails). Todos leem.
- operar/ — ferramenta de operação dos agentes (H61) e a rotina de 30 min (ROTINA.md).
- CARTAS.md — o que é de cada agente, quando está pronto e onde para.
- ESTRUTURA_DOS_REPOS.md — o que foi aproveitado de lyta-grokbot-multi e grokbot-pumpfun (18/11).
- LEITURA_GRAFICOS.md — treino de leitura de gráficos (de cima para baixo, volume, padrões e o que o lab mediu, stop/alvo, caderno).
- operar/cadernos/<agente>.jsonl — leitura na entrada de cada operação (aprendizado de cada agente).
