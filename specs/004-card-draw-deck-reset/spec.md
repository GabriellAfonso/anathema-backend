# Feature Specification: Compra de Carta e Reset de Deck

**Feature Branch**: `004-card-draw-deck-reset`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Compra de carta e reset de deck: a única porta pela qual uma carta sai do deck e entra na mão, com as duas guardas da §9."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. A §9 é o contrato
desta feature, inteira. A §4 (Upkeep, o primeiro chamador de verdade) e a §12
(constantes: teto de mão 10, reset de deck ilimitado) são referência. A §3, via
feature 003, já move carta do topo do deck para a mão — esta feature é a mesma
operação com as duas guardas por cima, e o movimento não pode acabar escrito
duas vezes.

## Clarifications

### Sessão 2026-09-10

- **P: O que acontece quando o deck está vazio, o cemitério também, e a mão tem
  menos de 10 cartas? Não há de onde comprar nem o que resetar.**
  R: A compra não acontece, pelo mesmo caminho da mão cheia — nada muda, nenhum
  erro é levantado, e quem chamou segue. É a única resposta que não contradiz a
  garantia da §9 de que nenhuma partida acaba por deck: levantar erro no Upkeep
  mataria a partida exatamente pelo motivo que a §9 proíbe.

  O estado é inalcançável em uma partida legal, e a conta fecha: as 40 cartas
  de um jogador estão sempre distribuídas entre deck, mão, banco, cemitério e
  pilha, porque nenhuma carta sai do jogo — o MVP não tem exílio. Mão tem teto
  de 10 e banco tem teto de 6 (§12); feitiço na pilha saiu da mão, e não se
  compra durante a Fase de Ação, então mão mais pilha também não passa de 10.
  Somando, mão mais pilha mais banco nunca passa de 16, e sobram pelo menos 24
  cartas entre deck e cemitério. Zerar os dois exigiria 40 cartas nas outras
  zonas, que não cabem.

  O comportamento é, portanto, defensivo: ele decide o que acontece se o estado
  for corrompido, não o que acontece em uma partida real. Fica testado por
  isso — para que a corrupção não vire uma exceção não tratada no meio de um
  Upkeep.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A porta única da compra (Priority: P1)

Toda compra do jogo passa por uma só regra. Hoje o setup da feature 003 chama
o movimento cru — tirar do topo, pôr na mão — porque nenhuma das duas guardas
da §9 pode disparar lá. A partir desta feature existe a regra geral, e é ela
que o setup, o Upkeep, a reposição do mulligan, o bônus de início de partida e
qualquer feitiço futuro chamam.

A regra tem três passos, nesta ordem, e a ordem é parte dela:

1. Mão com 10 cartas → não compra.
2. Deck vazio → reset de deck, e só então compra.
3. Caso contrário → a carta do topo do deck vai para a mão.

**Why this priority**: é o chão. As duas guardas, a compra múltipla e a
migração do setup são todas comportamentos desta única operação.

**Independent Test**: com uma mão de 3 cartas e um deck de 5, chamar a compra e
conferir que a mão foi para 4, o deck para 4, a carta que saiu foi a que estava
no topo, e o cemitério não foi tocado.

**Acceptance Scenarios**:

1. **Given** um jogador com 3 cartas na mão e 5 no deck, **When** ele compra,
   **Then** a mão tem 4, o deck tem 4, e a carta comprada é a que estava no
   topo do deck.
2. **Given** um jogador com 9 cartas na mão e deck com cartas, **When** ele
   compra, **Then** a mão fica com 10 e a compra aconteceu normalmente — a
   guarda é `>= 10`, não `>= 9`.
3. **Given** qualquer compra bem-sucedida, **When** leio o cemitério e o banco
   depois, **Then** os dois estão exatamente como estavam — comprar não
   descarta e não invoca.
4. **Given** uma carta comprada, **When** comparo o identificador dela na mão
   com o que ela tinha no deck, **Then** é o mesmo — trocar de zona não cunha
   identidade nova.
5. **Given** uma compra, **When** olho o oponente, **Then** nada no estado dele
   mudou — a compra é de um jogador só.

---

### User Story 2 - A guarda de mão cheia (Priority: P1)

Um jogador com 10 cartas na mão não compra. A carta continua no topo do deck.
Nada é queimado, nada vai para o cemitério, o deck não anda, o contador de
identidade não avança.

Isto **não é erro nem recusa**. É uma compra que não aconteceu, e quem chamou
segue normalmente. O Upkeep da §4 não pode explodir porque o jogador está com a
mão cheia — é situação corriqueira do jogo, não bug de chamador.

A §8 registra que não existe descarte por excesso de mão: o teto de 10 é
aplicado aqui, na compra, e em lugar nenhum mais.

**Why this priority**: é a metade da §9 que o resto do motor mais vai exercer,
e a que, se implementada como exceção, quebra o Upkeep em toda partida longa.

**Independent Test**: montar uma mão de 10 cartas com deck cheio, chamar a
compra e comparar o estado inteiro do jogador antes e depois, campo a campo.

**Acceptance Scenarios**:

1. **Given** um jogador com 10 cartas na mão e um deck com cartas, **When** ele
   compra, **Then** a mão continua com as mesmas 10 cartas, na mesma ordem, e o
   deck continua com as mesmas cartas, na mesma ordem.
2. **Given** o mesmo jogador, **When** ele compra, **Then** o cemitério dele
   continua com as mesmas cartas — nenhuma carta é queimada.
3. **Given** o mesmo jogador, **When** ele compra, **Then** a operação termina
   sem levantar erro, e quem chamou consegue seguir para o próximo passo.
4. **Given** um jogador com 10 na mão e o deck **vazio**, **When** ele compra,
   **Then** o cemitério dele continua onde está — a guarda de mão é verificada
   antes do reset, e um jogador de mão cheia nunca reseta o deck.
5. **Given** uma compra que não aconteceu, **When** leio o contador de
   identidade de carta da partida, **Then** ele não avançou.

---

### User Story 3 - O reset de deck (Priority: P1)

Deck vazio e mão com menos de 10: antes de comprar, todo o cemitério daquele
jogador vira o novo deck, embaralhado. A mão e o banco não são tocados. O
cemitério fica vazio. Depois disso a compra prossegue normalmente e entrega a
carta.

As cartas voltam com a identidade que já tinham. A carta que morreu na rodada
3 e voltou ao deck na rodada 9 é a mesma carta, com o mesmo identificador — o
identificador nasce com a carta e acompanha ela por todas as zonas, como a
feature 002 estabelece.

O reset é ilimitado: acontece toda vez que o deck zerar, quantas vezes for.
**Nenhuma partida acaba por deck** — só Nexus a 0 encerra (§10).

**Why this priority**: é a outra metade da §9, e é a que sustenta a garantia de
que a partida não termina por deck acabado.

**Independent Test**: montar um jogador com deck vazio, 4 cartas no cemitério e
2 na mão; chamar a compra; conferir que o cemitério ficou vazio, o deck ficou
com 3 cartas, a mão com 3, e que os 4 identificadores do cemitério são
exatamente os 4 que agora estão entre deck e mão.

**Acceptance Scenarios**:

1. **Given** um jogador com deck vazio, 4 cartas no cemitério e 2 na mão,
   **When** ele compra, **Then** a mão tem 3, o deck tem 3 e o cemitério está
   vazio.
2. **Given** o mesmo jogador, **When** ele compra, **Then** o conjunto de
   identificadores que estava no cemitério é exatamente o conjunto que agora
   está no deck mais a carta comprada — nada some, nada nasce.
3. **Given** o mesmo jogador, **When** ele compra, **Then** o banco dele
   continua exatamente como estava — o reset não mexe em unidade em campo.
4. **Given** um cemitério com uma unidade que morreu carregando dano e
   modificadores, **When** ela volta ao deck pelo reset, **Then** ela é uma
   carta de deck comum: identidade preservada, sem dano e sem modificador.
5. **Given** um jogador que já passou por um reset, **When** o deck dele zera
   de novo, **Then** um novo reset acontece — não existe limite de resets por
   partida nem por jogador.
6. **Given** uma partida em que os dois jogadores estão com o deck vazio,
   **When** cada um compra, **Then** cada reset usa só o cemitério do próprio
   jogador — os dois cemitérios nunca se misturam.
7. **Given** um jogador com deck vazio, cemitério vazio e 2 cartas na mão,
   **When** ele compra, **Then** nada muda em nenhuma zona, nenhum erro é
   levantado, e a operação relata que a compra não aconteceu.

---

### User Story 4 - Comprar mais de uma carta (Priority: P2)

A reposição do mulligan compra a mesma quantidade que o jogador devolveu, e o
setup compra 4 de uma vez. Comprar N cartas é N compras, uma a uma, cada uma
passando pelas mesmas guardas na sua vez.

A consequência que precisa valer: comprar 3 com 8 cartas na mão resulta em 10,
não em 11. As duas primeiras entram; a terceira encontra a mão em 10 e não
acontece.

Uma compra múltipla também pode atravessar um reset no meio: se o deck zerar na
segunda carta, a terceira dispara o reset e continua.

**Why this priority**: é composição, não regra nova — mas é onde uma
implementação que cheque a guarda uma vez só, antes do laço, erra por uma
carta.

**Independent Test**: com 8 cartas na mão e deck cheio, pedir 3 compras e
conferir que a mão parou em 10 e que o deck andou exatamente 2 posições.

**Acceptance Scenarios**:

1. **Given** um jogador com 8 cartas na mão e deck cheio, **When** ele compra
   3, **Then** a mão tem 10 e o deck perdeu exatamente 2 cartas.
2. **Given** um jogador com 10 cartas na mão, **When** ele compra 3, **Then**
   nada muda em nenhuma zona.
3. **Given** um jogador com 2 cartas na mão, 1 no deck e 3 no cemitério,
   **When** ele compra 3, **Then** a primeira vem do deck, a segunda dispara o
   reset e as três chegam à mão, que fica com 5.
4. **Given** um pedido de 0 compras, **When** ele é executado, **Then** nada
   muda — pedir zero é válido, não é erro.
5. **Given** uma compra múltipla, **When** conto quantas cartas entraram na
   mão, **Then** o número é conhecido por quem chamou, para que o Upkeep e a
   reposição do mulligan possam distinguir "comprou tudo" de "a mão encheu no
   meio".

---

### User Story 5 - Repetir um reset (Priority: P1)

A ordem do deck depois do reset depende da fonte de aleatoriedade, que chega
por parâmetro, como no setup da feature 003. Com a mesma fonte, o mesmo sorteio
e o mesmo cemitério, o deck resultante é sempre o mesmo.

Sem isso nenhum teste que atravesse um reset é repetível — e a partir do Upkeep
praticamente todo teste longo do motor atravessa um.

O sorteio vem do contador da partida, como todo sorteio desta partida: dois
resets nunca compartilham o mesmo ponto da sequência, e a partida recarregada
do Redis continua de onde parou.

**Why this priority**: decide a assinatura da operação de compra — a fonte de
aleatoriedade e a partida precisam chegar até ela. Adiar significa reescrever
todos os chamadores depois.

**Independent Test**: com o mesmo cemitério e a mesma semente, rodar o reset
duas vezes e comparar a ordem do deck resultante posição a posição.

**Acceptance Scenarios**:

1. **Given** o mesmo cemitério, a mesma semente e o mesmo ponto da sequência,
   **When** o reset acontece duas vezes, **Then** o deck resultante é idêntico,
   posição a posição.
2. **Given** duas sementes que diferem e o mesmo cemitério, **When** o reset
   acontece, **Then** os dois decks resultantes diferem — a semente é o que
   decide, não uma ordem fixa escondida.
3. **Given** uma fonte de teste que devolve uma ordem conhecida, **When** o
   reset acontece, **Then** a ordem do deck é exatamente a que a fonte ditou, e
   nenhum gerador global foi chamado.
4. **Given** um cemitério de N cartas, **When** o reset acontece, **Then** o
   deck é uma permutação exata dessas N cartas — nada duplicado, nada perdido.
5. **Given** uma partida que passou por um reset e foi gravada, **When** outro
   processo a recarrega e provoca um segundo reset, **Then** o resultado é o
   mesmo de uma partida que nunca saiu da memória — a sequência continua de
   onde parou.

---

### User Story 6 - Não quebrar o setup nem o round-trip (Priority: P2)

O setup da feature 003 compra 4 cartas para cada jogador, mais 1 para quem não
recebeu o token, e repõe o que o mulligan devolveu. Essas compras passam a usar
a regra desta feature.

As guardas nunca disparam durante o setup: a mão parte de zero e o deck tem 40.
Então o comportamento observável do setup não muda — mãos de 4 e 5 cartas,
mesmos identificadores, mesma ordem de deck para a mesma semente.

A garantia de round-trip da feature 002 continua valendo: qualquer estado
produzido aqui, reset incluído, sobrevive à ida e à volta pelo Redis.

**Why this priority**: é continuidade, não capacidade nova. Vale como história
porque a regressão aqui é silenciosa: o setup continuaria "funcionando" com uma
mão errada por uma carta.

**Independent Test**: rodar a suíte do setup da feature 003 sem alteração
nenhuma nos testes dela, e conferir que passa.

**Acceptance Scenarios**:

1. **Given** o setup da feature 003 com a mesma semente e os mesmos decks,
   **When** ele roda depois desta feature, **Then** produz exatamente a mesma
   partida que produzia antes — mãos, ordem de deck e identificadores
   inclusive.
2. **Given** o setup terminado, **When** conto as mãos, **Then** o dono do
   token tem 4 cartas e o oponente tem 5.
3. **Given** uma partida logo depois de um reset de deck, **When** ela vai ao
   Redis e volta, **Then** o estado reconstruído é igual ao original — ordem do
   deck novo, cemitério vazio e contadores inclusive.
4. **Given** o código depois desta feature, **When** procuro onde uma carta sai
   do deck e entra na mão, **Then** existe um único lugar, e todos os
   chamadores passam pela regra da §9.

---

### Edge Cases

- **Mão em 10 com deck cheio.** Não compra. Deck intacto, mão intacta,
  cemitério intacto.
- **Mão em 9.** Compra, e fica com 10. A guarda é sobre o estado **antes** da
  compra: ela impede a 11ª carta, não a 10ª.
- **Mão em 10 e deck vazio.** Não compra e **não reseta**. A guarda de mão é
  verificada antes do reset, então o cemitério fica onde está. Este é o caso
  que separa a ordem dos passos de qualquer outra ordem possível.
- **Deck vazio, cemitério com cartas, mão com menos de 10.** Reseta e compra,
  na mesma operação. Quem chamou vê uma compra normal.
- **Deck vazio e cemitério vazio, mão com menos de 10.** Não há de onde comprar
  nem o que resetar. A compra não acontece, pelo mesmo caminho da mão cheia:
  nada muda, nenhum erro é levantado, e quem chamou segue. É defesa contra
  estado corrompido, não caso de jogo — a conta da seção Clarifications mostra
  que o estado é inalcançável em partida legal.
- **Reset com cemitério de uma carta só.** Vale: o deck novo tem 1 carta, a
  compra a leva, e o deck volta a zero. O próximo reset encontra o cemitério
  vazio.
- **Compra múltipla que enche a mão no meio.** As compras seguintes não
  acontecem. Comprar 3 com 8 na mão dá 10, não 11.
- **Compra múltipla que atravessa um reset.** O reset acontece na carta em que
  o deck zerou, e as compras seguintes continuam do deck novo.
- **Compra de 0 cartas.** Válida, e nada muda. Existe porque o mulligan de 0
  cartas repõe 0.
- **Unidade morta voltando ao deck.** Volta como carta comum: sem dano
  acumulado e sem modificadores. O que ela conserva é o identificador.
- **Identidade através do reset.** O contador de identidade da partida **não**
  avança em nenhum caminho desta feature. Reset não cunha carta nova, e compra
  também não.
- **Cemitério do oponente.** Nunca entra. Cada reset usa só o cemitério do
  jogador que está comprando.
- **Comprar não descarta.** Nenhum caminho desta feature põe carta no
  cemitério. Descarte, morte e resolução de feitiço são de outras features.

## Requirements *(mandatory)*

### Functional Requirements

**A regra geral da §9**

- **FR-001**: O sistema MUST expor uma única operação de compra, e ela MUST ser
  a única porta pela qual uma carta sai do deck e entra na mão.
- **FR-002**: A operação MUST avaliar os três passos da §9 nesta ordem: guarda
  de mão, depois reset de deck, depois o movimento.
- **FR-003**: A guarda de mão MUST ser verificada **antes** do reset. Um
  jogador com a mão em 10 e o deck vazio MUST NOT resetar o deck.
- **FR-004**: A operação MUST agir sobre um jogador só. O estado do oponente
  MUST NOT ser lido nem alterado.

**Guarda de mão**

- **FR-005**: Quando a mão do jogador tiver 10 ou mais cartas, a compra MUST
  NOT acontecer.
- **FR-006**: Uma compra que não aconteceu MUST NOT alterar nenhuma zona: mão,
  deck, banco e cemitério MUST continuar com as mesmas cartas, na mesma ordem.
- **FR-007**: Uma compra que não aconteceu MUST NOT ser tratada como erro ou
  recusa. A operação MUST terminar normalmente e quem chamou MUST poder seguir
  sem tratar exceção.
- **FR-008**: A operação MUST informar a quem chamou se a compra aconteceu, e
  qual carta foi comprada quando aconteceu.
- **FR-009**: O teto de mão MUST ser 10, o valor da §12, e MUST vir de uma
  constante nomeada compartilhada, não repetida em cada ponto de uso.

**Reset de deck**

- **FR-010**: Quando o deck estiver vazio e a guarda de mão não tiver
  disparado, todo o cemitério do jogador MUST virar o novo deck, embaralhado.
- **FR-011**: Depois do reset o cemitério do jogador MUST ficar vazio.
- **FR-012**: O reset MUST NOT tocar a mão, o banco, o Nexus nem as energias do
  jogador.
- **FR-013**: Depois do reset a compra MUST prosseguir e entregar a carta do
  topo do deck novo, na mesma operação.
- **FR-014**: O reset MUST ser ilimitado — MUST acontecer toda vez que o deck
  zerar, quantas vezes for, sem contador e sem teto.
- **FR-015**: O reset MUST usar apenas o cemitério do jogador que está
  comprando.
- **FR-016**: O deck resultante do reset MUST ser uma permutação exata das
  cartas que estavam no cemitério — nenhuma perdida, nenhuma duplicada.
- **FR-017**: A operação de compra MUST NOT pôr carta no cemitério em nenhum
  dos seus caminhos. Comprar não descarta.

**Identidade**

- **FR-018**: A carta que volta do cemitério para o deck MUST manter o
  identificador que já tinha. O reset MUST NOT cunhar identidade nova.
- **FR-019**: O contador de identidade de carta da partida MUST NOT avançar em
  nenhum caminho desta feature.
- **FR-020**: A carta comprada MUST chegar à mão com o mesmo identificador que
  tinha no deck.

**Aleatoriedade**

- **FR-021**: A fonte de aleatoriedade MUST chegar por parâmetro à operação de
  compra, atrás da interface do projeto, como já acontece no setup da feature
  003. Nenhum gerador global MUST ser chamado.
- **FR-022**: O sorteio que embaralha o deck resetado MUST vir do contador de
  sorteios da partida, para que dois resets nunca compartilhem o mesmo ponto da
  sequência.
- **FR-023**: Com a mesma fonte, o mesmo ponto da sequência e o mesmo
  cemitério, o deck resultante MUST ser sempre o mesmo, em qualquer processo e
  depois de qualquer recarga do Redis.
- **FR-024**: O contador de sorteios MUST avançar apenas quando um reset
  acontece. Uma compra sem reset MUST NOT consumir aleatoriedade.

**Compra múltipla**

- **FR-025**: O sistema MUST oferecer a compra de N cartas, e cada uma das N
  MUST passar pelas guardas na sua vez.
- **FR-026**: Comprar N cartas MUST parar de entregar cartas assim que a mão
  atingir 10, sem erro.
- **FR-027**: Comprar N cartas MUST informar quantas efetivamente entraram na
  mão.
- **FR-028**: Comprar 0 cartas MUST ser válido e MUST NOT alterar nada.

**Migração dos chamadores existentes**

- **FR-029**: As compras do setup da feature 003 — as 4 iniciais, a de
  compensação de quem não recebeu o token, e a reposição do mulligan — MUST
  passar a usar a regra desta feature.
- **FR-030**: O comportamento observável do setup MUST NOT mudar: mesma
  semente e mesmos decks MUST produzir a mesma partida, com mãos de 4 e 5
  cartas.
- **FR-031**: Depois desta feature MUST existir um único ponto no código onde
  uma carta sai do deck e entra na mão. O movimento MUST NOT estar escrito duas
  vezes.
- **FR-032**: Qualquer estado produzido por esta feature, incluindo um estado
  logo depois de um reset, MUST sobreviver à ida e à volta pelo Redis com
  igualdade campo a campo.

**Deck e cemitério vazios ao mesmo tempo**

- **FR-033**: Quando o deck e o cemitério estiverem os dois vazios e a mão
  tiver menos de 10 cartas, a compra MUST NOT acontecer, e a operação MUST
  terminar sem levantar erro — o mesmo caminho da mão cheia.
- **FR-034**: Nesse caso nenhuma zona MUST ser alterada, nenhum sorteio MUST
  ser consumido, e o contador de identidade de carta MUST NOT avançar.

### Key Entities

Esta feature não cria estado novo. Ela opera sobre o que a feature 002 já
define:

- **Deck do jogador**: pilha ordenada de cartas da partida. O topo é a
  primeira posição, e comprar é tirar dali.
- **Mão do jogador**: cartas jogáveis, com teto de 10 aplicado na compra.
- **Cemitério do jogador**: cartas gastas e unidades mortas. É a fonte do
  reset, e esta feature só o esvazia — nunca o alimenta.
- **Carta da partida**: identidade própria mais o identificador do molde do
  catálogo. A identidade nasce com a carta e atravessa todas as zonas.
- **Resultado de compra**: o que a operação devolve a quem chamou — se a compra
  aconteceu e qual carta veio.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma compra com a mão em 10 deixa deck, mão, banco e cemitério
  idênticos ao estado anterior, campo a campo, e não levanta erro.
- **SC-002**: Uma compra com a mão em 9 e deck com cartas resulta em uma mão de
  10, e o deck perde exatamente 1 carta.
- **SC-003**: Uma compra com o deck vazio e o cemitério com N cartas termina
  com o cemitério vazio, o deck com N-1 cartas e 1 carta a mais na mão.
- **SC-004**: 100% dos identificadores que estavam no cemitério antes do reset
  estão, depois dele, entre o deck e a carta comprada — nenhum perdido, nenhum
  novo.
- **SC-005**: O mesmo cemitério com a mesma fonte de aleatoriedade e o mesmo
  ponto da sequência produz o deck resultante idêntico em 100% das repetições.
- **SC-006**: Uma partida jogada com resets sucessivos nunca termina por deck
  acabado: em 100 resets encadeados, a operação continua entregando cartas.
- **SC-007**: Comprar 3 cartas com 8 na mão resulta em uma mão de 10 e no
  relato de que 2 compras aconteceram.
- **SC-008**: A suíte do setup da feature 003 passa sem nenhuma alteração nos
  testes dela.
- **SC-009**: Qualquer estado produzido por esta feature volta idêntico do
  Redis, campo a campo.
- **SC-010**: Existe exatamente 1 lugar no código onde uma carta sai do deck e
  entra na mão.
- **SC-011**: Uma compra com deck e cemitério os dois vazios deixa o estado do
  jogador idêntico, campo a campo, e não levanta erro.

## Assumptions

- A operação de compra recebe a partida e a identidade do jogador, além da
  fonte de aleatoriedade, porque o sorteio do reset precisa do contador que
  vive na partida. É a mesma forma que o setup da feature 003 já usa.
- O resultado da compra é comunicado como valor de retorno, não como exceção
  nem como campo novo no estado: a mão cheia é fluxo normal do jogo, e quem
  chama precisa distinguir "comprou" de "não comprou" sem `try`.
- A compra múltipla é composição da compra única, não uma segunda regra. Ela
  não conhece as guardas; só chama a compra N vezes e conta quantas
  aconteceram.
- O teto de mão em 10 é a constante da §12, nomeada e declarada uma vez só. Ela
  vive junto de quem a aplica, que é a regra de compra — o mesmo lugar em que
  `DECK_SIZE` mora com a validação de deck e `STARTING_NEXUS` mora com o estado
  do jogador. O projeto não tem (nem precisa de) um módulo único de constantes.
- Nada aqui grava no Redis. Quem grava é o chamador, pelo caminho atômico que a
  feature 003 entregou.
- O Upkeep da §4 não é implementado aqui, mas a assinatura da compra é
  desenhada para ele: uma compra por jogador, por rodada, sem tratamento de
  erro.

## Out of Scope

- **O Upkeep da §4.** Quem chama a compra no início de cada rodada, junto da
  recarga de energia, é outra feature.
- **Descarte, mortes e resolução de feitiço** — todos os caminhos que põem
  carta no cemitério. Esta feature só consome o cemitério.
- **Feitiços que compram carta.** Quando existirem, usam esta regra sem
  mudá-la.
- **Qualquer regra sobre o que o jogador faz com a carta comprada.**
- **Notificação ao cliente.** Que uma compra aconteceu, ou que um reset
  aconteceu, é assunto do consumer e da view por jogador, não desta operação.
- **Teto de banco (§5A).** É aplicado ao jogar unidade, e não aqui. O único
  teto desta feature é o de mão.
