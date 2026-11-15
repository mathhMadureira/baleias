# Livros da O'Reilly — o que foi lido e o que virou código

15/11/2026. O dono deixou 10 livros em `~/Downloads` (PDF e EPUB). Os livros ficam na máquina dele e não sobem para o repositório.
Nenhum dos 10 é de trading ou de análise técnica. Quatro servem ao projeto; seis não.

| livro | serve? | por quê |
|---|---|---|
| Machine Learning for High-Risk Applications (Hall, Curtis, Pandey) | **sim, o mais útil** | como monitorar, testar e desligar um modelo que decide dinheiro |
| Analytical Skills for AI and Data Science (Vaughan) | sim | correlação × causa, confundidores, valor esperado, incerteza |
| Learning LangChain (Mayo Oshin) | sim | arquitetura de agentes: supervisor, reflexão, saída estruturada, avaliação |
| Data Science from Scratch (Grus) | sim | teste de hipótese, p-hacking, teste A/B |
| Building Generative AI Services with FastAPI | pouco | servidor web de IA; o painel já é Python puro e local |
| The AI Organization (Carmona) | não | gestão de empresa |
| Low-Code AI, Practical AI on Google Cloud | não | ferramentas pagas ou de nuvem do Google |
| AI and ML for On-Device Development, Practical AI with Swift | não | celular e Apple |

## O que cada livro ensinou e onde está no projeto

### 1. Machine Learning for High-Risk Applications, cap. 3 (depuração e implantação)

| lição do livro | no Baleias |
|---|---|
| "Modelos aprendem de uma foto parada do passado; o mundo muda" (deriva) e "monitore as previsões ao vivo com limites de controle" | **`executor/vigia_v4.py`**: a cada rodada da nuvem, acerto ao vivo do v4 nos últimos 7 dias contra os 53,46% do laboratório (H41), com alarme a 2 e 3 erros-padrão |
| Benchmark: "se o modelo simples ganha do modelo complexo, use o simples" | o vigia mede nas mesmas apostas duas referências triviais: "segue as 24 h da moeda" e "segue a maioria do mercado" |
| Análise de resíduos por segmento: "o erro médio esconde os pontos fracos" | o vigia quebra o acerto por lado, faixa de horário e faixa de confiança. Achado: 18–24 h UTC acertou 44,2% ao vivo (H46, pré-registrada) |
| Dados correlacionados enganam os testes | erro-padrão calculado por vela, não por aposta (as moedas de uma vela andam juntas) |
| Asserções de modelo: regras de negócio por cima do modelo | já existiam (stop, regra da tendência de 24 h); agora o chefe da mesa pode dar ordens aos robôs |
| Botão de desligar e monitoramento em tempo real | `PARAR`, piso de US$ 5, alarme de rotina parada; o vigia avisa na Sala de operações quando o estado muda |
| Retreino com o mesmo rigor do primeiro treino | já existia: `retreino.yml` com juiz (H41) |

### 2. Analytical Skills for AI and Data Science, caps. 2 e 6

- **Confundidores:** compras 48,1% × vendas 57,8% ao vivo não é achado, porque o mercado caiu nesses dias. Ficou anotado na H46 para ninguém
  "consertar" o lado com base nisso.
- **Valor esperado:** uma aposta só vale se acerto × ganho − erro × perda − custo > 0. É o critério que o laboratório já usa (custo de 0,12%).

### 3. Learning LangChain, caps. 7, 8 e 10

- **Arquitetura de supervisor** (um agente decide e delega aos outros): é a Sala de operações, com o Robô Claude como chefe (`baleias/equipe.py`).
- **Reflexão com dados externos** (o agente revisa a própria resposta conferindo com dados): cartilha, seção 7, com autocrítica em 5 pontos
  conferidos no retrato antes de gravar a decisão.
- **Saída estruturada:** a decisão do chefe é um JSON com campos fixos; o executor ignora ordem, agente ou ação fora da lista.
- **Avaliação com regras fixas antes de usar outro modelo como juiz:** é o que o juiz do laboratório faz (critério escrito antes de rodar).

### 4. Data Science from Scratch, cap. 7

- **p-hacking:** "teste hipóteses suficientes e uma vai parecer significativa". O protocolo já conta tentativas e corrige (Bonferroni, Sharpe
  deflacionado). A H46 nasceu dos dados ao vivo, por isso só pode ser julgada com apostas novas, de 16 a 22/11.
