---

description: "Task list for 011-deck-catalog-api"
---

# Tasks: Decks do jogador, e o catálogo servido ao cliente

**Input**: Design documents from `/specs/011-deck-catalog-api/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: incluídos e obrigatórios. Não é preferência desta feature — o princípio V da constituição exige teste para toda função nova, fake **nomeado** para toda I/O externa, e teste de regressão para todo bug. Os testes de cada história vêm antes da implementação dela.

**Organization**: tarefas agrupadas por história, na ordem de merge do plano — catálogo, modelo e validação, API de decks, isolamento, deck inicial, fila e socket, e a garantia do deck da entrada.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a história da spec a que a tarefa serve (US1…US7)
- Todo caminho de arquivo é relativo à raiz do repositório

## Path Conventions

Projeto Django único, sob `server/`:

- Código: `server/apps/game/`, `server/apps/players/`
- Testes: dentro do app — `server/apps/game/tests/`, `server/apps/players/tests/`
- Portas de qualidade: `cd server && pytest`, `cd server && mypy`, `cd server && black --check .`

---

## Phase 1: Setup

**Purpose**: partir de um baseline verde, para que toda falha seguinte seja desta feature.

- [X] T001 Rodar e registrar o baseline verde na branch `011-deck-catalog-api`: `cd server && pytest`, `cd server && mypy`, `cd server && black --check .`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a tabela do deck e o tradutor de problema, de que US3, US4, US5, US6 e US7 dependem.

**⚠️ Nota de escopo**: esta fase **não** bloqueia US1 nem US2. O catálogo pelo HTTP não toca o banco nem o deck, e a Phase 3 pode correr em paralelo com esta desde o início.

- [X] T002 [P] Criar o modelo `PlayerDeck` em `server/apps/players/models/deck.py`: FK `profile` para `PlayerProfile` com `on_delete=CASCADE` e `related_name="decks"`, `name` (`CharField(max_length=50)`), `card_ids` (`JSONField`), `created_at`/`updated_at`. Sem `unique_together` em `(profile, name)` — nome repetido é aceito (FR-019). Docstring dizendo por que a lista é `JSONField` e não tabela de junção (research D2)
- [X] T003 Reexportar os quatro modelos com `__all__` explícito em `server/apps/players/models/__init__.py` (hoje vazio), para que um modelo novo não dependa de alguém lembrar de importá-lo em `admin.py` (research D15)
- [X] T004 Gerar a migração com `cd server && python manage.py makemigrations players` e conferir que `server/apps/players/migrations/0002_playerdeck.py` traz só `CreateModel`, sem dado a migrar
- [X] T005 [P] Registrar `PlayerDeck` em `server/apps/players/admin.py`, no formato dos registros já existentes
- [X] T006 [P] Escrever `server/apps/players/tests/test_deck_model.py`: o deck guarda a lista com ordem e repetição intactas, `profile_id == user_id` (decisão 0001), e apagar o perfil apaga os decks dele
- [X] T007 [P] Criar `server/apps/players/services/deck_problem_payload.py`: traduzir a união `DeckProblem` da feature 001 para JSON com `match` + `assert_never`, nas três formas de [`data-model.md`](./data-model.md) (`wrong_deck_size`, `too_many_copies`, `unknown_card`), reusando `problem.message` como está
- [X] T008 [P] Escrever `server/apps/players/tests/test_deck_problem_payload.py`: uma asserção por forma, e um teste que falha se `DeckProblem` ganhar um braço sem tradução

**Checkpoint**: a tabela existe e um problema de deck já vira JSON. US3–US7 podem começar.

---

## Phase 3: User Story 1 - O cliente busca o catálogo e desenha qualquer carta (Priority: P1) 🎯 MVP

**Goal**: `GET game/cards/` serve as 29 cartas com tudo que o cliente precisa para desenhar: identificador, tipo, nome, custo, imagem, e ataque/vida para unidade, descrição para feitiço.

**Independent Test**: buscar o catálogo autenticado e conferir 29 cartas, 24 unidades com ataque e vida, 5 feitiços com descrição, resposta igual para dois usuários, e nenhum campo `id`.

### Tests for User Story 1

- [X] T009 [P] [US1] Escrever `server/apps/game/tests/test_card_payload.py`: os campos comuns de toda carta, ataque e vida só em unidade, descrição só em feitiço, e `card_id`/`card_type` no lugar de `id`/`type`. Usa `FakeCardCatalog` para os campos e `mvp_catalog()` para a contagem
- [X] T010 [P] [US1] Escrever `server/apps/game/tests/test_card_catalog_view.py`: `200` com 29 cartas ordenadas por `card_id`, 24 unidades e 5 feitiços, dois usuários recebem resposta idêntica campo a campo, sem `Authorization` responde `401`, e nenhuma chave `id` em nenhum objeto

### Implementation for User Story 1

- [X] T011 [US1] Criar `server/apps/game/card_payload.py`: uma função por tipo de carta e um despacho, montando os payloads de [`contracts/http_catalog.md`](./contracts/http_catalog.md). O catálogo entra por parâmetro; o payload da lista inteira é guardado com `functools.cache` (research D5)
- [X] T012 [US1] Criar `server/apps/game/card_catalog_view.py`: `APIView` com `IsAuthenticated`, `get` devolvendo `{"cards": [...]}` a partir de `card_payload`. Docstring com intenção e um exemplo
- [X] T013 [US1] Acrescentar `path("cards/", ...)` a `server/apps/game/urls.py`, de modo que a rota final seja `game/cards/`
- [X] T014 [US1] Rodar `cd server && pytest apps/game/tests/test_card_payload.py apps/game/tests/test_card_catalog_view.py`, `mypy` e `black`, e conferir o passo 1 de [`quickstart.md`](./quickstart.md) com `curl`

**Checkpoint**: o cliente já desenha qualquer carta. US1 é entregável sozinha.

---

## Phase 4: User Story 2 - O cliente sabe, antes de jogar, se o feitiço pede alvo e de qual lado (Priority: P1)

**Goal**: todo feitiço servido leva a forma estruturada do efeito — `requires_target`, `target_kind`, `duration`, `declaration_only` — com o mesmo texto que o motor usa.

**Independent Test**: para cada um dos 5 feitiços, ler a forma servida e conferir que ela bate com o que o motor aceita e recusa.

### Tests for User Story 2

- [X] T015 [P] [US2] Acrescentar a `server/apps/game/tests/test_card_payload.py` os testes da forma do efeito: os quatro campos presentes em todo feitiço, `requires_target` coerente com `target_kind`, e os valores servidos idênticos aos `.value` de `TargetKind` e `EffectDuration`
- [X] T016 [P] [US2] Escrever `server/apps/game/tests/test_effect_shape_matches_engine.py`: para cada feitiço do `mvp_catalog()`, a forma servida prevê o veredito do motor — feitiço `none` que recebe alvo é recusado com `spell_takes_no_target`, feitiço com `target_kind` que recebe o lado errado é recusado com `wrong_spell_target_side`, e `declaration_only` bate com `spell_only_in_declaration`

### Implementation for User Story 2

- [X] T017 [US2] Acrescentar o objeto `effect` ao payload de feitiço em `server/apps/game/card_payload.py`, lendo os quatro campos direto de `SpellEffectShape`, sem `match` sobre a união e sem expor `amount` (research D6)
- [X] T018 [US2] Rodar os testes das duas histórias do catálogo, `mypy` e `black`, e conferir o objeto `effect` na resposta real pelo passo 1 de [`quickstart.md`](./quickstart.md)

**Checkpoint**: a Parte 1 está inteira e pode ser mergeada sozinha, sem nada da Parte 2.

---

## Phase 5: User Story 3 - O jogador monta e guarda os próprios decks (Priority: P1)

**Goal**: listar, criar, renomear, trocar a lista e apagar os próprios decks, com validação no salvamento — sem rascunho.

**Independent Test**: criar dois decks, listar, renomear um, trocar as cartas do outro, tentar salvar 12 cartas e conferir a recusa, apagar o primeiro e conferir que restou um.

### Tests for User Story 3

- [X] T019 [P] [US3] Escrever `server/apps/players/tests/test_deck_validation.py`: nome vazio e só espaços recusados nomeando campo e valor; nome acima de 50 recusado; nome repetido **aceito**; as três regras delegadas a `deck_problems`; recusa com os três problemas de uma vez; teto de 20 recusando a criação com teto e contagem na mensagem. Usa `FakeCardCatalog`
- [X] T020 [P] [US3] Escrever `server/apps/players/tests/test_deck_api.py`: os cinco verbos de [`contracts/http_decks.md`](./contracts/http_decks.md), listagem vazia como `200`, `PATCH` com corpo vazio recusado, `PATCH` inválido deixando o deck guardado intacto, e nenhum campo `id` na resposta

### Implementation for User Story 3

- [X] T021 [P] [US3] Criar `server/apps/players/services/deck_validation.py`: `DECK_LIMIT_PER_PLAYER = 20`, a checagem de nome e a chamada a `deck_problems` da feature 001. O catálogo entra por parâmetro. Nenhuma das três regras é reescrita (FR-022)
- [X] T022 [P] [US3] Criar `server/apps/players/services/deck_queries.py` com a parte síncrona: o queryset dos decks de um dono e a busca de um deck do dono por `deck_id` — sempre `filter(profile=..., pk=...)`, nunca `get` seguido de checagem de posse (research D4)
- [X] T023 [US3] Criar `server/apps/players/services/deck_writes.py`: criar (com o teto), renomear, substituir a lista e apagar. Deck recusado não é salvo nem parcialmente
- [X] T024 [P] [US3] Criar `server/apps/players/deck_serializers.py`: leitura com `deck_id = IntegerField(source="pk", read_only=True)`, `name`, `card_ids`; escrita com `name` e `card_ids` opcionais no `PATCH`
- [X] T025 [US3] Criar `server/apps/players/deck_views.py`: uma view de coleção (`GET`, `POST`) e uma de item (`GET`, `PATCH`, `DELETE`), ambas com `IsAuthenticated`, partindo sempre do queryset do dono
- [X] T026 [US3] Traduzir as recusas nas views: nome inválido em `{"name": [...]}`, lista inválida em `{"deck_problems": [...]}` via `deck_problem_payload`, teto em `{"deck_limit": [...]}` — as formas de [`contracts/http_decks.md`](./contracts/http_decks.md)
- [X] T027 [US3] Acrescentar `decks/` e `decks/<int:deck_id>/` a `server/apps/players/urls.py`
- [X] T028 [US3] Conferir os limites da constituição em `server/apps/players/services/deck_validation.py`, `deck_queries.py`, `deck_writes.py`, `server/apps/players/deck_serializers.py` e `server/apps/players/deck_views.py`: funções de 4 a 20 linhas, arquivos abaixo de 500, docstring com intenção e exemplo nas funções públicas
- [X] T029 [US3] Rodar `cd server && pytest apps/players/`, `mypy`, `black`, e os passos 2, 3 e 4 de [`quickstart.md`](./quickstart.md)

**Checkpoint**: o construtor de deck funciona ponta a ponta pelo HTTP.

---

## Phase 6: User Story 4 - O deck de outro jogador não existe para mim (Priority: P1)

**Goal**: as cinco operações sobre deck alheio respondem exatamente o que responderiam sobre um deck inexistente.

**Independent Test**: com dois jogadores, pedir cada operação com o jogador B sobre um deck do jogador A e comparar a resposta, byte a byte, com a do mesmo pedido sobre um `deck_id` que não existe para ninguém.

### Tests for User Story 4

- [X] T030 [P] [US4] Escrever `server/apps/players/tests/test_deck_isolation.py`: `GET`, `PATCH`, `DELETE` sobre deck alheio devolvem `404` com **o mesmo corpo** do `404` de identificador inexistente; a listagem de B traz só os decks de B; o deck de A continua existindo e inalterado depois de cada tentativa; pedido sem autenticação é recusado antes de qualquer leitura
- [X] T031 [P] [US4] Escrever `server/apps/players/tests/test_deck_queries.py`: a busca por dono devolve `None` tanto para deck alheio quanto para inexistente, e o queryset do dono nunca inclui deck de outro

### Implementation for User Story 4

- [X] T032 [US4] Conferir em `server/apps/players/deck_views.py` e `server/apps/players/services/deck_queries.py` que não existe nenhum ramo que distinga "não é seu" de "não existe" — nenhum `PermissionDenied`, nenhum `get()` sem filtro de dono. Se houver, reescrever partindo do queryset do dono
- [X] T033 [US4] Rodar `cd server && pytest apps/players/tests/test_deck_isolation.py apps/players/tests/test_deck_queries.py` e o passo 5 de [`quickstart.md`](./quickstart.md)

**Checkpoint**: a fronteira de privacidade está fechada e testada.

---

## Phase 7: User Story 7 - Uma conta nova já nasce com um deck jogável (Priority: P2)

**Goal**: ao ter o perfil criado, o jogador ganha um deck inicial válido, editável e apagável como qualquer outro.

**Independent Test**: registrar uma conta, listar os decks e conferir que existe um com 40 cartas válidas; renomeá-lo e apagá-lo sem tratamento especial.

**Nota de ordem**: é P2, mas vem antes de US5 e US6 porque são três tarefas pequenas e sem elas todo teste manual da entrada na fila começa montando 40 cartas à mão. É a ordem de merge do plano.

### Tests for User Story 7

- [X] T034 [P] [US7] Escrever `server/apps/players/tests/test_starter_deck_creation.py`: conta registrada nasce com exatamente um deck válido; o deck inicial é renomeável, editável e apagável; uma falha na criação do deck desfaz perfil, stats e settings junto (FR-042); conta sem perfil não ganha deck (FR-043)

### Implementation for User Story 7

- [X] T035 [P] [US7] Criar `server/apps/players/services/starter_deck_creation.py`: cria o `PlayerDeck` inicial com nome `"Deck inicial"` e a lista de `starter_deck(catalog)`. O catálogo entra por parâmetro
- [X] T036 [US7] Acrescentar a criação do deck inicial a `server/apps/players/services/player_creation.py`, dentro da `@transaction.atomic` que já existe, e atualizar o docstring para dizer que o jogador nasce com perfil, stats, settings **e** deck
- [X] T037 [P] [US7] Reescrever o docstring de `server/apps/game/cards/starter_deck.py`: deixa de ser andaime do matchmaking e passa a ser o conteúdo do deck inicial. A função e o algoritmo não mudam (research D13)
- [X] T038 [US7] Rodar `cd server && pytest apps/players/` e o passo 2 de [`quickstart.md`](./quickstart.md) com uma conta recém-registrada

**Checkpoint**: nenhuma conta nasce sem poder jogar.

---

## Phase 8: User Story 5 - Entrar na fila exige dizer o deck, e ele é validado na hora (Priority: P1)

**Goal**: o cliente entra na fila dizendo com qual deck joga; deck ausente, alheio, inexistente ou inválido recusam a entrada, antes de o jogador ocupar lugar na fila.

**Independent Test**: mandar `join_queue` sem deck, com deck de outro, com deck inexistente e com deck inválido, conferindo em cada caso a recusa, o código, e que a fila continua vazia; depois entrar com deck válido e conferir que o par se fecha.

**⚠️ Esta é a única fase que muda comportamento existente.** Os testes de regressão do matchmaking, do setup e do relógio rodam com ela.

### Tests for User Story 5

- [X] T039 [P] [US5] Criar `server/apps/game/tests/fake_player_deck_source.py`: `FakePlayerDeckSource`, fake **nomeado** da porta `PlayerDeckSource`, devolvendo `None` para deck alheio e para inexistente, com a asserção estática de conformidade ao `Protocol` no rodapé, como `fake_card_catalog.py` já faz
- [X] T040 [P] [US5] Escrever `server/apps/game/tests/test_matchmaking_join.py`: as quatro recusas de [`contracts/matchmaking_messages.md`](./contracts/matchmaking_messages.md); `deck_not_found` com corpo **idêntico** para alheio e inexistente; `invalid_deck` levando `deck_problems` com todos os problemas; o socket continua aberto depois de cada recusa e aceita um `join_queue` seguinte; jogador recusado não ocupa lugar na fila; dois jogadores válidos fecham o par e recebem `match_found`
- [X] T041 [P] [US5] Ampliar `server/apps/game/tests/test_matchmaking_queue.py` para `QueueEntry`: a entrada sai do par com a lista intacta, a reentrada troca o deck sem duplicar o jogador, e as corridas concorrentes continuam pareando cada um exatamente uma vez

### Implementation for User Story 5

- [X] T042 [P] [US5] Criar `server/apps/game/protocol/matchmaking_refusals.py` com `DECK_NOT_SPECIFIED`, `DECK_NOT_FOUND` e `INVALID_DECK`, e reexportá-los em `server/apps/game/protocol/__init__.py` com `__all__` explícito
- [X] T043 [P] [US5] Dar a `send_refusal` um `**details` opcional em `server/apps/game/consumers/base.py`, sem mudar nenhum frame do socket de partida (a feature 009 não passa `details`)
- [X] T044 [US5] Reescrever `server/apps/game/matchmaking/queue.py`: `QueueEntry(user_id, deck)` congelada, o script de `join` com `LREM`/`RPUSH`/`HSET` e o `HMGET`/`HDEL` do par, o script de `leave` com `LREM`/`HDEL`, e a serialização JSON do deck dentro do módulo. A lista continua guardando só `user_id` — é o que faz o `LREM` da reentrada funcionar (research D10). Levantar com os dois `user_id` na mensagem se o hash devolver vazio para um dos pareados
- [X] T045 [US5] Acrescentar a `server/apps/players/services/deck_queries.py` o `Protocol` `PlayerDeckSource` e a implementação concreta com `database_sync_to_async`, devolvendo `Deck | None` — `None` para alheio e para inexistente, pelo mesmo filtro de dono
- [X] T046 [US5] Reescrever a entrada na fila em `server/apps/game/consumers/matchmaking.py`: `decks` entra por `__init__`/`as_asgi`; `on_connect` deixa de entrar na fila; `handle_join_queue` confere `deck_id`, busca o deck do dono, valida com `deck_problems` e **só então** chama `queue.join`. Nenhuma recusa depois da chamada à fila (FR-029)
- [X] T047 [US5] Remover `deck_for` de `server/apps/game/consumers/matchmaking.py` e passar os decks das duas `QueueEntry` a `MatchEntry` em `start_match_for`. O setup da §3 não muda
- [X] T048 [US5] Acrescentar log estruturado JSON a cada recusa de entrada na fila em `server/apps/game/consumers/matchmaking.py`, com `user_id`, `deck_id` e o código, no formato das recusas da feature 010
- [X] T049 [US5] Ajustar `server/apps/game/tests/test_matchmaking_clock.py` para o consumer com `decks=`, sem mudar o que o teste prova sobre o prazo do mulligan
- [X] T050 [US5] Rodar `cd server && pytest apps/game/tests/test_matchmaking_join.py apps/game/tests/test_matchmaking_queue.py apps/game/tests/test_matchmaking_clock.py apps/game/tests/test_match_setup.py apps/game/tests/test_full_match.py apps/game/tests/test_match_consumer_flow.py` e o passo 6 de [`quickstart.md`](./quickstart.md)

**Checkpoint**: entrar na fila exige deck, e o andaime saiu.

---

## Phase 9: User Story 6 - A partida usa o deck que foi validado, não o deck de agora (Priority: P1)

**Goal**: o que foi validado na entrada é o que a partida usa, mesmo que o deck seja editado ou apagado no instante seguinte.

**Independent Test**: entrar na fila com um deck válido, trocar todas as cartas dele (ou apagá-lo) antes de o par fechar, e conferir que a partida criada usa a lista validada na entrada.

### Tests for User Story 6

- [X] T051 [P] [US6] Escrever `server/apps/game/tests/test_queued_deck_is_frozen.py`: com a lista trocada entre o `join_queue` e o par, a partida nasce com a lista validada na entrada; com o deck apagado nesse intervalo, o par ainda fecha e a partida nasce com a mesma lista
- [X] T052 [P] [US6] Acrescentar a `server/apps/players/tests/test_deck_api.py` a regressão de partida em andamento: apagar o deck não muda nada do estado da partida gravada
- [X] T053 [P] [US6] Acrescentar a `server/apps/game/tests/test_matchmaking_queue.py` o teste de `leave`: sair da fila apaga a entrada inteira, e nenhum deck fica órfão no hash

### Implementation for User Story 6

- [X] T054 [US6] Conferir em `server/apps/game/consumers/matchmaking.py` que nada relê o deck depois do `queue.join` — o par vem das duas `QueueEntry`, e não de nova consulta ao banco (FR-031, FR-032). Corrigir se houver releitura
- [X] T055 [US6] Rodar `cd server && pytest apps/game/ apps/players/` e o passo 7 de [`quickstart.md`](./quickstart.md), que é o cenário que a feature existe para garantir

**Checkpoint**: as sete histórias estão entregues.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T056 [P] Conferir que nenhum payload da feature expõe campo `id`: varrer as respostas de `game/cards/` e `players/decks/` e os frames de `ws/matchmaking/` (princípio II da constituição)
- [X] T057 [P] Conferir que o andaime saiu: `cd server && grep -rn "deck_for" apps/game/consumers/` não devolve nada (passo 8 de [`quickstart.md`](./quickstart.md))
- [X] T058 [P] Conferir que `server/apps/game/cards/` não ganhou nenhuma importação de `apps.players` — o catálogo continua folha (research D1)
- [X] T059 Reler contra a constituição tudo que nasceu nesta feature em `server/apps/game/` e `server/apps/players/`: funções de 4 a 20 linhas, arquivos abaixo de 500 linhas, nomes específicos, mensagens de exceção com o valor ofensor e a forma esperada, docstring com intenção e exemplo
- [X] T060 Rodar as três portas de qualidade limpas: `cd server && pytest`, `cd server && mypy`, `cd server && black --check .`. Nenhuma relaxação nova em `server/mypy.ini`
- [ ] T061 Rodar [`quickstart.md`](./quickstart.md) do início ao fim, incluindo a lista de regressões que precisa continuar passando — **bloqueado nesta máquina**: o daemon do Docker não está de pé, `anathema_redis` não resolve e não há Redis local, então os passos 6 e 7 (socket de matchmaking) e os 59 testes que falam com Redis de verdade não têm como rodar. Os passos 1 a 5 e o 8 rodam; rodar o arquivo inteiro depois de `docker compose up`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependência.
- **Foundational (Phase 2)**: depende da Phase 1. Bloqueia US3, US4, US5, US6 e US7 — **não** bloqueia US1 nem US2.
- **US1 (Phase 3)** e **US2 (Phase 4)**: dependem só da Phase 1. US2 edita o mesmo `card_payload.py` que US1, então vem depois dela.
- **US3 (Phase 5)**: depende da Phase 2.
- **US4 (Phase 6)**: depende de US3 — é a mesma view e o mesmo queryset, auditados e testados.
- **US7 (Phase 7)**: depende da Phase 2. Independente de US3, US4, US5 e US6.
- **US5 (Phase 8)**: depende da Phase 2 (o modelo) e de US3 (a leitura por dono, T022). US7 antes dela é conveniência de teste, não dependência de código.
- **US6 (Phase 9)**: depende de US5 — prova a garantia que a `QueueEntry` de US5 dá.
- **Polish (Phase 10)**: depende de tudo que se pretende entregar.

### Paralelismo

- **Duas frentes desde o começo**: Phase 3 + Phase 4 (a Parte 1 inteira, catálogo) não tocam nenhum arquivo da Phase 2 em diante. Uma pessoa entrega a Parte 1 enquanto outra abre a Parte 2.
- Dentro da Phase 2: T002, T005, T006, T007 e T008 são `[P]`; T003 e T004 dependem de T002.
- Dentro de US3: T019 e T020 `[P]`; T021, T022 e T024 `[P]` entre si; T023 depende de T021 e T022; T025 depende de T023 e T024.
- Dentro de US5: T039, T040, T041 `[P]`; T042 e T043 `[P]`; T044, T045 e T046 tocam arquivos diferentes mas T046 depende dos três anteriores.
- Todo arquivo de teste novo é `[P]` em relação aos outros: são arquivos distintos.

---

## Parallel Example: User Story 5

```bash
# Os três arquivos de teste, juntos (arquivos distintos):
Task: "Criar FakePlayerDeckSource em server/apps/game/tests/fake_player_deck_source.py"
Task: "Escrever server/apps/game/tests/test_matchmaking_join.py"
Task: "Ampliar server/apps/game/tests/test_matchmaking_queue.py para QueueEntry"

# Os dois módulos de protocolo, juntos:
Task: "Criar server/apps/game/protocol/matchmaking_refusals.py"
Task: "Dar **details opcional a send_refusal em server/apps/game/consumers/base.py"
```

---

## Implementation Strategy

### MVP: a Parte 1 sozinha

1. Phase 1 (Setup)
2. Phase 3 (US1) + Phase 4 (US2)
3. **PARAR E VALIDAR**: o cliente desenha qualquer carta e sabe a mira de todo feitiço
4. Mergeável sozinha — não toca banco, fila, socket nem o deck

### Entrega incremental

1. Parte 1 → merge (US1, US2)
2. Phase 2 → tabela e tradutor de problema, nada exposto
3. US3 + US4 → o construtor de deck, com a fronteira de privacidade fechada → merge
4. US7 → nenhuma conta nasce sem poder jogar → merge
5. US5 + US6 → a entrada na fila exige deck, e o deck da entrada é o que a partida usa → merge
6. Phase 10 → portas de qualidade e quickstart inteiro

O passo 5 é o único que quebra o cliente atual: conectar deixa de entrar na fila. É quebra deliberada, registrada em [`contracts/matchmaking_messages.md`](./contracts/matchmaking_messages.md), e não há produção.

### Frente dupla

1. Pessoa A: Phase 1, depois Phase 3 e Phase 4 (a Parte 1 inteira)
2. Pessoa B: Phase 2, depois US3, US4 e US7
3. Quem terminar primeiro pega US5; US6 vem logo atrás, no mesmo par de arquivos

---

## Estado da execução — 2026-09-12

60 de 61 tarefas feitas. Portas de qualidade: `mypy` limpo (221 arquivos),
`black --check` limpo (222 arquivos), `pytest` com **998 passando, 12 skipped,
0 falhas**.

Os **59 erros** restantes do `pytest` são todos de conexão com o Redis: o
daemon do Docker não está de pé nesta máquina, `anathema_redis` não resolve, e
não há Redis local. 52 deles já erravam no baseline da T001, antes de qualquer
linha desta feature; os 7 novos são os testes de `QueueEntry` e do hash de
decks em `test_matchmaking_queue.py`.

**O que isso deixa sem prova nesta máquina**: os dois scripts Lua novos da
fila -- o `HSET`/`HMGET`/`HDEL` do par e o `LREM`/`HDEL` do `leave`. A lógica
do consumer em volta deles está coberta por `FakeMatchmakingQueue`, mas a
indivisibilidade e o formato no Redis só o Redis de verdade prova. Rodar
`docker compose up` e depois `cd server && pytest apps/game/tests/test_matchmaking_queue.py`
antes de considerar a US5 fechada.

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- Teste antes da implementação em cada história: o teste falha, e é a implementação que o faz passar
- Nenhuma das três regras de deck da feature 001 é reescrita — todas são chamadas
- Nenhum `id` nu em payload nenhum: `card_id`, `deck_id`, `user_id`, `match_id`
- Fake **nomeado** para toda I/O externa; `FakeCardCatalog`, `FakeMatchStore` e `FakeWallClock` já existem e são reusados
- Commit por tarefa ou por grupo lógico; parar em qualquer checkpoint valida a história sozinha
