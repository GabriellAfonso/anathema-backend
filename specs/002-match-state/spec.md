# Feature Specification: Estado de Partida

**Feature Branch**: `002-match-state`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Estado de partida: as estruturas que guardam uma partida viva e a serialização que as leva ao Redis e de volta. Sem regra de jogo — nada aqui decide se uma jogada é legal, aplica dano ou troca turno."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. A §2 é o contrato
desta feature; as §3 a §10 descrevem quem vai consumir este estado nas features
seguintes e existem aqui só como justificativa de campo.

## Clarifications

### Sessão 2026-09-09

- **P: Que forma tem o identificador de instância de carta?**
  R: Um inteiro sequencial, atribuído por um contador que vive no estado da
  partida. Opaco de propósito: não codifica `card_id`, não codifica dono, não
  codifica ordinal de cópia. Descartado o formato `15-A` / `15-B` usado em um
  jogo anterior — embutir o `card_id` dentro do identificador convida a lê-lo
  por parsing em vez de ler o campo, que é a mesma classe de erro que
  `card.py` já proibiu para as faixas de `card_id`.

- **P: O espaço de identificadores é único na partida ou um por jogador?**
  R: Único na partida. A pilha guarda o alvo como um número solto (§6); com
  numeração por jogador esse número seria ambíguo e obrigaria uma chave
  composta `(user_id, card_instance_id)` a viajar inteira por todo lugar,
  inclusive no pareamento de bloqueadores da §7.2, que atravessa os dois
  lados. As cartas continuam **armazenadas** separadas por jogador; só a
  numeração é compartilhada.

- **P: Vida da unidade é guardada como vida atual ou como dano acumulado?**
  R: Dano acumulado. Ataque e vida efetivos são derivados do molde mais os
  modificadores; o dano é a única alteração que não é modificador, porque não
  tem duração e não expira. Guardar vida atual absoluta obrigaria a desfazer
  na mão a expiração de um buff de vida temporário, e o resultado passaria a
  depender da ordem dos eventos. Com dano acumulado, expirar um modificador é
  removê-lo da lista.

- **P: O que um modificador guarda?**
  R: Uma união fechada de tipos, espelhando a disciplina de `effects.py`, não
  um registro genérico com `attribute` em string. `DamageImmunity` não tem
  quantidade, e um campo `amount` anulável deixaria existir combinação sem
  significado — o mesmo motivo pelo qual `requires_target` é derivado em
  `effects.py`. Um `match` que esqueça um braço vira erro de mypy.

- **P: Como os dois jogadores ficam dentro do estado?**
  R: Numa lista de dois, cada um carregando o próprio `user_id`. Nenhuma
  estrutura do estado é indexada por `user_id`, então o problema de chave de
  objeto JSON — que é sempre string, e que o modelo atual conserta na mão com
  `int(k)` — deixa de existir em vez de precisar ser tratado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Representar uma partida viva completa (Priority: P1)

O motor de regras — que ainda não existe — precisa de um lugar onde a partida
inteira caiba: quem joga, em que rodada está, quem tem o token de ataque e se
já o gastou, de quem é a prioridade, em que fase o jogo está, o que está
pendente na pilha e quantos passes consecutivos aconteceram. Do lado de cada
jogador: Nexus, deck, mão, banco, cemitério e as duas energias.

Hoje isso não existe: `Match` guarda `turn`, um `board_state` e `hands` de
`card_id` solto. Nenhum dos campos da §2 tem onde morar.

**Why this priority**: é o continente. Identidade de carta, pilha, visão e
serialização são todas propriedades de um estado que precisa existir primeiro.

**Independent Test**: montar um estado de partida com os dois jogadores e
conferir, campo a campo, que todos os campos da §2 estão presentes e com os
valores iniciais corretos.

**Acceptance Scenarios**:

1. **Given** dois jogadores, **When** monto uma partida, **Then** o estado
   expõe rodada atual, dono do token, token consumido, prioridade, fase atual,
   pilha e passes consecutivos.
2. **Given** uma partida montada, **When** leio o estado de um jogador,
   **Then** encontro Nexus, deck, mão, banco, cemitério, energia máxima e
   energia atual.
3. **Given** uma partida montada, **When** leio a fase atual, **Then** o valor
   pertence ao conjunto fechado de cinco fases da §2 e nenhum outro valor é
   representável.
4. **Given** uma partida montada, **When** procuro um jogador pelo `user_id`,
   **Then** encontro o estado dele; **And** procurando por um `user_id` de
   fora, a busca falha citando o `user_id` pedido.

---

### User Story 2 - Dar identidade própria a cada carta em partida (Priority: P1)

Duas cópias de KRONOS no banco são coisas diferentes. Um feitiço mirado numa
delas não pode acertar a outra. O catálogo entrega um molde compartilhado e
imutável; a partida precisa de cópias concretas, cada uma endereçável sozinha.

O identificador é um inteiro sequencial vindo de um contador no estado da
partida, e o espaço é único na partida inteira — não um por jogador.

**Why this priority**: é o ponto central da feature. Sem identidade individual
não existe alvo, não existe revalidação, não existe fizzle — e a §6 do Fluxo de
Partida deixa de ser implementável.

**Independent Test**: colocar duas cartas do mesmo `card_id` na mesma zona e
conferir que os identificadores diferem; mover uma delas de zona e conferir que
o identificador não mudou.

**Acceptance Scenarios**:

1. **Given** duas cópias do mesmo `card_id` no banco, **When** comparo os
   identificadores de instância, **Then** eles são diferentes entre si e ambos
   diferentes do `card_id`.
2. **Given** uma carta com identificador conhecido no deck, **When** ela passa
   para a mão, para o banco, para a pilha e para o cemitério, **Then** o
   identificador é o mesmo nas cinco zonas.
3. **Given** uma partida com as cartas dos dois jogadores criadas, **When**
   junto todos os identificadores dos dois lados, **Then** não há repetição.
4. **Given** o cemitério de um jogador com cartas identificadas, **When** essas
   cartas voltam ao deck (o reset da §9, executado por outra feature),
   **Then** a estrutura permite devolvê-las com os mesmos identificadores.
5. **Given** uma carta nova entrando na partida depois do setup, **When** ela
   recebe um identificador, **Then** o contador avança e o número não colide
   com nenhum já existente na partida.

---

### User Story 3 - Sobreviver à ida e volta pelo Redis (Priority: P1)

A partida mora no Redis para que qualquer worker do uvicorn enxergue a mesma
partida. O estado sai como JSON e volta como JSON. Nada pode se perder no
caminho — nem identificador, nem ordem de deck, nem ordem da pilha, nem dano
acumulado, nem modificador, nem o tipo de um `user_id`.

**Why this priority**: sem isto o estado novo simplesmente não persiste, e
`store.py` — que é o único caminho de gravação — para de funcionar.

**Independent Test**: serializar um estado de partida arbitrário mas válido,
passar por `json.dumps` / `json.loads`, desserializar e comparar com o
original.

**Acceptance Scenarios**:

1. **Given** um estado de partida válido qualquer, **When** faço a ida e a
   volta pelo JSON, **Then** o estado reconstruído é igual ao original.
2. **Given** um deck com ordem conhecida e uma pilha com dois feitiços,
   **When** faço a ida e a volta, **Then** as duas ordens são preservadas.
3. **Given** o estado serializado, **When** inspeciono a estrutura, **Then**
   nenhum objeto JSON tem `user_id` como chave — em nenhum nível.
4. **Given** uma unidade com dano acumulado e modificadores das duas durações,
   **When** faço a ida e a volta, **Then** o dano e cada modificador voltam com
   o mesmo tipo e os mesmos valores.

---

### User Story 4 - Guardar dano e modificadores da unidade no banco (Priority: P2)

Buff, dano e cura recaem sobre a instância, nunca sobre o molde. Uma unidade no
banco carrega o dano acumulado e os modificadores ativos sobre ela. Uma carta
na mão, no deck ou no cemitério não carrega dano nem buff — ela não está em
jogo.

Ataque e vida do molde não são copiados para dentro da instância: o catálogo
continua sendo a única fonte deles. A instância guarda só o que diverge.

Cada modificador registra se vale para sempre ou até o fim da rodada, porque o
Fim de Rodada (§8) varre os temporários. Varrer não é desta feature;
representar é.

**Why this priority**: é a diferença entre uma lista de `card_id` e um tabuleiro
de verdade. Depende de US2 (a unidade precisa ter identidade antes de ter
dano).

**Independent Test**: criar uma unidade no banco, acumular dano e adicionar
modificadores das duas durações, e conferir que o molde do catálogo
correspondente permanece intacto.

**Acceptance Scenarios**:

1. **Given** uma unidade no banco, **When** leio o estado dela, **Then**
   encontro identificador de instância, `card_id` de origem, dano acumulado e a
   lista de modificadores ativos — e nenhum valor de ataque ou vida copiado do
   molde.
2. **Given** duas instâncias do mesmo `card_id` no banco, **When** acumulo dano
   em uma, **Then** a outra e o molde do catálogo não mudam.
3. **Given** uma unidade com um modificador permanente e um até o fim da
   rodada, **When** leio os modificadores, **Then** cada um declara sua duração
   e é possível separar os dois grupos sem interpretar texto.
4. **Given** uma unidade com modificadores de ataque de sinais opostos,
   **When** leio a lista, **Then** os dois estão lá como itens independentes,
   sem que nenhum valor efetivo tenha sido pré-calculado e gravado.
5. **Given** uma carta na mão, no deck ou no cemitério, **When** leio o estado
   dela, **Then** não existe dano nem modificador a ler.

---

### User Story 5 - Guardar a pilha e responder pela validade do alvo (Priority: P2)

A pilha guarda feitiços pendentes e resolve em LIFO. Cada entrada diz qual
feitiço é, quem lançou e qual o alvo, quando houver alvo. O alvo é guardado
como identificador, nunca como referência ao objeto: quem resolve pergunta se
aquele identificador ainda está em algum banco. Se não estiver, o feitiço
fizzla.

**Why this priority**: é o que a nota de implementação da §6 exige, e a razão
pela qual US2 existe. Resolver a pilha é de outra feature; guardar a pilha e
responder a pergunta é desta.

**Independent Test**: empilhar dois feitiços, conferir a ordem de resolução,
consultar um identificador de alvo presente no banco e outro ausente.

**Acceptance Scenarios**:

1. **Given** dois feitiços empilhados em ordem conhecida, **When** leio a
   pilha, **Then** a ordem permite resolver o último empilhado primeiro.
2. **Given** um feitiço na pilha, **When** leio a entrada, **Then** encontro
   qual feitiço é, quem lançou e o alvo — ou a ausência explícita de alvo.
3. **Given** um identificador de instância que está no banco de um jogador,
   **When** pergunto ao estado se ele ainda está em campo, **Then** a resposta
   é positiva e me dá a unidade, sem que eu precise dizer de qual jogador ela
   é.
4. **Given** um identificador de instância que saiu do banco e está no
   cemitério, **When** faço a mesma pergunta, **Then** a resposta é negativa —
   o que permite o fizzle sem nenhuma regra de jogo aqui dentro.

---

### User Story 6 - Entregar a cada jogador só o que ele pode ver (Priority: P2)

O servidor é a autoridade. A ordem do deck nunca sai dele, e a mão do oponente
também não. Dado o estado completo e um `user_id`, produzir a visão daquele
jogador.

Ele vê: a própria mão, o próprio banco e o do oponente, os dois Nexus, a
própria energia e a do oponente, a fase, de quem é a prioridade, quem tem o
token e se já foi usado, a pilha e os dois cemitérios.

Ele não vê: o conteúdo nem a ordem de nenhum dos dois decks, e o conteúdo da
mão do oponente — só quantas cartas ela tem.

**Why this priority**: é a fronteira de confiança do jogo. Depende de US1 e
US2, mas é independentemente testável e independentemente entregável.

**Independent Test**: montar um estado com mãos e decks conhecidos e distintos,
gerar a visão dos dois jogadores e conferir, em cada uma, o que aparece e o que
não aparece.

**Acceptance Scenarios**:

1. **Given** um estado com as duas mãos preenchidas, **When** gero a visão do
   jogador A, **Then** a mão de A aparece com identificadores e `card_id`, e a
   mão de B aparece apenas como contagem.
2. **Given** um estado com os dois decks preenchidos e embaralhados, **When**
   gero a visão de qualquer um dos jogadores, **Then** nenhum `card_id` nem
   identificador de carta de deck aparece na estrutura, de nenhum dos lados.
3. **Given** um estado qualquer, **When** gero a visão de um jogador, **Then**
   encontro os dois bancos, os dois Nexus, os dois cemitérios, as duas
   energias, a fase, a prioridade, o dono do token e se ele foi consumido.
4. **Given** um `user_id` que não joga a partida, **When** peço a visão dele,
   **Then** a operação falha citando o `user_id` pedido, em vez de devolver uma
   visão parcial.

---

### User Story 7 - Não quebrar quem já depende da partida (Priority: P3)

Três consumidores já existem e continuam funcionando com o estado novo, mais
rico: o store que grava e lê no Redis, o consumer que pergunta se um `user_id`
participa da partida para fechar o socket de quem não joga, e o matchmaking que
cria a partida ao parear dois jogadores.

O setup de verdade da §3 — embaralhar, comprar 4, mulligan, sortear o token —
é a próxima feature. Até lá o caminho de criação produz uma partida válida,
ainda que não jogável.

**Why this priority**: é continuidade, não capacidade nova. Vale como história
porque tem teste próprio e porque a regressão aqui é silenciosa.

**Independent Test**: parear dois jogadores pelo caminho existente, gravar,
reler e conferir que os dois passam no gate de participante e que um terceiro
`user_id` não passa.

**Acceptance Scenarios**:

1. **Given** uma partida criada pelo caminho do matchmaking, **When** pergunto
   se cada um dos dois `user_id` participa, **Then** a resposta é positiva para
   os dois.
2. **Given** a mesma partida, **When** pergunto por um `user_id` de fora ou por
   um socket sem usuário autenticado, **Then** a resposta é negativa.
3. **Given** a mesma partida gravada no Redis, **When** outro processo a
   recarrega, **Then** ela volta completa e o gate de participante continua
   respondendo igual.
4. **Given** a mesma partida recarregada, **When** leio os dados públicos dos
   dois jogadores, **Then** apelido, ícone e nível continuam lá.

---

### Edge Cases

- **Zona vazia.** Deck, mão, banco, cemitério e pilha vazios são estado válido
  e precisam sobreviver à ida e volta como vazios, não como ausentes.
- **Feitiço sem alvo.** `RestoreNexus` e `SacrificeNexusForAttack` não miram
  nada. A ausência de alvo é explícita na entrada da pilha, distinta de um alvo
  que já sumiu.
- **Alvo que trocou de zona.** O identificador continua existindo no cemitério,
  mas a pergunta é "ainda está no banco?" — e a resposta precisa ser negativa.
- **Alvo no banco do próprio lançador.** A busca por identificador de alvo
  varre os dois bancos: `BuffUnitHealth` mira aliado, `DamageUnit` mira
  inimigo. Decidir qual é legal é de outra feature.
- **Dono derivado da faixa do identificador.** Como o setup numera em
  sequência, um jogador acaba ficando com os números baixos e o outro com os
  altos. É acidente de ordem de criação, não contrato: dono se descobre por em
  qual jogador a carta está, e nunca comparando o `card_instance_id` com um
  limite.
- **Modificador de ataque negativo.** Um modificador pode reduzir o ataque, e a
  soma pode ficar abaixo de zero. Se o ataque efetivo tem piso em 0 é regra de
  combate; esta feature guarda os insumos e não faz a conta.
- **`user_id` ausente.** Um socket sem usuário autenticado chega com `None` ao
  gate de participante; a resposta continua sendo negativa, nunca um erro.
- **Colisão de identificador.** Dois identificadores iguais dentro da mesma
  partida tornam o alvo ambíguo. O contador único da partida impede isso por
  construção; dois contadores por jogador o reintroduziriam.
- **Estado com fase `COMBATE`.** A fase existe no conjunto fechado desde já,
  mas o estado que o combate precisa (pareamento de bloqueadores, §7.2) entra
  na feature de combate. Como o espaço de identificadores é único na partida,
  esse pareamento é um mapa de número para número, e não de par composto para
  par composto.

## Requirements *(mandatory)*

### Functional Requirements

**Estado da partida**

- **FR-001**: O estado da partida MUST carregar `match_id`, os dois jogadores,
  a rodada atual, o dono do token de ataque, se o token já foi consumido na
  rodada, de quem é a prioridade, a fase atual, a pilha de feitiços pendentes,
  a contagem de passes consecutivos e o contador de identificadores de
  instância.
- **FR-002**: A fase MUST pertencer a um conjunto fechado de exatamente cinco
  valores — Upkeep, Ação, Resolução de Pilha, Combate e Fim de Rodada (§2).
  Nenhum outro valor pode ser representável.
- **FR-003**: Dono do token e prioridade MUST ser expressos como `user_id`,
  nunca como índice de lista nem como referência ao objeto do jogador.
- **FR-004**: O estado de um jogador MUST carregar `user_id`, Nexus, deck, mão,
  banco, cemitério, energia máxima e energia atual.
- **FR-005**: Os dois jogadores MUST ficar numa coleção ordenada de dois, cada
  um carregando o próprio `user_id`. Nenhuma estrutura do estado MUST ser
  indexada por `user_id`.
- **FR-006**: O estado MUST devolver o jogador correspondente a um `user_id`, e
  MUST falhar citando o `user_id` pedido quando ele não joga a partida.
- **FR-007**: Deck, mão, banco, cemitério e pilha MUST ser coleções ordenadas —
  a ordem é significativa em todas as cinco e precisa ser preservada.
- **FR-008**: O estado da partida MUST carregar os dados públicos de cada
  jogador (apelido, ícone, nível), como já carrega hoje.

**Identidade individual de carta**

- **FR-009**: Toda carta que pertence a uma partida MUST carregar um
  identificador próprio, distinto do `card_id` e do `user_id`, e único dentro
  daquela partida — não dentro de um jogador.
- **FR-010**: O identificador MUST ser um inteiro atribuído por um contador que
  vive no estado da partida e avança a cada carta criada.
- **FR-011**: O identificador MUST ser opaco. Ele MUST NOT codificar o
  `card_id`, o dono da carta, a zona onde ela está nem o ordinal da cópia, e
  nenhum código MUST derivar qualquer um desses fatos a partir do valor ou da
  faixa dele.
- **FR-012**: O identificador MUST nascer com a carta e MUST NOT mudar ao
  trocar de zona — deck, mão, banco, pilha e cemitério.
- **FR-013**: Duas cópias do mesmo `card_id` MUST ser distinguíveis uma da
  outra em qualquer zona.
- **FR-014**: A estrutura MUST permitir que o reset de deck (§9) devolva as
  cartas do cemitério ao deck com os mesmos identificadores, sem consultar o
  contador. Executar o reset é de outra feature.
- **FR-015**: O contador MUST sobreviver à ida e volta, para que uma carta
  criada depois de uma recarga do Redis não colida com nenhuma existente.

**Unidade no banco**

- **FR-016**: Uma unidade no banco MUST carregar identificador de instância,
  `card_id` de origem, dano acumulado e os modificadores ativos sobre ela.
- **FR-017**: A instância MUST NOT copiar ataque nem vida do molde. Esses
  valores permanecem no catálogo, e o efetivo é derivado do molde mais os
  modificadores — nunca pré-calculado e gravado no estado. Derivar é de outra
  feature.
- **FR-018**: Dano acumulado e modificadores MUST NOT existir para carta na
  mão, no deck ou no cemitério.
- **FR-019**: O molde do catálogo MUST NOT ser alterado por nada nesta feature.
  Buff, dano e cura recaem sobre a instância.
- **FR-020**: Os modificadores MUST ser uma união fechada de tipos, e não um
  registro genérico com o atributo alterado em texto livre. Um tipo sem
  quantidade MUST NOT ter campo de quantidade.
- **FR-021**: Cada modificador MUST registrar se vale para sempre ou até o fim
  da rodada, e MUST ser possível separar os dois grupos sem interpretar texto.
  Aplicar e varrer modificador não é desta feature.
- **FR-022**: A união MUST cobrir o que os efeitos do catálogo do MVP produzem:
  alteração de ataque, alteração de vida e imunidade a dano. Um efeito que não
  produz modificador (dano direto, cura de Nexus) MUST NOT ganhar um tipo só
  para constar.

**Pilha**

- **FR-023**: Uma entrada da pilha MUST dizer qual feitiço é, quem o lançou e
  qual o alvo quando houver alvo.
- **FR-024**: A ausência de alvo MUST ser explícita e distinguível de um alvo
  que existiu e sumiu.
- **FR-025**: O alvo MUST ser guardado como identificador de instância, nunca
  como referência ao objeto alvo.
- **FR-026**: A ordem da pilha MUST permitir resolução LIFO e MUST sobreviver à
  ida e volta.
- **FR-027**: O estado MUST responder se um identificador de instância ainda
  está em algum banco, devolvendo a unidade quando estiver, sem que quem
  pergunta precise informar de qual jogador ela é. É essa pergunta que torna o
  fizzle da §6 implementável.

**Serialização**

- **FR-028**: O estado inteiro MUST virar uma estrutura compatível com JSON e
  voltar sem perda.
- **FR-029**: A ida e volta a partir de qualquer estado válido MUST devolver um
  estado igual ao original — identificadores, contador, ordem do deck, ordem da
  pilha, dano acumulado e modificadores inclusive.
- **FR-030**: Nenhum objeto JSON do estado serializado MUST ter `user_id` como
  chave, em nenhum nível. Chave de objeto JSON é sempre string, e o modelo
  atual só sobrevive porque converte de volta na mão; o formato novo remove a
  necessidade da conversão em vez de repeti-la.
- **FR-031**: Zona vazia MUST voltar vazia, nunca ausente.

**Visão do jogador**

- **FR-032**: Dado o estado completo e um `user_id`, o sistema MUST produzir a
  visão daquele jogador.
- **FR-033**: A visão MUST conter a própria mão, os dois bancos, os dois Nexus,
  a própria energia e a do oponente, a fase, a prioridade, o dono do token, se
  o token foi consumido, a pilha, os dois cemitérios e a rodada atual.
- **FR-034**: A visão MUST NOT conter o conteúdo nem a ordem de nenhum dos dois
  decks.
- **FR-035**: A visão MUST NOT conter a identidade das cartas na mão do
  oponente. A contagem MUST aparecer; o conteúdo não.
- **FR-036**: As cartas visíveis na visão MUST carregar o identificador de
  instância, para que o cliente possa mirar uma cópia específica.
- **FR-037**: Pedir a visão de um `user_id` que não joga a partida MUST falhar
  com mensagem citando o `user_id` pedido.

**Continuidade**

- **FR-038**: A pergunta "este `user_id` participa desta partida?" MUST
  continuar existindo, respondendo negativamente para `None` e para `user_id`
  de fora.
- **FR-039**: O store do Redis MUST continuar gravando e lendo o estado novo
  pela mesma interface, sem mudança nos seus chamadores.
- **FR-040**: O caminho de criação usado pelo matchmaking MUST continuar
  produzindo uma partida válida, ainda que não jogável, sem executar o setup da
  §3.
- **FR-041**: O catálogo de cartas MUST chegar por parâmetro a quem precisar
  dele, nunca por import no ponto de uso.
- **FR-042**: O `play_card` atual MUST ser removido, não migrado — é regra de
  jogo, e regra de jogo não é desta feature.
- **FR-043**: Os fakes e testes que cobrem o modelo atual
  (`fake_match_store.py`, `test_match_model.py`, `test_match_store.py`) MUST
  acompanhar a troca.
- **FR-044**: A representação do estado de combate (pareamento de bloqueadores,
  §7.2) MUST poder ser acrescentada depois sem reescrever o que esta feature
  entrega.

### Key Entities

- **Estado da partida**: uma partida viva inteira. Endereçada por `match_id`.
  Guarda os dois jogadores, a rodada, o token e seu consumo, a prioridade, a
  fase, a pilha, os passes consecutivos e o contador de identificadores de
  instância.
- **Estado do jogador**: um lado do tabuleiro. `user_id`, os dados públicos do
  jogador, Nexus, as quatro zonas de carta (deck, mão, banco, cemitério) e as
  duas energias.
- **Carta em partida**: uma cópia concreta de um molde do catálogo. Um
  identificador de instância, único na partida, mais o `card_id` que aponta
  para o molde. É o que vive no deck, na mão e no cemitério, e é só isso — sem
  nome, custo, ataque nem vida copiados.
- **Unidade no banco**: uma carta em partida que está em campo. Acrescenta dano
  acumulado e modificadores ativos. Só existe enquanto está no banco.
- **Modificador**: uma alteração ativa sobre uma unidade no banco. União
  fechada de tipos — alteração de ataque, alteração de vida, imunidade a dano —
  cada um com duração permanente ou até o fim da rodada.
- **Entrada da pilha**: um feitiço lançado e ainda não resolvido. Qual feitiço,
  quem lançou, qual alvo — ou nenhum.
- **Fase**: conjunto fechado das cinco fases da §2.
- **Visão do jogador**: o recorte do estado que um `user_id` pode receber.
  Derivada, nunca armazenada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos campos da §2 do Fluxo de Partida têm onde morar no
  estado — a lista da nota e a lista dos campos coincidem sem sobra nem falta
  dos dois lados.
- **SC-002**: Qualquer estado válido de partida, incluindo os limites (zonas
  vazias, banco cheio com 6, pilha com mais de um feitiço, mão no teto de 10),
  volta idêntico da ida e volta pela serialização.
- **SC-003**: Duas cópias da mesma carta são distinguíveis em cada uma das
  cinco zonas, e o identificador de uma delas é o mesmo antes e depois de
  percorrer todas as cinco.
- **SC-004**: Reunindo os identificadores das 80 cartas dos dois jogadores, não
  há um único valor repetido.
- **SC-005**: Perguntar se um identificador de alvo ainda está em campo é
  respondido por uma única consulta ao estado, sem que quem pergunta precise
  varrer zona por zona nem saber de qual jogador o alvo é.
- **SC-006**: Nenhum valor de ataque ou vida vindo do catálogo aparece no
  estado serializado — verificável por inspeção do JSON gravado.
- **SC-007**: A visão de um jogador não contém nenhum `card_id` nem
  identificador vindo de qualquer um dos dois decks nem da mão do oponente —
  verificável por inspeção da estrutura produzida, não por confiança no
  chamador.
- **SC-008**: Os dois jogadores pareados pelo matchmaking continuam passando no
  gate de participante depois de a partida ir ao Redis e voltar, e um terceiro
  `user_id` continua sendo recusado.
- **SC-009**: `cd server && pytest` e `cd server && mypy` passam, e
  `black --check server/` fica limpo — as três portas da constituição.

## Assumptions

- **Estado inicial sem setup.** A partida criada pelo matchmaking nasce com
  rodada 1, fase Upkeep, Nexus 20 para os dois, energia máxima e atual em 0,
  token consumido `false`, passes consecutivos 0, pilha vazia e as quatro zonas
  de carta vazias. Embaralhar, comprar 4, mulligan e sortear o token são a §3 e
  entram na próxima feature.
- **Dono do token inicial.** Sem o sorteio da §3, o dono inicial é
  determinístico — o primeiro jogador do par —, e a prioridade nasce igual a
  ele. É valor de espera, não regra: quem sorteia é a feature de setup.
- **Contador parado no MVP.** Nenhuma carta nasce depois do setup: as 80
  circulam entre as cinco zonas até a partida acabar, e o reset de deck da §9
  reaproveita as mesmas. O contador existe pelo primeiro efeito que invocar
  unidade (§13 lista palavras-chave em aberto) e para tornar essa adição
  indolor, como o FR-044 pede.
- **Dados públicos do jogador continuam no estado.** Apelido, ícone e nível
  ficam onde já estão. O matchmaking também os envia no `match_found`, mas quem
  reconecta ao socket de partida precisa deles sem uma nova consulta ao banco,
  e são quatro campos pequenos por jogador.
- **Contagem de deck na visão.** O tamanho de cada deck aparece na visão dos
  dois jogadores. O que a §2 protege é conteúdo e ordem; a contagem não revela
  carta nenhuma e o cliente precisa dela para desenhar a pilha de compra.
- **Cemitério é público.** Os dois cemitérios aparecem inteiros, com conteúdo e
  ordem, na visão dos dois jogadores. É informação já revelada.
- **A visão manda `card_id`, não a carta inteira.** O cliente já tem o catálogo
  para desenhar arte e nome; a visão não repete nome, custo, ataque nem vida.
- **Dano sem teto explícito.** Cura abaixo de zero de dano e dano acima da vida
  do molde não são limitados por esta feature — limitar é regra.
- **Sem versionamento de estado.** O estado gravado no Redis não carrega número
  de versão. Partidas vivas do formato antigo são descartadas na troca; o TTL
  de 6 horas fecha a janela sozinho e não existe base de produção a migrar.
- **A visão não é o envelope.** Produzir a visão é desta feature; empacotar,
  transmitir e reenviar na reconexão é do websocket.

## Out of Scope

- Qualquer regra de jogo: validar jogada, aplicar efeito, calcular dano, trocar
  prioridade, avançar fase, resolver a pilha, executar o fizzle.
- Derivar ataque e vida efetivos a partir do molde e dos modificadores. Esta
  feature guarda os insumos; a conta é do motor.
- O setup do início da partida (§3) e a compra, incluindo o reset de deck (§9).
- O pareamento de bloqueadores do combate (§7.2). A fase Combate existe no
  conjunto fechado; o estado que ela precisa entra na feature de combate.
- Traduzir efeito de feitiço em modificador. Os tipos de modificador existem
  aqui; quem os cria a partir de um `SpellEffect` é o motor.
- Envelope de mensagem, broadcast e reconexão no websocket.
- Atomicidade do read-modify-write no Redis. `store.py` já registra que a
  mutação vai precisar de script Lua; continua verdade e continua fora.
- Timeout de jogada (§13 do Fluxo de Partida) — problema de transporte.

## Dependencies

- **Catálogo de cartas** (feature 001, `server/apps/game/cards/`): a fonte dos
  moldes, e a única fonte de ataque e vida. Chega por parâmetro, nunca por
  import no ponto de uso.
- **`PlayerData`** (`apps/players/services/player_queries`): os dados públicos
  do jogador que o matchmaking já injeta na criação da partida.
- **`Game/Fluxo de Partida.md`** no vault: §2 é o contrato; §6, §8 e §9
  justificam campos individuais.
