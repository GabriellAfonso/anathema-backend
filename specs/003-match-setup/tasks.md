---

description: "Task list for 003-match-setup"
---

# Tasks: Setup de Partida

**Input**: Design documents from `specs/003-match-setup/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/match_setup.md](./contracts/match_setup.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio
V da constituição exige teste para toda função nova, e o SC-011 da spec põe
`pytest` como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem que as
dependências permitem. Onde a ordem diverge da numeração da spec, a razão está
escrita na fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US6)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Duas coisas nesta feature não podem ser aditivas: o `Match` ganha um campo
obrigatório, e o caminho de criação da partida troca de dono. As duas foram
isoladas em fases próprias e curtas.

- **Fases 2, 4, 5, 6, 7 e 8 são aditivas.** Arquivo novo, ninguém importa dele
  ainda, suíte verde do começo ao fim.
- **A Fase 3 cresce o estado.** Para não arrastar o vermelho, `Match.start`
  **sobrevive** a esta fase com a assinatura intacta: ela passa a cunhar uma
  semente internamente. Nenhum chamador muda de forma; o que muda é o que os
  testes existentes afirmam sobre a fase inicial e sobre o dono do token.
- **A Fase 9 faz a troca de verdade.** `Match.start` e `MatchStore.create`
  morrem, o matchmaking passa a chamar `start_match`, e os fakes acompanham.

A suíte fica verde em **todo checkpoint de fase**. Dentro da Fase 3 e da Fase 9
ela passa por vermelho entre tarefas, e as duas são curtas de propósito.

Consequência prática: **não pare entre a Fase 8 e a Fase 9**. Parar ali deixa
dois caminhos de criação de partida no repositório, um deles produzindo a
partida não jogável que esta feature existe para matar.

### Por que US4 vem depois de US2, e US3 depois das duas

`record_mulligan` (US2) termina chamando `finish_setup` (US4) quando o segundo
jogador responde. A Fase 5 entrega o mulligan sem essa cauda — testável com um
jogador só respondendo — e a Fase 6 acrescenta a cauda junto com o sorteio.

US3 (a espera simultânea) precisa do `mutate` do store, e o `mutate` só tem o
que provar depois que existe uma mutação real para disputar. Por isso ela fecha
o trio, na Fase 7.

---

## Phase 1: Setup

**Purpose**: linha de base e esqueleto de arquivos, para que as fases seguintes
sejam edição pura e o `[P]` seja seguro.

- [X] T001 Rodar as três portas e registrar a linha de base verde: `cd server && pytest`, `cd server && mypy`, `black --check server/`
- [X] T002 Criar o módulo vazio `server/apps/game/randomness.py` e o pacote vazio `server/apps/game/engine/` com `__init__.py`, `card_draw.py`, `match_setup.py` e `mulligan.py`
- [X] T003 [P] Criar o módulo vazio `server/apps/game/cards/starter_deck.py`

---

## Phase 2: Foundational A — aleatoriedade e movimento de compra

**Purpose**: os tipos folha que US1, US2, US4 e US5 consomem. Tudo em arquivo
novo; nada aqui é importado por código existente, então a suíte continua verde.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase e da Fase 3 fecharem.

- [X] T004 Implementar `RandomSeed`, `Roll` e `new_random_seed()` em `server/apps/game/randomness.py` — `RandomSeed` é `NewType` sobre `str`, `Roll` é dataclass congelada `(seed, ordinal)`, e a semente vem de `secrets.token_hex(16)` (research.md D2)
- [X] T005 Implementar o `Protocol` `RandomSource` em `server/apps/game/randomness.py` com `shuffled(items, roll)` e `choose(options, roll)`, sobre um `TypeVar` de módulo
- [X] T006 Implementar `SeededRandomSource` em `server/apps/game/randomness.py` sobre `random.Random(f"{roll.seed}:{roll.ordinal}")`, um gerador por chamada e nenhum estado entre chamadas — este é o único ponto do projeto que importa `random`
- [X] T007 [P] Criar `ScriptedRandomSource` em `server/apps/game/tests/fake_random_source.py`, com a asserção estática de conformidade de `Protocol` no formato de `fake_card_catalog.py` (e o comentário que manda não apagá-la)
- [X] T008 [P] Implementar `draw_from_deck_top(player)` e `EmptyDeckError` em `server/apps/game/engine/card_draw.py` — tira `deck[0]`, põe no fim da mão, devolve a carta; o teto de mão e o reset de deck da §9 ficam **em volta**, não dentro (research.md D7)
- [X] T009 [P] Implementar `starter_deck(catalog)` em `server/apps/game/cards/starter_deck.py`, derivando 40 identificadores do catálogo injetado, com docstring dizendo que é andaime e qual feature o substitui (research.md D9)
- [X] T010 [P] Exportar `starter_deck` em `server/apps/game/cards/__init__.py`, na lista `__all__`
- [X] T011 Exportar `draw_from_deck_top` e `EmptyDeckError` em `server/apps/game/engine/__init__.py`, com `__all__` explícito
- [X] T012 [P] Escrever `server/apps/game/tests/test_card_draw.py`: a carta sai do topo, entra no fim da mão, mantém o identificador, e deck vazio levanta citando o `user_id`
- [X] T013 [P] Escrever `server/apps/game/tests/test_starter_deck.py`: `deck_problems(starter_deck(catalog), catalog)` é vazio, e o deck tem 40 cartas

**Checkpoint**: `pytest`, `mypy` e `black --check` limpos. Nada existente mudou.

---

## Phase 3: Foundational B — o estado cresce

**Purpose**: os três campos novos, a fase nova e os dois campos que ficam
opcionais. Serve US1, US3 e US5 igualmente, por isso não é fase de história.

**⚠️ Janela vermelha declarada**: entre T014 e T023 a suíte fica vermelha.
`Match.start` **não é removida aqui** — ela passa a cunhar a semente
internamente e mantém a assinatura, para que nenhum chamador precise mudar de
forma antes da Fase 9.

- [X] T014 Acrescentar `MULLIGAN = "mulligan"` a `MatchPhase` em `server/apps/game/match/match_state.py` e reescrever o docstring do enum: a §2 lista cinco porque descreve o ciclo da rodada, e o setup acontece antes da primeira (FR-025)
- [X] T015 Acrescentar `random_seed: RandomSeed` (obrigatório) e `next_roll_ordinal: int = 1` ao `Match` em `server/apps/game/match/match_state.py`
- [X] T016 Implementar `Match.mint_roll()` em `server/apps/game/match/match_state.py`, no formato de `mint_card_instance_id` — único ponto que produz um `Roll`
- [X] T017 Trocar `token_holder_user_id` e `priority_user_id` para `int | None`, padrão `None`, e o padrão de `phase` para `MatchPhase.MULLIGAN`, em `server/apps/game/match/match_state.py` (research.md D4, D5)
- [X] T018 Ajustar `Match.start` em `server/apps/game/match/match_state.py` para cunhar a própria semente e deixar dono do token e prioridade em `None` — assinatura intacta, e um comentário registrando que o método morre na Fase 9
- [X] T019 [P] Acrescentar `mulligan_taken: bool = False` a `PlayerState` em `server/apps/game/match/player_state.py`
- [X] T020 Implementar a propriedade derivada `Match.awaiting_mulligan_user_ids` em `server/apps/game/match/match_state.py`, sobre `mulligan_taken`, nunca sobre um campo gravado (research.md D3)
- [X] T021 [P] Acrescentar `mulligan_taken` a `PlayerDocument`, e `random_seed: str` e `next_roll_ordinal: int` a `MatchDocument`, afrouxando os dois `user_id` de token e prioridade para `int | None`, em `server/apps/game/match/documents.py`
- [X] T022 Levar e trazer os três campos novos em `server/apps/game/match/serialization.py`, reembrulhando a semente em `RandomSeed` na volta
- [X] T023 [P] Afrouxar `token_holder_user_id` e `priority_user_id` para `int | None` no `PlayerView` de `server/apps/game/match/player_view.py`
- [X] T024 Atualizar `server/apps/game/tests/fake_match_state.py` para os campos novos, mantendo o docstring que explica por que ele monta zonas na mão
- [X] T025 Atualizar as asserções que afirmavam o comportamento antigo: `test_match_state.py` (fase inicial e dono do token), `test_match_serialization.py` (os três campos novos na ida e volta) e `test_player_view.py`, em `server/apps/game/tests/`
- [X] T026 Atualizar `server/apps/game/tests/test_match_store.py` onde ele afirma que a partida criada nasce em `UPKEEP`

**Checkpoint**: `pytest`, `mypy` e `black --check` limpos de novo. O estado
cabe o setup; ninguém o preenche ainda.

---

## Phase 4: User Story 1 — Nascer uma partida com os dois decks prontos (P1) 🎯 MVP

**Goal**: dois decks válidos e uma semente produzem uma partida com os dois
decks embaralhados, 4 cartas na mão de cada um, Nexus 20, energia zerada e 80
identificadores distintos. Deck ruim não vira partida.

**Independent Test**: chamar `start_match` com dois decks válidos e conferir
campo a campo; depois com um deck de 39 cartas e conferir que a recusa nomeia
o problema e nada é devolvido.

### Testes

- [X] T027 [P] [US1] Escrever `server/apps/game/tests/test_match_setup.py` com os casos de criação: 36/4 nos dois lados, Nexus 20, energia 0/0, fase `MULLIGAN`, dono do token `None`, espera com os dois `user_id`
- [X] T028 [P] [US1] Acrescentar a `server/apps/game/tests/test_match_setup.py` os casos de identidade: três cópias do mesmo `card_id` viram três cartas distintas, e os 80 identificadores dos dois lados não repetem
- [X] T029 [P] [US1] Acrescentar a `server/apps/game/tests/test_match_setup.py` as três recusas de deck (tamanho, cópias, carta fora do catálogo), o caso de um lado só inválido, e a prova de que a mensagem nomeia todos os problemas de uma vez

### Implementação

- [X] T030 [US1] Implementar `MatchEntry` em `server/apps/game/engine/match_setup.py` — dataclass congelada `(profile, deck)`, para que perfil e deck não possam ser trocados de par
- [X] T031 [US1] Implementar `InvalidPlayerDeckError` em `server/apps/game/engine/match_setup.py`, envolvendo `deck_problems()` da feature 001 e acrescentando de quem era o deck (research.md D10)
- [X] T032 [US1] Implementar a validação dos dois decks em `server/apps/game/engine/match_setup.py`, antes de qualquer materialização ou gravação (FR-002, FR-005)
- [X] T033 [US1] Implementar a materialização do deck em `server/apps/game/engine/match_setup.py`: cada `card_id` vira um `MatchCard` com identidade cunhada pela partida
- [X] T034 [US1] Implementar `start_match(first, second, *, catalog, randomness, seed)` em `server/apps/game/engine/match_setup.py`: valida, monta o `Match`, materializa, embaralha com `mint_roll()`, compra 4 com `draw_from_deck_top`, deixa em `MULLIGAN`
- [X] T035 [US1] Exportar `MatchEntry`, `start_match` e `InvalidPlayerDeckError` em `server/apps/game/engine/__init__.py`

**Checkpoint**: `start_match` produz a partida da §3 até a espera do mulligan.
`Match.start` continua de pé, e ninguém chama `start_match` ainda.

---

## Phase 5: User Story 2 — Trocar cartas no mulligan, na ordem que a regra exige (P1)

**Goal**: cada jogador troca de 0 a 4 cartas, na ordem (a) sair da mão, (b)
comprar a reposição, (c) devolver ao deck, (d) reembaralhar — e uma carta
descartada não pode voltar na compra.

**Independent Test**: com uma fonte controlada, devolver cartas conhecidas e
conferir por identificador que nenhuma delas está entre as compradas, e que
todas voltaram ao deck com o mesmo identificador.

**Nota**: `record_mulligan` fica aqui sem a cauda que fecha o setup. A Fase 6
acrescenta a chamada a `finish_setup`.

### Testes

- [X] T036 [P] [US2] Escrever `server/apps/game/tests/test_mulligan.py` com o caso central: nenhuma das cartas devolvidas aparece na reposição, e todas estão no deck com o identificador que já tinham
- [X] T037 [P] [US2] Acrescentar a `server/apps/game/tests/test_mulligan.py` as cinco quantidades (0, 1, 2, 3 e 4), conferindo em todas que a mão volta a 4 e o deck a 36
- [X] T038 [P] [US2] Acrescentar a `server/apps/game/tests/test_mulligan.py` a prova de que `next_card_instance_id` não avança no mulligan — a carta devolvida é a mesma, não uma nova (FR-018)
- [X] T039 [P] [US2] Acrescentar a `server/apps/game/tests/test_mulligan.py` as quatro recusas — `user_id` de fora, mulligan repetido, carta fora da mão, identificador repetido na seleção — cada uma conferindo que mão, deck e `mulligan_taken` ficaram intactos (FR-023)

### Implementação

- [X] T040 [US2] Implementar `MulliganAlreadyTakenError` e `CardNotInHandError` em `server/apps/game/engine/mulligan.py`, cada uma citando o valor ofensor e a forma esperada
- [X] T041 [US2] Implementar a validação da seleção em `server/apps/game/engine/mulligan.py`: resolve todos os identificadores contra a mão antes de mutar qualquer coisa, consumindo a mão candidata para que o repetido caia sozinho (research.md D10)
- [X] T042 [US2] Implementar os quatro movimentos do mulligan em `server/apps/game/engine/mulligan.py`, nesta ordem e como funções próprias: separar, comprar, devolver, reembaralhar com `mint_roll()`
- [X] T043 [US2] Implementar `record_mulligan(match, user_id, selection, *, randomness)` em `server/apps/game/engine/mulligan.py`, reusando `match.player(user_id)` para a recusa de quem não joga e marcando `mulligan_taken`
- [X] T044 [US2] Exportar `record_mulligan`, `MulliganAlreadyTakenError` e `CardNotInHandError` em `server/apps/game/engine/__init__.py`

**Checkpoint**: o mulligan de um jogador funciona e é recusável. O setup ainda
não fecha.

---

## Phase 6: User Story 4 — Sortear o token e compensar quem não o recebeu (P1)

**Goal**: com os dois mulligans registrados, sorteia-se o dono do token, o
outro compra 1, a prioridade nasce com o dono, e a partida fica posicionada
para o Upkeep da Rodada 1.

**Independent Test**: com uma fonte que force cada um dos dois resultados,
conferir que a mão do dono tem 4, a do oponente tem 5, e a prioridade é do dono
nos dois casos.

### Testes

- [X] T045 [P] [US4] Acrescentar a `server/apps/game/tests/test_match_setup.py` os casos do sorteio: exatamente um dono, mão 4/5 conforme o token, prioridade igual ao dono, e os dois resultados do sorteio trocando de lado juntos
- [X] T046 [P] [US4] Acrescentar a `server/apps/game/tests/test_match_setup.py` o estado final completo: rodada 1, token não consumido, passes 0, pilha vazia, bancos e cemitérios vazios, energia 0/0 dos dois lados (FR-012, FR-011)
- [X] T047 [P] [US4] Acrescentar a `server/apps/game/tests/test_mulligan.py` a prova de que o setup **não** avança com um mulligan só: dono do token continua `None` e ninguém comprou a quinta carta (FR-027)

### Implementação

- [X] T048 [US4] Implementar `finish_setup(match, *, randomness)` em `server/apps/game/engine/match_setup.py`: sorteia o dono com `choose` e `mint_roll()`, compra 1 para o outro, iguala a prioridade ao dono e põe a fase em `UPKEEP`
- [X] T049 [US4] Fazer `finish_setup` em `server/apps/game/engine/match_setup.py` não fazer nada enquanto `awaiting_mulligan_user_ids` não for vazia, e mover para lá a intenção do comentário de `Match.start` sobre quem sorteia o dono do token (plan.md, ⚠️ da checagem de constituição)
- [X] T050 [US4] Ligar a cauda em `server/apps/game/engine/mulligan.py`: `record_mulligan` chama `finish_setup` depois de marcar `mulligan_taken`
- [X] T051 [US4] Exportar `finish_setup` em `server/apps/game/engine/__init__.py`
- [X] T052 [P] [US4] Criar `server/apps/game/tests/fake_setup.py` com partidas já passadas pelo setup, para os testes das fases seguintes não repetirem a montagem

**Checkpoint**: dois decks e uma semente produzem, ponta a ponta, uma partida
posicionada para o primeiro Upkeep.

---

## Phase 7: User Story 3 — Esperar os dois jogadores sem travar a partida (P1)

**Goal**: a espera vive no estado gravado, sobrevive à ida e volta pelo Redis, e
duas respostas concorrentes de workers diferentes não podem perder uma à outra.

**Independent Test**: gravar com um mulligan só registrado, recarregar em outra
instância de store, conferir que a espera do outro continua lá; e disparar os
dois mulligans em paralelo contra o Redis de verdade, conferindo que os dois
ficam registrados.

### Testes

- [X] T053 [P] [US3] Acrescentar a `server/apps/game/tests/test_match_serialization.py` a ida e volta com o mulligan pendente: fase, `mulligan_taken` dos dois lados, mãos, ordens de deck, semente e ordinal voltam iguais
- [X] T054 [P] [US3] Acrescentar a `server/apps/game/tests/test_match_store.py` o teste de concorrência do SC-010: dois `mutate` em `asyncio.gather`, os dois registrados, fase final `UPKEEP` e espera vazia
- [X] T055 [P] [US3] Acrescentar a `server/apps/game/tests/test_match_store.py` os casos de `mutate`: exceção levantada dentro de `change` não grava nada, e a versão avança a cada escrita

### Implementação

- [X] T056 [US3] Trocar a forma gravada em `server/apps/game/match/store.py` de string para hash de dois campos, `state` e `version`, ajustando `get` e `save` e mantendo o TTL de 6 horas (research.md D6)
- [X] T057 [US3] Escrever o script Lua de compare-and-swap em `server/apps/game/match/store.py`, no formato comentado de `PAIR_SCRIPT` em `matchmaking/queue.py`: grava só se a versão bater
- [X] T058 [US3] Implementar `MatchStore.mutate(match_id, change)` e `ConcurrentMatchWriteError` em `server/apps/game/match/store.py`, com releitura e teto de tentativas, e exceção de dentro de `change` abortando sem gravar
- [X] T059 [US3] Reescrever o comentário de topo de `server/apps/game/match/store.py` que diz não existir caminho de mutação — ele deixa de ser verdade aqui, e a razão de o CAS existir toma o lugar dele; deixar explícito que `version` é versão de escrita, não de esquema
- [X] T060 [US3] Acrescentar `mutate` a `server/apps/game/tests/fake_match_store.py`, mantendo a mesma superfície da `MatchStore`

**Checkpoint**: a partida atravessa o Redis no meio do setup, e o mulligan
simultâneo é seguro entre workers.

---

## Phase 8: User Story 5 — Repetir o mesmo setup duas vezes (P1)

**Goal**: com a mesma semente, os mesmos decks, as mesmas escolhas e a mesma
ordem de chegada, o setup produz exatamente a mesma partida — inclusive depois
de a partida ir ao Redis e voltar entre os dois mulligans.

**Independent Test**: rodar o setup inteiro duas vezes e comparar os dois
`Match` campo a campo.

- [X] T061 [P] [US5] Escrever em `server/apps/game/tests/test_setup_randomness.py` os testes de `SeededRandomSource`: o mesmo `Roll` dá o mesmo resultado em instâncias diferentes, `shuffled` é permutação exata, e `choose` de sequência vazia levanta
- [X] T062 [P] [US5] Acrescentar a `server/apps/game/tests/test_setup_randomness.py` o teste do FR-038: a mesma semente e as mesmas entradas produzem dois `Match` iguais; sementes diferentes produzem partidas diferentes
- [X] T063 [P] [US5] Acrescentar a `server/apps/game/tests/test_setup_randomness.py` o teste do SC-009: gravar depois do primeiro mulligan, recarregar por outra instância de store e mandar o segundo produz a mesma partida que o setup que nunca saiu da memória
- [X] T064 [P] [US5] Acrescentar a `server/apps/game/tests/test_setup_randomness.py` a prova de que trocar **só** a ordem de chegada muda a partida — comportamento definido, não corrida (FR-042, *Assumptions* da spec)
- [X] T065 [US5] Conferir por inspeção que `server/apps/game/randomness.py` é o único arquivo de `server/apps/` que importa `random`, e registrar a checagem no docstring do módulo (SC-008)

**Checkpoint**: o resto do motor pode ser testado sobre partidas repetíveis.

---

## Phase 9: User Story 6 — Não quebrar quem já cria e lê a partida (P2)

**Goal**: o matchmaking passa a criar a partida pelo setup de verdade, e os dois
caminhos antigos morrem. É aqui que a feature substitui, em vez de acrescentar.

**Independent Test**: parear dois jogadores pelo caminho existente, gravar,
reler e conferir que a partida volta com deck embaralhado, mãos de 4 e a espera
do mulligan intactos, e que o gate de participante continua respondendo igual.

**⚠️ Janela vermelha declarada**: entre T066 e T071 a suíte fica vermelha.

- [X] T066 [US6] Remover `Match.start` de `server/apps/game/match/match_state.py` e o docstring que a cita em `server/apps/game/match/__init__.py`
- [X] T067 [US6] Remover `MatchStore.create` de `server/apps/game/match/store.py`, deixando o store com `get`, `save` e `mutate` — três operações, todas sobre bytes
- [X] T068 [US6] Remover `create` de `server/apps/game/tests/fake_match_store.py` e atualizar o docstring de exemplo
- [X] T069 [US6] Fazer `server/apps/game/tests/fake_match_state.py` construir o `Match` diretamente, com uma semente fixa de teste
- [X] T070 [US6] Reescrever `join_queue` em `server/apps/game/consumers/matchmaking.py` para montar dois `MatchEntry` com `starter_deck`, chamar `start_match` e gravar com `store.save`
- [X] T071 [US6] Injetar catálogo, fonte de aleatoriedade e semente em `server/apps/game/consumers/matchmaking.py` pelo construtor, com padrão de processo e sobrescrita nos testes, no formato de `queue` e `matches` que já existe ali
- [X] T072 [US6] Tratar `InvalidPlayerDeckError` em `server/apps/game/consumers/matchmaking.py` reusando o aviso de falha de pareamento, para que nenhuma partida meio-criada fique no Redis
- [X] T073 [P] [US6] Atualizar `server/apps/game/tests/test_match_store.py` nos oito pontos que chamavam `store.create`
- [X] T074 [P] [US6] Atualizar `server/apps/game/tests/test_match_consumer_access.py` para `start_match` mais `save`
- [X] T075 [US6] Acrescentar a `server/apps/game/tests/test_match_consumer_access.py` o caso do US6: a partida anunciada já tem deck embaralhado, mãos de 4 e fase `MULLIGAN`, e o gate continua recusando um terceiro `user_id` e um socket sem usuário autenticado

**Checkpoint**: existe um caminho de criação só, e ele produz uma partida
jogável.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: o que atravessa as histórias, e as três portas.

- [X] T076 [P] Revisar os docstrings públicos dos módulos novos: intenção mais um exemplo de uso, como a constituição exige, conferindo contra `contracts/match_setup.md`
- [X] T077 [P] Conferir que nenhum arquivo tocado passou de 500 linhas e nenhuma função passou de 20, com atenção a `store.py` e `mulligan.py`, os dois maiores previstos
- [X] T078 [P] Conferir que nenhum campo `id` nu entrou, e que nenhum objeto JSON do estado gravado é indexado por `user_id` — o teste `test_no_stored_json_object_is_keyed_by_user_id` já cobre o segundo
- [ ] T079 Rodar o roteiro de [quickstart.md](./quickstart.md), os sete cenários, e corrigir o que divergir — **pendente**: os cenários 5, 6 e 7 precisam de um Redis vivo (`docker compose up -d anathema_redis`)
- [ ] T080 Rodar as três portas: `cd server && pytest`, `cd server && mypy`, `black --check server/` — **pendente**: `mypy` e `black` limpos, `pytest` verde em 237 testes com `test_match_store.py` e `test_matchmaking_queue.py` fora; os dois precisam de um Redis vivo
- [X] T081 Conferir contra a spec que os 51 requisitos funcionais e os 11 critérios de sucesso têm onde ser verificados, e registrar em [checklists/requirements.md](./checklists/requirements.md) qualquer sobra

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1 (Setup)**: sem dependência.
- **Fase 2 (Foundational A)**: depende da Fase 1. Aditiva.
- **Fase 3 (Foundational B)**: depende da Fase 2 (precisa de `RandomSeed` e
  `Roll`). **Bloqueia todas as histórias.**
- **Fase 4 (US1)**: depende das Fases 2 e 3.
- **Fase 5 (US2)**: depende da Fase 4 — o mulligan opera sobre uma partida que
  `start_match` produziu.
- **Fase 6 (US4)**: depende da Fase 5 — `finish_setup` é a cauda de
  `record_mulligan`.
- **Fase 7 (US3)**: depende da Fase 6 — o teste de concorrência precisa de duas
  mutações reais para disputar.
- **Fase 8 (US5)**: depende da Fase 7 — o teste de recarga passa pelo store.
- **Fase 9 (US6)**: depende de todas as anteriores. **Não pule.**
- **Fase 10 (Polish)**: depende da Fase 9.

### User Story Dependencies

Ao contrário do caso comum, as histórias desta feature **não** são
independentes entre si: são os passos de um procedimento único, e a §3 os
numera em ordem. O que cada fase entrega é um incremento testável, não um
recorte entregável sozinho.

- **US1** é a única que se sustenta sozinha, e é o MVP.
- **US2** precisa de US1. **US4** precisa de US2. **US3** e **US5** provam
  propriedades do que US1, US2 e US4 construíram.
- **US6** é a troca, e por definição vem por último.

### Parallel Opportunities

- Fase 2: T007 a T013 são sete arquivos diferentes. T004, T005 e T006 tocam o
  mesmo arquivo e são sequenciais entre si.
- Fase 3: T019, T021 e T023 são arquivos diferentes; T014 a T018 e T020 tocam
  `match_state.py` e são sequenciais.
- Fases 4 a 8: todo bloco de testes marcado `[P]` pode ser escrito junto, antes
  da implementação da mesma fase.
- Fase 9: T073 e T074 são arquivos diferentes; o resto é sequencial porque a
  janela vermelha só fecha na ordem.
- Fase 10: T076, T077 e T078 são leituras independentes.

---

## Parallel Example: Fase 2

```bash
# Depois de T004-T006 (randomness.py fechado), sete arquivos ao mesmo tempo:
Task: "ScriptedRandomSource em server/apps/game/tests/fake_random_source.py"
Task: "draw_from_deck_top em server/apps/game/engine/card_draw.py"
Task: "starter_deck em server/apps/game/cards/starter_deck.py"
Task: "Exportar starter_deck em server/apps/game/cards/__init__.py"
Task: "test_card_draw.py em server/apps/game/tests/"
Task: "test_starter_deck.py em server/apps/game/tests/"
```

---

## Implementation Strategy

### MVP (US1)

1. Fase 1 — Setup
2. Fase 2 — Foundational A
3. Fase 3 — Foundational B (janela vermelha curta)
4. Fase 4 — US1
5. **PARE E VALIDE**: `start_match` produz a partida da §3 até a espera do
   mulligan, e deck ruim não vira partida.

Neste ponto a feature já entrega o cenário 1 do quickstart. O que falta é o
mulligan, o sorteio e a troca do caminho de criação.

### Entrega incremental

1. Fases 1 a 3 → o estado cabe o setup
2. Fase 4 (US1) → partida nasce embaralhada, com mão de 4
3. Fase 5 (US2) → o mulligan funciona, e a carta descartada não volta
4. Fase 6 (US4) → o setup fecha ponta a ponta
5. Fase 7 (US3) → sobrevive ao Redis e à concorrência
6. Fase 8 (US5) → é repetível
7. Fase 9 (US6) → o matchmaking passa a usá-lo, e o caminho antigo morre
8. Fase 10 → portas

### Estratégia com mais de uma pessoa

O caminho crítico é sequencial da Fase 3 à Fase 6. O que dá para paralelizar de
verdade:

- Enquanto alguém faz a Fase 3, outra pessoa fecha a Fase 2 e escreve os testes
  da Fase 4 (T027 a T029) contra o contrato, que já está escrito.
- A Fase 7 (store, CAS, Lua) é independente do motor depois da Fase 3, e pode
  correr em paralelo com as Fases 5 e 6 — só o teste de concorrência (T054)
  precisa esperar.

---

## Notes

- `[P]` = arquivos diferentes, sem dependência pendente
- Todo teste roda com `cd server && pytest`; nada de runner próprio
- I/O externo só com fake nomeado — `ScriptedRandomSource`, `FakeCardCatalog`,
  `FakeMatchStore`. Nenhum stub inline, nenhum `lambda` de aleatoriedade
- Commit por tarefa ou por grupo lógico; nunca no meio de uma janela vermelha
- Dois comentários existentes **mudam de verdade** e são reescritos, não
  apagados: o "valor de espera" de `Match.start` (T049) e o "não existe caminho
  de mutação" de `store.py` (T059). A constituição trata comentário perdido em
  refactor como perda de intenção
- Fora de escopo, e nenhuma tarefa acima os pressupõe: `handle_mulligan` no
  consumer, o Upkeep da §4, o teto de mão e o reset de deck da §9, e o timeout
  da §13
