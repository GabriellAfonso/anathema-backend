# Feature Specification: Decks do jogador, e o catálogo servido ao cliente

**Feature Branch**: `011-deck-catalog-api`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Decks do jogador, e o catálogo servido ao cliente. Duas partes. A primeira é o que o cliente precisa para desenhar qualquer carta; a segunda é o jogador escolhendo com o que joga. A primeira não depende da segunda, e a segunda não existe sem a primeira."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Duas partes na mesma feature. A **Parte 1** é o catálogo servido ao cliente: as
29 cartas da feature 001, com tudo que o cliente precisa para desenhar uma
carta e para decidir se um feitiço pede alvo antes de mandar a jogada. A
**Parte 2** é o deck do jogador: montar, guardar, escolher na entrada da fila.
A Parte 1 não depende da Parte 2; a Parte 2 não existe sem a Parte 1.

Nada das regras de deck é reescrito aqui. As três regras — 40 cartas, no máximo
3 cópias do mesmo identificador, toda carta no catálogo — já existem na feature
001, com recusa estruturada que nomeia cada problema. Esta feature as **usa**;
a spec as nomeia como fronteira, nunca como desenho novo, pela convenção das
specs 005 a 010.

O andaime que esta feature remove é o deck igual para todo mundo entregue no
pareamento. Com o deck vindo do jogador, o setup da §3 passa a receber dois
decks de verdade — e o setup não muda em nada.

## Vocabulário desta feature

- **Catálogo**: as cartas que existem. Somente leitura, igual para todo mundo,
  imutável em tempo de execução.
- **Forma estruturada do efeito**: os campos pelos quais o cliente decide a
  mira de um feitiço — se exige alvo, que tipo de alvo aceita, e se há
  restrição de momento. São os mesmos campos pelos quais o motor decide. A
  descrição em português é para o jogador ler, nunca para o cliente interpretar.
- **Deck**: uma lista de identificadores de carta que pertence a um jogador,
  com identificador próprio e nome escolhido por ele. Lista, não conjunto:
  repetição é esperada.
- **Deck válido**: deck que passa pelas três regras da feature 001 contra o
  catálogo do momento.
- **Problema de deck**: uma recusa concreta e nomeada — a contagem errada, o
  identificador que passou do limite com sua contagem, o identificador que o
  catálogo não conhece. Uma recusa lista **todos** os problemas de uma vez.
- **Entrada na fila**: o ato de entrar na fila de espera. É aqui que o jogador
  diz com qual deck joga, e é aqui que o deck é conferido e validado.
- **Deck da entrada**: a cópia do deck validado que viaja junto com o jogador
  na fila e é o que a partida usa. Não é relido no pareamento.
- **Deck inicial**: o deck que todo jogador ganha quando o perfil é criado, para
  que nenhuma conta nasça sem poder jogar. Deck comum: editável e apagável.

## Clarifications

### Sessão 2026-09-12

- **P: Quantos decks um jogador pode ter?**
  R: 20. Folga larga para quem gosta de variar, e teto baixo o bastante para a
  listagem caber numa resposta só, sem paginação. A criação acima do teto é
  recusada nomeando o teto e a contagem atual.
- **P: Deck incompleto pode ser salvo?**
  R: Não. As três regras da feature 001 valem no salvamento e na entrada da
  fila. Não existe rascunho: um deck guardado sempre passou pelas três regras
  no momento em que foi guardado. É mais chato de usar do que um construtor com
  rascunho, e é a regra escolhida.
- **P: Então a validação da fila vira redundante?**
  R: Não. Ela continua sendo a que decide se o jogador joga: um deck salvo
  ontem pode citar uma carta que saiu do catálogo hoje. O salvamento valida
  contra o catálogo daquele momento; a fila valida contra o catálogo do
  momento da partida.
- **P: Nome de deck vazio ou repetido?**
  R: Vazio — ou só espaços — é recusado nomeando o campo e o valor recebido.
  Repetido é aceito: a identidade do deck é o `deck_id`, e o nome é rótulo do
  jogador.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - O cliente busca o catálogo e desenha qualquer carta (Priority: P1)

O cliente recebe `card_id` em toda mensagem de partida e não tem de onde tirar
nome, custo, ataque, vida nem imagem. Ele pede o catálogo e recebe as cartas
com esses campos: identificador, tipo, nome, custo de energia, imagem e — para
unidade — ataque e vida; para feitiço, a descrição que o jogador lê.

O catálogo é somente leitura, igual para todo mundo, e não muda durante a
partida.

**Why this priority**: sem isso o cliente não desenha nada. Toda mensagem de
partida fala em `card_id` e nenhuma delas carrega o molde da carta.

**Independent Test**: buscar o catálogo e conferir que as 29 cartas vêm com
todos os campos de desenho, que unidade traz ataque e vida, que feitiço traz
descrição, e que dois requisitantes diferentes recebem exatamente a mesma
resposta.

**Acceptance Scenarios**:

1. **Given** o catálogo do MVP carregado, **When** o cliente busca o catálogo,
   **Then** recebe as 29 cartas, cada uma com identificador, tipo, nome, custo
   de energia e imagem.
2. **Given** a resposta do catálogo, **When** o cliente lê uma unidade, **Then**
   encontra ataque e vida daquela unidade.
3. **Given** a resposta do catálogo, **When** o cliente lê um feitiço, **Then**
   encontra a descrição em português para mostrar ao jogador.
4. **Given** dois jogadores diferentes, **When** cada um busca o catálogo,
   **Then** recebem a mesma resposta, campo a campo.
5. **Given** uma partida em curso, **When** o catálogo é buscado, **Then** a
   resposta é a mesma de fora de partida — nada nela depende de partida.
6. **Given** a resposta do catálogo, **When** o cliente procura um campo
   chamado `id`, **Then** não existe nenhum: o espaço de identidade é nomeado
   (`card_id`).

---

### User Story 2 - O cliente sabe, antes de jogar, se o feitiço pede alvo e de qual lado (Priority: P1)

Para cada feitiço, o catálogo entrega a forma estruturada do efeito: se exige
alvo, que tipo de alvo aceita (nenhum, unidade aliada, unidade inimiga) e se há
restrição de momento — o feitiço que só vale na declaração de ataque.

Sem isso o cliente não sabe se deve pedir um alvo antes de mandar a jogada, nem
de qual lado do tabuleiro, e acaba mandando jogada que o servidor vai recusar.

**Why this priority**: é o que separa um cliente que erra a mira de um cliente
que não deixa o jogador errá-la. O motor já decide por esses campos; o cliente
passa a decidir pelos mesmos.

**Independent Test**: para cada um dos 5 feitiços, ler a forma do efeito e
comparar com o que o motor aceita: mandar a jogada que a forma indica e conferir
que é aceita, mandar a que a forma proíbe e conferir a recusa.

**Acceptance Scenarios**:

1. **Given** a resposta do catálogo, **When** o cliente lê um feitiço que causa
   dano a unidade inimiga, **Then** vê que exige alvo e que o alvo aceito é
   unidade inimiga.
2. **Given** a resposta do catálogo, **When** o cliente lê um feitiço que dá
   vida a unidade aliada, **Then** vê que exige alvo e que o alvo aceito é
   unidade aliada.
3. **Given** a resposta do catálogo, **When** o cliente lê um feitiço sem alvo,
   **Then** vê que não exige alvo, e não desenha mira nenhuma.
4. **Given** a resposta do catálogo, **When** o cliente lê o feitiço que só vale
   na declaração de ataque, **Then** vê a restrição de momento e mantém a carta
   indisponível fora da declaração.
5. **Given** a forma do efeito de um feitiço, **When** o cliente monta a jogada
   exatamente como a forma indica, **Then** o servidor aceita — a forma servida
   e a regra do motor não divergem.
6. **Given** um feitiço sem alvo, **When** o cliente manda a jogada com alvo,
   **Then** recebe a recusa de sempre — a forma servida existe para evitar esse
   caso, não para criar uma segunda regra.

---

### User Story 3 - O jogador monta e guarda os próprios decks (Priority: P1)

O jogador lista os decks dele, cria um novo, renomeia, troca as cartas e apaga.
Cada deck tem identificador próprio, um nome que ele escolhe, e a lista de
cartas — lista mesmo, com repetição esperada, até 3 entradas do mesmo
identificador.

Salvar exige deck válido: as três regras valem no salvamento, não só na fila.
Não existe rascunho de 12 cartas, e a recusa nomeia cada problema.

**Why this priority**: é a razão da feature. Sem deck guardado, escolher com o
que jogar não existe.

**Independent Test**: criar dois decks, listar e conferir os dois, renomear um,
trocar as cartas do outro, tentar salvar uma lista de 12 cartas e conferir a
recusa, apagar o primeiro e conferir que a lista ficou com um só.

**Acceptance Scenarios**:

1. **Given** um jogador autenticado, **When** ele cria um deck com nome e uma
   lista de cartas válida, **Then** o deck passa a existir com identificador
   próprio e aparece na lista dele.
2. **Given** um deck do jogador, **When** ele o renomeia, **Then** o novo nome
   é o que a listagem mostra, e a lista de cartas não muda.
3. **Given** um deck do jogador, **When** ele troca a lista de cartas, **Then**
   a nova lista é a que fica guardada, com a repetição como foi enviada.
4. **Given** um deck do jogador, **When** ele o apaga, **Then** o deck some da
   listagem dele e uma consulta seguinte a ele responde como inexistente.
5. **Given** um jogador sem nenhum deck, **When** ele lista, **Then** recebe uma
   lista vazia — e não um erro.
6. **Given** um deck salvo, **When** ele é lido de volta, **Then** nenhum campo
   se chama `id`: o deck é identificado por `deck_id` e pertence a um
   `user_id`.
7. **Given** um jogador autenticado, **When** ele tenta salvar um deck com 12
   cartas, **Then** é recusado dizendo 12 encontradas contra as 40 exigidas, e
   nada é salvo.
8. **Given** um deck válido guardado, **When** o jogador tenta trocar a lista
   por uma inválida, **Then** é recusado com todos os problemas, e o deck
   continua com a lista antiga.
9. **Given** um jogador com 20 decks, **When** ele tenta criar o vigésimo
   primeiro, **Then** é recusado com o teto 20 e a contagem 20 na mensagem, e
   nada é salvo.
10. **Given** um jogador autenticado, **When** ele tenta salvar um deck com
    nome vazio ou só espaços, **Then** é recusado nomeando o campo e o valor
    recebido.
11. **Given** um jogador com um deck chamado "Agro", **When** ele cria outro
    deck com o mesmo nome, **Then** os dois existem, com `deck_id` diferentes.

---

### User Story 4 - O deck de outro jogador não existe para mim (Priority: P1)

Um deck de outro jogador não é legível, nem renomeável, nem editável, nem
apagável. O pedido é recusado **como se o deck não existisse** — confirmar que
o deck 5 existe já entrega informação a quem não deveria tê-la.

**Why this priority**: é a fronteira de privacidade da feature, e ela vale para
toda operação, não só para as de escrita. Uma recusa que distingue "não é seu"
de "não existe" transforma a listagem alheia em algo enumerável.

**Independent Test**: com dois jogadores, pedir com o jogador B cada operação
sobre um deck do jogador A e conferir que a resposta é idêntica — texto e
código — à do mesmo pedido sobre um identificador que não existe para ninguém.

**Acceptance Scenarios**:

1. **Given** um deck do jogador A, **When** o jogador B tenta lê-lo, **Then**
   recebe a mesma resposta que receberia por um deck inexistente.
2. **Given** um deck do jogador A, **When** o jogador B tenta renomeá-lo ou
   trocar as cartas, **Then** recebe a mesma resposta de inexistente, e o deck
   de A não muda.
3. **Given** um deck do jogador A, **When** o jogador B tenta apagá-lo, **Then**
   recebe a mesma resposta de inexistente, e o deck de A continua existindo.
4. **Given** decks de A e de B, **When** B lista os decks dele, **Then** a
   listagem traz só os de B.
5. **Given** um pedido sem autenticação, **When** ele chega a qualquer operação
   de deck, **Then** é recusado antes de qualquer leitura.

---

### User Story 5 - Entrar na fila exige dizer o deck, e ele é validado na hora (Priority: P1)

O cliente entra na fila dizendo com qual deck joga. O servidor confere que o
deck é daquele jogador e o valida contra o catálogo do momento. Deck não
informado, deck de outro jogador, deck inexistente e deck inválido recusam a
**entrada na fila** — não o pareamento. A recusa por deck inválido nomeia cada
problema, todos de uma vez.

Recusar no pareamento faria o oponente perder o tempo de fila dele por um
problema que não é dele, e o par já teria sido consumido.

**Why this priority**: é a validação que decide se o jogador joga. A validação
do salvamento não a substitui: um deck salvo ontem pode citar uma carta que
saiu do catálogo hoje.

**Independent Test**: entrar na fila sem deck, com deck de outro, com deck
inexistente e com deck que deixou de ser válido, conferindo em cada caso a
recusa, a mensagem e que o jogador **não** ficou na fila; depois entrar com deck
válido e conferir que ficou.

**Acceptance Scenarios**:

1. **Given** um jogador com deck válido, **When** ele entra na fila informando
   esse deck, **Then** é aceito na fila e espera o pareamento como hoje.
2. **Given** um jogador autenticado, **When** ele entra na fila sem informar
   deck, **Then** é recusado, e não ocupa lugar na fila.
3. **Given** um deck do jogador A, **When** o jogador B entra na fila
   informando esse deck, **Then** é recusado com a mesma resposta de deck
   inexistente, e não ocupa lugar na fila.
4. **Given** um deck do jogador que tinha 40 cartas e passou a citar uma carta
   fora do catálogo, **When** ele entra na fila com esse deck, **Then** é
   recusado com o identificador da carta desconhecida nomeado.
5. **Given** um deck com 40 entradas em que uma carta aparece 4 vezes, **When**
   o jogador entra na fila com ele, **Then** a recusa nomeia aquela carta e a
   contagem 4 contra o limite 3 — não um "deck inválido" genérico.
6. **Given** um deck com mais de um problema, **When** o jogador entra na fila
   com ele, **Then** a recusa traz todos os problemas de uma vez.
7. **Given** um jogador recusado na entrada da fila, **When** outro jogador
   entra na fila em seguida, **Then** ele não é pareado com o recusado e não
   perde tempo de fila por causa dele.
8. **Given** dois jogadores com decks válidos, **When** o segundo entra,
   **Then** o par se fecha, a partida é criada e os dois recebem o aviso de
   pareamento, como hoje.

---

### User Story 6 - A partida usa o deck que foi validado, não o deck de agora (Priority: P1)

O deck validado viaja com a entrada na fila. Editar ou apagar o deck depois de
entrar na fila não muda a fila nem a partida que sair dela: o que foi validado
na entrada é o que a partida usa.

Apagar o deck com que se está numa partida em andamento não muda a partida em
nada — ela já tem as cartas dela desde o setup.

**Why this priority**: a fila fecha o par depois, possivelmente em outro
worker. Reler o deck no pareamento deixaria uma janela em que uma edição produz
uma partida diferente da que foi validada, ou nenhuma partida.

**Independent Test**: entrar na fila com um deck válido, trocar todas as cartas
dele (ou apagá-lo) antes de o par fechar, e conferir que a partida criada usa a
lista validada no momento da entrada.

**Acceptance Scenarios**:

1. **Given** um jogador na fila com um deck validado, **When** ele troca todas
   as cartas desse deck antes do pareamento, **Then** a partida criada usa a
   lista que foi validada na entrada.
2. **Given** um jogador na fila com um deck validado, **When** ele apaga esse
   deck antes do pareamento, **Then** o par ainda se fecha e a partida é criada
   com a lista validada na entrada.
3. **Given** uma partida em andamento, **When** um dos jogadores apaga o deck
   com que entrou, **Then** a partida não muda em nada e segue até o fim.
4. **Given** dois jogadores pareados, **When** a partida é criada, **Then** o
   setup recebe os dois decks de verdade, e o resultado do setup é o mesmo que
   o de hoje para as mesmas listas e a mesma semente.
5. **Given** um jogador que sai da fila antes do par, **When** ele sai,
   **Then** o deck da entrada sai junto e não fica sobrando na fila.

---

### User Story 7 - Uma conta nova já nasce com um deck jogável (Priority: P2)

Uma conta nova sem deck nenhum não conseguiria entrar na fila, e não existiria
partida para ela. Ao ter o perfil criado, o jogador ganha um deck inicial
válido — editável, renomeável e apagável como qualquer outro.

**Why this priority**: sem ele o caminho do registro até a primeira partida
passa obrigatoriamente por montar 40 cartas à mão. Depende de a Parte 2
existir, então vem depois dela.

**Independent Test**: registrar uma conta, listar os decks e conferir que existe
um, entrar na fila com ele sem editar nada, e conferir que a partida nasce.

**Acceptance Scenarios**:

1. **Given** um registro de conta que cria o perfil, **When** o perfil é
   criado, **Then** o jogador tem um deck válido na listagem dele.
2. **Given** uma conta recém-criada, **When** o jogador entra na fila com o
   deck inicial sem editar nada, **Then** é aceito e a partida nasce.
3. **Given** o deck inicial, **When** o jogador o renomeia, edita ou apaga,
   **Then** ele se comporta como qualquer outro deck — não é protegido.
4. **Given** uma falha na criação do deck inicial, **When** o registro é
   processado, **Then** nenhum perfil pela metade sobrevive: ou o jogador nasce
   com perfil e deck, ou não nasce.
5. **Given** uma conta criada fora do registro (por exemplo `createsuperuser`),
   **When** ela não tem perfil, **Then** não ganha deck nenhum — deck é do
   jogador, e ela não é jogador.

---

### Edge Cases

- **Entrar na fila sem informar deck.** Recusa. O jogador não ocupa lugar na
  fila.
- **Entrar na fila com deck de outro jogador.** Recusa idêntica à de deck
  inexistente, sem confirmar que aquele deck existe.
- **Entrar na fila com deck que era válido e deixou de ser.** Recusa nomeando
  cada problema concreto.
- **Entrar na fila duas vezes, com decks diferentes.** A segunda entrada
  substitui a primeira, e é o deck da segunda que vale — a fila já trata
  reentrada removendo a entrada anterior.
- **Apagar o deck com que se está na fila.** A entrada na fila não muda: ela já
  carrega a lista validada.
- **Apagar o deck com que se está numa partida em andamento.** A partida não
  muda em nada.
- **Deck com 40 entradas e uma carta aparecendo 4 vezes.** Recusa nomeando a
  carta e a contagem, não um "deck inválido" genérico.
- **Deck com vários problemas ao mesmo tempo** (39 cartas, uma carta 4 vezes e
  uma carta fora do catálogo). Recusa com os três problemas de uma vez.
- **Salvar deck com nome vazio ou só espaços.** Recusa nomeando o campo e o
  valor recebido.
- **Salvar deck com nome igual ao de outro deck do mesmo jogador.** Aceito: o
  deck é identificado por `deck_id`, e o nome é rótulo do jogador. Dois
  jogadores diferentes com decks de mesmo nome nunca se cruzam.
- **Salvar deck com lista contendo um identificador que não existe no
  catálogo.** Recusa nomeando o identificador; nada é salvo.
- **Salvar deck com 12 cartas.** Recusa: não existe rascunho. A mensagem diz 12
  encontradas contra as 40 exigidas.
- **Salvar deck com lista vazia.** Mesmo caso: recusa dizendo 0 contra 40.
- **Editar um deck válido para uma lista inválida.** Recusa, e o deck guardado
  continua como estava — a edição não deixa um deck meio-salvo.
- **Teto de 20 decks atingido.** A criação é recusada dizendo o teto e a
  contagem atual; nada é salvo. Editar e apagar continuam funcionando.
- **Deck que era válido e o catálogo mudou.** Continua guardado como está;
  quem recusa é a entrada na fila, nomeando o problema. A feature não apaga nem
  conserta deck por mudança de catálogo.
- **Apagar o último deck.** Permitido. O jogador fica sem deck e não consegue
  entrar na fila até criar um — a recusa da fila explica isso.
- **Catálogo consultado por quem não está autenticado.** Recusado pelo mesmo
  gate de autenticação do resto da API; o conteúdo do catálogo não depende de
  quem pergunta, mas o acesso segue a regra da API.
- **Dois pedidos simultâneos editando o mesmo deck.** O último a gravar vence;
  não há resolução de conflito nesta feature.

## Requirements *(mandatory)*

### Functional Requirements

#### Parte 1 — O catálogo servido ao cliente

- **FR-001**: O sistema MUST servir o catálogo completo de cartas por HTTP,
  somente leitura.
- **FR-002**: Cada carta servida MUST trazer o identificador, o tipo (unidade
  ou feitiço), o nome, o custo de energia e a imagem.
- **FR-003**: Toda unidade servida MUST trazer ataque e vida.
- **FR-004**: Todo feitiço servido MUST trazer a descrição em português
  destinada ao jogador.
- **FR-005**: Todo feitiço servido MUST trazer a forma estruturada do efeito:
  se exige alvo, que tipo de alvo aceita, e se tem restrição de momento.
- **FR-006**: Os valores possíveis de tipo de alvo e de restrição de momento
  MUST ser um conjunto fechado e estável, com o mesmo texto que o motor usa,
  para que o cliente possa compará-los.
- **FR-007**: O cliente MUST conseguir decidir a mira de qualquer feitiço lendo
  só os campos estruturados, sem interpretar a descrição em português.
- **FR-008**: A resposta do catálogo MUST ser idêntica para todo requisitante e
  MUST NOT depender de partida em curso, de quem pergunta ou de qualquer estado
  de jogador.
- **FR-009**: O catálogo servido MUST ser exatamente o catálogo que o motor já
  usa. O sistema MUST NOT manter uma segunda lista de cartas para servir.
- **FR-010**: Nenhum campo servido MUST se chamar `id`: o identificador de
  carta é `card_id` (Constituição, princípio II).
- **FR-011**: O acesso ao catálogo MUST exigir autenticação, como o resto da
  API HTTP do projeto.

#### Parte 2 — O deck do jogador

- **FR-012**: Um deck MUST pertencer a exatamente um jogador, identificado por
  `user_id`, e MUST ter identificador próprio (`deck_id`).
- **FR-013**: Um deck MUST ter um nome escolhido pelo jogador e uma lista de
  identificadores de carta.
- **FR-014**: A lista de cartas MUST ser uma lista e não um conjunto:
  repetição é esperada, e a lista MUST ser guardada como foi enviada.
- **FR-015**: Um jogador MUST poder listar os decks dele, criar um deck,
  renomear, substituir a lista de cartas e apagar.
- **FR-016**: Listar MUST devolver só os decks do jogador autenticado, e lista
  vazia MUST ser resposta válida.
- **FR-017**: Ler, renomear, editar ou apagar um deck que não é do jogador
  autenticado MUST ser recusado com a **mesma** resposta de um deck
  inexistente — mesmo código e mesma mensagem, sem confirmar a existência.
- **FR-018**: O nome do deck MUST ser não vazio depois de remover espaços nas
  pontas; a recusa MUST nomear o campo e o valor recebido.
- **FR-019**: Nomes repetidos entre decks do mesmo jogador MUST ser aceitos: o
  deck é identificado por `deck_id`, e o nome é rótulo.
- **FR-020**: Um jogador MUST poder ter no máximo **20** decks. A criação acima
  do teto MUST ser recusada com uma mensagem que traz o teto e a contagem
  atual, e nada MUST ser salvo.
- **FR-021**: Ao salvar um deck — criação ou edição da lista — o sistema MUST
  aplicar as três regras e MUST recusar o salvamento de qualquer deck que não
  passe nelas. Não existe rascunho: todo deck guardado passou pelas três regras
  contra o catálogo do momento em que foi guardado.
- **FR-022**: A validação de deck MUST usar as regras da feature 001 como
  estão — exatamente 40 cartas, no máximo 3 cópias do mesmo identificador,
  toda carta no catálogo. O sistema MUST NOT reimplementar nenhuma delas. A
  validação do salvamento MUST NOT substituir a da entrada na fila: um deck
  válido quando salvo pode deixar de ser válido se o catálogo mudar, e é a
  validação da fila que decide se o jogador joga.
- **FR-023**: Toda recusa por deck inválido MUST listar **todos** os problemas
  de uma vez, cada um nomeando o valor ofensor: a contagem encontrada e a
  exigida, o identificador excedente com sua contagem e o limite, o
  identificador desconhecido.

#### Parte 2 — A entrada na fila

- **FR-024**: Entrar na fila MUST exigir que o cliente informe qual deck usa.
- **FR-025**: Entrada na fila sem deck informado MUST ser recusada, e o jogador
  MUST NOT ocupar lugar na fila.
- **FR-026**: Na entrada na fila, o sistema MUST conferir que o deck pertence
  ao jogador e MUST validá-lo contra o catálogo do momento.
- **FR-027**: Deck inexistente e deck de outro jogador MUST receber a mesma
  recusa na entrada na fila, sem confirmar a existência do deck.
- **FR-028**: Deck inválido MUST recusar a entrada na fila nomeando cada
  problema (FR-023).
- **FR-029**: Toda recusa de deck MUST acontecer **antes** de o jogador ocupar
  lugar na fila, para que nenhum par seja consumido e nenhum oponente perca
  tempo de fila por um problema que não é dele.
- **FR-030**: A recusa MUST NOT fechar o socket de matchmaking: o cliente
  recebe a recusa e pode tentar de novo com outro deck.
- **FR-031**: O deck validado MUST viajar junto com a entrada na fila, de modo
  que o pareamento não precise relê-lo.
- **FR-032**: A partida criada MUST usar exatamente o deck validado na entrada
  na fila, mesmo que o deck tenha sido editado ou apagado entre a entrada e o
  pareamento.
- **FR-033**: Editar ou apagar um deck MUST NOT alterar nenhuma partida em
  andamento.
- **FR-034**: Sair da fila MUST remover a entrada inteira, deck junto.
- **FR-035**: Reentrar na fila MUST substituir a entrada anterior do mesmo
  jogador, valendo o deck da entrada mais recente.
- **FR-036**: O andaime que hoje entrega o mesmo deck derivado do catálogo a
  todo jogador no matchmaking MUST ser removido.
- **FR-037**: O setup da §3 MUST continuar como está: para as mesmas duas
  listas e a mesma semente, o resultado MUST ser o mesmo de hoje.
- **FR-038**: O fluxo de matchmaking MUST continuar funcionando ponta a ponta:
  entrar na fila, parear, criar a partida, avisar os dois jogadores, e o
  cliente abrir o socket de partida em seguida.
- **FR-039**: O protocolo de partida e o relógio das features 009 e 010 MUST
  NOT mudar.

#### Parte 2 — O deck inicial

- **FR-040**: Ao criar o perfil de um jogador, o sistema MUST criar para ele um
  deck inicial válido.
- **FR-041**: O deck inicial MUST ser um deck comum: renomeável, editável e
  apagável como qualquer outro, sem proteção especial.
- **FR-042**: A criação do perfil e a do deck inicial MUST ser tudo ou nada:
  nenhum jogador MUST existir com perfil e sem deck por falha parcial.
- **FR-043**: Uma conta sem perfil MUST NOT receber deck: deck pertence a
  jogador, e conta sem perfil não é jogador.

### Key Entities

- **Carta de catálogo**: o molde imutável de uma carta — identificador, tipo,
  nome, custo de energia, imagem; ataque e vida para unidade; descrição e forma
  estruturada do efeito para feitiço. Somente leitura, comum a todos.
- **Forma estruturada do efeito**: o que o cliente lê para decidir a mira —
  exige alvo, tipo de alvo aceito, restrição de momento. Espelha o que o motor
  já usa para decidir.
- **Deck do jogador**: identificador próprio, o jogador dono, o nome e a lista
  de identificadores de carta com repetição. Pertence a um jogador e só a ele.
- **Entrada na fila**: o jogador esperando pareamento **e** a lista de cartas
  validada no momento em que ele entrou. É o que o pareamento consome.
- **Problema de deck**: a recusa concreta de uma das três regras, com o valor
  ofensor. Vem da feature 001 e não é redefinido aqui.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O cliente desenha qualquer uma das 29 cartas usando só a resposta
  do catálogo, sem nenhum valor de carta embutido nele.
- **SC-002**: Para cada um dos 5 feitiços, o cliente decide corretamente, só
  pelos campos estruturados, se pede alvo e de qual lado do tabuleiro — 5 de 5,
  sem ler a descrição em português.
- **SC-003**: Jogadas recusadas por mira que o cliente poderia ter evitado com
  a forma servida caem a zero.
- **SC-004**: 100% das tentativas de ler, renomear, editar ou apagar um deck de
  outro jogador recebem resposta indistinguível da de um deck inexistente.
- **SC-005**: Uma conta recém-registrada entra na fila e chega a uma partida
  sem criar nem editar deck nenhum.
- **SC-006**: Um deck de 40 entradas em que uma carta aparece 4 vezes recebe
  recusa que nomeia aquela carta e a contagem 4 contra o limite 3.
- **SC-007**: Um deck com três problemas ao mesmo tempo recebe uma única recusa
  com os três, não três recusas nem só o primeiro.
- **SC-008**: 100% das entradas na fila com deck ausente, alheio, inexistente
  ou inválido são recusadas sem que o jogador ocupe lugar na fila e sem que
  nenhum outro jogador seja pareado com ele.
- **SC-009**: Um deck editado ou apagado entre a entrada na fila e o pareamento
  produz, em 100% dos casos, a mesma partida que a lista validada na entrada
  produziria.
- **SC-010**: Apagar um deck no meio de uma partida deixa a partida idêntica —
  nenhuma carta, mão, banco ou cemitério muda.
- **SC-011**: O fluxo de matchmaking ponta a ponta (fila, par, partida, aviso,
  socket de partida) continua passando, com decks de verdade no lugar do
  andaime.
- **SC-012**: 100% dos decks guardados passaram pelas três regras no momento em
  que foram guardados — nenhum deck de 12 cartas existe no armazenamento.
- **SC-013**: Nenhum jogador chega a 21 decks; a vigésima primeira criação é
  recusada com o teto e a contagem na mensagem.

## Out of Scope

- **Coleção**: quais cartas um jogador possui. Todo jogador tem acesso a todas
  as 29 cartas.
- **Pacotes, recompensa e economia** de qualquer forma.
- **Compartilhar deck por código, importar e exportar.**
- **Estatística de deck**, taxa de vitória, sugestão de carta.
- **Cliente.** A spec diz o que o servidor entrega e por quê; desenhar a tela
  não é desta feature.
- **Edição concorrente do mesmo deck** com resolução de conflito.
- **Mudar as regras de deck** da feature 001, o setup da §3, o protocolo da 009
  ou o relógio da 010.
- **Deck favorito ou deck padrão** implícito: a entrada na fila sempre diz qual
  deck usa.

## Assumptions

- O catálogo continua sendo o do MVP, com 29 cartas, e continua imutável em
  tempo de execução. Servi-lo não muda nada nele.
- O acesso ao catálogo exige autenticação como o resto da API HTTP. O conteúdo
  não depende de quem pergunta; só o acesso segue a regra da API.
- Um jogador é um `PlayerProfile`, um por usuário e permanente, com
  `profile.pk == user.id` (decisão 0001 do vault). O dono de um deck é nomeado
  por `user_id`.
- O deck inicial é derivado do catálogo, como o andaime de hoje: até 3 cópias
  de cada carta em ordem de identificador, até fechar 40. Não é escolha de
  balanceamento e pode mudar sem aviso.
- A ordem da lista de cartas de um deck é preservada como enviada, mas não tem
  significado de jogo: o setup embaralha.
- Dois decks do mesmo jogador podem ter o mesmo nome; o `deck_id` é a
  identidade.
- O deck inicial conta para o teto de 20: um jogador novo já tem 1 de 20.
- Um deck guardado que deixou de ser válido por mudança de catálogo continua
  guardado. A feature não varre o armazenamento atrás desses decks nem os
  conserta; quem os recusa é a entrada na fila.
- O socket de matchmaking recusa sem fechar, como o protocolo da feature 009 já
  faz para mensagem malformada.
- A fila continua FIFO e continua tratando reentrada removendo a entrada
  anterior do mesmo jogador.
- Não há migração de dados a fazer: nenhum deck de jogador existe hoje.

## Dependencies

- **Feature 001 — Catálogo de cartas.** As 29 cartas, a forma estruturada do
  efeito e as três regras de deck com recusa estruturada. Usadas como estão.
- **Feature 003 — Setup da partida.** Recebe os dois decks. Não muda.
- **Feature 009 — Protocolo de partida** e **feature 010 — Relógio.** Não
  mudam; a recusa da entrada na fila segue a forma de recusa já estabelecida.
- **`PlayerProfile`** e a criação de jogador, que passa a criar também o deck
  inicial na mesma transação.
- **A fila de matchmaking**, que hoje guarda só `user_id` e passa a guardar a
  entrada com o deck validado.
