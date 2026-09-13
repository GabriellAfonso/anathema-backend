---

description: "Task list for 012-match-result-history"
---

# Tasks: Resultado de partida, registrado uma vez só

**Input**: Design documents from `/specs/012-match-result-history/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: incluídos. Não é opção neste projeto — a constituição (princípio V)
exige teste para toda função nova e regressão para todo conserto, e as três
portas de qualidade (`pytest`, `mypy`, `black`) são a condição de pronto.

**Organization**: tarefas agrupadas por user story. A fatia 1 do plano (o estado
carregar o começo e o deck) e a derivação pura são **Foundational**: as três
histórias dependem delas.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a qual user story a tarefa pertence (US1, US2, US3)
- Todo caminho é a partir da raiz do repositório

## Path Conventions

Projeto Django, um só backend. O código vive em `server/apps/<app>/`, e o teste
de cada app dentro do próprio app — `apps/game/tests/` para tudo que é de
partida, como a constituição manda.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: os dois pacotes novos que o resto das fases preenche.

- [x] T001 Converter `server/apps/game/models.py` (vazio, scaffold do Django) no pacote `server/apps/game/models/`, com `__init__.py` carregando docstring e `__all__` explícito — `no_implicit_reexport` do mypy strict exige a lista, pela mesma razão documentada em `server/apps/players/models/__init__.py`
- [x] T002 [P] Criar o pacote `server/apps/game/history/` com `__init__.py` e docstring dizendo o que ele é: a segunda vida do desfecho, fora do motor e fora da mutação de estado

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: o estado da partida passa a carregar o instante de criação e o deck
da entrada, e a transição passa a ser derivável. Nada disso escreve no banco.

**⚠️ CRÍTICO**: nenhuma user story começa antes desta fase fechar. É também a
única fase que toca vários arquivos de partida já existentes — o risco de
regressão mora aqui.

### Testes desta fase

- [x] T003 [P] Em `server/apps/game/tests/test_match_serialization.py`, cobrir a ida e a volta de `started_at` e de `chosen_deck`, e o documento **sem** os dois campos (o caso da janela de implantação) desserializando com `None` em vez de levantar
- [x] T004 [P] Em `server/apps/game/tests/test_matchmaking_queue.py`, cobrir que o nome do deck viaja junto da lista na entrada da fila e volta no par, e que `leave` continua removendo a entrada inteira
- [x] T005 [P] Criar `server/apps/game/tests/test_finished_match.py` cobrindo a derivação pura: transição por Nexus devolve o registro com vencedor derivado de `opponent_of`, transição por desistência idem, partida já terminada em `before` devolve `None`, partida em andamento devolve `None`, `started_at` ausente vira duração 0

### Implementação desta fase

- [x] T006 [P] Criar `server/apps/game/match/chosen_deck.py` com o dataclass congelado `ChosenDeck(name: str, card_ids: tuple[CardId, ...])` e docstring explicando por que é cópia congelada e não referência ao `PlayerDeck` (research D6)
- [x] T007 Reexportar `ChosenDeck` em `server/apps/game/match/__init__.py`, mantendo o `__all__` explícito do módulo
- [x] T008 [P] Acrescentar `chosen_deck: ChosenDeck | None = None` a `PlayerState` em `server/apps/game/match/player_state.py`, com comentário separando-o de `PlayerState.deck` — que é a pilha de compra e **muda** durante a partida
- [x] T009 [P] Acrescentar `started_at: EpochMillis | None = None` a `Match` em `server/apps/game/match/match_state.py`, com o comentário de estado de **transporte** no mesmo formato do que `clock` já carrega: nenhuma regra o lê, nenhuma porta do motor o escreve
- [x] T010 Em `server/apps/game/match/documents.py`, acrescentar as bases `TypedDict(total=False)` com `started_at` e `chosen_deck`, mais o `ChosenDeckDocument`, e fazer `MatchDocument` e `PlayerDocument` herdarem delas (research D8)
- [x] T011 Em `server/apps/game/match/serialization.py`, escrever e ler os dois campos novos usando `.get(...)`, mantendo a garantia do cabeçalho do módulo: serializar e desserializar devolve o original (depende de T008, T009, T010)
- [x] T012 Em `server/apps/game/matchmaking/queue.py`, acrescentar `deck_name: str` a `QueueEntry` e trocar o valor do hash de deck de array JSON para objeto `{"name": ..., "card_ids": [...]}`; a lista do Redis continua guardando `user_id` pelado, porque é o `LREM` por valor exato que impede o jogador de ser pareado consigo mesmo
- [x] T013 Em `server/apps/players/services/deck_queries.py`, fazer `PlayerDeckSource.deck_for` devolver `ChosenDeck | None` em vez de `Deck | None`, e `DatabasePlayerDeckSource` montar o nome junto da lista numa leitura só (depende de T006)
- [x] T014 Atualizar `server/apps/game/tests/fake_player_deck_source.py` para o novo tipo de retorno, mantendo-o classe nomeada (depende de T013)
- [x] T015 Em `server/apps/game/engine/match_setup.py`, acrescentar `deck_name: str` a `MatchEntry` e montar `PlayerState.chosen_deck` no setup; o motor continua sem ler tempo e sem conhecer banco (depende de T006, T008)
- [x] T016 Em `server/apps/game/consumers/matchmaking.py`, levar o nome do deck de `join_with_deck` até `MatchEntry` (validação continua chamando `deck_problems` sobre `chosen.card_ids`) e escrever `match.started_at = self.clock.now_ms()` em `open_match`, na mesma linha em que hoje escreve `opening_match_clock`; ajustar `server/apps/game/tests/test_matchmaking_join.py` e `server/apps/game/tests/test_queued_deck_is_frozen.py` ao novo tipo (depende de T009, T012, T013, T015)
- [x] T017 [P] Criar `server/apps/game/history/finished_match.py` com `FinishedSide`, `FinishedMatch` (mais a propriedade `duration_seconds`) e a função pura `finished_match(before, after, ended_at) -> FinishedMatch | None`; o vencedor sai de `after.opponent_of(defeated_user_id)`, nunca de campo gravado (depende de T006, T008, T009)

**Checkpoint**: `cd server && pytest` verde. O estado atravessa o Redis com o
instante de criação e o deck da entrada, e a transição é derivável. Nada foi
gravado em banco ainda.

---

## Phase 3: User Story 1 - A partida que acaba vira exatamente um registro (Priority: P1) 🎯 MVP

**Goal**: a transição para terminada produz uma linha no banco, com `match_id`,
vencedor, derrotado, motivo, começo, fim, duração, rodada final, Nexus final e o
deck da partida dos dois. Uma linha, nunca duas, nunca nenhuma.

**Independent Test**: rodar uma partida até o Nexus chegar a zero e conferir a
linha campo a campo; repetir com desistência e com desistência no mulligan;
entregar o estado final aos dois e reconectar 20 vezes, conferindo que a contagem
daquele `match_id` continua em 1; deixar uma partida expirar sem terminar e
conferir zero linhas. As estatísticas continuam zeradas nesta fase — é a US2 que
as sobe.

### Testes para a User Story 1

- [x] T018 [P] [US1] Criar `server/apps/game/tests/test_finished_match_record.py` cobrindo a gravação: partida por Nexus e partida por desistência viram uma linha cada, com os campos do contrato; desistência no mulligan registra com `final_round == 1`; o Nexus final de quem desistiu **não** é zero; o deck da partida dos dois é a lista da entrada na fila, com o nome dela; editar o nome e apagar o deck depois deixa a linha idêntica campo a campo
- [x] T019 [P] [US1] Criar `server/apps/game/tests/test_finished_match_once.py` cobrindo o exatamente-uma-vez: duas gravações concorrentes do mesmo resultado deixam uma linha só e a perdedora recebe `False` sem levantar; reconectar 20 vezes à partida terminada não cria linha nova; a mudança reaplicada pelo compare-and-swap (via `server/apps/game/tests/interleaved_match_store.py`, que já existe) não produz segunda linha; partida abandonada que expira produz zero linhas
- [x] T020 [P] [US1] Em `server/apps/game/tests/test_finished_match_record.py`, cobrir a falha: gravação do registro explodindo não impede nenhum dos dois jogadores de receber o frame do estado final, e a falha sai em log estruturado com o `match_id`

### Implementação para a User Story 1

- [x] T021 [P] [US1] Criar `server/apps/game/models/match_record.py` com `MatchRecord` — `match_id` `unique=True`, `winner`/`loser` como `ForeignKey(PlayerProfile, on_delete=SET_NULL, null=True)` sem coluna espelho de `user_id`, `end_reason` com `choices` de `MatchEndReason`, tempos, `duration_seconds`, `final_round`, Nexus final dos dois e as quatro colunas de deck; `Meta.indexes` com `["winner", "-ended_at"]` e `["loser", "-ended_at"]` (data-model §3)
- [x] T022 [US1] Reexportar `MatchRecord` em `server/apps/game/models/__init__.py` com `__all__` explícito (depende de T001, T021)
- [x] T023 [US1] Gerar `server/apps/game/migrations/0001_initial.py` com `python manage.py makemigrations game` e conferir que ela cria a tabela, a unicidade de `match_id` e os dois índices compostos (depende de T021, T022)
- [x] T024 [P] [US1] Criar `server/apps/game/tests/fake_finished_match_recorder.py` com `FakeFinishedMatchRecorder` — classe nomeada, lista `recorded` em memória e a mesma regra de unicidade por `match_id`, para que o teste de socket exercite o contrato da produção sem tocar o banco (depende de T017)
- [x] T025 [US1] Criar `server/apps/game/history/recorder.py` com o `Protocol` `FinishedMatchRecorder` e o `DatabaseFinishedMatchRecorder`, gravando **só** o `MatchRecord` nesta fase: `@database_sync_to_async` + `@transaction.atomic`, com o `INSERT` dentro de um `atomic()` aninhado para que o `IntegrityError` da corrida vire `False` sem marcar a transação para rollback (research D3, D9; depende de T017, T021)
- [x] T026 [US1] Criar `server/apps/game/history/record_finished_match.py` com `record_finished_match(recorder, before, stored, *, ended_at)`: deriva, volta sem fazer nada se não foi transição, e envolve a gravação em `try` que registra a falha em log estruturado e **nunca** levanta (depende de T017, T025)
- [x] T027 [US1] Em `server/apps/game/consumers/match.py`, injetar `recorder: FinishedMatchRecorder | None = None` no construtor (padrão `DatabaseFinishedMatchRecorder()`, como `matches` e `catalog` já fazem) e chamar `record_finished_match` em `play`, **depois** de `deliver_match_update`, com `ended_at=self.clock.now_ms()` (depende de T026)
- [x] T028 [US1] Em `server/apps/game/match_timers/ticker.py`, acrescentar `recorder` às dependências obrigatórias por palavra-chave e chamar `record_finished_match` em `_expire`, depois de `deliver_match_update`, com `ended_at=now`; `_warn` **não** chama — a marca do aviso não passa pelo motor e nunca termina partida (depende de T026)
- [x] T029 [US1] Ligar o gravador de verdade em `server/core/asgi.py`, dentro de `build_match_clock_ticker` (depende de T028)
- [x] T030 [US1] Atualizar os três construtores de ticker dos testes — `server/apps/game/tests/clock_boards.py`, `server/apps/game/tests/test_match_consumer_clock.py` e `server/apps/game/tests/test_match_wake_queue.py` — para passar o `FakeFinishedMatchRecorder` (depende de T024, T028)

**Checkpoint**: uma partida terminada tem linha no banco, uma só, e nenhuma
observação cria outra. As estatísticas continuam em zero — é o próximo
incremento. A suíte de websocket continua sem tocar o banco.

---

## Phase 4: User Story 2 - As estatísticas dos dois sobem junto com o registro (Priority: P1)

**Goal**: `matches_played`, `wins`, `losses` e `play_time` deixam de ser zero para
sempre. As duas escritas — registro e estatísticas — acontecem juntas ou nenhuma.

**Independent Test**: partir de dois jogadores zerados, terminar uma partida de
duração conhecida e conferir os quatro contadores dos dois lados; terminar a
sexta partida de um jogador e conferir que os contadores sobem de um, sem
recontar; forçar a falha da escrita de estatística e conferir que o registro
também não ficou.

### Testes para a User Story 2

- [x] T031 [P] [US2] Em `server/apps/game/tests/test_finished_match_record.py`, cobrir os contadores: `matches_played` 1 para os dois, `wins` 1 só para o vencedor, `losses` 1 só para o derrotado, `play_time` somando a mesma duração para os dois; e um jogador com cinco partidas registradas cujos contadores sobem de um na sexta
- [x] T032 [P] [US2] Em `server/apps/game/tests/test_finished_match_once.py`, cobrir a atomicidade e a concorrência: escrita de estatística falhando deixa zero linhas daquela partida e zero contadores mexidos; duas partidas do mesmo jogador terminando ao mesmo tempo somam as duas, sem incremento perdido; perfil sem `PlayerStats` (conta criada fora do registro) não impede a gravação

### Implementação para a User Story 2

- [x] T033 [US2] Em `server/apps/game/history/recorder.py`, acrescentar `_bump_stats` dentro da **mesma** `transaction.atomic` do `INSERT`: dois `PlayerStats.objects.filter(profile_id=...).update(...)` com expressões `F()`, para que o incremento aconteça no banco e não se perca sob concorrência (research D4; depende de T025)
- [x] T034 [US2] Documentar em `server/apps/game/history/recorder.py` por que o `update()` filtrado é a forma certa quando o perfil não tem `PlayerStats` — afeta 0 linhas e segue, em vez de derrubar o registro de uma partida que de fato aconteceu (depende de T033)

**Checkpoint**: US1 e US2 verdes juntas. Uma partida terminada produz uma linha e
quatro contadores corretos, ou nada.

---

## Phase 5: User Story 3 - O jogador consulta o próprio histórico (Priority: P2)

**Goal**: `GET /game/matches/` devolve as partidas do autenticado, da mais recente
para a mais antiga, em páginas de 20. Só as próprias.

**Independent Test**: com registros semeados para dois jogadores, pedir o
histórico de um e conferir ordem, conteúdo da linha, paginação e que nenhuma linha
do outro aparece; conferir `401` sem token, `404` sem perfil, lista vazia para
quem não jogou, e `opponent: null` quando o perfil do oponente foi apagado.

**Depende de**: US1 — a tabela é dela. Sem registro não há o que listar.

### Testes para a User Story 3

- [x] T035 [P] [US3] Criar `server/apps/game/tests/test_match_history_api.py` cobrindo o contrato inteiro de `contracts/http_match_history.md`: ordem decrescente por `ended_at`; 50 partidas percorridas em páginas devolvem 50 linhas sem repetir nem pular; `page_size` acima de 100 vale 100; nenhuma linha de outro jogador aparece; `401` sem autenticação; `404` sem `PlayerProfile`; `200` com lista vazia para quem não jogou; perfil do oponente apagado deixa a linha com `opponent: null` e o desfecho intacto; nenhum campo chamado `id` no corpo

### Implementação para a User Story 3

- [x] T036 [P] [US3] Criar `server/apps/game/history/match_history_queries.py` com a consulta partindo sempre do perfil autenticado — `filter(Q(winner=profile) | Q(loser=profile)).select_related("winner", "loser").order_by("-ended_at")` — e docstring dizendo que o isolamento sai da consulta, não de uma checagem depois dela, como `deck_queries.py` já argumenta (depende de T021)
- [x] T037 [P] [US3] Criar `server/apps/game/match_history_serializers.py` com a linha do histórico do ponto de vista de quem pede: `match_id`, `won` derivado, `end_reason`, `opponent` (campos públicos do perfil, ou `null`), `duration_seconds`, `final_round`, `ended_at`; deck e Nexus final ficam guardados e **não** são expostos (depende de T021)
- [x] T038 [US3] Criar `server/apps/game/match_history_view.py` com a `PageNumberPagination` própria (`page_size=20`, `page_size_query_param="page_size"`, `max_page_size=100`) e a `ListAPIView` com `IsAuthenticated`, resolvendo o perfil do autenticado e recusando com `404` quem não é jogador — mesma recusa e mesma razão de `PlayerMeView` (depende de T036, T037)
- [x] T039 [US3] Acrescentar `path("matches/", MatchHistoryView.as_view(), name="match_history")` a `server/apps/game/urls.py`, que sobe como `/game/matches/` (depende de T038)

**Checkpoint**: as três histórias funcionam. O jogador consulta o próprio
histórico e não alcança o de ninguém.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T040 [P] Registrar `MatchRecord` em `server/apps/game/admin.py` com `list_display` e `search_fields` por `match_id`, somente leitura — nenhuma rota desta feature altera registro, e o admin não devia ser a exceção
- [x] T041 [P] Conferir que `server/apps/game/tests/test_engine_reads_no_time.py` continua verde: `started_at` entra pelo consumer de matchmaking, não pelo motor
- [~] T042 Rodar os oito cenários de [quickstart.md](quickstart.md) e corrigir o que divergir
- [~] T043 As três portas de qualidade verdes: `cd server && pytest`, `cd server && mypy`, `black --check server/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependência, começa já
- **Foundational (Phase 2)**: depende do Setup — **bloqueia todas as histórias**
- **US1 (Phase 3)**: depende da Foundational. É o MVP
- **US2 (Phase 4)**: depende de US1 — ela acrescenta as estatísticas à transação que US1 criou
- **US3 (Phase 5)**: depende de US1 — a tabela é dela
- **Polish (Phase 6)**: depende de tudo que se quiser entregar

### User Story Dependencies

Ao contrário do caso comum, as três histórias **não** são paralelas entre si, e
isso é do desenho, não do plano: US2 escreve dentro da mesma transação que US1
abre, e US3 lê a tabela que US1 cria. O que cada uma preserva é a
**testabilidade independente** — US1 fecha com estatísticas ainda zeradas, e US2
fecha sem que exista rota de histórico.

Depois de US1, **US2 e US3 podem ser feitas em paralelo**: uma toca
`history/recorder.py`, a outra só arquivos novos mais uma linha em `urls.py`.

### Dentro de cada fase

- Teste escrito antes da implementação, e reprovando antes dela
- Estado antes de derivação, derivação antes de gravação, gravação antes de consulta
- Modelo antes de migração, migração antes do gravador

### Parallel Opportunities

- **Phase 2**: T003, T004 e T005 juntos (três arquivos de teste). Depois T006, T008, T009 e T017 são arquivos diferentes — T017 só precisa dos três primeiros existirem
- **Phase 3**: T018, T019 e T020 juntos; T021 e T024 juntos
- **Phase 5**: T036 e T037 juntos (arquivos novos independentes)
- **Phase 6**: T040 e T041 juntos

---

## Parallel Example: Foundational

```bash
# Os três arquivos de teste da fase, juntos:
Task: "Ida e volta de started_at e chosen_deck em server/apps/game/tests/test_match_serialization.py"
Task: "Nome do deck na entrada da fila em server/apps/game/tests/test_matchmaking_queue.py"
Task: "Derivação pura em server/apps/game/tests/test_finished_match.py"

# Os campos de estado, arquivos diferentes:
Task: "ChosenDeck em server/apps/game/match/chosen_deck.py"
Task: "PlayerState.chosen_deck em server/apps/game/match/player_state.py"
Task: "Match.started_at em server/apps/game/match/match_state.py"
```

## Parallel Example: User Story 1

```bash
# Os três arquivos de teste da história:
Task: "Gravação campo a campo em server/apps/game/tests/test_finished_match_record.py"
Task: "Exatamente uma vez em server/apps/game/tests/test_finished_match_once.py"
Task: "Falha de gravação não derruba a partida em server/apps/game/tests/test_finished_match_record.py"

# Modelo e fake, independentes:
Task: "MatchRecord em server/apps/game/models/match_record.py"
Task: "FakeFinishedMatchRecorder em server/apps/game/tests/fake_finished_match_recorder.py"
```

---

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1: Setup — os dois pacotes
2. Phase 2: Foundational — o estado carrega o começo e o deck, e a transição é derivável
3. Phase 3: US1 — a partida terminada vira uma linha, uma só
4. **PARAR E VALIDAR**: cenários 1, 2, 3, 4, 6 e 7 do quickstart
5. O desfecho já sobrevive ao TTL. `PlayerStats` ainda em zero, e nenhuma rota nova

### Incremental Delivery

1. Foundational → estado pronto, nada gravado
2. + US1 → o desfecho sobrevive (MVP)
3. + US2 → as estatísticas deixam de ser zero para sempre
4. + US3 → o jogador enxerga o próprio histórico
5. Polish → as três portas de qualidade e o quickstart inteiro

### Parallel Team Strategy

1. Foundational é de uma pessoa só: ela toca vários arquivos de partida
   existentes, e dividi-la troca coordenação por conflito
2. US1 idem — o caminho de gravação é um só
3. Depois de US1, duas frentes: US2 em `history/recorder.py`, US3 nos arquivos
   novos do HTTP

---

## Estado da execução (2026-09-13)

T001 a T041 feitas. T042 e T043 ficaram **parciais**, e por um bloqueio de
ambiente, não de código: depois que o Docker Desktop subiu nesta máquina, todo
`socket.socketpair()` passou a falhar com `WinError 10013` -- reserva de porta do
WinNAT, que só sai com `net stop winnat` elevado ou um reboot.

Verificado:

- `mypy` limpo, 237 arquivos.
- `python manage.py check`, sem problemas.
- 24 testes de serialização, 14 da derivação pura, 14 do contrato HTTP do
  histórico: todos verdes.
- 998 testes da suíte (tudo que não depende de Redis) verdes **antes** do
  bloqueio, com as mudanças da fase Foundational já aplicadas.

**Não** verificado, e a rodar assim que o socket destravar:

- todo teste `async` -- socket de partida, ticker, e os de gravação no banco
  (`test_finished_match_record.py`, `test_finished_match_once.py`);
- os testes que dependem de Redis (`test_match_store.py`,
  `test_match_wake_queue.py`, `test_matchmaking_queue.py`), que exigem o
  `anathema_redis` do compose de pé;
- `black`, que também usa `asyncio` e não roda.

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- O motor não é tocado por nenhuma tarefa. Se uma delas precisar mexer em
  `apps/game/engine/victory.py`, o desenho está errado — volte ao plano
- Nenhuma tarefa escreve no banco de dentro de `MatchStore.mutate`. O
  compare-and-swap reaplica a mudança numa retentativa, e a escrita aconteceria
  duas vezes
- Nenhuma tarefa faz teste de websocket tocar o banco. É para isso que o
  `FakeFinishedMatchRecorder` existe
- Commit por tarefa ou por grupo lógico; parar em qualquer checkpoint deixa a
  suíte verde
