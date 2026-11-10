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

- 2026-11-10: repositório público; cérebro roda no GitHub a cada 15 min (painel espelha); fluxos acrescentam no ramo `estado`; Livro de Métodos; referência "sempre sobe"; `checar.py`.

- 2026-11-10: H14–H18 testadas e reprovadas (reversão intradiária, força relativa, sazonalidade com contagem corrigida, funding contrário, Vórtice+CHOP). Mapa do mercado inteiro (~170 moedas) e previsor H19 (Vórtice invertido) ao vivo. Robô rápido em 5 min com teto de perda de US$ 100/dia; robô de funding visível.

- 2026-11-10: monitor caía em ciclo com "database is locked" (o Gemini segurava a gravação durante chamadas de rede de até minutos). Commit antes de cada chamada de rede e conexões esperando 30 s. Também confirmado: depois de pausa da máquina, o motor ao vivo se recupera sozinho.
- 2026-11-10: conciliação das posições com a corretora ao ligar (modo real).

- 2026-11-09: robô rápido ao vivo (1 h) com gráfico ao vivo; replay; Bybit; nuvem grátis no GitHub; stops com a máquina desligada; memória do projeto.
