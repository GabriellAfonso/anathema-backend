---

description: "Task list for 013-socket-heartbeat"
---

# Tasks: Heartbeat de aplicação nos sockets

**Input**: Design documents from `/specs/013-socket-heartbeat/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: incluídos. Neste projeto não são opcionais. A constituição (princípio
V) exige teste para toda função nova, e a spec pede a prova com testes de
consumer nos dois sockets e com a partida de fumaça.

**Organization**: tarefas agrupadas por user story. A regra do ping e a mudança
no `receive` são **Foundational**: os dois sockets passam pelo mesmo trecho, e
as três histórias dependem dele. Por isso as fases das histórias são sobretudo
de prova. O código de produção fica pronto na Fase 2, e cada história fecha
quando os testes dela provam o comportamento que a spec promete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a qual user story a tarefa pertence (US1, US2, US3)
- Todo caminho é a partir da raiz do repositório

## Path Conventions

Projeto Django, um só backend. Código em `server/apps/game/`, testes em
`server/apps/game/tests/`, fumaça em `scripts/`. Comandos de teste e tipo rodam de
`server/`; `black` e a fumaça rodam da raiz.

## Desvio do plano

Duas peças de teste que o plano não listava, achadas ao quebrar as tarefas. O
`plan.md` e o `quickstart.md` já foram atualizados:

- `server/apps/game/tests/matchmaking_sockets.py`: abrir o socket de fila com os
  fakes. Três arquivos de teste precisam dele, e repetir a montagem violaria o
  princípio IV. Mesmo papel do `match_sockets.py` existente.
- `server/apps/game/tests/test_heartbeat_echo.py`: o eco nos dois sockets, num
  arquivo só, parametrizado pelo socket. Assim a US3 não divide arquivo com a
  US1 nem com a US2.
- `server/apps/game/tests/heartbeat_sockets.py` (achado na implementação):
  `open_accepted_socket(kind)`, `expect_pong` e `expect_ping_burst_answered`.
  O eco, os gates e as duas rajadas precisam abrir "qualquer um dos dois
  sockets" e ler pong; sem ele, três arquivos repetiriam a montagem.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: fixar a linha de base e deixar a fumaça pronta para **falhar**
contra o servidor de hoje. É o que prova que ela testa o que diz testar.

- [X] T001 Registrar a linha de base na branch `013-socket-heartbeat` antes de qualquer mudança de código: `cd server && pytest` (anotar a contagem de testes) e `cd server && mypy`, os dois verdes
- [X] T002 Rodar `venv/Scripts/black scripts/smoke_match.py` **sozinho** e commitar à parte como `style(scripts): apply black to the smoke match` — o arquivo entrou em 53f6a89, depois do commit de estilo, e é o único que `black --check server/ scripts/` reprova hoje; separar mantém o diff do heartbeat legível
- [X] T003 [P] Criar `scripts/smoke_heartbeat.py` com docstring de módulo (o que é, por que é módulo separado: `smoke_match.py` já está perto das 500 linhas — research D10). Conteúdo: dataclass `HeartbeatLedger` (marcadores mandados → `time.monotonic()` do envio, pongs recebidos, ecos errados, maior latência em ms); `ping_frame(ledger: HeartbeatLedger) -> str`, que devolve o JSON de `{"type": "ping", "payload": {"smoke_marker": <int sequencial>}}` e anota o envio; `invalid_ping_frame(ledger) -> str`, que devolve `{"type": "ping", "payload": 42}` e anota que o próximo pong sem marcador deve vir com `{}`; `record_pong(ledger, payload: object) -> None`, que casa o marcador, mede a latência e anota eco errado; `heartbeat_problems(ledger, label: str) -> list[str]`, que devolve pongs ≠ pings, ecos errados e latência ≥ 1000 ms. **Não** importa nada de `smoke_match.py`: devolve problemas em texto, e quem chama transforma em `SmokeFailure`
- [X] T004 Integrar em `scripts/smoke_match.py` (depende de T002 e T003): campo `heartbeat: HeartbeatLedger` no `Bot`; em `find_match`, mandar `ping_frame` **antes** do `join_queue` e aceitar `pong` no laço (chamando `record_pong`, sem retornar); em `on_frame`, ramo `pong` que chama `record_pong` e devolve `True` **sem** chamar `act`; em `on_state`, mandar `ping_frame` na primeira vez que o bot vê cada fase (`mulligan`, `action`, `declaration`, `combat`, `finished` — em `finished`, antes de retornar `False`), e `invalid_ping_frame` uma vez, no primeiro `action`; em `on_refusal`, `expect` que o código não é `unknown_message_type`; em `report`, imprimir por bot pings, pongs e maior latência; em `run`, depois do `report`, `expect` sobre `heartbeat_problems` dos dois bots. O arquivo termina abaixo de 500 linhas
- [X] T005 Com `docker compose up -d` rodando o código **sem** as mudanças de servidor (nenhuma tarefa da Fase 2 aplicada), rodar `venv/Scripts/python scripts/smoke_match.py` e confirmar que **falha**: o socket de fila responde ao primeiro ping com `message_refused` / `unknown_message_type`. Anotar a linha de falha no PR. Se passar, a fumaça não está testando o ping, e T003/T004 estão errados

**Checkpoint**: fumaça pronta e comprovadamente vermelha contra o servidor de
hoje.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a regra pura do ping e o ponto único onde os dois sockets a
aplicam. Todo o código de produção da feature está aqui.

**⚠️ CRÍTICO**: nenhuma user story começa antes desta fase fechar. É a única fase
que mexe em código existente, e o `receive` é o caminho de **toda** mensagem dos
dois sockets. O risco de regressão está aqui.

### Testes desta fase (escrever primeiro)

- [X] T006 [P] Criar `server/apps/game/tests/test_heartbeat.py`, com docstring de módulo, cobrindo a regra pura de `apps.game.protocol.heartbeat`. `is_ping` é verdadeiro para `{"type": "ping"}` e para `{"type": "ping", "payload": 42, "extra": 1}`, e falso para `{"type": "pong"}`, `"Ping"`, `"PING"`, `" ping"`, `"ping "`, `type` ausente, `type` `None` e `type` `1`. `pong_payload` devolve o objeto recebido para `{"sent_at_ms": 1726000000000}` e para `{"a": {"b": [1, {"c": None}]}}`, e `{}` para `payload` ausente, `None`, `42`, `4.2`, `"x"`, `True`, `[1, 2]` e `{}`. Usar `pytest.mark.parametrize` com ids legíveis. Falha na coleta até T010 existir
- [X] T007 [P] Criar `server/apps/game/tests/access_counting_match_store.py` com `AccessCountingMatchStore(FakeMatchStore)`, subclasse nomeada (research D8): atributo `accesses: Counter[str]`; `get`, `get_stored`, `save` e `mutate` incrementam a chave com o próprio nome e delegam a `super()`, repassando argumentos e keywords (`renews_expiry` no `mutate`); `forget_accesses() -> None` zera a contagem. Docstring com o porquê: o `FakeMatchStore` prova "não gravou", não "não leu", e o socket lê uma vez no gate, então o teste zera depois de conectar. Mesmo movimento de `interleaved_match_store.py`
- [X] T008 [P] Criar `server/apps/game/tests/matchmaking_sockets.py` com docstring de módulo ("não é fake", como `match_sockets.py`) e `async def open_matchmaking_socket(user: FakePlayerUser | FakeAnonymousUser, *, queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource) -> WebsocketTestClient`. Monta `MatchmakingConsumer.as_asgi(queue=cast(MatchmakingQueue, queue), matches=cast(MatchStore, FakeMatchStore()), decks=decks, catalog=get_card_catalog(), randomness=ScriptedRandomSource(), clock=FakeWallClock())` sobre `WebsocketTestClient(..., "/ws/matchmaking/")`, põe `user` no scope, chama `connect()` e devolve o cliente sem ler frame nenhum — o gate de autenticação ainda tem frames a entregar. `__all__` explícito
- [X] T009 Criar `server/apps/game/tests/test_heartbeat_gates.py` (depende de T008), com docstring de módulo citando FR-012 a FR-015 e research D3. Cobrir: (a) socket de matchmaking **e** de partida com `FakeAnonymousUser`: mandar `{"type": "ping"}` logo depois de conectar, receber exatamente o `auth_denied` de hoje, close code `UNAUTHENTICATED`, e `nothing_received()` verdadeiro; (b) os três gates da partida — sem `matchId` (`MATCH_ID_MISSING`), partida inexistente (`MATCH_NOT_FOUND`), jogador de fora (`NOT_A_PARTICIPANT`), montados como em `test_match_consumer_access.py` —, cada um com ping, o `match_denied` de hoje, o close code, e `nothing_received()`; (c) nos dois sockets aceitos, `{"type": "pong"}`, `{"type": "Ping"}`, `{"type": "PING"}` e `{"type": " ping"}` recusados com `unknown_message_type`; (d) nos dois sockets aceitos, texto cru `ping` e frame binário `b'{"type": "ping"}'` recusados com `malformed_message`. O caso (a) no socket de matchmaking falha hoje (sai `unknown_message_type` depois do close); os outros já passam e ficam como guarda de regressão — anotar isso na docstring do teste

### Implementação desta fase

- [X] T010 [P] Criar `server/apps/game/protocol/heartbeat.py` (research D2). Docstring de módulo: o que é o ping, por que ele não é jogada, e o contrato em `specs/013-socket-heartbeat/contracts/heartbeat_messages.md`. Conteúdo: `PING = "ping"`, `PONG = "pong"`, `def is_ping(content: Mapping[str, object]) -> bool` e `def pong_payload(content: Mapping[str, object]) -> dict[str, object]`, cada função com docstring de intenção e um exemplo `>>>`. Sem I/O, sem import do Channels
- [X] T011 Em `server/apps/game/protocol/__init__.py` (depende de T010): acrescentar `heartbeat` à lista da docstring do pacote ("o ping dos dois sockets, que não é jogada — feature 013"), importar `PING`, `PONG`, `is_ping`, `pong_payload` e pô-los no `__all__` sob um comentário `# Heartbeat dos dois sockets (feature 013)`
- [X] T012 Em `server/apps/game/consumers/base.py`, dividir `receive` **sem mudar comportamento**: novo `async def decode_client_frame(self, text_data: str | None) -> dict[str, object] | None` com as três recusas de hoje (binário, JSON inválido, não-objeto), que devolve o objeto ou `None` depois de recusar. `receive` passa a chamá-lo e seguir para `receive_json`. A docstring atual do `receive` (o `receive` do Channels levanta e derruba o socket; feature 009, FR-023) vai para `decode_client_frame`, preservada. Rodar `cd server && pytest apps/game/tests/test_base_consumer_lifecycle.py apps/game/tests/test_match_consumer_play.py apps/game/tests/test_match_consumer_flow.py`: verde sem alteração
- [X] T013 Em `server/apps/game/consumers/base.py` (depende de T011 e T012): (1) `def passed_socket_gates(self) -> bool`, que devolve `self.accepted`, com docstring explicando que o gate aceita antes de recusar e que frame depois do close é o `RuntimeError` que `test_base_consumer_lifecycle.py` registra; (2) `async def answer_ping(self, content: Mapping[str, object]) -> None`, que retorna sem mandar nada se `not self.passed_socket_gates()` e, senão, faz `await self.send_event(type=PONG, payload=pong_payload(content))`, com docstring citando research D4 (só este socket, nunca o channel layer) e D5 (não renova presença); (3) em `receive`, depois de `decode_client_frame` e antes de `receive_json`: `if is_ping(content): await self.answer_ping(content); return`, com comentário do porquê — o `MatchConsumer` substitui `receive_json`, então este é o último ponto comum aos dois sockets (research D1). **Não** tocar `set_heartbeat`, `heartbeat_key` nem o ramo do `disconnect`
- [X] T014 Em `server/apps/game/consumers/match.py` (depende de T013): sobrescrever `def passed_socket_gates(self) -> bool` com `super().passed_socket_gates() and self.match_id is not None`, e docstring: o gate da partida aceita, entra no grupo de usuário e só então recusa, então `accepted` sozinho não basta; `match_id` é `None` exatamente no socket recusado, como `on_disconnect` e `receive_json` já assumem
- [X] T015 Checkpoint da fase: `cd server && pytest apps/game/tests/test_heartbeat.py apps/game/tests/test_heartbeat_gates.py` verde; `cd server && pytest` inteiro verde, com a contagem de T001 mais os testes novos; `cd server && mypy` verde; `git diff --name-only --diff-filter=M -- server/apps/game/tests` vazio, porque nenhum teste existente mudou (SC-011)

**Checkpoint**: os dois sockets respondem ping. As histórias agora provam cada uma
o seu lado, e podem seguir em paralelo.

---

## Phase 3: User Story 1 - O cliente em partida sabe que a conexão está viva (Priority: P1) 🎯 MVP

**Goal**: no socket de partida, todo ping recebe um pong só naquele socket, em
qualquer fase, sem ler nem gravar a partida, sem versão, sem `match_update` e
sem mexer no relógio.

**Independent Test**: abrir os dois sockets de uma partida em cada fase, pingar
por um deles, e conferir o pong, zero acesso ao store, `match_snapshot` e versão
idênticos, prazos idênticos, e silêncio no outro socket.

### Tests for User Story 1

Todas em `server/apps/game/tests/test_match_consumer_heartbeat.py`: mesmo
arquivo, então em sequência.

- [X] T016 [US1] Criar `server/apps/game/tests/test_match_consumer_heartbeat.py`, com docstring de módulo citando FR-007, SC-003 e research D8. Fixtures: `clock` (`FakeWallClock`), `matches` (`AccessCountingMatchStore(clock)`), `recorder` (`FakeFinishedMatchRecorder`), `catalog` (`mvp_catalog()`). Helper local `async def expect_pong(client: WebsocketTestClient, payload: Frame) -> None`, que afirma o frame inteiro `{"type": "pong", "payload": payload}`. Primeiro teste: partida de `with_a_turn` (de `clock_boards.py`), `open_match_socket` para `PLAYER_ONE` com o `clock` e o `recorder`, `send_json_to({"type": "ping"})`, `expect_pong(client, {})`, e `nothing_received()` depois
- [X] T017 [US1] No mesmo arquivo, teste parametrizado pelas fases que se montam direto no store — `mulligan` (`awaiting_mulligan`), `action` (`with_a_turn`) e `combat` (`with_a_turn` seguido de `declare_combat(match, 0)` e novo `saved`). Abrir os dois sockets com `both_sockets`, guardar `match_snapshot` e `matches.matches[match_id].version`, `matches.forget_accesses()`, guardar `len(matches.expiry_renewals)`; pingar pelo socket de quem **não** tem prioridade; `expect_pong`; afirmar `matches.accesses` vazio, snapshot igual (isso cobre os prazos da vez e do mulligan, que fazem parte do documento), versão igual, `expiry_renewals` do mesmo tamanho, e `nothing_received()` nos dois sockets
- [X] T018 [US1] No mesmo arquivo, a fase `declaration`: partida de `with_a_turn`, `both_sockets`, `PLAYER_ONE` manda `declare_attack` com a primeira unidade do banco (montar por `message_for` de `match_sockets.py`), consumir o `match_update` dos dois com `next_update` e conferir `view["phase"] == "declaration"`; depois as mesmas afirmações de T017, pingando pelos dois sockets
- [X] T019 [US1] No mesmo arquivo, a fase `finished`: `both_sockets` numa partida de `with_a_turn`, `PLAYER_ONE` manda `forfeit`, consumir o `match_update` final dos dois; pingar pelos dois sockets; `expect_pong` em cada um, nenhum `match_is_over` nem outra recusa, versão igual à do estado final, `len(recorder.recorded) == 1` (SC-004)
- [X] T020 [US1] No mesmo arquivo, o relógio: numa partida de `with_a_turn`, pingar pelo socket de quem tem a vez algumas vezes, avançando o `clock` entre os pings até pouco antes de `EXPIRY_SECONDS`; depois fazer a vez estourar com `ticker_over` exatamente como `test_match_consumer_clock.py` faz, e conferir que o estouro chega no mesmo instante em que chegaria sem ping — o ping não conta como ação nem estende o prazo (US1, cenário 3)
- [X] T021 [US1] No mesmo arquivo, isolamento do pong (SC-006): abrir **dois** sockets de `PLAYER_ONE` e um de `PLAYER_TWO` na mesma partida; pingar pelo primeiro de `PLAYER_ONE`; `expect_pong` nele, `nothing_received()` no segundo socket de `PLAYER_ONE` e no de `PLAYER_TWO`
- [X] T022 [US1] No mesmo arquivo, rajada (SC-001): 50 pings seguidos com `{"n": i}`, depois ler 50 frames e afirmar que são `pong` com `n` de 0 a 49 em ordem, sem nenhum `message_refused`
- [X] T023 [US1] No mesmo arquivo, partida expirada: abrir o socket, chamar `matches.forget(match_id)`, pingar e receber pong (o ping não consulta a partida); em seguida mandar `pass` e receber `match_not_found` como hoje
- [X] T024 [US1] Checkpoint: `cd server && pytest apps/game/tests/test_match_consumer_heartbeat.py` verde, e `cd server && mypy` verde

**Checkpoint**: US1 provada. É o MVP: o detector do cliente arma no socket de
partida.

---

## Phase 4: User Story 2 - O cliente na fila sabe que a conexão está viva (Priority: P1)

**Goal**: no socket de matchmaking, todo ping recebe pong em qualquer momento,
sem entrar, sair ou mudar de lugar na fila, e sem consultar deck.

**Independent Test**: abrir o socket de fila com `FakeMatchmakingQueue` e
`FakePlayerDeckSource`, pingar antes do `join_queue`, na fila, depois de recusa e
depois de `match_found`, e conferir um pong por ping com `queue.waiting` e
`decks.asked` idênticos.

### Tests for User Story 2

Todas em `server/apps/game/tests/test_matchmaking_heartbeat.py`: mesmo arquivo,
então em sequência. Nenhum teste passa por pareamento, então nenhum chega ao
`profile_for`, que toca banco (research D9).

- [X] T025 [US2] Criar `server/apps/game/tests/test_matchmaking_heartbeat.py`, com docstring de módulo citando FR-008, SC-005 e research D9. Fixtures: `queue` (`FakeMatchmakingQueue`), `decks` (`FakePlayerDeckSource` com o deck de `fake_chosen_deck(starter_deck(get_card_catalog()))` em `(PLAYER_ONE, THEIR_DECK_ID)`), e constantes `PLAYER_ONE`, `THEIR_DECK_ID`, `NOBODYS_DECK_ID` com os valores de `test_matchmaking_join.py`. Primeiro teste: `open_matchmaking_socket(FakePlayerUser(PLAYER_ONE), ...)`, ping **antes** do `join_queue`, pong `{}`, `await queue.size() == 0`, `decks.asked == []`
- [X] T026 [US2] No mesmo arquivo, na fila: `join_queue` com `THEIR_DECK_ID`; sozinho, nenhum frame sai, então conferir `nothing_received()`; guardar `list(queue.waiting)` e `list(decks.asked)`; pingar; pong; `queue.waiting` igual (mesmo jogador, mesma posição, mesmo deck), `decks.asked` igual, e `nothing_received()` — nenhum `match_found`
- [X] T027 [US2] No mesmo arquivo, depois de recusa: `join_queue` com `NOBODYS_DECK_ID`, receber `message_refused` com `deck_not_found`; guardar `decks.asked`; pingar; pong; `await queue.size() == 0`, `decks.asked` igual
- [X] T028 [US2] No mesmo arquivo, depois do `match_found`: com o socket aberto, `get_channel_layer().group_send(MatchmakingConsumer.user_group(PLAYER_ONE), {"type": "client_event", "event": "match_found", "payload": {"match_id": "m-1"}})`, receber o frame, pingar, pong, `await queue.size() == 0`
- [X] T029 [US2] No mesmo arquivo, rajada (SC-001): 50 pings com `{"n": i}`, 50 pongs em ordem, nenhum `message_refused`, fila vazia no fim
- [X] T030 [US2] Checkpoint: `cd server && pytest apps/game/tests/test_matchmaking_heartbeat.py` verde, e `cd server && mypy` verde

**Checkpoint**: US2 provada. O detector do cliente arma nos dois sockets.

---

## Phase 5: User Story 3 - O cliente mede a latência pelo eco (Priority: P2)

**Goal**: nos dois sockets, o `payload` objeto volta idêntico no pong, e qualquer
outra coisa volta como `{}`, sem recusa.

**Independent Test**: parametrizar pelo socket e conferir o eco de marcador, de
objeto aninhado, de payload inválido e de campos a mais.

### Tests for User Story 3

- [X] T031 [US3] Criar `server/apps/game/tests/test_heartbeat_echo.py`, com docstring de módulo citando FR-003 a FR-006 e SC-002. Fixture parametrizada `socket` com ids `match` e `matchmaking`: `match` abre `open_match_socket` para `PLAYER_ONE` sobre `FakeMatchStore` com `await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))`, e já consome o `match_start` (o helper faz isso); `matchmaking` abre `open_matchmaking_socket(FakePlayerUser(PLAYER_ONE), queue=FakeMatchmakingQueue(), decks=FakePlayerDeckSource())`; a fixture desconecta no teardown. Primeiro teste: `{"type": "ping", "payload": {"sent_at_ms": 1726000000000}}` volta como `{"type": "pong", "payload": {"sent_at_ms": 1726000000000}}`
- [X] T032 [US3] No mesmo arquivo, objeto aninhado: `{"a": {"b": [1, {"c": None}], "d": "x"}, "e": 2.5}` volta igual por `==`, nos dois sockets
- [X] T033 [US3] No mesmo arquivo, payload que não é objeto, parametrizado: ausente (mensagem sem a chave), `None`, `42`, `"x"`, `True`, `[1, 2]`. Cada um volta como pong com `{}`, e `nothing_received()` depois, sem recusa
- [X] T034 [US3] No mesmo arquivo, campos a mais: `{"type": "ping", "payload": {"k": 1}, "user_id": 99, "extra": [1]}` volta como `{"type": "pong", "payload": {"k": 1}}`, e o servidor não acrescenta chave nenhuma (FR-006)
- [X] T035 [US3] Checkpoint: `cd server && pytest apps/game/tests/test_heartbeat_echo.py` verde, e `cd server && mypy` verde

**Checkpoint**: as três histórias provadas.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: a prova contra o servidor de verdade, as portas de qualidade, e os
papéis do vault.

- [X] T036 Com `docker compose up -d` rodando esta branch, rodar `venv/Scripts/python scripts/smoke_match.py`, `venv/Scripts/python scripts/smoke_match.py --spells` e `venv/Scripts/python scripts/smoke_match.py --forfeit-at 3`. As três terminam em `== OK`, com pongs igual a pings nos dois bots, nenhuma recusa `unknown_message_type`, maior latência abaixo de 1000 ms e a partida no histórico uma vez por jogador (SC-009, SC-010). Colar o resumo no PR, ao lado da falha de T005
- [X] T037 [P] Em `C:/Users/gabri/Obsidian/Projetos/Anathema/Backend/TODO.md`, na seção "Heartbeat / presença", acrescentar uma linha curta, em português: o ping de aplicação cliente→servidor existe desde a feature 013 (`ping`/`pong` nos dois sockets, sem presença); continuam em aberto a presença e a detecção de cliente travado, que precisa de ping servidor→cliente. Não alterar o resto do item
- [X] T038 [P] Em `C:/Users/gabri/Obsidian/Projetos/Anathema/Backend/Consumers/BaseConsumer.md`, na seção "3. Roteamento de mensagens recebidas", acrescentar uma linha: `ping` é respondido com `pong` antes do roteamento, igual para todo consumer, porque o `MatchConsumer` não usa `handle_<type>`. Nota curta, em português
- [X] T039 Portas de qualidade finais, da raiz do repositório: `cd server && pytest` (tudo verde), `cd server && mypy` (verde), `venv/Scripts/black --check server/ scripts/` (limpo)
- [X] T040 Conferência de tamanho (princípio IV): toda função nova ou alterada em `server/apps/game/consumers/base.py`, `server/apps/game/consumers/match.py`, `server/apps/game/protocol/heartbeat.py` e `scripts/smoke_heartbeat.py` entre 4 e 20 linhas; `scripts/smoke_match.py` e todo arquivo novo abaixo de 500 linhas; no máximo 2 níveis de indentação nos ramos novos
- [X] T041 Conferência do que **não** podia mudar, contra `dev`. Vazios: `git diff dev --name-only --diff-filter=M -- server/apps/game/tests` (nenhum teste existente alterado, SC-011); `git diff dev -- server/apps/game/protocol/refusal_codes.py server/apps/game/protocol/matchmaking_refusals.py specs/009-match-protocol/contracts/refusal_codes.md` (catálogo intocado, FR-019); `git diff dev -- server/apps/game/consumers/matchmaking.py server/apps/game/protocol/client_messages.py` (sem cópia da regra, FR-016). E `git diff dev -- server/apps/game/consumers/base.py` sem nenhuma linha removida ou acrescentada que cite `set_heartbeat`, `heartbeat_key` ou `presence` (FR-010, research D5)
- [X] T042 Percorrer [quickstart.md](quickstart.md), seções 1 a 3, e confirmar que cada linha da tabela da seção 2 corresponde a um teste que existe e passa

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependência. T005 **precisa** rodar antes de qualquer
  tarefa da Fase 2 estar aplicada ao código que o compose serve.
- **Foundational (Phase 2)**: depende de T001. Não depende da fumaça (T002–T005),
  mas T005 tem de ter rodado antes de T012 mudar o servidor. Bloqueia as três
  histórias.
- **User Stories (Phases 3–5)**: dependem só da Fase 2. Arquivos distintos, então
  podem seguir em paralelo.
- **Polish (Phase 6)**: T036 depende da Fase 2 e de T004; T039–T042 dependem de
  todas as fases; T037 e T038 podem ser feitos a qualquer momento depois da
  Fase 2.

### User Story Dependencies

- **US1 (P1)**: depende da Fase 2 (T007 para o `AccessCountingMatchStore`). Sem
  dependência de outra história.
- **US2 (P1)**: depende da Fase 2 (T008 para `open_matchmaking_socket`). Sem
  dependência de outra história.
- **US3 (P2)**: depende da Fase 2 (T008). Usa `match_sockets.py`, que já existe.
  Sem dependência de outra história.

### Within Each Phase

- Fase 2: testes (T006–T009) antes da implementação (T010–T014). T006 e T009
  falham até T010 e T013 existirem.
- T012 (divisão sem mudança de comportamento) fica verde sozinho antes de T013
  acrescentar o ramo do ping. É o que isola regressão da divisão de regressão do
  ping.
- Nas histórias, as tarefas de um mesmo arquivo seguem em ordem.

### Parallel Opportunities

- Fase 1: T003 em paralelo com T002.
- Fase 2: T006, T007, T008 e T010 em paralelo. T009 depois de T008. T011 depois de
  T010. T012 → T013 → T014 em sequência (mesmo arquivo, depois override).
- Depois da Fase 2: US1 (T016–T024), US2 (T025–T030) e US3 (T031–T035) em
  paralelo, cada uma no próprio arquivo.
- Fase 6: T037 e T038 em paralelo entre si e com T036.

---

## Parallel Example: Phase 2

```bash
# Testes e peças de apoio que não dependem de nada:
Task: "Criar server/apps/game/tests/test_heartbeat.py (T006)"
Task: "Criar server/apps/game/tests/access_counting_match_store.py (T007)"
Task: "Criar server/apps/game/tests/matchmaking_sockets.py (T008)"
Task: "Criar server/apps/game/protocol/heartbeat.py (T010)"
```

## Parallel Example: depois da Fase 2

```bash
# Uma história por arquivo:
Task: "US1 — server/apps/game/tests/test_match_consumer_heartbeat.py (T016–T024)"
Task: "US2 — server/apps/game/tests/test_matchmaking_heartbeat.py (T025–T030)"
Task: "US3 — server/apps/game/tests/test_heartbeat_echo.py (T031–T035)"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Fase 1: linha de base, fumaça pronta e comprovadamente vermelha.
2. Fase 2: regra pura, `receive` dividido, ping no ponto comum, gates.
3. Fase 3: US1 provada no socket de partida.
4. **Parar e validar**: `cd server && pytest` inteiro verde, nenhum teste
   existente alterado.

Como o código de produção fica pronto na Fase 2, o MVP já responde ping nos dois
sockets. O que a US1 sozinha entrega é a **prova** no socket onde a queda custa
a vez.

### Incremental Delivery

1. Setup + Foundational: os dois sockets respondem ping, os gates provados.
2. + US1: sem efeito na partida, provado em todas as fases.
3. + US2: sem efeito na fila, provado em todos os momentos.
4. + US3: eco provado nos dois sockets.
5. Polish: fumaça verde contra o servidor de verdade, vault atualizado, portas
   de qualidade.

### Commits sugeridos

- `style(scripts): apply black to the smoke match` (T002, sozinho)
- `test(scripts): ping both sockets during the smoke match` (T003–T004)
- `feat(game): answer application ping on both sockets` (T006–T015)
- `test(game): prove ping leaves match and queue untouched` (T016–T035)

---

## Notes

- [P] = arquivo diferente, sem dependência pendente.
- A presença (`set_heartbeat`, `heartbeat_key`, o ramo do `disconnect`) **não** é
  tocada por nenhuma tarefa. Apagá-la ou ligá-la é o item do `Backend/TODO.md`,
  não esta feature (research D5).
- Nenhuma tarefa altera teste existente. Se alguma parecer exigir isso, pare: é
  sinal de que o `receive` mudou comportamento para mensagem que não é ping.
