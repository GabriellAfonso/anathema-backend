# Feature Specification: Setup de Partida

**Feature Branch**: `003-match-setup`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Setup de partida: tudo que acontece uma vez, antes da Rodada 1, para transformar dois jogadores pareados em uma partida pronta para o primeiro Upkeep."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. A §3 é o contrato
desta feature, passo a passo. A §9 (compra e reset de deck) e a §12
(constantes) são referência. A §2 descreve o estado que esta feature preenche
— e que ela precisa crescer para caber a espera do mulligan.

## Clarifications

### Sessão 2026-09-10

- **P: Quando cada mulligan é aplicado — na chegada, ou os dois juntos quando
  o segundo responde?**
  R: Na chegada. Os passos (a) a (d) executam assim que a resposta daquele
  jogador chega, e o estado guarda só que ele já respondeu. A seleção nunca
  precisa persistir: as cartas separadas voltam ao deck dentro da mesma
  operação, e não existe "set-aside" gravado no Redis. O preço é que os dois
  jogadores consomem a fonte de aleatoriedade na ordem em que responderam, e
  quem respondeu primeiro muda o resultado. É preço aceito: repetir o setup
  exige repetir também a ordem de chegada, o que um teste controla e a
  produção não precisa.

- **P: De onde vem a aleatoriedade no mulligan e no sorteio do token, que
  acontecem depois da criação e possivelmente em outro worker?**
  R: De uma semente guardada na partida. A fonte é reconstituída da semente a
  cada operação, e o estado carrega quanto da sequência já foi consumido, para
  que duas operações não repitam os mesmos números. Assim qualquer worker,
  depois de qualquer recarga do Redis, produz a mesma sequência — o setup é
  reproduzível a partir do estado gravado, e não só de um arranjo de teste em
  um processo só. A alternativa, injetar uma fonte nova a cada chamada sem
  semente no estado, deixaria dois workers com dois fluxos diferentes.

- **P: Duas respostas de mulligan concorrentes, em workers diferentes, podem
  perder uma das duas?**
  R: Não. Esta feature entrega a mutação atômica no store para o caminho de
  registrar o mulligan — o read-modify-write que a feature 002 registrou como
  adiado, e que o mulligan simultâneo é o primeiro a exercer de verdade.
  Fazer agora evita que os handlers de gameplay nasçam em cima de um caminho
  sabidamente inseguro; é a mesma peça que todo caminho de mutação futuro vai
  reusar. Isto emenda o Out of Scope da feature 002, que deixava a
  atomicidade para depois.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nascer uma partida com os dois decks prontos (Priority: P1)

Dois jogadores acabaram de ser pareados. Cada um chega com um deck: uma lista
de 40 identificadores de carta. Do outro lado precisa sair uma partida com os
dois decks embaralhados, cada carta com identidade própria, Nexus 20 dos dois
lados, energia zerada e 4 cartas na mão de cada um.

Deck ruim não vira partida: a validação da feature 001 roda antes de qualquer
outra coisa, e a recusa nomeia todos os problemas de uma vez.

Hoje `Match.start` produz uma partida com as quatro zonas vazias, e o próprio
código diz que é assim porque o setup é a §3. Esta feature é a §3.

**Why this priority**: é o chão. Mulligan, sorteio do token e compensação são
todos operações sobre uma partida que precisa existir com deck e mão primeiro.

**Independent Test**: entregar dois decks válidos e uma fonte de
aleatoriedade, e conferir campo a campo que a partida nasce com 36 cartas em
cada deck, 4 em cada mão, Nexus 20, energia máxima e atual em 0, e 80
identificadores distintos.

**Acceptance Scenarios**:

1. **Given** dois decks válidos de 40 cartas, **When** crio a partida,
   **Then** cada jogador tem 4 cartas na mão e 36 no deck, e nenhuma carta se
   perdeu no caminho.
2. **Given** dois decks válidos, **When** leio o estado inicial de cada
   jogador, **Then** Nexus é 20, energia máxima é 0 e energia atual é 0.
3. **Given** um deck com três cópias do mesmo `card_id`, **When** crio a
   partida, **Then** as três viram cartas distintas e endereçáveis
   separadamente.
4. **Given** os dois decks criados, **When** junto os identificadores dos dois
   lados, **Then** são 80 valores e nenhum se repete.
5. **Given** um deck com 39 cartas, quatro cópias de um `card_id` e uma carta
   fora do catálogo, **When** tento criar a partida, **Then** a criação é
   recusada nomeando os três problemas, e nenhuma partida é gravada.
6. **Given** um deck válido e um inválido, **When** tento criar a partida,
   **Then** a criação é recusada e nenhuma partida nasce — não existe partida
   com um lado só.

---

### User Story 2 - Trocar cartas no mulligan, na ordem que a regra exige (Priority: P1)

Cada jogador olha as 4 cartas e escolhe de 0 a 4 para trocar. A ordem das
operações é a regra: as escolhidas saem da mão e ficam de lado, o jogador
compra do deck a mesma quantidade que devolveu, **só então** as separadas
voltam ao deck, e o deck é reembaralhado.

Errar essa ordem muda o jogo: se as cartas voltassem ao deck antes da compra,
uma carta jogada fora poderia ser recomprada na hora.

A carta devolvida mantém a identidade que já tinha. É a mesma carta voltando,
não uma nova.

**Why this priority**: é a única decisão de jogador em todo o setup, e a
ordem das operações é a parte da §3 mais fácil de implementar errado sem que
nenhum teste de contagem perceba.

**Independent Test**: com uma fonte de aleatoriedade controlada, devolver
cartas conhecidas e conferir que nenhuma delas aparece entre as compradas na
reposição, e que a mão continua com 4 cartas.

**Acceptance Scenarios**:

1. **Given** uma mão de 4 cartas, **When** o jogador troca 2, **Then** a mão
   volta a ter 4 cartas e o deck volta a ter 36.
2. **Given** uma mão de 4 cartas com identificadores conhecidos, **When** o
   jogador troca 2, **Then** nenhuma das 2 devolvidas está entre as 2
   compradas.
3. **Given** as 2 cartas devolvidas, **When** procuro por elas depois do
   mulligan, **Then** as duas estão no deck, com os mesmos identificadores que
   tinham na mão.
4. **Given** uma mão de 4 cartas, **When** o jogador troca 0, **Then** a mão
   fica exatamente como estava, e isso é uma escolha válida — não um erro nem
   uma ausência de resposta.
5. **Given** uma mão de 4 cartas, **When** o jogador troca as 4, **Then** a mão
   tem 4 cartas novas e nenhuma das 4 antigas, e as 4 antigas estão no deck.
6. **Given** um jogador que já respondeu o mulligan, **When** ele envia outro,
   **Then** o segundo é recusado citando o `user_id` — o mulligan é uma vez por
   partida.
7. **Given** uma seleção que cita uma carta que não está na mão daquele
   jogador — do deck, do cemitério, da mão do oponente ou inexistente —,
   **When** o mulligan é enviado, **Then** é recusado nomeando a carta, e a mão
   não é tocada.
8. **Given** um `user_id` que não joga a partida, **When** ele envia um
   mulligan, **Then** é recusado citando o `user_id`.

---

### User Story 3 - Esperar os dois jogadores sem travar a partida (Priority: P1)

O mulligan é a única coisa simultânea da partida inteira. Os dois jogadores
decidem em paralelo, e o setup não avança para o sorteio do token até os dois
terem respondido.

Enquanto espera, a partida já existe e já está gravada. As duas decisões
chegam por duas conexões websocket diferentes, possivelmente em workers
diferentes do uvicorn — então "estou esperando o mulligan de fulano" precisa
estar no estado, não na memória de um processo.

A fase atual precisa distinguir esse momento das cinco fases da §2: a partida
não está em Upkeep ainda, e nunca esteve.

**Why this priority**: sem isto o mulligan simultâneo não é implementável em
mais de um worker, e a partida gravada no meio do setup volta do Redis sem
saber de quem ainda está esperando.

**Independent Test**: criar a partida, gravar, reler, enviar o mulligan de um
jogador só, gravar, reler de novo e conferir que o estado ainda diz que espera
o outro, e que o token ainda não foi sorteado.

**Acceptance Scenarios**:

1. **Given** uma partida recém-criada, **When** leio a fase atual, **Then** ela
   diz "esperando mulligan" e não é nenhuma das cinco fases da §2.
2. **Given** uma partida recém-criada, **When** pergunto de quem o setup está
   esperando, **Then** a resposta nomeia os dois `user_id`.
3. **Given** o mulligan de um jogador só registrado, **When** faço a mesma
   pergunta, **Then** a resposta nomeia só o outro `user_id`, e a fase continua
   sendo a espera.
4. **Given** o mulligan de um jogador só registrado, **When** leio o dono do
   token, **Then** o sorteio ainda não aconteceu e nenhum jogador comprou a
   quinta carta.
5. **Given** o mulligan dos dois registrado, **When** leio a fase, **Then** ela
   deixou de ser a espera e a partida está posicionada para o Upkeep da Rodada
   1.
6. **Given** uma partida em qualquer ponto do setup, **When** ela vai ao Redis
   e volta, **Then** a fase, quem já respondeu e quem falta voltam iguais.
7. **Given** os dois mulligans disparados ao mesmo tempo por processos
   diferentes, **When** os dois são registrados, **Then** as duas respostas
   ficam gravadas e nenhuma sobrescreve a outra.

---

### User Story 4 - Sortear o token e compensar quem não o recebeu (Priority: P1)

Com os dois mulligans respondidos, sorteia-se qual jogador recebe o token de
ataque na Rodada 1. Quem **não** recebeu compra 1 carta adicional — a
compensação pela desvantagem de iniciativa da §3. Ele termina com 5 na mão; o
outro, com 4.

A prioridade nasce com o dono do token, e a partida fica posicionada para o
Upkeep da Rodada 1. Executar o Upkeep não é desta feature.

**Why this priority**: é o que fecha o setup. Sem o sorteio a partida não tem
como começar, e sem a compensação a mão inicial contradiz a §12.

**Independent Test**: com uma fonte de aleatoriedade que force cada um dos dois
resultados, conferir que a mão do dono do token tem 4 cartas, a do outro tem 5,
e a prioridade é do dono do token nos dois casos.

**Acceptance Scenarios**:

1. **Given** os dois mulligans respondidos, **When** o setup termina, **Then**
   exatamente um jogador é o dono do token.
2. **Given** o dono do token sorteado, **When** conto as mãos, **Then** a dele
   tem 4 cartas e a do oponente tem 5.
3. **Given** o dono do token sorteado, **When** leio a prioridade, **Then** ela
   é do dono do token.
4. **Given** o setup terminado, **When** leio o resto do estado, **Then** a
   rodada é 1, o token não foi consumido, os passes consecutivos são 0, a pilha
   está vazia, os dois bancos e os dois cemitérios estão vazios, e a energia
   dos dois continua em 0.
5. **Given** uma fonte que sorteia o primeiro jogador do par e outra que
   sorteia o segundo, **When** rodo o setup com cada uma, **Then** o dono do
   token e a mão de 5 cartas trocam de lado junto.

---

### User Story 5 - Repetir o mesmo setup duas vezes (Priority: P1)

Embaralhar e sortear o token consomem aleatoriedade. As duas precisam ser
controláveis de fora: com a mesma semente, os mesmos decks e as mesmas escolhas
de mulligan, o setup produz exatamente a mesma partida.

Sem isso nenhum teste do resto do motor é repetível — combate, pilha e compra
todos partem de uma partida montada pelo setup.

A fonte chega por parâmetro, como o catálogo e o cliente Redis já chegam neste
projeto, e fica atrás de uma interface própria do projeto em vez de um módulo
importado no ponto de uso. A semente vive na partida, junto de quanto da
sequência já foi consumido, para que o mulligan e o sorteio — que acontecem
depois da criação, possivelmente em outro worker — continuem a mesma sequência
de onde ela parou.

**Why this priority**: é uma exigência que atravessa as outras quatro
histórias e decide a forma da assinatura de criação. Adiar significa reescrever
tudo depois.

**Independent Test**: rodar o setup duas vezes com a mesma semente, os mesmos
decks, as mesmas escolhas e a mesma ordem de chegada, e comparar as duas
partidas campo a campo, identificadores e ordem de deck inclusive.

**Acceptance Scenarios**:

1. **Given** a mesma semente, os mesmos dois decks, as mesmas escolhas de
   mulligan e a mesma ordem de chegada, **When** rodo o setup duas vezes,
   **Then** as duas partidas são iguais em ordem de deck, conteúdo de mão, dono
   do token e prioridade.
2. **Given** duas sementes que diferem, os mesmos decks e as mesmas escolhas,
   **When** rodo o setup duas vezes, **Then** as duas partidas diferem — a
   semente é o que decide, e não uma ordem fixa escondida.
3. **Given** uma fonte de teste que devolve uma ordem conhecida, **When** rodo
   o setup, **Then** a ordem do deck é exatamente a que a fonte ditou, e
   nenhuma chamada a um gerador global aconteceu.
4. **Given** um deck de 40 cartas, **When** embaralho, **Then** o resultado é
   uma permutação das mesmas 40 cartas — nada duplicado, nada perdido.
5. **Given** uma partida gravada logo depois do primeiro mulligan, **When**
   outro processo a recarrega e recebe o segundo mulligan, **Then** o resultado
   é o mesmo de um setup que nunca saiu da memória — a sequência continua de
   onde parou, não do começo.

---

### User Story 6 - Não quebrar quem já cria e lê a partida (Priority: P2)

Três pontos já dependem da criação da partida e continuam funcionando com a
forma nova: o store que grava e lê no Redis, o consumer de matchmaking que cria
a partida ao parear dois jogadores, e o substituto de teste do store.

O estado novo — com a espera do mulligan — precisa sobreviver à ida e à volta
pelo Redis como todo o resto. A garantia de round-trip da feature 002 continua
valendo depois desta.

**Why this priority**: é continuidade, não capacidade nova. Vale como história
porque tem teste próprio e porque a regressão aqui é silenciosa.

**Independent Test**: parear dois jogadores pelo caminho existente, gravar,
reler e conferir que a partida volta completa, com mãos, decks e a espera do
mulligan intactos.

**Acceptance Scenarios**:

1. **Given** uma partida em qualquer ponto do setup, **When** ela vai ao Redis
   e volta, **Then** o estado reconstruído é igual ao original — ordem de deck,
   mãos, identificadores, contador e a espera do mulligan inclusive.
2. **Given** o caminho de criação do matchmaking, **When** dois jogadores são
   pareados, **Then** a partida nasce com o setup até a espera do mulligan
   executado, e os dois recebem o aviso de pareamento.
3. **Given** um deck recusado no pareamento, **When** o matchmaking tenta criar
   a partida, **Then** os dois jogadores recebem um erro que nomeia o problema,
   e nenhuma partida meio-criada fica no Redis.
4. **Given** a partida criada, **When** pergunto se cada um dos dois `user_id`
   participa, **Then** a resposta é positiva para os dois e negativa para um
   terceiro e para um socket sem usuário autenticado.

---

### Edge Cases

- **Mulligan de 0 cartas.** Escolha válida e resposta completa. É diferente de
  "ainda não respondeu": o jogador que troca 0 já avançou o setup.
- **Mulligan das 4 cartas.** Escolha válida. Como as 4 saem da mão antes da
  compra, as 4 compradas vêm de um deck de 36 e nenhuma delas pode ser uma das
  devolvidas.
- **Seleção com a mesma carta repetida.** Citar duas vezes o mesmo
  identificador é recusa, não uma troca de 1 contada como 2 — a segunda
  ocorrência não está mais na mão.
- **Seleção com mais de 4 cartas.** Impossível sem repetição ou sem citar carta
  de fora da mão; nos dois casos a recusa já existe e nomeia o problema.
- **Mulligan depois do setup.** Um mulligan que chega quando a partida já saiu
  da espera é recusado pelo mesmo caminho da segunda tentativa.
- **Carta devolvida volta com o mesmo identificador.** Não é uma carta nova: o
  contador de identificadores não avança no mulligan.
- **Ordem do deck depois do reembaralhamento.** As cartas devolvidas podem cair
  em qualquer posição, topo inclusive. A garantia é sobre a compra de
  reposição, que já aconteceu, não sobre a posição final delas.
- **Os dois mulligans chegando ao mesmo tempo.** São duas conexões
  possivelmente em workers diferentes, lendo e gravando a mesma partida. O
  registro é atômico: as duas respostas ficam registradas, em alguma ordem, e
  nenhuma se perde.
- **Ordem de chegada muda o resultado.** Como cada mulligan executa na chegada,
  os dois consomem a sequência da semente na ordem em que responderam.
  Trocar a ordem de chegada, com as mesmas escolhas, produz outra partida — e
  isso é comportamento definido, não corrida. Repetir um setup exige repetir
  também a ordem.
- **Deck recusado.** A partida não nasce. Não existe estado parcial gravado, e
  não existe partida com um jogador só.
- **Fila de espera sem timeout.** Um jogador que nunca envia o mulligan trava a
  partida na espera. Nada nesta feature resolve isso — é o mesmo problema de
  relógio que a §13 do Fluxo de Partida registra em aberto, e mora na camada de
  transporte.
- **Teto de mão e reset de deck.** Nenhuma das duas condições da §9 pode
  ocorrer durante o setup: a mão parte de zero e o deck tem 40 cartas. O
  movimento de tirar do topo do deck e pôr na mão, porém, é o mesmo que a §9 vai
  usar, e não pode acabar escrito duas vezes.
- **Fase Combate no conjunto.** A fase nova entra ao lado das cinco da §2, não
  no lugar de nenhuma delas. Nenhuma partida volta à espera do mulligan depois
  de sair dela.

## Requirements *(mandatory)*

### Functional Requirements

**Entrada e validação de deck**

- **FR-001**: A criação da partida MUST receber o deck de cada jogador como
  parâmetro: uma lista ordenada de 40 identificadores de carta.
- **FR-002**: Os dois decks MUST ser validados antes de qualquer outra coisa —
  antes de embaralhar, antes de cunhar identificador e antes de gravar.
- **FR-003**: A validação MUST reaproveitar a regra de deck da feature 001 (40
  cartas, no máximo 3 cópias do mesmo identificador, toda carta existente no
  catálogo). Nenhuma dessas três regras MUST ser reescrita nesta feature.
- **FR-004**: Deck recusado MUST impedir a partida de nascer, e a recusa MUST
  nomear cada problema encontrado, não só o primeiro.
- **FR-005**: Um deck inválido de qualquer um dos dois lados MUST recusar a
  partida inteira. Não MUST existir partida gravada com um lado só ou com um
  deck não validado.
- **FR-006**: O catálogo MUST chegar por parâmetro a quem valida e a quem
  materializa as cartas, nunca por import no ponto de uso.

**Materialização e embaralhamento**

- **FR-007**: Cada identificador do deck MUST virar uma carta concreta daquela
  partida, com identidade própria, usando o contador de identificadores que já
  vive no estado (feature 002).
- **FR-008**: Três cópias do mesmo identificador MUST virar três cartas
  distintas e endereçáveis separadamente.
- **FR-009**: Os 80 identificadores dos dois jogadores MUST ser distintos entre
  si — o espaço é único na partida, não por jogador.
- **FR-010**: O deck de cada jogador MUST ser embaralhado, e o resultado MUST
  ser uma permutação exata das mesmas 40 cartas.

**Valores iniciais**

- **FR-011**: Cada jogador MUST começar com Nexus 20, energia máxima 0 e
  energia atual 0. Subir a energia para 1 é do primeiro Upkeep, e não é desta
  feature.
- **FR-012**: A partida MUST começar na rodada 1, com token não consumido,
  passes consecutivos em 0, pilha vazia, e banco e cemitério vazios dos dois
  lados.

**Compra**

- **FR-013**: Cada jogador MUST comprar 4 cartas do topo do próprio deck, na
  ordem em que o embaralhamento as deixou.
- **FR-014**: O movimento de tirar a carta do topo do deck e pô-la na mão MUST
  existir em um único lugar, reutilizável pela regra geral de compra da §9. As
  duas condições da §9 — teto de mão e reset de deck — não podem ocorrer
  durante o setup, mas o movimento MUST NOT acabar escrito duas vezes.

**Mulligan**

- **FR-015**: Cada jogador MUST poder escolher de 0 a 4 cartas da própria mão
  para trocar. Zero e quatro MUST ser escolhas válidas.
- **FR-016**: O mulligan MUST executar nesta ordem, e a ordem é a regra: (a) as
  cartas escolhidas saem da mão e ficam de lado; (b) o jogador compra do deck a
  mesma quantidade que devolveu; (c) só então as separadas voltam para o deck;
  (d) o deck é reembaralhado.
- **FR-017**: Uma carta devolvida no mulligan MUST NOT poder ser comprada na
  reposição do mesmo mulligan.
- **FR-018**: A carta devolvida ao deck MUST manter o identificador que já
  tinha. O contador de identificadores MUST NOT avançar no mulligan.
- **FR-019**: O mulligan MUST ser aceito uma única vez por jogador por partida.
  Uma segunda tentativa do mesmo jogador MUST ser recusada citando o `user_id`.
- **FR-020**: Um mulligan enviado por um `user_id` que não joga a partida MUST
  ser recusado citando o `user_id`.
- **FR-021**: Uma seleção que cita uma carta que não está na mão daquele jogador
  MUST ser recusada nomeando a carta, e a mão MUST NOT ser alterada.
- **FR-022**: Uma seleção que cita o mesmo identificador mais de uma vez MUST
  ser recusada pelo mesmo caminho: a segunda ocorrência não está mais na mão.
- **FR-023**: Uma recusa de mulligan MUST deixar o estado exatamente como
  estava — nem a mão, nem o deck, nem o registro de quem já respondeu.

**Espera simultânea no estado**

- **FR-024**: O estado da partida MUST representar "esperando o mulligan de
  quem ainda não respondeu", e MUST responder quais `user_id` ainda faltam.
- **FR-025**: A fase atual MUST distinguir esse momento das cinco fases da §2.
  O conjunto fechado de fases cresce para caber a espera do setup; ele deixa de
  ter exatamente cinco valores, o que emenda o FR-002 da feature 002.
- **FR-026**: A espera MUST viver no estado gravado, não na memória de um
  processo: as duas decisões chegam por conexões diferentes, possivelmente em
  workers diferentes do uvicorn.
- **FR-027**: O setup MUST NOT avançar para o sorteio do token enquanto os dois
  mulligans não tiverem sido registrados.
- **FR-028**: Registrar o mulligan de um jogador MUST deixar a partida gravada e
  legível por outro worker, com a espera do outro jogador intacta.
- **FR-029**: O mulligan de um jogador MUST executar por inteiro — os passos
  (a) a (d) — no momento em que a resposta dele chega, e não quando o segundo
  jogador responder.
- **FR-030**: A seleção de mulligan MUST NOT ser guardada no estado. As cartas
  separadas voltam ao deck dentro da mesma operação, então não existe conjunto
  de cartas "de lado" que sobreviva a uma gravação.

**Token de ataque e compensação**

- **FR-031**: Com os dois mulligans registrados, o sistema MUST sortear qual
  jogador recebe o token de ataque na Rodada 1.
- **FR-032**: O jogador que NÃO recebeu o token MUST comprar 1 carta adicional,
  depois do mulligan.
- **FR-033**: Ao fim do setup, a mão do dono do token MUST ter 4 cartas e a do
  oponente MUST ter 5.
- **FR-034**: A prioridade MUST nascer com o dono do token.
- **FR-035**: A partida MUST ficar posicionada para o Upkeep da Rodada 1.
  Executar o Upkeep não é desta feature.

**Aleatoriedade injetada**

- **FR-036**: Embaralhar e sortear o dono do token MUST consumir a mesma fonte
  de aleatoriedade, e as duas MUST ser controláveis de fora.
- **FR-037**: A fonte MUST chegar por parâmetro, como o catálogo e o cliente
  Redis já chegam neste projeto.
- **FR-038**: A fonte MUST ficar atrás de uma interface própria do projeto, e
  nenhum código de domínio MUST importar um gerador de aleatoriedade no ponto de
  uso.
- **FR-039**: A partida MUST carregar uma semente, e a fonte usada em cada
  operação do setup MUST ser reconstituída dela. A semente MUST nascer na
  criação da partida e MUST NOT mudar depois.
- **FR-040**: A partida MUST carregar quanto da sequência já foi consumido, para
  que duas operações do setup não repitam os mesmos números.
- **FR-041**: Semente e consumo MUST sobreviver à ida e à volta pelo Redis, de
  modo que qualquer worker, depois de qualquer recarga, continue a mesma
  sequência de onde ela parou.
- **FR-042**: Com a mesma semente, os mesmos decks, as mesmas escolhas de
  mulligan e a mesma ordem de chegada das duas respostas, o setup MUST produzir
  exatamente a mesma partida — ordem de deck, conteúdo de mão, identificadores,
  dono do token e prioridade inclusive.
- **FR-043**: A semente MUST poder ser fornecida de fora na criação da partida.
  Um teste MUST poder fixá-la; a produção MUST obtê-la de uma fonte de entropia
  do sistema.

**Concorrência**

- **FR-044**: Registrar o mulligan de um jogador MUST ser uma mutação atômica
  sobre a partida gravada: ler, alterar e gravar MUST NOT poder ser
  intercalados por outra resposta.
- **FR-045**: Duas respostas de mulligan concorrentes, vindas de workers
  diferentes, MUST NOT poder perder uma das duas. As duas MUST ficar
  registradas, em alguma ordem.
- **FR-046**: A mutação atômica MUST ficar no store, atrás da mesma interface
  que já esconde o Redis do resto do projeto, e MUST ser reutilizável pelos
  caminhos de mutação que as features de gameplay vão trazer. Isto emenda o Out
  of Scope da feature 002, que deixava a atomicidade para depois.

**Continuidade**

- **FR-047**: A serialização MUST levar e trazer o estado novo sem perda — a
  espera do mulligan, a semente, o consumo, as mãos, a ordem dos decks e os
  identificadores inclusive. A garantia de round-trip da feature 002 MUST
  continuar valendo.
- **FR-048**: O caminho de criação da partida MUST passar a exigir os dois
  decks e a semente, e seus chamadores MUST acompanhar.
- **FR-049**: O consumer de matchmaking MUST continuar criando a partida ao
  parear dois jogadores, agora fornecendo os dois decks.
- **FR-050**: O substituto de teste do store MUST acompanhar a mudança de forma
  da criação e o caminho de mutação atômica, continuando a servir os testes de
  consumer sem Redis.
- **FR-051**: O `Match.start` atual MUST ser substituído, não mantido ao lado do
  novo: o comentário que chama o dono do token de "valor de espera" deixa de ser
  verdade nesta feature.

### Key Entities

- **Setup de partida**: a operação que roda uma vez, antes da Rodada 1, e
  transforma dois decks validados em uma partida pronta para o Upkeep. Tem duas
  metades separadas pela espera: o que roda na criação (validar, materializar,
  embaralhar, comprar 4) e o que roda quando o segundo mulligan chega (sortear o
  token, compensar, posicionar para o Upkeep).
- **Deck de entrada**: a lista ordenada de 40 identificadores de carta com que
  um jogador chega. Não é ainda um deck de partida — vira um quando cada
  identificador ganha identidade própria.
- **Escolha de mulligan**: a resposta de um jogador. Quem respondeu, e quais
  cartas da própria mão ele quer trocar — de 0 a 4, identificadas pelo
  identificador de instância.
- **Espera de mulligan**: o registro, dentro do estado da partida, de quais
  jogadores ainda não responderam. Vazia significa setup pronto para o sorteio
  do token.
- **Fase de setup**: o valor de fase que diz que a partida está na espera do
  mulligan. Distinto das cinco fases da §2, e um caminho só de ida.
- **Fonte de aleatoriedade**: a interface própria do projeto por trás da qual
  vivem o embaralhamento e o sorteio do token. Chega por parâmetro,
  substituível por uma fonte de teste que dita a ordem.
- **Semente da partida**: o valor, guardado no estado, do qual a fonte é
  reconstituída a cada operação do setup. Nasce na criação, não muda, e vem
  acompanhada da contagem de quanto da sequência já foi consumido — é o par que
  torna o setup reproduzível a partir do estado gravado, em qualquer worker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dois decks válidos e uma fonte de aleatoriedade produzem uma
  partida com os dois decks embaralhados, Nexus 20 dos dois lados, energia
  máxima e atual em 0, dono do token sorteado, prioridade com ele, e a partida
  posicionada para o primeiro Upkeep.
- **SC-002**: Ao fim do setup, a mão do dono do token tem exatamente 4 cartas e
  a do oponente exatamente 5 — verificável por contagem, nos dois resultados
  possíveis do sorteio.
- **SC-003**: A mesma semente, os mesmos decks, as mesmas escolhas de mulligan
  e a mesma ordem de chegada produzem duas partidas idênticas campo a campo,
  ordem de deck e identificadores inclusive. Trocando só a semente, as duas
  partidas diferem.
- **SC-004**: Uma carta descartada no mulligan não aparece entre as cartas
  compradas na reposição do mesmo mulligan — verificável por identificador, em
  cada uma das cinco quantidades possíveis (0, 1, 2, 3 e 4).
- **SC-005**: As 80 cartas dos dois jogadores têm 80 identificadores distintos
  depois do setup completo, e o total de cartas por jogador continua sendo 40
  em todo momento do setup.
- **SC-006**: Cada um dos seis casos de recusa — deck com tamanho errado, deck
  com cópias demais, deck com carta fora do catálogo, mulligan repetido,
  mulligan de quem não joga, e carta fora da mão — produz uma recusa que nomeia
  o valor ofensor, e deixa o estado inalterado.
- **SC-007**: Uma partida parada na espera do mulligan vai ao Redis e volta com
  a fase, as mãos, as ordens de deck e a lista de quem ainda falta iguais.
- **SC-008**: Nenhum ponto do código de domínio consome aleatoriedade sem que
  ela tenha chegado por parâmetro ou sido reconstituída da semente da partida —
  verificável por inspeção dos imports do pacote de partida.
- **SC-009**: Um setup interrompido no meio da espera, gravado e recarregado
  por outro processo, termina exatamente igual a um setup que nunca saiu da
  memória — a semente e o consumo levam a sequência de onde ela parou.
- **SC-010**: Dois registros de mulligan disparados ao mesmo tempo sobre a
  mesma partida deixam as duas respostas registradas, em 100% das execuções de
  um teste que force a concorrência.
- **SC-011**: `cd server && pytest` e `cd server && mypy` passam, e
  `black --check server/` fica limpo — as três portas da constituição.

## Assumptions

- **De onde vêm os decks no matchmaking.** Guardar deck de jogador em banco é
  outra feature. Até lá o consumer de matchmaking fornece um deck de partida
  determinístico montado a partir do catálogo do MVP, igual para os dois
  jogadores. É insumo de andaime, não regra: quando a feature de deck existir,
  ela substitui essa origem sem tocar no setup.
- **Recusa de deck no pareamento.** Como o deck de andaime é sempre válido, a
  recusa no caminho do matchmaking é um caminho de erro que existe para quando a
  origem real chegar. Ele reusa o aviso de falha de pareamento que o consumer já
  tem.
- **De onde vem a semente em produção.** O ponto de composição da aplicação a
  obtém de uma fonte de entropia do sistema no momento de criar a partida e a
  passa adiante. Nada no domínio a inventa; o domínio só a recebe e a consome.
  Uma semente não é segredo de jogo: ela não revela a ordem do deck a ninguém
  que não já leia o estado inteiro, e o estado inteiro nunca sai do servidor.
- **Reproduzir um setup exige reproduzir a ordem de chegada.** Como cada
  mulligan executa na chegada, a ordem em que as duas respostas chegam faz
  parte da entrada. Um teste a controla trivialmente; a produção não precisa
  reproduzir setup nenhum.
- **A espera é um caminho só de ida.** Uma partida sai da espera do mulligan
  quando o segundo jogador responde e nunca volta para ela. Não existe
  cancelamento nem repetição de setup.
- **O mulligan não é anunciado ao oponente.** Quantas cartas o outro trocou é
  informação de partida; empacotar e transmitir isso é do websocket, e a visão
  do jogador da feature 002 já decide o que cada lado enxerga.
- **A mão inicial é sempre 4 antes do mulligan.** A compensação da §3 acontece
  depois do mulligan, nunca antes — quem vai receber a quinta carta ainda não é
  conhecido quando as mãos são formadas.
- **Nenhum identificador nasce no mulligan.** As 80 cartas da partida nascem na
  criação. O contador da feature 002 fica parado do fim da criação em diante,
  como aquela spec já assumia.
- **A energia continua em 0 ao fim do setup.** A §4 sobe para 1 no primeiro
  Upkeep. Uma partida entregue com energia 1 estaria com o Upkeep já executado.
- **Sem versionamento de estado.** Como na feature 002, o estado gravado não
  carrega número de versão. Partidas vivas do formato anterior são descartadas
  na troca; o TTL de 6 horas fecha a janela sozinho.
- **A fase nova não muda a visão do jogador.** A visão da feature 002 já
  transporta a fase atual; ela passa a poder carregar o valor novo sem mudança
  de forma.

## Out of Scope

- O Upkeep da §4 e qualquer coisa da Fase de Ação. O setup entrega a partida
  pronta e para.
- A regra geral de compra da §9 — teto de mão em 10 e reset de deck pelo
  cemitério. Nenhuma das duas condições pode ocorrer durante o setup; só o
  movimento compartilhado de tirar do topo e pôr na mão é desta feature.
- De onde vem o deck de um jogador. Ele chega por parâmetro; guardar deck de
  jogador em banco é outra feature.
- Timeout de mulligan. Um jogador que nunca responde trava a partida na espera,
  e nada nesta feature resolve isso — é o problema de relógio da §13, e mora na
  camada de transporte.
- Envelope de mensagem, broadcast e reconexão no websocket. Esta feature define
  o que a decisão de mulligan significa, não como ela viaja.
- Redesenhar o estado de partida da feature 002. Esta feature preenche esse
  estado e o cresce para caber a espera do mulligan; não o refaz.
- Mostrar ao oponente o que o outro jogador fez no mulligan.

## Dependencies

- **Catálogo e regras de deck** (feature 001, `server/apps/game/cards/`): a
  validação de 40 cartas, do limite de 3 cópias e da existência no catálogo já
  existe e é reaproveitada. O catálogo chega por parâmetro.
- **Estado de partida e serialização** (feature 002,
  `server/apps/game/match/`): o estado que esta feature preenche, o contador de
  identificadores de carta e a garantia de round-trip pelo Redis.
- **`PlayerData`** (`apps/players/services/player_queries`): os dados públicos
  do jogador que o matchmaking já injeta na criação da partida.
- **`Game/Fluxo de Partida.md`** no vault: a §3 é o contrato desta feature; a
  §9 e a §12 são referência.
