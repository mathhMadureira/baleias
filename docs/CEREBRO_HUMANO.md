# Como o cérebro humano aprende — e o que isso vira no nosso cérebro de day trade

Estudo de base para o Cérebro v2 (`baleias/cerebro.py`). As referências são trabalhos clássicos e amplamente citados da neurociência. As traduções para o software são minhas e estão marcadas como **→ no robô**.

## 1. Neurônios e sinapses: o aprendizado é a mudança da força das conexões

O cérebro tem cerca de 86 bilhões de neurônios (Azevedo et al., 2009). Cada neurônio recebe sinais de milhares de outros por sinapses. Aprender, em grande parte, é **mudar a força dessas sinapses** (plasticidade sináptica).

- **Regra de Hebb (1949):** "neurônios que disparam juntos se conectam". Se A ajuda a disparar B, a conexão A→B se fortalece.
- **STDP (Bi & Poo, 1998):** o *tempo* importa. Se A dispara um pouco **antes** de B, a sinapse fortalece. Se dispara **depois**, ela enfraquece. A sinapse aprende **causa → efeito**, não só coincidência.
- **→ no robô:** uma sinapse só deve ganhar força quando a opinião dela veio **antes** do resultado e o previu. Isso já é feito: ela opina no fechamento da vela e é julgada na vela seguinte.

## 2. Dopamina: o sinal de "erro de previsão de recompensa"

Schultz, Dayan & Montague (1997) mostraram que os neurônios de dopamina não sinalizam a recompensa em si, mas a **diferença entre a recompensa recebida e a esperada**:
- recompensa melhor que o esperado → pico de dopamina (reforça o que foi feito);
- igual ao esperado → nada muda;
- pior que o esperado → queda de dopamina (enfraquece).

Esse é o mesmo cálculo do aprendizado por diferença temporal (TD) usado em aprendizado por reforço.

- **→ no robô (v1):** hoje uma sinapse ganha ou perde peso só por **acertar ou errar**, sem importar o tamanho.
- **→ v2:** o reforço vem do **erro de previsão de lucro**: (resultado obtido − resultado esperado), com o tamanho do movimento. Acertar uma vela grande vale mais que acertar uma vela parada.

## 3. Dois sistemas de memória que se complementam

McClelland, McNaughton & O'Reilly (1995), teoria dos sistemas complementares:
- **Hipocampo:** aprende **rápido** episódios específicos, como "o que aconteceu hoje".
- **Neocórtex:** aprende **devagar** padrões gerais. Se aprendesse rápido, apagaria o que já sabia (interferência catastrófica).
- **Sono:** durante o sono, o hipocampo **reencena** (*replay*) os episódios do dia, e o córtex os incorpora aos poucos, intercalados com o conhecimento antigo (Wilson & McNaughton, 1994).

- **→ no robô (v1):** a rede neural aprende só com a vela mais recente, uma vez.
- **→ v2:** o cérebro guarda os episódios (medidas da vela + resultado) num **hipocampo** e, uma vez por dia, **"dorme"**: reencena os episódios guardados, embaralhados e com taxa de aprendizado pequena. É o mesmo princípio do *experience replay* usado em IA (Mnih et al., 2015).

## 4. Homeostase: nenhuma sinapse pode dominar tudo

Turrigiano (2008), escalonamento sináptico: se um neurônio fica ativo demais, todas as sinapses dele são reduzidas na mesma proporção, e se fica ativo de menos, são aumentadas. Sem isso, o aprendizado de Hebb entra em realimentação e satura.

A **hipótese da homeostase sináptica do sono** (Tononi & Cirelli, 2014) diz que, durante a vigília, as sinapses se fortalecem, e no sono elas são renormalizadas para baixo, mantendo as diferenças relativas.

- **→ no robô (v1):** a rede neural chegou a peso ~34 contra ~1 das outras sinapses. Uma voz só domina o voto.
- **→ v2:** **escalonamento homeostático**: depois de cada atualização, nenhuma sinapse pode ter mais de 40% do voto total. No "sono" diário, todos os pesos são comprimidos em direção à média, preservando a ordem.

## 5. Esquecer é uma função, não um defeito

O cérebro esquece de propósito: memórias não usadas enfraquecem, e isso evita que regras velhas atrapalhem num ambiente novo (Richards & Frankland, 2017, "a persistência e a transitoriedade da memória").

- **→ no robô (v1):** o placar de cada sinapse soma **tudo desde o início**. Uma regra que funcionou há um mês e parou de funcionar continua "comprovada".
- **→ v2:** o placar usado para decidir é **com esquecimento** (média móvel exponencial, meia-vida de ~300 previsões). O placar completo continua guardado só para relatório.

## 6. Surpresa e incerteza mudam a velocidade de aprender

Yu & Dayan (2005): dois neuromoduladores sinalizam tipos diferentes de incerteza.
- **Acetilcolina:** incerteza **esperada** ("sei que isto é ruidoso") → confiar menos em cada observação.
- **Noradrenalina:** incerteza **inesperada**, quando o mundo muda ("o que eu sabia parou de valer") → aumentar a taxa de aprendizado e explorar.

- **→ v2:** **surpresa** = o quanto o acerto recente se afasta do acerto de longo prazo. Com surpresa alta (o mercado mudou), a taxa de aprendizado sobe. Com o mercado estável, ela volta ao normal.

## 7. Prever o tempo todo (codificação preditiva)

A hipótese do cérebro preditivo (Rao & Ballard, 1999; Friston, 2010) diz que o córtex está sempre **prevendo** o que vai sentir e propagando para cima só o **erro** da previsão. Aprender é reduzir esse erro.

- **→ no robô:** isso já é a estrutura do cérebro: cada vela é uma previsão feita antes, e só o erro ensina.

## 8. Saber o que não sabe (metacognição)

O córtex pré-frontal estima a **confiança** na própria decisão (Kiani & Shadlen, 2009). Com pouca confiança, a escolha mais comum é **não decidir**, ou buscar mais informação.

- **→ no robô:** o cérebro já se abstém quando a probabilidade calibrada fica abaixo de 52%.
- **→ v2:** a confiança passa a usar o placar **com esquecimento**: depois de uma sequência ruim, ele aposta menos sozinho.

## 9. Nascer e podar conexões

No desenvolvimento, o cérebro cria conexões em excesso e depois **poda** as pouco usadas (Huttenlocher, 1979). No adulto, o hipocampo ainda forma neurônios novos, e só sobrevivem os que entram em circuitos úteis.

- **→ no robô:** já existe. Sinapses novas nascem em observação, são promovidas se provarem acerto e podadas se falharem.

## Resumo: o que o v2 acrescenta

| Mecanismo do cérebro | v1 | v2 |
|---|---|---|
| Hebb/STDP (causa → efeito) | sim | sim |
| Dopamina (erro de previsão de recompensa) | acerto/erro | **erro de lucro, com tamanho** |
| Hipocampo + sono (replay) | não | **sono diário reencenando episódios** |
| Homeostase sináptica | não (uma sinapse com 34× o peso) | **teto de 40% do voto + compressão no sono** |
| Esquecimento | não | **placar com meia-vida de ~300** |
| Noradrenalina (surpresa → aprender mais rápido) | não | **taxa de aprendizado adaptativa** |
| Metacognição (abster-se) | limiar fixo | **limiar + confiança recente** |
| Nascimento e poda de conexões | sim | sim |

Os dois cérebros rodam lado a lado, ao vivo, nas mesmas velas. Quem decide se a biologia ajudou são os resultados (H21).
