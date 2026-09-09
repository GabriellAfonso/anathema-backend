# Feature Specification: Catálogo de Cartas do MVP

**Feature Branch**: `001-card-catalog`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Catálogo de cartas do MVP: a fonte única de verdade sobre quais cartas existem, quanto custam e o que fazem. Os dados vêm do jogo anterior (dumcrown `cards_data`: `units.py` e `spells.py`), 24 unidades e 5 feitiços; os valores numéricos são reaproveitados como estão, o formato muda."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

## Clarifications

### Sessão 2026-09-09

- **P: Que forma tem o identificador de carta?**
  R: Um `card_id` numérico, único em todo o catálogo. O prefixo `s` dos
  feitiços do jogo anterior é abandonado — o tipo passa a ser um campo próprio
  (`type` = `unit` | `spell`), não um detalhe codificado dentro do
  identificador. Unidade e feitiço vivem no mesmo espaço de identificadores.
- **P: Como as faixas são repartidas?**
  R: Por convenção de alocação, unidade recebe `card_id` de 1 a 1000 e feitiço
  a partir de 1001. Serve para ler uma lista de deck crua e reconhecer o que é
  o quê sem consultar o catálogo. É convenção, não regra do motor: quem quer
  saber o tipo lê o campo `type`, nunca a faixa.
- **P: E a identidade de uma cópia?**
  R: Um deck pode ter até 3 cópias do mesmo `card_id`, e cada cópia precisa de
  identidade própria quando vira carta na mão ou unidade no banco. Essa
  identidade **não** é atribuída pelo catálogo: o catálogo dá o molde, a camada
  de partida dá a identidade da instância. Fica registrado em *Out of Scope*
  para a feature que criar a instância.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar uma carta pelo identificador (Priority: P1)

O motor de regras recebe um `card_id` — vindo da mão de um jogador, de uma lista
de deck ou de uma mensagem de websocket — e precisa saber o que aquela carta é:
tipo, nome, custo de energia e, se for unidade, ataque e vida. O catálogo
responde com a carta ou recusa com um erro que diz qual identificador foi
pedido.

**Why this priority**: sem isso nada mais do catálogo tem uso. Toda outra
capacidade (listar, validar deck, ler efeito) depende de resolver um
identificador em uma carta.

**Independent Test**: pedir ao catálogo cada um dos 29 identificadores
conhecidos e conferir os valores; pedir um identificador inexistente e conferir
que o erro cita o identificador pedido.

**Acceptance Scenarios**:

1. **Given** o catálogo do MVP carregado, **When** consulto o `card_id` de uma
   unidade conhecida, **Then** recebo tipo `unit`, nome, custo de energia,
   ataque, vida e imagem daquela unidade.
2. **Given** o catálogo do MVP carregado, **When** consulto o `card_id` de um
   feitiço conhecido, **Then** recebo tipo `spell`, nome, custo de energia,
   imagem, descrição legível e o efeito estruturado.
3. **Given** o catálogo do MVP carregado, **When** consulto um `card_id` que não
   existe, **Then** a operação falha e a mensagem de erro contém o identificador
   que foi pedido.

---

### User Story 2 - Ler o efeito estruturado de um feitiço (Priority: P2)

O motor de regras precisa decidir, sem interpretar português, se uma jogada de
feitiço é legal: se exige alvo, que tipo de alvo aceita e se o resultado dura
para sempre ou só até o fim da rodada. O motor consulta essas propriedades duas
vezes — ao aceitar a jogada e de novo ao resolver a pilha (ver
`Game/Fluxo de Partida.md` §5B e §6).

**Why this priority**: é o que diferencia este catálogo de uma tabela de dados.
A descrição em texto existe só para o cliente mostrar ao jogador; o motor nunca
a lê.

**Independent Test**: para cada um dos 5 feitiços, ler exigência de alvo, tipo
de alvo e duração, e comparar com a tabela de efeitos desta spec — sem
inspecionar a descrição textual.

**Acceptance Scenarios**:

1. **Given** o feitiço SUMMONED AX, **When** leio seu efeito, **Then** ele
   declara que exige alvo, que o tipo de alvo é unidade inimiga, e que causa 3
   de dano.
2. **Given** o feitiço LIFE POTION, **When** leio seu efeito, **Then** ele
   declara que não exige alvo e que recupera 5 de Nexus do próprio jogador.
3. **Given** o feitiço MAGIC BARRIER, **When** leio seu efeito, **Then** ele
   declara duração "até o fim da rodada atual".
4. **Given** o feitiço SOMEONE'S SHIELD, **When** leio seu efeito, **Then** ele
   declara duração "permanente".
5. **Given** qualquer feitiço do MVP, **When** o motor precisa decidir se a
   jogada é legal, **Then** consegue fazê-lo lendo apenas campos estruturados,
   sem ler a descrição em português.

---

### User Story 3 - Listar o catálogo (Priority: P3)

Um consumidor — tela de coleção do cliente, ferramenta de construção de deck,
teste — precisa da lista de tudo que existe, ou só das unidades, ou só dos
feitiços.

**Why this priority**: necessário para qualquer superfície que mostre cartas ao
jogador, mas o motor de partida funciona sem.

**Independent Test**: listar tudo e contar 29; listar unidades e contar 24;
listar feitiços e contar 5.

**Acceptance Scenarios**:

1. **Given** o catálogo do MVP, **When** listo todas as cartas, **Then** recebo
   29 cartas.
2. **Given** o catálogo do MVP, **When** listo só unidades, **Then** recebo as
   24 unidades e nenhum feitiço.
3. **Given** o catálogo do MVP, **When** listo só feitiços, **Then** recebo os 5
   feitiços e nenhuma unidade.
4. **Given** um catálogo que não contém feitiços, **When** listo só feitiços,
   **Then** recebo uma lista vazia — não um erro.

---

### User Story 4 - Validar um deck (Priority: P4)

Antes de uma partida começar, o deck declarado por um jogador precisa ser aceito
ou recusado. Recusa não pode ser genérica: tem que dizer o que está errado com
aquele deck específico.

**Why this priority**: porta de entrada da partida, mas depende da consulta por
identificador já funcionar.

**Independent Test**: submeter um deck válido de 40 e ver aceitação; submeter
decks com cada defeito isolado e conferir que a mensagem nomeia o defeito
concreto.

**Acceptance Scenarios**:

1. **Given** uma lista de 40 `card_id` existentes com no máximo 3 cópias de
   cada, **When** valido o deck, **Then** ele é aceito.
2. **Given** uma lista de 39 `card_id` válidos, **When** valido o deck, **Then**
   ele é recusado e a mensagem diz que o deck tem 39 cartas e que o exigido são
   40.
3. **Given** uma lista de 40 `card_id` em que um deles aparece 4 vezes, **When**
   valido o deck, **Then** ele é recusado e a mensagem nomeia esse identificador
   e quantas cópias ele tem.
4. **Given** uma lista de 40 `card_id` em que um não existe no catálogo, **When**
   valido o deck, **Then** ele é recusado e a mensagem nomeia o identificador
   inexistente.
5. **Given** um deck que viola mais de uma regra ao mesmo tempo, **When** valido
   o deck, **Then** a recusa relata todos os problemas encontrados, não apenas o
   primeiro.

---

### Edge Cases

- Deck vazio: recusado, informando 0 cartas contra as 40 exigidas.
- Deck com 41 ou mais cartas: recusado, informando a quantidade real.
- Deck com vários identificadores acima de 3 cópias: cada um é nomeado, com sua
  contagem.
- Deck com vários identificadores inexistentes: cada um é nomeado.
- Consulta com identificador ausente ou fora do formato numérico: mesmo
  tratamento de identificador desconhecido, e a mensagem mostra o valor
  recebido.
- Listagem por tipo em um catálogo sem cartas daquele tipo: lista vazia, nunca
  erro.
- Duas cartas com o mesmo `card_id` na carga do catálogo: a carga falha,
  nomeando o identificador duplicado. O catálogo não pode subir ambíguo.
- Consumidor tenta alterar uma carta obtida do catálogo: a alteração não pode se
  propagar para consultas seguintes.

## Requirements *(mandatory)*

### Functional Requirements

#### Conteúdo do catálogo

- **FR-001**: O catálogo MUST conter exatamente as 29 cartas do MVP: 24 unidades
  e 5 feitiços, listados no apêndice *Dados de Origem*.
- **FR-002**: Todos os valores numéricos (custo de energia, ataque, vida) MUST
  ser idênticos aos do jogo anterior. Esta feature muda o formato, não o
  balanceamento.
- **FR-003**: Toda carta MUST ter identificador próprio, tipo, nome, custo de
  energia e referência de imagem.
- **FR-004**: O identificador MUST se chamar `card_id`, ser numérico e ser único
  em todo o catálogo — unidades e feitiços compartilham o mesmo espaço de
  identificadores, sem colisão. Unidade MUST receber `card_id` entre 1 e 1000;
  feitiço MUST receber `card_id` a partir de 1001.
- **FR-005**: O `card_id` MUST NOT codificar o tipo da carta. O prefixo `s` dos
  feitiços do jogo anterior é abandonado, e a faixa de FR-004 é convenção de
  alocação, não fonte de verdade: nenhum consumidor MUST decidir o tipo de uma
  carta comparando o `card_id` com 1000.
- **FR-006**: Toda carta MUST declarar seu tipo em um campo próprio, com valor
  `unit` ou `spell`, consultável sem inspecionar quais outros campos a carta
  tem.
- **FR-007**: O `card_id` MUST ser exposto sempre com esse nome e nunca como um
  campo `id` nu, conforme a decisão em vigor sobre espaços de identidade.
- **FR-008**: A referência de imagem MUST ser tratada como metadado opaco: o
  motor de regras não a interpreta e nunca decide nada com base nela.

#### Unidades

- **FR-009**: Toda unidade MUST ter, além dos campos comuns, ataque e vida.
- **FR-010**: O campo do jogo anterior chamado `defense` MUST ser renomeado para
  o atributo de vida da unidade. "Defesa" é proibido como nome porque colide
  conceitualmente com bloqueio, que é outra mecânica.
- **FR-011**: O nome do atributo de vida da unidade MUST ser distinto do nome da
  vida do jogador (Nexus). Os dois conceitos não podem compartilhar nome em
  nenhuma superfície: modelo, payload ou mensagem.

#### Feitiços

- **FR-012**: Todo feitiço MUST ter uma descrição legível pelo jogador e um
  efeito estruturado.
- **FR-013**: O efeito MUST NOT ser texto livre. Toda decisão que o motor toma
  sobre um feitiço MUST ser possível lendo apenas campos estruturados.
- **FR-014**: Todo efeito MUST declarar, de forma consultável: (a) se exige
  alvo; (b) que tipo de alvo aceita — unidade aliada, unidade inimiga ou nenhum;
  (c) se dura para sempre ou até o fim da rodada atual.
- **FR-015**: Os cinco efeitos do MVP MUST corresponder exatamente à tabela
  *Efeitos do MVP* abaixo.
- **FR-016**: As propriedades de alvo MUST ser consultáveis pelo motor tanto no
  momento de aceitar a jogada quanto no momento de resolver a pilha, com o mesmo
  resultado nas duas leituras.

#### Consulta e listagem

- **FR-017**: O catálogo MUST permitir obter uma carta pelo `card_id`.
- **FR-018**: `card_id` desconhecido MUST ser erro, e a mensagem MUST conter o
  identificador que foi pedido.
- **FR-019**: O catálogo MUST permitir listar todas as cartas.
- **FR-020**: O catálogo MUST permitir listar apenas unidades e apenas feitiços,
  usando o campo de tipo como critério.

#### Validação de deck

- **FR-021**: Um deck MUST ser considerado válido quando tem exatamente 40
  cartas, no máximo 3 cópias de um mesmo `card_id`, e todos os `card_id` existem
  no catálogo.
- **FR-022**: Deck com quantidade errada MUST ser recusado com mensagem que
  informa a quantidade encontrada e a exigida.
- **FR-023**: Deck que excede o limite de cópias MUST ser recusado com mensagem
  que nomeia cada `card_id` excedente e sua contagem.
- **FR-024**: Deck com `card_id` inexistente MUST ser recusado com mensagem que
  nomeia cada identificador desconhecido.
- **FR-025**: A validação MUST relatar todos os problemas encontrados em uma
  única passada, não interromper no primeiro.

#### Natureza do catálogo

- **FR-026**: O catálogo MUST ser somente leitura em tempo de execução. Nenhuma
  operação do jogo altera uma carta do catálogo.
- **FR-027**: Buff, dano e qualquer mudança de estado MUST recair sobre a
  instância da unidade em campo, nunca sobre a carta do catálogo. Duas partidas
  simultâneas leem o mesmo catálogo sem interferir uma na outra.
- **FR-028**: O acesso ao catálogo MUST se dar por uma interface, de modo que um
  consumidor possa receber um catálogo alternativo por injeção.
- **FR-029**: A interface MUST permitir que um teste injete um catálogo pequeno
  e controlado (por exemplo 3 cartas) no lugar das 29 reais, sem alterar o
  código do consumidor.
- **FR-030**: A carga do catálogo MUST falhar em voz alta se houver `card_id`
  duplicado, nomeando o identificador em conflito.

### Efeitos do MVP

| Feitiço | Custo | O que faz | Exige alvo | Tipo de alvo | Duração |
|---|---|---|---|---|---|
| SOMEONE'S SHIELD | 2 | Soma 2 à vida da unidade alvo | Sim | Unidade aliada | Permanente |
| MAGIC BARRIER | 3 | A unidade alvo não recebe nenhum dano | Sim | Unidade aliada | Até o fim da rodada atual |
| SACRIFICIAL FIRE | 8 | O próprio jogador perde 8 de Nexus e todas as unidades dele em campo ganham 3 de ataque | Não | Nenhum | Permanente |
| LIFE POTION | 4 | O próprio jogador recupera 5 de Nexus | Não | Nenhum | Permanente |
| SUMMONED AX | 5 | Causa 3 de dano à unidade alvo | Sim | Unidade inimiga | Permanente |

### Key Entities *(include if feature involves data)*

- **Carta**: o que é comum a tudo que existe no catálogo — `card_id`, tipo
  (`unit` ou `spell`), nome, custo de energia, referência de imagem. Nunca muda
  em partida.
- **Unidade**: carta de tipo `unit`, permanente em campo. Acrescenta ataque e
  vida. É o molde do qual a instância em campo é criada; a instância pertence a
  outra feature.
- **Feitiço**: carta de tipo `spell`, de efeito único. Acrescenta descrição
  legível (para o jogador) e efeito estruturado (para o motor).
- **Efeito de Feitiço**: descrição executável do que o feitiço faz, mais as três
  propriedades que o motor consulta: exigência de alvo, tipo de alvo e duração.
- **Tipo de Alvo**: conjunto fechado — unidade aliada, unidade inimiga, nenhum.
- **Duração de Efeito**: conjunto fechado — permanente, até o fim da rodada
  atual. O segundo valor é o que a limpeza de Fim de Rodada usa (§8 do Fluxo de
  Partida).
- **Catálogo**: a coleção completa e imutável, acessada por uma interface que
  admite substituição.
- **Deck**: lista de 40 `card_id` submetida para validação. Repetição é
  esperada: até 3 entradas com o mesmo `card_id`. Esta feature só valida a
  lista; não a persiste e não dá identidade às cópias.
- **Erro de Deck**: problema concreto encontrado na validação, com o valor
  ofensor — a quantidade errada, o `card_id` excedente com sua contagem, ou o
  `card_id` inexistente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: As 29 cartas do MVP estão disponíveis, e uma conferência campo a
  campo contra os dados do jogo anterior mostra 0 divergências de valor
  numérico.
- **SC-002**: Consultar qualquer um dos 29 `card_id` retorna a carta correta;
  consultar um `card_id` inexistente falha, e a mensagem contém o identificador
  pedido em 100% dos casos.
- **SC-003**: O motor decide a legalidade de jogada dos 5 feitiços lendo apenas
  campos estruturados — 0 decisões dependem de interpretar texto em português.
- **SC-004**: 100% dos decks inválidos testados são recusados com uma mensagem
  que nomeia o valor ofensor concreto; nenhuma recusa é genérica.
- **SC-005**: Um deck válido de 40 cartas é aceito, e um deck com múltiplos
  defeitos simultâneos tem todos eles relatados em uma única validação.
- **SC-006**: Nenhum caminho de execução do jogo altera uma carta do catálogo —
  verificável ao ler o catálogo antes e depois de uma partida completa e obter
  os mesmos valores.
- **SC-007**: A suíte de testes desta feature roda com um catálogo substituto de
  5 cartas ou menos, sem carregar as 29 reais.
- **SC-008**: Nenhum dos 29 `card_id` se repete, todas as 24 unidades caem na
  faixa 1–1000 e todos os 5 feitiços em 1001 ou acima, e separar unidades de
  feitiços usa apenas o campo de tipo — 0 consultas dependem do formato ou da
  faixa do identificador.

## Out of Scope

- **Identidade de cópia.** Um deck tem até 3 cópias do mesmo `card_id`, e cada
  cópia precisa de identidade própria assim que vira carta na mão ou unidade no
  banco. Quem atribui essa identidade é a camada de partida, não o catálogo. O
  catálogo entrega o molde; a instância é outra feature.
- Aplicar o efeito de um feitiço. O catálogo descreve o efeito; quem executa é a
  feature da pilha de feitiços.
- Estado de partida, instância de unidade em campo, buffs ativos, Nexus.
- Persistir o deck de um jogador em banco de dados. Se o catálogo virar tabela
  no banco mais tarde, o `card_id` já está pronto para ser a chave — mas essa
  migração não é esta feature.
- Arquivos de imagem e demais assets — o catálogo guarda só a referência.
- Balanceamento, cartas novas, palavras-chave (Rally, Escudo, Investida).
- Endpoint HTTP ou mensagem de websocket que exponha o catálogo ao cliente.

## Assumptions

- **Números atribuídos aos feitiços**: sem o prefixo `s`, o feitiço `s1`
  colidiria com a unidade `1`. As unidades ficam com os `card_id` herdados
  (1–21, 55–57), todos dentro da faixa 1–1000, e os 5 feitiços recebem
  **1001 a 1005**, na ordem original `s1, s2, s5, s7, s8`.
- **Tamanho da faixa de unidades**: 1000 é folga deliberada, não previsão. Com
  24 unidades hoje, a faixa comporta qualquer expansão do MVP sem que um
  identificador de feitiço precise ser remanejado. Se a coleção de unidades
  passar de 1000, a faixa de feitiços é que se move — nunca o contrário, porque
  `card_id` de unidade já vai estar gravado em deck de jogador.
- **Alvo do MAGIC BARRIER**: a descrição herdada não diz de quem é a unidade
  protegida. Assumido **unidade aliada**, por ser um feitiço defensivo. Se o
  desenho pretendia permitir proteger unidade inimiga, esta spec precisa mudar.
- **Duração do SACRIFICIAL FIRE**: nem a descrição herdada nem o pedido dizem que
  o +3 de ataque expira. Assumido **permanente**, coerente com o custo de 8 de
  energia mais 8 de Nexus.
- **Efeitos sobre Nexus**: LIFE POTION e SACRIFICIAL FIRE alteram Nexus de forma
  pontual; são classificados como permanentes por não deixarem nada para a
  limpeza de Fim de Rodada remover.
- **Tamanho do deck e limite de cópias**: as 40 cartas vêm de
  `Game/Fluxo de Partida.md` §12. O limite de 3 cópias vem deste pedido e ainda
  não está registrado em nota de decisão do vault.
- **Lacunas na numeração**: o jogo anterior tem buracos (unidades 22–54
  ausentes). Os buracos ficam como estão; não são cartas a recriar, e não
  impedem nada — o catálogo é um mapa de `card_id` para carta, não uma sequência
  contígua.
- **Descrições dos feitiços**: as descrições herdadas estão em português e falam
  em "defesa" e "vida". Serão reescritas para o vocabulário novo (vida de
  unidade, Nexus), sem mudar o que o feitiço faz.
- **Nomes de carta**: permanecem em inglês e em caixa alta, como no jogo
  anterior.

## Dependencies

- `Game/Fluxo de Partida.md` no vault Obsidian — define Nexus, deck de 40,
  duração "até o fim da rodada" e a revalidação de alvo na pilha. Se o catálogo
  discordar dessa nota, o catálogo está errado.
- Dados de origem em
  `dumcrown/dumcrown/dumcrown/server/cards_data/{units.py,spells.py}` — leitura
  única, para migração. O jogo anterior não é dependência de runtime.

## Dados de Origem *(apêndice)*

Transcrição dos dados do jogo anterior, já com `defense` lido como vida da
unidade e com o `card_id` novo atribuído.

### Unidades (24) — `type: unit`, faixa 1–1000

| `card_id` | Id herdado | Nome | Energia | Ataque | Vida | Imagem |
|---|---|---|---|---|---|---|
| 1 | 1 | JOHN COPPER | 5 | 7 | 5 | john_card |
| 2 | 2 | CAROL ARLET | 5 | 7 | 6 | carol_card |
| 3 | 3 | MORTEM | 5 | 7 | 2 | mortem_card |
| 4 | 4 | KRONOS | 6 | 7 | 4 | kronos_card |
| 5 | 5 | DARK AGE | 1 | 3 | 2 | darkage1_card |
| 6 | 6 | KHRAS | 1 | 2 | 4 | khras_card |
| 7 | 7 | SKILLET | 2 | 4 | 5 | skillet_card |
| 8 | 8 | CDC | 4 | 6 | 2 | cdc_card |
| 9 | 9 | OKADA | 6 | 8 | 5 | okada_card |
| 10 | 10 | SMOOTH CRIMINAL | 3 | 4 | 3 | smoothcriminal_card |
| 11 | 11 | BOOGIE | 2 | 4 | 1 | boogie_card |
| 12 | 12 | SPRING | 4 | 7 | 1 | spring_card |
| 13 | 13 | POLAROID | 3 | 2 | 6 | polaroid_card |
| 14 | 14 | MANIAC | 7 | 10 | 1 | maniac_card |
| 15 | 15 | CRAZY | 1 | 2 | 4 | crazy_card |
| 16 | 16 | THE O'JAYS | 8 | 10 | 5 | theojays_card |
| 17 | 17 | NEON B. | 8 | 3 | 10 | neonb_card |
| 18 | 18 | BALLHAN | 1 | 1 | 4 | ballhan_card |
| 19 | 19 | DARK NECESSITES | 2 | 5 | 1 | darknecessites_card |
| 20 | 20 | ANOMALY | 8 | 8 | 8 | anomaly_card |
| 21 | 21 | RHIOROS GHOST | 1 | 1 | 1 | rhioros_ghost_card |
| 55 | 55 | DARK AGE II | 4 | 5 | 3 | darkage2_card |
| 56 | 56 | DARK AGE III | 8 | 7 | 5 | darkage3_card |
| 57 | 57 | DARK AGE IV | 10 | 9 | 10 | darkage4_card |

### Feitiços (5) — `type: spell`, faixa a partir de 1001

| `card_id` | Id herdado | Nome | Energia | Imagem |
|---|---|---|---|---|
| 1001 | s1 | SOMEONE'S SHIELD | 2 | someones_shield |
| 1002 | s2 | MAGIC BARRIER | 3 | magic_barrier |
| 1003 | s5 | SACRIFICIAL FIRE | 8 | sacrificial_fire |
| 1004 | s7 | LIFE POTION | 4 | life_potion |
| 1005 | s8 | SUMMONED AX | 5 | summoned_ax |
