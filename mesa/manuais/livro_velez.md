# Livro da equipe — o método Oliver Velez (28/11/2026)

Pedido do dono: "imersão em conhecimento… médias móveis, indicadores, vela de retração, falso rompimento, região de suporte e resistência; o Oliver Velez ensina muito de graça". Este livro junta as regras das fontes gratuitas, o que a equipe escolheu onde as fontes não dão número e **o que medimos nos nossos dados** (H90). Leia junto com `livro_padroes.md` e as lições em `licoes_operador.md`.

**Regra de ouro da equipe:** nenhuma entrada sem `python3 -I /home/servidor-de-producao/OpenBot/Shared/baleias/checagem.py <MOEDA>` dar PASSA no lado. A checagem agora também mostra o estado 20/200 e o setup de Velez do momento.

---

## 1. Médias móveis (o coração do método)
- **Tipo:** SIMPLES (MMA), não exponencial. Períodos **8, 20 e 200** (20 e 21 são equivalentes). [P2 p.40; SS sl.27; B14]
- **Onde olhar:** viés no 60 min e 15 min (8/20/200); operação no 5 min; ajuste fino no 2 min. [P2 p.27–38]
- **Imagem de força (alta):** preço > MMA20 **subindo** > MMA200. **Baixa:** o espelho. Só compre com a MMA20 subindo acima da MMA200; só venda com a MMA20 caindo abaixo da MMA200. [P2 p.38, p.45; SS sl.21–23, 47]
- **MMA20 plana:** sem tendência → compre embaixo, venda em cima (lateral), sem perseguir. [P2 p.41]
- **MMA20 é suporte quando sobe e resistência quando cai.** Compras perto da MMA8/MMA20 subindo; vendas perto da MMA8/MMA20 caindo. [P2 p.41; SS sl.27]
- **Ímã:** preço muito longe da MMA20 volta para ela. Preço longe da MMA20 **e** MMA20 longe da MMA200 = risco de reversão maior. [P2 p.41, p.52]
- **MMA200 plana** segura o preço (quase sempre há repique quando ele chega lá), e segura mais quanto mais longe está a MMA20. [P2 p.52, p.57; SS sl.35]
- **Estado estreito** (20 e 200 juntas) costuma preceder explosão; **estado expandido** pede cautela. [P2 p.28–31; SS sl.47]
- **MMA8:** segura os movimentos mais fortes; serve de stop móvel. Cruzar 8 sobre 20 é qualidade a mais, não gatilho. [P2 p.40; P1]

## 2. O alfabeto das velas
- **Cor = quem venceu** (fechamento acima/abaixo da abertura). A ponta da barra mostra a força. [P2 p.4–6]
- **Controle e a regra dos 2/3:** quando a barra seguinte apaga 50% da cor da anterior, o controle enfraqueceu; quando apaga **2/3 ou mais**, o controle virou (ponto de virada). [P2 p.10–23]
- **Barra elefante (BE):** muito maior que as recentes. No **começo** do movimento = **ignição** (espere continuação). Depois de um movimento longo = **exaustão** (o último empurrão, com volume alto). Só jogue elefante perto de uma média; longe de tudo, não. [P2 p.6–9; B14]
- **Pavios:** **BT (bottoming tail)** = pavio inferior longo, compradores defendendo. **TT (topping tail)** = pavio superior longo, vendedores defendendo. Gatilho de Velez: BT na MMA20 subindo (compra), TT na MMA20 caindo (venda). [P2 p.26; SS sl.39–41]
- **NRB (barra estreita):** pausa; perto das médias, a favor da tendência, costuma anteceder explosão; doji longe da média = exaustão. [P1; SD]

## 3. Os setups (com o que medimos — H90, 20 moedas, ~1 mês, custo 0,12%)
| setup | regra (fonte) | medido (melhor grupo) |
|---|---|---|
| **RBI / GBI** | tendência; barra 1 da cor da tendência; barra 2 pequena contrária (ideal no terço de cima da barra 1 no RBI); entra 1 tick além da barra 2; a mínima da barra vermelha não pode ser violada. [P2 p.287–298; B24] | **perde**: RBI 15 min n 1.188, −0,32%, acerto 21% |
| **Bull 180 / Bear 180** | barra forte de uma cor + barra forte oposta que fecha além do extremo dela; quanto mais longe da MMA20, melhor; alvo ≈ tamanho da barra. [P2 p.274–286; B24; P1] | **Bear 180 venda 1 h: +0,65%/op, n 75, t 1,44** (perto, não passa) |
| **Elefante de ignição / GIFT** | rompe a máxima da BE (stop na mínima); se não romper, o recuo de até 2/3 da BE é o "presente" para entrar melhor. [B14; P1] | perde (1 h −1,3%) |
| **BT / TT na MMA20** | ver §2. [SS sl.40–41] | perde (−0,1 a −0,3%) |
| **Lei das 3–5 barras** | o preço raramente anda mais de 3–5 barras seguidas; depois de 3–5 barras de recuo, compre o rompimento da máxima da barra anterior (a favor da tendência). [SS sl.14–17] | **perde forte**: 15 min n 3.000, −0,25% |
| **NRB na MMA20** | barra estreita na média, a favor do estado. [P1; SD] | compra 1 h +0,42% (n 51, não passa); venda perde |
| **CDB / CAS (climático)** | 5+ barras da mesma cor, a última a maior, longe da MMA20, volume subindo, horário de reversão → reverte com Bull/Bear 180 ou pavio; alvo 50% do movimento. Comprar queda depois de alta climática tem baixa probabilidade. [P2 p.278–279, p.334; SD] | CDB 1 h +1,2% mas n 10 (pouco) |
| **BOP / BDP** | base apertada depois de uma perna (8 e 20 se juntando, máximas e mínimas diminuindo) → entra na barra que rompe os últimos 2/3 da base, perto de uma média. [P1; P2 p.265–271] | ainda não programado |
| **Falso rompimento** | passa do topo/fundo anterior e **fecha de volta dentro** → opera o lado contrário, stop além do extremo falho; o reteste que falha confirma. [P2 p.277–282; guias de price action] | perde no 15 min (t −3) com stop de uma barra |

**Sem definição nas fontes gratuitas (não inventamos):** Twin Tower, GSP/GCP, TTO/DTTO, BTTO/DBTTO, RBTO/GBTO (só a regra de local: RBTO acima das médias, GBTO abaixo), gatilho exato de VBS/VSS e GIFT.

**O que os números dizem:** com o stop de Velez (uma barra) e alvo 2R, o acerto no cripto de 15 min fica em 20–30%: a barra-sinal é pequena perto do ruído e do custo. **As vendas a favor no 1 h (Bear 180) são o único lado perto de pagar**, igual à H85/H86. Próximo teste (H91): os mesmos setups com stop pela ESTRUTURA (além do pivô, ≥ 1 ATR) e alvo no próximo suporte/resistência.

## 4. Suporte, resistência, retração e falso rompimento
- **S/R:** MMA20 e MMA200, máximas e mínimas anteriores, fechamento do dia anterior, pontos de virada do 60 min. Opere os setups **em suporte forte** (compra) / resistência forte (venda). [P2 p.35, p.268, p.302; SS sl.29]
- **Nunca venda em cima de suporte nem compre embaixo de resistência** (lição da ZEC, 27/11): a checagem barra a menos de 1 ATR do nível.
- **Retração:** 50% = controle fraco; **2/3 = controle perdido**. GBI em 50% de retração = nova perna de queda. Alvo de CDB = 50% do movimento. [P2 p.11–22; SS sl.36]
- **Vela de retração vs reversão:** retração é a pausa contra a tendência (barra pequena, pouca cor apagada, não passa 2/3) → continuação. Reversão apaga 2/3+ da cor, vem com pavio forte/180/engolfo **em S/R ou longe da MMA20** → virada.
- **Falso rompimento:** fechou de volta dentro da faixa = armadilha; volume sozinho não prova nada; o reteste do nível rompido decide (segura = rompimento real; falha = armadilha).

## 5. Stop, alvo e gestão (Velez)
- Stop: 1 tick além da barra de entrada (compra abaixo da mínima; venda acima da máxima). **No cripto de 15 min esse stop é curto demais (H90)**: use o stop do outro lado da estrutura/nível, mínimo ~1 ATR.
- **Breakeven:** com 1:1 a favor, mova o stop para a entrada. [P2 glossário]
- **Stop móvel:** barra a barra, MMA8 (movimentos fortes) ou MMA20 (movimentos maduros). [P2 p.40, p.320; SS sl.47]
- **Tamanho:** risco fixo R; quantidade = R ÷ (entrada − stop). [P2 cap. 20]
- Saídas parciais na força; adicione em RBI/GBI a favor. [SS sl.30–32]

## 6. Checklist do operador (cripto, BingX)
1. 60 min/15 min: imagem de força? (MMA20 subindo acima da 200 → só compra; caindo abaixo → só venda; plana → lateral).
2. Onde está o preço: perto da MMA20/MMA200 (bom) ou longe (cuidado: ímã)? Perto de S/R contra o lado? → não entra.
3. Vela do momento: setup de Velez + pavio/180 a favor, controle (2/3) do lado certo.
4. Força compradora × vendedora e livro de ordens a favor.
5. `checagem.py <MOEDA>` = PASSA.
6. Stop do outro lado da estrutura (≥ 1 ATR); alvo no próximo S/R (≥ 2× o risco); breakeven em 1:1; stop móvel na MMA8/MMA20.

## Fontes (gratuitas)
- P1 — [Setup's - Oliver Velez (PDF)](https://pdfcoffee.com/setupx27s-oliver-velez-pdf-free.html)
- P2 — [Manual Oliver Velez - Trade (PDF, iFundTraders)](https://pdfcoffee.com/manual-oliver-velez-trade-pdf-free.html)
- B14 — [Setup Oliver Velez parte 1/4 (Brasil Traders)](https://brasiltraders.wordpress.com/2017/03/20/setup-oliver-velez-parte-14/)
- B24 — [Setup Oliver Velez parte 2/4 (Brasil Traders)](https://brasiltraders.wordpress.com/2017/07/03/setup-oliver-velez-parte-24/)
- SS — [5 Trading Tactics – Velez (SlideShare)](https://www.slideshare.net/slideshow/178511583-5tradingtacticsvelez/57440904)
- SD — [Complementary Setups OV (Scribd)](https://www.scribd.com/document/960610079/Complementary-Setups-Op-OV-Updated)
- SN — [Oliver Velez 20/200 (guia de terceiro)](https://www.snappchart.app/blog/beginner-playbook/oliver-velez-trading-strategy)
- Medição: `lab/PROTOCOLO_LAB.md` H90 e `dados/lab/h90_velez.json` (repositório).
