---

description: "Task list for Catálogo de Cartas do MVP"
---

# Tasks: Catálogo de Cartas do MVP

**Input**: Design documents from `specs/001-card-catalog/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/card_catalog.md](./contracts/card_catalog.md), [quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é opção de estilo: o princípio V da
constituição manda que toda função nova ganhe teste, e a suíte inteira roda com
`cd server && pytest`.

**Organization**: agrupadas por user story, na ordem de prioridade da spec.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo — arquivo diferente, sem dependência pendente
- **[Story]**: a qual user story a tarefa pertence (US1…US4)
- Todo caminho de arquivo é relativo à raiz do repositório

## Path Conventions

Projeto Django, código em `server/`. O catálogo é um subpacote de app existente:

- Implementação: `server/apps/game/cards/`
- Testes: `server/apps/game/tests/` (constituição: "game tests under `apps/game/tests`")

Nenhum arquivo fora dessas duas pastas é tocado, com uma exceção declarada
(T039, nota no vault).

---

## Phase 1: Setup

**Purpose**: criar o pacote.

- [X] T001 Criar o pacote `server/apps/game/cards/` com um `__init__.py` vazio — a superfície pública é fechada em T037, depois que os nomes existirem

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: os tipos e a máquina de catálogo de que todas as quatro stories
dependem.

**⚠️ CRITICAL**: nenhuma user story começa antes desta fase fechar.

- [X] T002 [P] Definir `CardId` (`NewType` sobre `int`), o `StrEnum` `CardType` e as constantes de faixa `UNIT_ID_MIN`, `UNIT_ID_MAX`, `SPELL_ID_MIN` em `server/apps/game/cards/card.py`
- [X] T003 [P] Definir os `StrEnum` `TargetKind` (`NONE`/`ALLIED_UNIT`/`ENEMY_UNIT`) e `EffectDuration` (`PERMANENT`/`UNTIL_END_OF_ROUND`) em `server/apps/game/cards/effects.py`
- [X] T004 Definir as cinco dataclasses congeladas de efeito (`BuffUnitHealth`, `PreventUnitDamage`, `DamageUnit`, `RestoreNexus`, `SacrificeNexusForAttack`), cada uma com `target_kind` e `duration`, e a união `SpellEffect` em `server/apps/game/cards/effects.py` (depende de T003)
- [X] T005 Definir as dataclasses congeladas `Unit` (com `health`, nunca `defense`) e `Spell` (com `description` e `effect`) e a união `Card` em `server/apps/game/cards/card.py` (depende de T002, T004)
- [X] T006 [P] Definir a hierarquia de exceções `CardCatalogError`, `UnknownCardError`, `DuplicateCardIdError` e `CardIdOutOfRangeError` em `server/apps/game/cards/catalog.py`, cada mensagem carregando o valor ofensor
- [X] T007 Definir o `Protocol` `CardCatalog` com os quatro métodos (`card`, `all_cards`, `units`, `spells`) em `server/apps/game/cards/catalog.py` (depende de T005)
- [X] T008 Implementar a construção de `FrozenCardCatalog` em `server/apps/game/cards/catalog.py` — índice por `card_id`, recusando `card_id` duplicado e `card_id` fora da faixa do tipo (depende de T006, T007)
- [X] T009 [P] Escrever `FakeCardCatalog` com os quatro métodos e um punhado de cartas de amostra em `server/apps/game/tests/fake_card_catalog.py`, no mesmo formato de `fake_match_store.py` (depende de T007)
- [X] T010 Escrever os testes de invariante de carga — `card_id` duplicado e `card_id` fora de faixa, conferindo que a mensagem cita o identificador — em `server/apps/game/tests/test_card_catalog.py` (depende de T008)

**Checkpoint**: os tipos existem, o catálogo carrega ou recusa em voz alta, e já
existe um catálogo pequeno injetável. As stories podem começar em paralelo.

---

## Phase 3: User Story 1 - Consultar uma carta pelo identificador (Priority: P1) 🎯 MVP

**Goal**: dado um `card_id`, devolver a carta; dado um desconhecido, falhar com
uma mensagem que diz qual foi pedido.

**Independent Test**: pedir os 29 identificadores conhecidos e conferir os
valores contra o apêndice *Dados de Origem*; pedir um inexistente e conferir que
o erro cita o identificador.

- [X] T011 [US1] Implementar `FrozenCardCatalog.card()` levantando `UnknownCardError` com o `card_id` pedido na mensagem em `server/apps/game/cards/catalog.py` (depende de T008)
- [X] T012 [P] [US1] Escrever os auxiliares `_unit` e `_spell` — que embrulham o `int` em `CardId` e fixam o `card_type` — e as 24 unidades do apêndice, com `defense` transcrito como `health`, em `server/apps/game/cards/mvp_catalog.py`
- [X] T013 [US1] Acrescentar os 5 feitiços (`card_id` 1001–1005) com o efeito da tabela *Efeitos do MVP* e a descrição reescrita para "vida da unidade" e "Nexus" — nunca "defesa" — em `server/apps/game/cards/mvp_catalog.py` (depende de T004, T012)
- [X] T014 [US1] Escrever a fábrica `mvp_catalog() -> CardCatalog` em `server/apps/game/cards/mvp_catalog.py` (depende de T013)
- [X] T015 [US1] Testar que buscar um `card_id` de unidade e um de feitiço devolve todos os campos esperados em `server/apps/game/tests/test_card_catalog.py` (depende de T011, T014)
- [X] T016 [US1] Testar que `card_id` desconhecido levanta `UnknownCardError` com o identificador pedido no texto em `server/apps/game/tests/test_card_catalog.py` (depende de T015)
- [X] T017 [US1] Testar que escrever em uma carta devolvida levanta `FrozenInstanceError` e que a consulta seguinte traz o valor original em `server/apps/game/tests/test_card_catalog.py` (depende de T016)
- [X] T018 [P] [US1] Conferir as 29 cartas campo a campo contra o apêndice *Dados de Origem* e conferir as faixas — 24 unidades em 1–1000, 5 feitiços em 1001+ — em `server/apps/game/tests/test_mvp_catalog.py` (depende de T014)

**Checkpoint**: o catálogo do MVP existe e responde por identificador. É o MVP.

---

## Phase 4: User Story 2 - Ler o efeito estruturado de um feitiço (Priority: P2)

**Goal**: o motor decide a legalidade de uma jogada de feitiço lendo só campos.

**Independent Test**: para os 5 feitiços, ler `requires_target`, `target_kind` e
`duration` e comparar com a tabela da spec, sem tocar em `description`.

**Nota sobre o tamanho desta fase**: os tipos de efeito nascem na Fase 2 e são
ligados às cartas em T013, porque `Spell` não existe sem `effect`. O que sobra
aqui é a superfície que o motor consome e a prova de que ela basta — que é
exatamente o valor da story.

- [X] T019 [US2] Acrescentar a propriedade derivada `requires_target` (`target_kind is not TargetKind.NONE`) aos efeitos em `server/apps/game/cards/effects.py` — derivada, não campo, para não existir efeito com `requires_target=True` e `target_kind=NONE` (depende de T004)
- [X] T020 [P] [US2] Testar que os 5 efeitos batem com a tabela *Efeitos do MVP* — classe, números, `target_kind` e `duration` — em `server/apps/game/tests/test_spell_effects.py` (depende de T014, T019)
- [X] T021 [US2] Testar `requires_target` nos dois sentidos: `True` para SOMEONE'S SHIELD, MAGIC BARRIER e SUMMONED AX, `False` para SACRIFICIAL FIRE e LIFE POTION, em `server/apps/game/tests/test_spell_effects.py` (depende de T020)
- [X] T022 [US2] Testar que duas leituras seguidas das propriedades de alvo dão o mesmo resultado — a validação na jogada e a revalidação na pilha veem o mesmo — em `server/apps/game/tests/test_spell_effects.py` (depende de T021)

**Checkpoint**: o motor de regras tem tudo de que precisa sobre feitiço sem ler
uma linha de português.

---

## Phase 5: User Story 3 - Listar o catálogo (Priority: P3)

**Goal**: listar tudo, só unidades ou só feitiços.

**Independent Test**: contar 29, 24 e 5; e listar feitiços em um catálogo sem
feitiço e receber tupla vazia.

- [X] T023 [US3] Implementar `FrozenCardCatalog.all_cards()` devolvendo tupla ordenada por `card_id` em `server/apps/game/cards/catalog.py` (depende de T008)
- [X] T024 [US3] Implementar `FrozenCardCatalog.units()` e `spells()` filtrando por `card_type` — nunca comparando `card_id` com a faixa, que FR-005 proíbe — em `server/apps/game/cards/catalog.py` (depende de T023)
- [X] T025 [P] [US3] Testar as contagens 29 / 24 / 5 e que nenhum feitiço aparece em `units()` nem unidade em `spells()` em `server/apps/game/tests/test_card_listing.py` (depende de T014, T024)
- [X] T026 [US3] Testar que um catálogo montado só com unidades devolve tupla vazia em `spells()`, sem levantar, em `server/apps/game/tests/test_card_listing.py` (depende de T025)

**Checkpoint**: qualquer superfície que mostre cartas ao jogador tem de onde
tirar a lista.

---

## Phase 6: User Story 4 - Validar um deck (Priority: P4)

**Goal**: aceitar um deck de 40 ou recusar nomeando o problema concreto.

**Independent Test**: um deck válido passa; cada defeito isolado produz uma
mensagem que cita o valor ofensor; um deck com vários defeitos relata todos.

- [X] T027 [P] [US4] Definir `DECK_SIZE = 40`, `MAX_COPIES_PER_CARD = 3` e o alias `Deck = Sequence[CardId]` em `server/apps/game/cards/deck_rules.py`
- [X] T028 [US4] Definir as dataclasses congeladas `WrongDeckSize`, `TooManyCopies` e `UnknownDeckCard`, cada uma com uma propriedade `message` que inclui o valor ofensor, e a união `DeckProblem` em `server/apps/game/cards/deck_rules.py` (depende de T027)
- [X] T029 [US4] Implementar `deck_problems(deck, catalog)` devolvendo todos os problemas em uma passada — tupla vazia quando o deck é válido, nunca levantando por deck ruim — em `server/apps/game/cards/deck_rules.py` (depende de T011, T028)
- [X] T030 [US4] Implementar `InvalidDeckError`, guardando `problems`, e `ensure_valid_deck(deck, catalog)` em `server/apps/game/cards/deck_rules.py` (depende de T029)
- [X] T031 [P] [US4] Testar que um deck de 40 com no máximo 3 cópias por `card_id` devolve tupla vazia em `server/apps/game/tests/test_deck_rules.py` (depende de T029)
- [X] T032 [US4] Testar que um deck de 39 produz `WrongDeckSize` com `39` e `40` na mensagem em `server/apps/game/tests/test_deck_rules.py` (depende de T031)
- [X] T033 [US4] Testar que 4 cópias do mesmo `card_id` produzem `TooManyCopies` com o identificador e a contagem na mensagem em `server/apps/game/tests/test_deck_rules.py` (depende de T032)
- [X] T034 [US4] Testar que um `card_id` inexistente produz `UnknownDeckCard` com o identificador na mensagem em `server/apps/game/tests/test_deck_rules.py` (depende de T033)
- [X] T035 [US4] Testar que um deck que viola mais de uma regra ao mesmo tempo relata todos os problemas, não só o primeiro, em `server/apps/game/tests/test_deck_rules.py` (depende de T034)
- [X] T036 [US4] Testar que `ensure_valid_deck` retorna em silêncio para deck válido e levanta `InvalidDeckError` com todos os problemas em `.problems` para deck ruim, em `server/apps/game/tests/test_deck_rules.py` (depende de T035)

**Checkpoint**: as quatro stories estão de pé. A feature está completa.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T037 Fechar a superfície pública com `__all__` explícito em `server/apps/game/cards/__init__.py` — `strict` liga `no_implicit_reexport`, então sem isso nenhum consumidor importa do pacote (depende de T030)
- [X] T038 [P] Revisar docstring das funções e classes públicas: intenção mais um exemplo de uso, no formato que `match/store.py` e `matchmaking/queue.py` já usam
- [X] T039 [P] Registrar em `C:/Users/gabri/Obsidian/Projetos/Anathema/Backend/TODO.md` que `apps/game/match/models.py` deve trocar `CardId = str` por um import de `apps.game.cards.card` quando o motor consumir o catálogo — decisão adiada, não bug solto
- [X] T040 Rodar `black` — o maintainer autorizou instalar a ferramenta, então em vez de só o pacote novo o formatador rodou em `server/` inteiro: `black==26.5.1` fixado em `server/requirements.txt`, 27 arquivos reformatados, `black --check server/` limpo. `mypy` e `pytest` conferidos depois, sem mudança de resultado
- [X] T041 Rodar `cd server && mypy` e fechar tudo sem acrescentar relaxação em `mypy.ini`
- [X] T042 Rodar `cd server && pytest` — a suíte inteira, não só os testes novos
- [X] T043 Percorrer os 10 cenários de [quickstart.md](./quickstart.md) e conferir cada resultado esperado

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependência
- **Foundational (Fase 2)**: depende da Fase 1 — **bloqueia todas as stories**
- **US1 (Fase 3)**: depende da Fase 2
- **US2 (Fase 4)**: depende da Fase 2 e de T014 (precisa dos feitiços reais)
- **US3 (Fase 5)**: depende da Fase 2 e de T014 (precisa das 29 cartas para as contagens)
- **US4 (Fase 6)**: depende da Fase 2 e de T011 (`card()` é como o deck descobre carta inexistente)
- **Polish (Fase 7)**: depende de todas as stories desejadas

### User Story Dependencies

As quatro stories dependem do catálogo do MVP existir (T014), o que faz de US1 o
tronco. É consequência do domínio, não do desenho: US2 fala dos 5 feitiços
reais, US3 conta 29 cartas reais, US4 valida contra o catálogo real. Depois de
T014, as três seguintes não dependem uma da outra e podem ser feitas em qualquer
ordem ou em paralelo.

### Within Each User Story

- Implementação antes do teste que a exerce
- Testes no mesmo arquivo rodam em sequência — `test_card_catalog.py`,
  `test_spell_effects.py`, `test_deck_rules.py` e `test_card_listing.py` cada um
  concentra uma story, então o conflito é só interno
- Story fechada antes de passar para a próxima prioridade

### Parallel Opportunities

- **Fase 2**: T002, T003, T006 são três arquivos diferentes e abrem juntos. T009 abre assim que T007 fecha.
- **Fase 3**: T012 (dados) é independente de T011 (método `card()`) — arquivos diferentes. T018 abre junto com T015 assim que T014 fecha.
- **Depois de T014**: US2, US3 e US4 abrem em paralelo, uma por pessoa.
- **Fase 7**: T038 e T039 são independentes entre si e do resto.

---

## Parallel Example: Fase 2

```bash
# Três arquivos diferentes, nenhum depende do outro:
Task: "T002 CardId, CardType e faixas em server/apps/game/cards/card.py"
Task: "T003 TargetKind e EffectDuration em server/apps/game/cards/effects.py"
Task: "T006 hierarquia de exceções em server/apps/game/cards/catalog.py"
```

## Parallel Example: depois do MVP

```bash
# Com T014 fechado, as três stories restantes não se tocam:
Task: "Fase 4 (US2) — efeitos: T019 a T022"
Task: "Fase 5 (US3) — listagem: T023 a T026"
Task: "Fase 6 (US4) — deck: T027 a T036"
```

---

## Implementation Strategy

### MVP First (US1)

1. Fase 1 — criar o pacote
2. Fase 2 — tipos e catálogo (**bloqueia tudo**)
3. Fase 3 — US1
4. **PARAR E VALIDAR**: cenários 1, 2, 8 e 10 do quickstart
5. O motor de partida já consegue resolver `card_id` em carta

### Incremental Delivery

1. Setup + Foundational → base pronta
2. + US1 → catálogo consultável (**MVP**)
3. + US2 → o motor decide feitiço sem ler português
4. + US3 → o cliente tem de onde tirar a coleção
5. + US4 → deck aceito ou recusado com mensagem específica

### Parallel Team Strategy

Com mais de uma pessoa, o gargalo é T014. Até lá vale uma pessoa só; depois,
US2, US3 e US4 saem em paralelo sem se tocarem — arquivos de implementação
distintos (`effects.py`, `catalog.py`, `deck_rules.py`) e arquivos de teste
distintos.

---

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- Cada tarefa nomeia o arquivo exato; nenhuma exige contexto além destes documentos
- Commit por tarefa ou por grupo lógico
- As três portas da constituição (`pytest`, `mypy`, `black`) valem por commit, não só na Fase 7 — T040 a T042 são a passada final, não a primeira
- Nenhum arquivo existente do repositório é alterado. A única escrita fora de `server/apps/game/` é T039, uma nota no vault
