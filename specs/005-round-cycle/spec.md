# Feature Specification: Ciclo de Rodada

**Feature Branch**: `005-round-cycle`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Ciclo de rodada: a partida saindo do setup e girando sozinha. Upkeep, a alternância da Fase de Ação com duas das quatro ações, e o Fim de Rodada."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. As §4 (Upkeep), §5
(Fase de Ação) e §8 (Fim de Rodada) são o contrato desta feature. A §12 dá as
constantes: teto de energia 10, incremento +1 por rodada, sem carryover, teto
de banco 6, sem doença de invocação. A §9 (compra) é consumida como a feature
004 a entregou, sem cópia e sem variante. A §3 (setup, feature 003) é o estado
de entrada, e não é alterada.

Esta é a primeira feature que aceita uma ação de jogador e a primeira que muda
o estado de uma partida em andamento. O que ela entrega é uma partida que gira
de ponta a ponta por quantas rodadas se quiser — sem feitiço, sem pilha e sem
combate.

## Clarifications

### Sessão 2026-09-10

- **P: O Upkeep resolve os dois jogadores "sem interação entre eles", mas os
  dois compram, e uma compra que dispara reset de deck consome um sorteio do
  contador único da partida. Se os dois resetarem no mesmo Upkeep, a ordem em
  que forem resolvidos decide qual pega qual ponto da sequência.**
  R: A ordem é fixa e documentada: o Upkeep resolve sempre o primeiro jogador
  da partida e depois o segundo, na ordem em que eles estão no estado. O
  contador de sorteios continua sendo um só, da partida, como a feature 002 o
  define.

  O que a §4 garante deixa de ser "a ordem não é observável" e passa a ser
  **independência**: nenhum passo do Upkeep de um jogador lê ou depende do
  estado do outro. Energia e compra de um lado dão o mesmo resultado
  qualquer que seja o estado do outro lado.

  A ordem em si é observável, e é isso que a torna testável: com a mesma
  semente e o mesmo estado, dois Upkeeps produzem a mesma partida, inclusive
  quando os dois jogadores resetam o deck na mesma rodada. É o mesmo argumento
  do mulligan da feature 003, em que a ordem de chegada das respostas faz parte
  da entrada e está registrada como comportamento definido.

  As alternativas foram recusadas por raio de impacto: um contador de sorteios
  por jogador mudaria o estado e a serialização da feature 002, e um ordinal
  derivado de `(rodada, user_id)` mudaria a regra de cunhagem de sorteio da
  partida inteira — setup, mulligan e reset juntos.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dar o primeiro empurrão (Priority: P1)

O setup da feature 003 entrega uma partida montada, com token sorteado,
prioridade no dono do token e fase `UPKEEP` — parada, sem ter executado o
Upkeep da Rodada 1. Alguém precisa dar o primeiro empurrão.

Esta feature expõe a operação que faz isso: ela roda o Upkeep da Rodada 1 e
devolve a partida já na Fase de Ação, esperando a primeira ação de jogador.
Depois desse empurrão a partida nunca mais precisa de outro: toda transição
automática seguinte acontece dentro da resposta a uma ação.

**Why this priority**: sem ela a partida montada pelo setup não sai do lugar. É
a porta de entrada do ciclo inteiro.

**Independent Test**: montar uma partida pelo setup, chamar a operação de
início, e conferir que a fase é Fase de Ação, a rodada é 1, os dois jogadores
têm 1 de energia e cada um tem uma carta a mais na mão do que tinha.

**Acceptance Scenarios**:

1. **Given** uma partida recém-entregue pelo setup, **When** a partida é
   iniciada, **Then** a fase é Fase de Ação, a rodada é 1, e a prioridade é do
   dono do token.
2. **Given** uma partida recém-entregue pelo setup, **When** a partida é
   iniciada, **Then** os dois jogadores têm energia máxima 1 e energia atual 1.
3. **Given** um jogador com 4 cartas na mão e o outro com 5, saídos do setup,
   **When** a partida é iniciada, **Then** eles têm 5 e 6 cartas.
4. **Given** uma partida já iniciada, **When** a operação de início é chamada
   de novo, **Then** ela é recusada citando a fase atual, e nada muda — o
   Upkeep não roda duas vezes na mesma rodada.
5. **Given** uma partida ainda em mulligan, **When** a operação de início é
   chamada, **Then** ela é recusada citando a fase, e nada muda.

---

### User Story 2 - O Upkeep de toda rodada (Priority: P1)

Automática, sem input, no início de toda rodada, inclusive a primeira. Para os
dois jogadores:

- A energia máxima sobe 1, com teto de 10.
- A energia atual passa a ser a máxima. Recarga total: o que não foi gasto na
  rodada anterior é perdido, energia não acumula.
- Cada um compra 1 carta, pela regra da §9 que a feature 004 entrega.

Os dois jogadores são resolvidos numa ordem fixa — o primeiro do estado, depois
o segundo — e nenhum dos dois lê o estado do outro. O que a §4 garante é
independência, não indiferença à ordem: a ordem existe, é sempre a mesma, e é o
que torna um Upkeep em que os dois resetam o deck reproduzível.

Depois dos dois jogadores: o token volta a estar disponível, a contagem de
passes zera, a prioridade vai para o dono do token, e a partida entra na Fase
de Ação.

Progressão de energia: rodada 1 com 1, rodada 2 com 2, e assim por diante até
10, que se mantém nas rodadas seguintes.

**Why this priority**: é o que reabastece a partida a cada volta. Sem Upkeep a
segunda rodada é igual a uma partida travada.

**Independent Test**: rodar o Upkeep sobre uma partida na rodada N com energias
gastas e conferir energia máxima N, energia atual N, uma carta a mais em cada
mão, passes em zero, prioridade no dono do token e fase de Ação.

**Acceptance Scenarios**:

1. **Given** uma partida na rodada 3 com os dois jogadores em energia máxima 2,
   **When** o Upkeep roda, **Then** os dois ficam com energia máxima 3 e
   energia atual 3.
2. **Given** um jogador que terminou a rodada anterior com 4 de energia atual
   sobrando, **When** o Upkeep roda, **Then** a energia atual dele é a máxima
   nova, não a máxima mais o que sobrou.
3. **Given** uma partida na rodada 11 com os dois em energia máxima 10, **When**
   o Upkeep roda, **Then** os dois continuam com energia máxima 10 e energia
   atual 10.
4. **Given** um Upkeep, **When** ele termina, **Then** cada jogador comprou
   exatamente 1 carta pela regra da §9.
5. **Given** um jogador com 10 cartas na mão, **When** o Upkeep roda, **Then**
   ele não compra, nenhum erro é levantado, e o Upkeep segue normalmente para o
   outro jogador e para o fim da fase.
6. **Given** um jogador com o deck vazio e o cemitério cheio, **When** o Upkeep
   roda, **Then** o reset de deck da §9 acontece e ele compra, sem que a §9
   seja reescrita aqui.
7. **Given** um Upkeep, **When** ele termina, **Then** o token está disponível,
   a contagem de passes é 0, a prioridade é do dono do token e a fase é a Fase
   de Ação.
8. **Given** um Upkeep, **When** ele termina, **Then** nenhum Nexus mudou e
   nenhuma unidade saiu ou entrou em banco.
9. **Given** uma partida em que os **dois** jogadores estão com o deck vazio e
   o cemitério cheio, **When** o Upkeep roda duas vezes a partir do mesmo
   estado e da mesma semente, **Then** as duas partidas resultantes são
   idênticas — a ordem de resolução é fixa, e os dois resets caem sempre no
   mesmo ponto da sequência.
10. **Given** dois estados que diferem só no lado do oponente, **When** o
    Upkeep roda, **Then** o lado do primeiro jogador termina igual nos dois —
    o Upkeep de um lado não depende do outro.

---

### User Story 3 - Jogar unidade (Priority: P1)

Quem tem a prioridade pode jogar uma unidade da mão. Exige energia atual maior
ou igual ao custo da carta e menos de 6 unidades no banco.

O que acontece: desconta a energia, tira a carta da mão, põe a unidade no
banco. A unidade entra pronta e sem dano — não existe doença de invocação, e
nada a marca como recém-jogada. Não usa pilha, resolve na hora. A contagem de
passes zera. A prioridade troca.

**Why this priority**: é a primeira ação de jogador do motor e a única desta
feature que gasta recurso e muda zona. É ela que define a forma da ação que
feitiço, ataque, bloqueio e mulligan vão herdar.

**Independent Test**: com 3 de energia, uma unidade de custo 2 na mão e o banco
vazio, jogar a unidade e conferir energia em 1, mão com uma carta a menos,
banco com uma unidade sem dano e sem modificador, passes em 0 e prioridade no
oponente.

**Acceptance Scenarios**:

1. **Given** um jogador com prioridade, 3 de energia e uma unidade de custo 2
   na mão, **When** ele joga a unidade, **Then** a energia atual dele é 1, a
   carta saiu da mão e a unidade está no banco dele.
2. **Given** a unidade recém-posta no banco, **When** eu a leio, **Then** o
   dano acumulado é 0 e a lista de modificadores está vazia.
3. **Given** a unidade recém-posta no banco, **When** eu comparo o
   identificador dela com o que a carta tinha na mão, **Then** é o mesmo —
   trocar de zona não cunha identidade nova.
4. **Given** um jogador com energia atual exatamente igual ao custo da carta,
   **When** ele joga a unidade, **Then** a jogada é aceita e a energia dele fica
   em 0 — a guarda é `energia >= custo`.
5. **Given** um jogador com 5 unidades no banco, **When** ele joga uma unidade,
   **Then** a jogada é aceita e o banco fica com 6 — a guarda é `banco < 6`.
6. **Given** uma jogada de unidade aceita, **When** a operação termina, **Then**
   a contagem de passes é 0 e a prioridade é do oponente.
7. **Given** um oponente que já tinha passado uma vez, **When** o jogador com
   prioridade joga uma unidade, **Then** a contagem de passes volta a 0.
8. **Given** uma jogada de unidade aceita, **When** eu leio o estado do
   oponente, **Then** só a prioridade mudou — mão, banco, energias, deck,
   cemitério e Nexus dele estão intactos.
9. **Given** uma jogada de unidade aceita, **When** eu leio os dois Nexus,
   **Then** os dois estão como estavam.

---

### User Story 4 - Passar e a saída da Fase de Ação (Priority: P1)

Passar soma 1 à contagem de passes e troca a prioridade. É a ação que sempre
está disponível para quem tem a prioridade.

Depois de **qualquer** ação, a saída da fase é verificada, como a §5 manda:

- Dois passes consecutivos com a pilha vazia → Fim de Rodada.
- Dois passes consecutivos com a pilha não vazia → Resolução de Pilha.

Nesta feature a pilha está sempre vazia, porque nada a enche. A condição fica
escrita como a §5 manda para que a feature de pilha encaixe nela sem reescrever
a saída.

Como a prioridade troca a cada ação, dois passes consecutivos significam sempre
que os dois jogadores passaram, nunca que um passou duas vezes.

**Why this priority**: é a ação que fecha a rodada. Sem ela a partida não vira.

**Independent Test**: com a partida na Fase de Ação e passes em 0, fazer o
jogador com prioridade passar e conferir passes em 1, prioridade no oponente e
fase ainda de Ação; fazer o oponente passar e conferir que a rodada virou.

**Acceptance Scenarios**:

1. **Given** uma partida na Fase de Ação com passes em 0, **When** o jogador
   com prioridade passa, **Then** a contagem de passes é 1, a prioridade é do
   oponente e a fase continua sendo a Fase de Ação.
2. **Given** uma partida com passes em 1, **When** o jogador com prioridade
   passa, **Then** a rodada fecha e a partida volta pronta para agir na rodada
   seguinte.
3. **Given** uma partida com passes em 1, **When** o jogador com prioridade
   joga uma unidade em vez de passar, **Then** os passes voltam a 0 e a rodada
   não fecha.
4. **Given** uma sequência passar–jogar unidade–passar–passar, **When** ela é
   executada, **Then** a rodada fecha só no último passe, porque a jogada de
   unidade quebrou a sequência.
5. **Given** uma ação de passar, **When** ela termina, **Then** nenhuma zona de
   carta mudou, nenhuma energia mudou e nenhum Nexus mudou.

---

### User Story 5 - O Fim de Rodada (Priority: P1)

Automática, sem input, na ordem da §8:

1. Todo modificador marcado como "até o fim da rodada" é removido das unidades
   no banco dos dois jogadores. Os permanentes ficam.
2. O token de ataque passa para o outro jogador.
3. O número da rodada sobe 1.
4. Volta para o Upkeep.

Nenhum feitiço existe ainda para criar um modificador temporário, mas o estado
da feature 002 já os representa. A varredura precisa existir e ser testada com
um modificador posto à mão — senão a feature de pilha teria que voltar aqui.

Não existe descarte por excesso de mão. O teto de 10 é aplicado na compra (§9),
não aqui.

Dano acumulado **não** é modificador: ele não expira e não é varrido no Fim de
Rodada.

**Why this priority**: é a metade do ciclo que devolve a partida ao Upkeep. Sem
ela o token nunca troca e a rodada nunca sobe.

**Independent Test**: pôr à mão um modificador temporário e um permanente em
unidades dos dois bancos, fechar a rodada com dois passes, e conferir que só os
temporários sumiram, que o token trocou de dono e que a rodada subiu 1.

**Acceptance Scenarios**:

1. **Given** uma unidade com um modificador "até o fim da rodada", **When** a
   rodada fecha, **Then** o modificador não está mais na lista dela.
2. **Given** uma unidade com um modificador permanente, **When** a rodada
   fecha, **Then** o modificador continua na lista dela.
3. **Given** uma unidade com um modificador temporário e um permanente, **When**
   a rodada fecha, **Then** sobra exatamente o permanente.
4. **Given** unidades com modificadores temporários nos bancos dos **dois**
   jogadores, **When** a rodada fecha, **Then** os dois bancos foram varridos.
5. **Given** uma unidade com dano acumulado, **When** a rodada fecha, **Then** o
   dano dela continua o mesmo.
6. **Given** uma rodada N com o token no jogador A, **When** a rodada fecha,
   **Then** o token é do jogador B e a rodada é N+1.
7. **Given** um jogador com 10 cartas na mão, **When** a rodada fecha, **Then**
   ele não descarta nada.
8. **Given** o Fim de Rodada, **When** ele termina, **Then** nenhum Nexus mudou,
   nenhuma unidade saiu do banco e nenhuma carta foi para o cemitério.

---

### User Story 6 - A cascata: uma ação, um estado estabilizado (Priority: P1)

Upkeep e Fim de Rodada são passagem, não parada. A partida nunca fica em fase
automática esperando outro empurrão.

A consequência é que um único "passar" pode disparar a cascata inteira: fim de
rodada, varredura de modificadores, troca de token, rodada +1, Upkeep da rodada
seguinte com energia e compra dos dois, e a partida volta esperando ação.

O resultado observável de uma ação é o estado **já estabilizado**, nunca um
estado intermediário. Quem chamou nunca vê a partida em `UPKEEP` nem em
`ROUND_END`.

**Why this priority**: é a diferença entre um motor que passa nos testes
unitários e um motor que trava na primeira partida real. Uma implementação que
execute um passo por chamada e devolva a partida em `ROUND_END` satisfaz cada
regra isolada e não roda uma partida.

**Independent Test**: com a partida na Fase de Ação da rodada 1 e passes em 1,
executar um único "passar" e conferir, numa única leitura do resultado, que a
rodada é 2, o token trocou, as energias são 2, cada mão ganhou 1 carta, os
passes estão em 0 e a fase é a Fase de Ação.

**Acceptance Scenarios**:

1. **Given** uma partida na rodada 1 com passes em 1, **When** o jogador com
   prioridade passa, **Then** o estado devolvido tem rodada 2, fase de Ação,
   passes 0, energias em 2 e o token no outro jogador.
2. **Given** qualquer ação aceita, **When** a operação termina, **Then** a fase
   da partida é sempre a Fase de Ação.
3. **Given** qualquer ação aceita, **When** a operação termina, **Then** existe
   sempre um jogador com prioridade, e ele é participante da partida.
4. **Given** uma partida iniciada, **When** dez rodadas são jogadas em sequência
   com dois passes cada, **Then** a partida chega à rodada 11 sem travar em
   nenhuma fase automática, e as energias param em 10.
5. **Given** uma cascata que atravessa o Fim de Rodada e o Upkeep, **When** ela
   termina, **Then** a ordem dos passos foi a da §8 seguida da §4 — a varredura
   de modificadores acontece antes da troca de token, e a compra do Upkeep
   acontece depois da rodada já ter subido.

---

### User Story 7 - A forma da ação e a recusa que nomeia o ofensor (Priority: P1)

É a primeira vez que uma jogada entra no motor. Toda ação carrega quem a
executa e o que ela é; jogar unidade carrega também qual carta.

Toda ação passa pelas mesmas guardas, **nessa ordem**:

1. O autor joga esta partida.
2. O autor tem a prioridade.
3. A fase atual permite esta ação.

Só depois disso a regra específica da ação é verificada.

**Uma ação ilegal não muda nada.** A recusa deixa o estado exatamente como
estava — não desconta energia, não tira carta da mão, não troca prioridade, não
mexe na contagem de passes, não avança contador nenhum. Meia ação aplicada é
pior que ação nenhuma, porque a partida fica em estado que nenhuma regra
produziria.

**Toda recusa nomeia o valor ofensor.** Custo contra energia disponível, o
limite do banco, qual carta, qual jogador, qual fase, quem tem a prioridade.
Recusa genérica não serve para o cliente mostrar nada nem para depurar.

Jogar feitiço e declarar ataque não são ações válidas ainda. Elas entram com as
features de pilha e de combate.

**Why this priority**: a forma que sair daqui vai ser reusada por feitiço,
ataque, bloqueio e mulligan. Se ficar torta, as três features seguintes herdam
a torção.

**Independent Test**: para cada caso de recusa, capturar o estado inteiro da
partida antes, executar a ação ilegal, e comparar campo a campo com o estado
depois; e conferir que a mensagem da recusa cita o valor ofensor.

**Acceptance Scenarios**:

1. **Given** um jogador com 1 de energia e uma unidade de custo 3 na mão,
   **When** ele tenta jogá-la, **Then** a ação é recusada citando o custo 3 e a
   energia disponível 1, e o estado fica idêntico.
2. **Given** um jogador com 6 unidades no banco, **When** ele tenta jogar uma
   unidade, **Then** a ação é recusada citando o limite de 6, e o estado fica
   idêntico.
3. **Given** um jogador que cita uma carta que não está na mão dele, **When**
   ele tenta jogá-la, **Then** a ação é recusada citando a carta pedida, e o
   estado fica idêntico.
4. **Given** um jogador que cita uma carta da mão que é feitiço, **When** ele
   usa a ação de jogar unidade, **Then** a ação é recusada citando a carta e o
   tipo dela, e o estado fica idêntico.
5. **Given** um jogador sem a prioridade, **When** ele tenta qualquer ação,
   **Then** a ação é recusada citando quem tem a prioridade, e o estado fica
   idêntico.
6. **Given** uma partida em fase que não é a Fase de Ação, **When** um jogador
   tenta qualquer ação, **Then** a ação é recusada citando a fase atual, e o
   estado fica idêntico.
7. **Given** um `user_id` que não joga esta partida, **When** ele envia qualquer
   ação, **Then** a ação é recusada citando o `user_id`, e o estado fica
   idêntico.
8. **Given** um jogador que cita a carta de outro jogador, **When** ele tenta
   jogá-la, **Then** a ação é recusada citando a carta — a mão consultada é
   sempre a do autor da ação.
9. **Given** uma ação recusada, **When** eu leio o contador de identidade de
   carta e o contador de sorteios da partida, **Then** nenhum dos dois avançou.
10. **Given** um jogador sem prioridade **e** com energia insuficiente, **When**
    ele tenta jogar a unidade, **Then** a recusa é a de prioridade — as guardas
    comuns vêm antes da regra específica da ação.

---

### User Story 8 - Não quebrar 002, 003 e 004 (Priority: P2)

Esta feature consome o que as três anteriores entregaram e não as altera.

- **Feature 002.** Todo estado produzido aqui sobrevive à ida e à volta pelo
  Redis, campo a campo — banco povoado, modificadores, energias, contadores e
  fase inclusive.
- **Feature 003.** O setup continua entregando a partida do mesmo jeito: mesma
  semente e mesmos decks produzem a mesma partida parada em `UPKEEP`, com mãos
  de 4 e 5 cartas.
- **Feature 004.** A regra de compra é usada como está, sem cópia e sem
  variante. O Upkeep chama a mesma operação que o setup chama.

**Why this priority**: é continuidade, não capacidade nova. Vale como história
porque a regressão aqui é silenciosa.

**Independent Test**: rodar as suítes das features 002, 003 e 004 sem alteração
nenhuma nos testes delas, e conferir que passam.

**Acceptance Scenarios**:

1. **Given** uma partida no meio de uma Fase de Ação, com unidades no banco e
   modificadores, **When** ela vai ao Redis e volta, **Then** o estado
   reconstruído é igual ao original, campo a campo.
2. **Given** o setup da feature 003 com a mesma semente e os mesmos decks,
   **When** ele roda depois desta feature, **Then** produz exatamente a mesma
   partida que produzia antes, e ela continua parada antes do Upkeep.
3. **Given** o código depois desta feature, **When** procuro onde uma carta sai
   do deck e entra na mão, **Then** continua existindo um único lugar, e o
   Upkeep passa por ele.
4. **Given** as suítes das features 002, 003 e 004, **When** elas rodam,
   **Then** passam sem alteração.

---

### Edge Cases

**Upkeep**

- **Rodada 11 e seguintes.** Energia máxima continua 10, não 11. O teto é da
  §12 e vale para sempre.
- **Mão cheia no Upkeep.** O jogador não compra, nenhum erro é levantado, e o
  Upkeep segue — para o outro jogador e para o fim da fase.
- **Deck vazio no Upkeep.** A §9 reseta pelo cemitério e a compra acontece. Esta
  feature não conhece o reset; ela chama a compra.
- **Energia sobrando da rodada anterior.** É perdida. Energia atual vira a
  máxima, não a máxima mais o resto.
- **Token no Upkeep.** Volta a estar disponível toda rodada, mesmo nesta feature
  em que nada o consome.
- **Os dois jogadores resetando o deck no mesmo Upkeep.** Acontece na ordem
  fixa — primeiro jogador do estado, depois o segundo —, então os dois resets
  caem sempre nos mesmos pontos da sequência de sorteios da partida. É
  reproduzível, e a ordem não depende de prioridade nem de dono do token.

**Fase de Ação**

- **Energia exatamente igual ao custo.** Jogada aceita, energia vai a 0.
- **Banco em 5.** Jogada aceita, banco vai a 6.
- **Banco em 6.** Recusa citando o limite, mesmo com energia de sobra.
- **Unidade de custo 0.** Jogável com 0 de energia — a guarda é `>=`.
- **Carta de feitiço na ação de jogar unidade.** Recusa. Jogar feitiço é ação de
  outra feature, e usar a ação errada não é atalho para ela.
- **Jogar unidade com o oponente já tendo passado uma vez.** Os passes voltam a
  0; a rodada não fecha.
- **Dois passes com a pilha não vazia.** Levaria à Resolução de Pilha. Nesta
  feature é inalcançável — nada empilha —, mas a condição de saída é escrita
  como a §5 manda, para que a feature de pilha encaixe nela sem reescrever a
  saída.
- **Mão vazia na Fase de Ação.** Passar continua sendo ação legal. Uma mão vazia
  não trava a partida.

**Fim de Rodada**

- **Banco vazio nos dois lados.** A varredura de modificadores roda e não faz
  nada. Não é erro.
- **Unidade só com modificadores permanentes.** Nada é removido dela.
- **Unidade com dano acumulado.** O dano fica. Dano não é modificador.
- **Mão em 10 no Fim de Rodada.** Não há descarte por excesso de mão.

**Cascata**

- **Um passe que vira a rodada.** O chamador recebe a partida já na Fase de Ação
  da rodada seguinte, com energia nova e cartas compradas. Ele nunca observa
  `ROUND_END` nem `UPKEEP`.
- **Dez rodadas seguidas.** A partida chega à rodada 11 sem travar em fase
  automática nenhuma.
- **Cascata com mão cheia dos dois lados.** O Upkeep da rodada nova não compra
  para ninguém e a cascata termina normalmente na Fase de Ação.

**Recusas**

- **Ação de quem não joga a partida.** Recusa citando o `user_id`, sem tocar em
  nada.
- **Ação fora da Fase de Ação.** Recusa citando a fase. Vale para a partida em
  mulligan e para qualquer fase automática que um chamador tente pegar no meio.
- **Duas guardas falhando ao mesmo tempo.** Vence a primeira da ordem:
  participante, prioridade, fase, e só então a regra da ação.
- **Recusa não consome aleatoriedade.** Nenhum contador da partida avança numa
  ação recusada.

## Requirements *(mandatory)*

### Functional Requirements

**Início do ciclo**

- **FR-001**: O sistema MUST expor uma operação que executa o Upkeep da Rodada 1
  sobre uma partida entregue pelo setup e devolve a partida na Fase de Ação.
- **FR-002**: Essa operação MUST ser recusada, citando a fase atual, quando a
  partida não estiver parada antes do Upkeep. Chamá-la duas vezes MUST NOT rodar
  o Upkeep duas vezes.
- **FR-003**: Essa operação MUST NOT alterar o que o setup da feature 003
  produz. O setup continua entregando a partida parada antes do Upkeep.

**Upkeep (§4)**

- **FR-004**: O Upkeep MUST rodar no início de toda rodada, inclusive a
  primeira, sem input de jogador.
- **FR-005**: Para cada jogador, a energia máxima MUST subir 1, com teto de 10.
- **FR-006**: Para cada jogador, a energia atual MUST passar a ser a energia
  máxima. Energia não gasta MUST NOT ser acumulada.
- **FR-007**: Para cada jogador, o Upkeep MUST comprar 1 carta pela regra da §9
  entregue pela feature 004, sem cópia e sem variante dela.
- **FR-008**: Um jogador que não consegue comprar — mão cheia — MUST NOT
  interromper o Upkeep. Nenhum erro MUST ser levantado, e o outro jogador e o
  fim da fase MUST acontecer normalmente.
- **FR-009**: O Upkeep de um jogador MUST NOT ler nem alterar o estado do
  outro. O resultado de um lado MUST ser o mesmo qualquer que seja o estado do
  outro lado.
- **FR-009a**: O Upkeep MUST resolver os jogadores numa ordem fixa — o primeiro
  jogador da partida e depois o segundo, na ordem em que eles estão no estado.
  A ordem MUST NOT depender de prioridade, de dono do token nem de qualquer
  outro campo variável.
- **FR-009b**: Com a mesma partida e a mesma semente, dois Upkeeps MUST
  produzir o mesmo resultado, inclusive quando os dois jogadores disparam reset
  de deck na mesma rodada.
- **FR-010**: Ao fim do Upkeep o token MUST voltar a estar disponível, a
  contagem de passes MUST ser 0, a prioridade MUST ser do dono do token, e a
  fase MUST ser a Fase de Ação.
- **FR-011**: O teto de energia (10) e o incremento por rodada (+1) MUST vir de
  constantes nomeadas, declaradas uma vez, junto de quem as aplica.
- **FR-012**: O Upkeep MUST NOT alterar Nexus, banco, cemitério nem
  modificadores.

**Fase de Ação (§5) — alternância**

- **FR-013**: Só o jogador com a prioridade MUST poder executar uma ação, e ele
  MUST executar exatamente uma por vez.
- **FR-014**: Depois de qualquer ação aceita, a prioridade MUST passar ao
  oponente.
- **FR-015**: Depois de qualquer ação aceita, a saída da fase MUST ser
  verificada.
- **FR-016**: A saída MUST ser: dois passes consecutivos com a pilha vazia → Fim
  de Rodada; dois passes consecutivos com a pilha não vazia → Resolução de
  Pilha. A segunda condição MUST estar escrita mesmo sendo inalcançável nesta
  feature.

**Ação: jogar unidade (§5A)**

- **FR-017**: A ação MUST exigir que a carta citada esteja na mão do autor.
- **FR-018**: A ação MUST exigir que a carta citada seja uma unidade.
- **FR-019**: A ação MUST exigir energia atual maior ou igual ao custo da carta.
- **FR-020**: A ação MUST exigir menos de 6 unidades no banco do autor.
- **FR-021**: Aceita, a ação MUST descontar o custo da energia atual, tirar a
  carta da mão e pôr a unidade no banco do autor.
- **FR-022**: A unidade MUST entrar pronta: sem dano acumulado, sem
  modificadores, e sem marca de recém-jogada. Doença de invocação MUST NOT
  existir.
- **FR-023**: A unidade MUST manter o identificador que a carta tinha na mão.
- **FR-024**: A ação MUST NOT usar a pilha. Ela resolve na hora.
- **FR-025**: A ação MUST zerar a contagem de passes, inclusive quando o
  oponente já tiver passado uma vez.
- **FR-026**: O teto de banco (6) MUST vir de uma constante nomeada, declarada
  uma vez, junto de quem a aplica.

**Ação: passar (§5D)**

- **FR-027**: A ação MUST somar 1 à contagem de passes.
- **FR-028**: A ação MUST NOT alterar zona de carta, energia, Nexus nem
  modificador.

**Ações ainda inexistentes**

- **FR-029**: Jogar feitiço e declarar ataque MUST NOT ser ações aceitas nesta
  feature.

**Fim de Rodada (§8)**

- **FR-030**: O Fim de Rodada MUST rodar sem input de jogador, na ordem da §8.
- **FR-031**: Todo modificador marcado como "até o fim da rodada" MUST ser
  removido das unidades no banco dos **dois** jogadores.
- **FR-032**: Modificadores permanentes MUST permanecer.
- **FR-033**: Dano acumulado MUST NOT ser afetado pela varredura — dano não é
  modificador e não expira.
- **FR-034**: O token de ataque MUST passar para o outro jogador.
- **FR-035**: O número da rodada MUST subir 1.
- **FR-036**: O Fim de Rodada MUST voltar para o Upkeep.
- **FR-037**: MUST NOT existir descarte por excesso de mão no Fim de Rodada.
- **FR-038**: O Fim de Rodada MUST NOT alterar Nexus, mão, deck, cemitério nem a
  composição dos bancos.

**A cascata**

- **FR-039**: Uma ação de jogador MUST devolver o estado já estabilizado. Upkeep
  e Fim de Rodada MUST ser atravessados dentro da mesma operação.
- **FR-040**: Ao fim de qualquer ação aceita, a fase MUST ser a Fase de Ação.
- **FR-041**: O chamador MUST NOT observar a partida em `UPKEEP` nem em
  `ROUND_END` como resultado de uma ação.
- **FR-042**: A cascata MUST executar os passos na ordem das seções: §8 inteira
  e só então a §4 da rodada nova.

**A forma da ação e as guardas comuns**

- **FR-043**: Toda ação MUST carregar a identidade do autor e o que ela é; jogar
  unidade MUST carregar também a carta.
- **FR-044**: Toda ação MUST passar pelas guardas comuns nesta ordem: o autor
  joga esta partida; o autor tem a prioridade; a fase atual permite esta ação.
- **FR-045**: A regra específica da ação MUST ser verificada só depois das três
  guardas comuns.
- **FR-046**: A forma da ação MUST ser a mesma para as duas ações desta feature,
  e MUST comportar as ações das features seguintes sem mudar de formato.
- **FR-047**: A mão, o banco e a energia consultados por uma ação MUST ser
  sempre os do autor da ação.

**Recusa**

- **FR-048**: Uma ação recusada MUST deixar o estado da partida exatamente como
  estava, campo a campo, em qualquer ponto de falha.
- **FR-049**: Uma ação recusada MUST NOT descontar energia, mover carta, trocar
  prioridade, alterar a contagem de passes nem mudar a fase.
- **FR-050**: Uma ação recusada MUST NOT avançar o contador de identidade de
  carta nem o contador de sorteios da partida.
- **FR-051**: Toda recusa MUST nomear o valor ofensor: o custo contra a energia
  disponível, o limite do banco, a carta pedida, o `user_id`, a fase atual, ou
  quem tem a prioridade — conforme a guarda que falhou.
- **FR-052**: A recusa MUST identificar qual guarda falhou, de forma que o
  cliente possa distinguir os casos sem interpretar texto livre.

**Fronteiras**

- **FR-053**: Nada nesta feature MUST alterar Nexus. A condição de vitória da
  §10 MUST NOT ser alcançável aqui.
- **FR-054**: Nada nesta feature MUST empilhar feitiço nem consumir a pilha.
- **FR-055**: Nada nesta feature MUST pôr carta no cemitério.
- **FR-056**: Qualquer estado produzido por esta feature MUST sobreviver à ida e
  à volta pelo Redis com igualdade campo a campo.
- **FR-057**: Esta feature MUST NOT gravar no Redis. Quem grava é o chamador,
  pelo caminho que a feature 003 entregou.

### Key Entities

Esta feature cria uma entidade nova — a ação — e opera sobre o estado que a
feature 002 define:

- **Ação de jogador**: a intenção de uma jogada. Carrega quem a executa, o que
  ela é, e os parâmetros que aquele tipo exige — para jogar unidade, a carta. É
  a forma que feitiço, ataque, bloqueio e mulligan vão reusar.
- **Recusa de ação**: por que a jogada não aconteceu, com o valor ofensor
  nomeado e a guarda que falhou identificável sem interpretar texto.
- **Fase da partida**: `UPKEEP`, `ACTION`, `ROUND_END` e as demais que a feature
  002 já define. Upkeep e Fim de Rodada são fases de passagem: existem no
  modelo, e nenhuma ação termina com a partida numa delas.
- **Contagem de passes**: 0, 1 ou 2 passes consecutivos. Zera no Upkeep e a cada
  jogada de unidade.
- **Prioridade**: de quem é a vez. Troca a cada ação aceita, e é reposta no dono
  do token a cada Upkeep.
- **Token de ataque**: quem poderá declarar ataque. Troca de dono no Fim de
  Rodada e volta a estar disponível no Upkeep, mesmo sem combate nesta feature.
- **Energia do jogador**: máxima e atual. A máxima sobe 1 por rodada até 10; a
  atual é recarregada até a máxima e não acumula.
- **Modificador de unidade**: alteração com duração. O Fim de Rodada varre os
  marcados como "até o fim da rodada" e deixa os permanentes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma partida recém-montada pelo setup, depois de iniciada, está na
  Fase de Ação da rodada 1 com 1 de energia dos dois lados e 1 carta a mais na
  mão de cada jogador.
- **SC-002**: Em 10 rodadas jogadas em sequência, a energia máxima dos dois
  jogadores é 1, 2, 3, ..., 10, e na rodada 11 continua 10.
- **SC-003**: Dois passes consecutivos fecham a rodada, trocam o dono do token,
  sobem a rodada em 1 e devolvem a partida na Fase de Ação com a energia da
  rodada nova — tudo numa única resposta.
- **SC-004**: Em 100% das ações aceitas, a fase da partida devolvida é a Fase de
  Ação.
- **SC-005**: Dez rodadas seguidas rodam sem que a partida fique parada em
  `UPKEEP` ou `ROUND_END` em nenhum momento observável.
- **SC-006**: Um modificador "até o fim da rodada" posto à mão desaparece no Fim
  de Rodada, e um permanente posto à mão na mesma unidade continua lá.
- **SC-007**: Em 100% dos casos de recusa listados nos Edge Cases, o estado da
  partida depois é idêntico ao estado antes, campo a campo — contadores
  inclusive.
- **SC-008**: Em 100% dos casos de recusa, a mensagem cita o valor ofensor, e a
  guarda que falhou é identificável sem interpretar texto livre.
- **SC-009**: Os dois jogadores conseguem alternar jogadas de unidade e passes
  até o banco de um deles chegar a 6, e a 7ª tentativa é recusada citando o
  limite.
- **SC-010**: Nenhum Nexus muda em nenhuma sequência de ações desta feature, por
  mais longa que seja.
- **SC-011**: Qualquer estado produzido por esta feature volta idêntico do
  Redis, campo a campo.
- **SC-012**: As suítes das features 002, 003 e 004 passam sem nenhuma alteração
  nos testes delas.
- **SC-013**: Existe exatamente 1 lugar no código onde a compra da §9 é
  executada, e o Upkeep passa por ele.
- **SC-014**: Um Upkeep em que os dois jogadores disparam reset de deck produz
  a partida idêntica em 100% das repetições a partir do mesmo estado e da mesma
  semente.

## Assumptions

- **O primeiro empurrão é uma operação própria desta feature**, chamada pela
  camada de transporte quando a partida sai do setup. Não é dobrada dentro do
  setup, porque a feature 003 tem que continuar entregando a partida do mesmo
  jeito.
- **A recusa é levantada, não devolvida como valor.** É a forma que o motor já
  usa para jogada ilegal (`MulliganAlreadyTakenError`, `CardNotInHandError`,
  `NotAParticipantError`), e ela deixa o caminho de sucesso com um retorno só.
  Diferente da compra da §9, em que "não comprou" é fluxo normal do jogo: aqui a
  ação ilegal é jogada inválida, e quem chama precisa tratá-la.
- **A ordem das checagens específicas de jogar unidade** é: carta na mão → carta
  é unidade → energia suficiente → banco com espaço. A carta precisa ser
  resolvida antes de se poder citar o custo dela na recusa.
- **A ação chega ao motor já com a identidade do autor**, vinda da camada
  autenticada. O motor não confia nela: a primeira guarda comum é justamente
  conferir que aquele `user_id` joga esta partida.
- **A operação recebe a partida e devolve a partida.** Ela não lê nem grava no
  Redis; quem grava é o chamador, pelo caminho atômico da feature 003.
- **As constantes da §12 vivem junto de quem as aplica**, como `MAX_HAND_SIZE`
  vive com a compra e `STARTING_NEXUS` com o estado do jogador. O projeto não
  tem um módulo único de constantes.
- **A pilha é sempre vazia nesta feature.** A condição de saída que a menciona é
  escrita, e o ramo da Resolução de Pilha fica sem implementação — ele não é
  alcançável enquanto nada empilhar.
- **O token volta a estar disponível todo Upkeep** mesmo sem combate, porque a
  §4 manda e porque a feature de combate encontra o campo já correto.
- **Nada aqui altera a §9.** O Upkeep chama a compra como o setup a chama.
- **O contador de sorteios continua sendo um só, da partida**, como a feature
  002 o define. O Upkeep compensa isso com uma ordem de resolução fixa, em vez
  de mudar o estado da feature 002 ou a regra de cunhagem de sorteio — as duas
  alternativas teriam raio de impacto maior do que o problema.

## Out of Scope

- **Jogar feitiço, a pilha e a resolução em LIFO (§6).**
- **Declarar ataque e todo o combate (§7).**
- **A condição de vitória (§10).** Sem combate e sem feitiço, ninguém perde
  vida.
- **Envelope de mensagem, broadcast e reconexão no websocket.** Esta feature
  recebe uma ação e devolve o estado novo; quem fala com o cliente é outra
  camada.
- **Timeout de jogada.** Sem relógio, dois jogadores que nunca agem deixam a
  partida parada para sempre. É problema de transporte, e continua em aberto na
  §13 do Fluxo de Partida.
- **Descarte por excesso de mão.** Não existe (§8).
- **Persistência.** Gravar a partida no Redis é do chamador.
