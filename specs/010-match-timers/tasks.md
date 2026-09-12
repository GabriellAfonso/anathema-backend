---

description: "Task list for 010-match-timers"
---

# Tasks: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Input**: Design documents from `specs/010-match-timers/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: obrigatórios (princípio V da constituição). Em cada história, os
testes vêm antes da implementação e falham antes dela.

**Organization**: a Parte 1 (US1) não depende de nada da Parte 2 e pode começar
logo depois do T001. A Parte 2 tem uma fundação grande de propósito, como a 009:
estado do relógio, índice de despertar, as funções puras e a costura do
consumer são o mesmo caminho para as seis histórias do relógio. Com a fundação
pronta, a US2 liga o ticker, e as outras histórias são conjuntos de testes que
provam um ângulo cada, com o ajuste que o teste exigir.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1 a US7, as histórias da [spec.md](./spec.md)

---

## Phase 1: Setup

- [X] T001 Rodar `cd server && pytest && mypy && black --check .` e a suíte com Redis no container (`docker compose run --rm --no-deps anathema_server sh -c "cd /server && pytest"`) e confirmar a base verde antes de mexer em qualquer arquivo

---

## Phase 2: Foundational (Blocking Prerequisites da Parte 2)

**Purpose**: o relógio gravado, o índice de despertar, as regras puras do relógio e o consumer costurado. Nenhuma história de relógio (US2–US7) começa antes disto. A US1 não depende desta fase.

- [X] T002 [P] Criar `server/apps/game/wall_clock.py` ([research.md D2](./research.md#d2-tempo-injetado-wallclock)): `EpochMillis = NewType("EpochMillis", int)`, `WallClock(Protocol)` com `now_ms() -> EpochMillis`, `SystemWallClock` com `time.time_ns() // 1_000_000`; cabeçalho no formato de `randomness.py` dizendo que é o único módulo que importa `time`. Criar `server/apps/game/tests/fake_wall_clock.py`: `FakeWallClock(start_ms: int = 1_000_000)` com `now_ms()`, `advance(seconds: float)` e `set_ms(ms: int)`, mais a asserção estática `FAKE_WALL_CLOCK_MATCHES_THE_PROTOCOL: WallClock = FakeWallClock()` com o comentário do `fake_random_source.py`. Testes em `server/apps/game/tests/test_wall_clock.py`: `SystemWallClock().now_ms()` fica entre `time.time_ns() // 1_000_000` lido antes e depois; `FakeWallClock.advance(1.5)` soma 1500
- [X] T003 Criar `server/apps/game/match/match_clock.py` ([data-model.md](./data-model.md#relógio-da-partida-matchmatch_clockpy)): `TurnDeadline` e `MatchClock` como `@dataclass(frozen=True, slots=True)`, `IDLE_MATCH_CLOCK`, e `clock_wake_at(clock: MatchClock) -> EpochMillis | None` pela tabela de despertar. Testes em `server/apps/game/tests/test_match_clock.py`: idle → `None`; só mulligan → o prazo dele; vez sem aviso → `warns_at_ms`; vez com aviso → `expires_at_ms`
- [X] T004 `Match.clock: MatchClock = IDLE_MATCH_CLOCK` em `server/apps/game/match/match_state.py` (comentário: estado de transporte, nunca lido pelo motor, [research.md D3](./research.md#d3-o-estado-do-relógio-mora-no-documento-da-partida)); `MatchClockDocument` e `TurnDeadlineDocument` obrigatórios em `server/apps/game/match/documents.py`; `to_match_clock_document` / `match_clock_from_document` em `server/apps/game/match/serialization.py`, reembrulhando os instantes em `EpochMillis`; exportar `MatchClock`, `TurnDeadline`, `IDLE_MATCH_CLOCK` e `clock_wake_at` em `server/apps/game/match/__init__.py`. Em `server/apps/game/tests/test_match_clock.py`: ida e volta por `json.dumps`/`json.loads` com relógio idle, com mulligan e com vez avisada. Ajustar os testes que comparam o documento inteiro (`grep -rln "to_match_document\|MatchDocument" server/apps/game/tests`) à chave `clock`
- [X] T005 Índice de despertar e expiração em `server/apps/game/match/store.py` ([research.md D5](./research.md#d5-índice-de-despertar-atômico-com-a-gravação), [D6](./research.md#d6-estouro-não-renova-a-expiração)): `wake_index_key(key_prefix) -> str` (`f"{key_prefix}:wake"`); `SAVE_SCRIPT` com `KEYS[2]` = índice e `ARGV[3]` = `match_id`, `ARGV[4]` = score ou `""`, fazendo `ZADD` ou `ZREM`; `SWAP_SCRIPT` com `KEYS[2]` = índice, `ARGV[3]` = TTL (`0` pula o `EXPIRE`), `ARGV[4]` = `match_id`, `ARGV[5]` = score ou `""`, tocando o índice só quando a troca é aceita; `mutate(match_id, change, *, renews_expiry: bool = True)`; o score vem de `clock_wake_at(match.clock)`. Atualizar o docstring do módulo. Em `server/apps/game/tests/test_match_store.py`: `save` grava o membro com o score; `mutate` que abre vez move o score; partida terminada remove o membro; swap recusado não toca o índice; `renews_expiry=False` preserva o `PTTL` (reduzir o TTL com `PEXPIRE` antes e conferir que não voltou a 6h); `renews_expiry=True` renova. Ajustar `AlwaysStaleMatchStore._swap_state` à assinatura nova
- [X] T006 [P] Criar `server/apps/game/match/wake_queue.py` ([research.md D7](./research.md#d7-ticker-por-worker-com-lease)): `ClaimedWake(match_id: str, lease_until_ms: EpochMillis)` frozen; `MatchWakeQueue(redis, key_prefix="match")` com três scripts Lua registrados — `claim_due(now, *, lease_ms, limit) -> list[ClaimedWake]` (`ZRANGEBYSCORE -inf now LIMIT 0 limit`, depois `ZADD XX now+lease` em cada), `release(claimed, wake_at: EpochMillis | None)` (só se `ZSCORE` ainda é `lease_until_ms`: `ZADD` com `wake_at` ou `ZREM`), `forget(match_id)` (`ZREM`). Testes Redis em `server/apps/game/tests/test_match_wake_queue.py`: vencido é reivindicado e não vencido não; reivindicado não volta antes do lease e volta depois; `limit` respeitado; `release` reagenda; `release` depois de uma gravação que mudou o score não sobrescreve; `forget` remove; duas `MatchWakeQueue` sobre o mesmo Redis reivindicando ao mesmo tempo (`asyncio.gather`) — cada membro sai para uma só
- [X] T007 [P] Portas do ticker e fakes: criar `server/apps/game/match_timers/__init__.py` (docstring do pacote, `__all__`) e `server/apps/game/match_timers/ports.py` com `TickerMatchStore(Protocol)` (`get_stored`, `mutate(match_id, change, *, renews_expiry)`) e `TickerWakeQueue(Protocol)` (`claim_due`, `release`, `forget`). Editar `server/apps/game/tests/fake_match_store.py`: construtor `FakeMatchStore(clock: WallClock | None = None)`; `mutate` com laço de `MUTATE_ATTEMPTS` que lê a versão, chama o gancho `async _between_read_and_write(match_id) -> None` (vazio aqui), aplica a mudança numa cópia e só grava se a versão não mudou; `renews_expiry` registrado em `self.expiry_renewals: list[bool]`; expiração: `save` e `mutate(renews_expiry=True)` marcam `expires_at_ms = clock.now_ms() + MATCH_TTL_SECONDS * 1000` quando há `clock`, e `get`/`get_stored`/`mutate` tratam a partida vencida como ausente; `wake_at: dict[str, EpochMillis]` mantido por `save`/`mutate` com `clock_wake_at`. Criar `server/apps/game/tests/fake_match_wake_queue.py`: `FakeMatchWakeQueue(store: FakeMatchStore)` operando sobre `store.wake_at` com a mesma semântica de lease, e asserções estáticas de conformidade às duas portas. Criar `server/apps/game/tests/interleaved_match_store.py`: `InterleavedMatchStore(FakeMatchStore)` que recebe `interloper: Callable[[], Awaitable[None]]` e o executa uma vez no gancho — a jogada concorrente com nome, no formato do `AlwaysStaleMatchStore`
- [X] T008 [P] Criar `server/apps/game/protocol/turn_clock.py` ([research.md D4](./research.md#d4-vez-nova-derivada-do-estado-depois-da-mudança)): `TURN_WARNING_MS = 30_000`, `TURN_EXPIRY_MS = 45_000`, `MULLIGAN_EXPIRY_MS = 30_000` com comentário citando a §12; `opening_match_clock(now) -> MatchClock`; `advance_match_clock(match, now) -> None` pela tabela de transições, em funções de até 20 linhas. Testes em `server/apps/game/tests/test_turn_clock.py`, montando estados com `fake_combat_board` e as ações reais do motor via `submit_action`: fim do mulligan abre a vez 1; jogar unidade e passar abrem vez nova do oponente; feitiço, declarar ataque, mandar mais, puxar um e puxar o último mantêm número e prazos; **Atacar** abre a vez do defensor; bloquear e remover mantêm; **Resolver** abre a vez do dono do token; dois passes abrem vez nova **com o mesmo dono** e rodada nova; desistência e Nexus a zero voltam a `IDLE_MATCH_CLOCK`; `MULLIGAN` não mexe no prazo
- [X] T009 [P] Criar `server/apps/game/protocol/clock_events.py` ([research.md D9](./research.md#d9-a-guarda-do-estouro-roda-dentro-da-mutação), [D10](./research.md#d10-a-ação-automática-é-a-da-fase-de-agora)): `TurnWarning`, `TurnExpiry`, `MulliganExpiry` frozen; `ClockEvent` e `ClockExpiry = TurnExpiry | MulliganExpiry`; `ClockEventNotDueError(match_id, event, now)` com mensagem citando o evento e o instante esperado; `due_clock_event(match, now) -> ClockEvent | None` (estouro antes de aviso; mulligan devolve o primeiro sem resposta); `ensure_clock_event_due(match, event, now) -> None`; `automatic_command(match, event: ClockExpiry) -> ClientCommand` com `match` e `assert_never`. Testes em `server/apps/game/tests/test_clock_events.py`: nada vencido; aviso aos 30 s; estouro aos 45 s; os dois vencidos dão estouro; mulligan com um e com os dois sem resposta; a guarda recusa `turn_number` diferente, prazo não vencido, aviso já mandado, mulligan já respondido e partida fora do mulligan; a ação é `PassAction`, `ConfirmAttackAction`, `EndDefenseWindowAction` e `MulliganCommand(user_id, ())` conforme a fase
- [X] T010 Criar `server/apps/game/protocol/match_changes.py` ([research.md D15](./research.md#d15-a-mudança-e-a-entrega-compartilhadas-entre-consumer-e-ticker)): mover `RecordedChange` de `server/apps/game/consumers/match.py` preservando os comentários; `PlayerChange(command, catalog, randomness, clock)` — guarda o antes, `apply_command`, `advance_match_clock(match, clock.now_ms())`; `ClockChange(event: ClockExpiry, catalog, randomness, now)` — guarda o antes, `ensure_clock_event_due`, `automatic_command`, guarda o comando em `applied_command`, `apply_command`, `advance_match_clock`; `TurnWarningMark(event: TurnWarning, now)` — `ensure_clock_event_due` e troca `match.clock` por uma cópia com `warning_sent=True` (`dataclasses.replace`). Testes em `server/apps/game/tests/test_match_changes.py`: o antes é o da última tentativa; `PlayerChange` de passe abre vez nova; `ClockChange` numa vez vencida aplica o passe e expõe o comando; `ClockChange` numa vez velha levanta `ClockEventNotDueError` sem mudar a partida; `TurnWarningMark` marca e não mexe em mais nada
- [X] T011 Frames e eventos ([research.md D12](./research.md#d12-clock-ao-lado-da-visão-e-o-frame-turn_warning), [D13](./research.md#d13-eventos-de-origem), [contracts/server_frames.md](./contracts/server_frames.md)): em `server/apps/game/protocol/match_events.py`, `TurnTimedOutEvent`, `MulliganTimedOutEvent`, `PlayerOrigin`, `ClockOrigin(event: ClockExpiry)`, `ChangeOrigin` e `origin_events(origin) -> list[MatchEvent]`, com `describe_change` intocada; em `server/apps/game/protocol/match_frames.py`, `TurnClockView`, `ClockView`, `TurnWarningPayload`, `clock_view(match, recipient_user_id, now)`, `turn_warning_payload(match, now)`, e `match_start_payload(match, version, user_id, now)` / `match_update_payload(before, after, version, command, user_id, *, origin, now)` com `clock` e os eventos de origem prefixados; exportar em `server/apps/game/protocol/__init__.py`. Testes em `server/apps/game/tests/test_match_events.py` (origem do socket não acrescenta nada; `turn_timed_out` antes de `passed`; `mulligan_timed_out` antes de `mulligan_taken`) e `server/apps/game/tests/test_match_frames.py` (`remaining_ms` e `warning` aos 20 s e aos 40 s; nunca negativo; `turn` nulo no mulligan e no fim; `mulligan_remaining_ms` só do destinatário e só sem resposta; nenhum campo com instante absoluto no frame serializado). Ajustar as chamadas existentes dos dois payloads nos testes
- [X] T012 Costura do consumer: criar `server/apps/game/consumers/match_delivery.py` com `ChannelGroupSender(Protocol)`, `MatchUpdateMessage` (movida de `consumers/match.py`), `TurnWarningMessage`, `deliver_match_update(channel_layer, before, stored, command, *, origin, now)` — um frame por jogador ao `MatchConsumer.user_group` dele — e `deliver_turn_warning(channel_layer, stored, now)` — só ao grupo do dono da vez. Em `server/apps/game/consumers/match.py`: `clock: WallClock | None = None` no construtor (default `SystemWallClock()`); `play` usa `PlayerChange` e `deliver_match_update(origin=PlayerOrigin())`; `send_match_start` passa `now`; handler `match_turn_warning` que confere `match_id` e manda `turn_warning`. Em `server/apps/game/tests/match_sockets.py`: `open_match_socket(..., clock: WallClock | None = None)` repassando ao `as_asgi` e `next_turn_warning(client) -> Frame`. Ajustar `server/apps/game/tests/test_match_consumer_state.py`, `test_match_consumer_play.py` e `test_match_consumer_flow.py` onde leem o payload inteiro
- [X] T013 [P] Extrair `_engine_sources` de `server/apps/game/tests/test_full_match.py` para `server/apps/game/tests/engine_sources.py` (`engine_sources() -> list[Path]`) e usá-lo lá; criar `server/apps/game/tests/test_engine_reads_no_time.py` ([research.md D17](./research.md#d17-o-motor-intocado-verificado)) que percorre os módulos com `ast` e falha se algum importa `time`, `datetime`, `apps.game.wall_clock` ou `apps.game.match.match_clock`, ou acessa um atributo chamado `clock`

**Checkpoint**: `pytest` e `mypy` verdes; o socket continua jogando como na 009, agora com `clock` nos frames; ninguém estoura ainda.

---

## Phase 3: User Story 1 - SACRIFICIAL FIRE sem alvo (Priority: P1) 🎯 MVP

**Goal**: o FIRE lançado sem alvo na declaração dá +3 a toda unidade da zona de ataque naquele instante; com alvo, é recusado.

**Independent Test**: com a declaração aberta e duas unidades na zona, lançar sem alvo e conferir +3 nas duas e o Nexus; mandar uma terceira e conferir que não tem +3; lançar com alvo e conferir `SpellTakesNoTargetError`.

**Pode começar logo depois do T001.** Não toca nada da Fase 2.

### Tests for User Story 1

- [X] T014 [US1] Em `server/apps/game/tests/fake_spell_board.py`: `open_declaration(match, *bank_indexes: int) -> CombatState` — atalho de estado, como `declare_combat` de `fake_combat_board.py`: `phase = DECLARATION`, `combat` com aquelas posições do banco do primeiro jogador, prioridade nele, `token_consumed` falso, passes zerados; exportar em `__all__`
- [X] T015 [P] [US1] Em `server/apps/game/tests/test_spell_effects.py`: `1003` passa a `(TargetKind.NONE, EffectDuration.PERMANENT)` na tabela; `needs_target` passa a `{1001, 1002, 1005}`; `test_only_sacrificial_fire_is_declaration_only` fica
- [X] T016 [P] [US1] Em `server/apps/game/tests/test_mvp_catalog.py`: `test_sacrificial_fire_description_names_the_whole_attack_zone` — a descrição do 1003 contém "zona de ataque" e não contém "alvo"
- [X] T017 [US1] Reescrever o bloco SACRIFICIAL FIRE de `server/apps/game/tests/test_spell_effect.py` sobre `fake_spell_board` + `open_declaration`, chamando `apply_spell_effect(..., None, ...)`: custo de 8; `test_fire_gives_three_attack_to_every_unit_in_the_attack_zone` (banco `(TOUGH_UNIT, FRAGILE_UNIT, TOUGH_UNIT)`, zona nas posições 0 e 2 → modificador nas duas e nada na 1); unidades do oponente intocadas; piso de 1; Nexus 1 ainda dá o bônus; nunca termina a partida (fase continua `DECLARATION`). Em `test_every_mvp_effect_has_an_arm`, abrir a declaração antes e passar `None` para o FIRE
- [X] T018 [US1] Reescrever `server/apps/game/tests/test_sacrificial_fire.py`: cabeçalho com a §14 corrigida (sem alvo, toda a zona, só na declaração, só o atacante, piso de 1); `declaring` aceita quantas unidades mandar; testes — sem alvo dá +3 às duas unidades mandadas e cobra 8, vez continua com o atacante; unidade mandada depois do FIRE (`DeclareAttackAction` com a terceira) fica sem modificador; alvo numa unidade da zona → `SpellTakesNoTargetError`; alvo em unidade própria fora da zona e em unidade do oponente → `SpellTakesNoTargetError`; puxar de volta uma unidade com bônus mantém o bônus; Nexus baixo deixa 1; Fase de Ação e defensor continuam `SpellOnlyInDeclarationError`, inclusive com alvo. Sai o teste de `SpellNeedsTargetError` e os imports de `UnitIsNotAttackingError`, `WrongSpellTargetSideError` e `TargetKind`. Confirmar que T015–T018 falham

### Implementation for User Story 1

- [X] T019 [US1] Em `server/apps/game/cards/effects.py`: tirar `ALLIED_ATTACKER` de `TargetKind` (e o comentário dele); `SacrificeNexusForAttack.target_kind = TargetKind.NONE`; reescrever o docstring com a regra da §14 corrigida e o doctest devolvendo `<TargetKind.NONE: 'none'>`, registrando que até esta feature o motor pedia alvo único
- [X] T020 [US1] Em `server/apps/game/engine/spell_cast_guards.py`: `_expected_owner` compara só com `TargetKind.ALLIED_UNIT`; remover `_ensure_attacking_when_asked` e a chamada em `_target_on_the_right_side`; remover o import de `UnitIsNotAttackingError`
- [X] T021 [US1] Em `server/apps/game/engine/spell_effect.py`: o braço `SacrificeNexusForAttack` chama `_sacrifice_nexus_for_attack(match, caster, effect)` sem `_targeted`; a função dá `AttackModifier(amount=effect.attack_bonus, duration=effect.duration)` a cada `match.bank_unit(...)` de `match.ongoing_combat().attacker_card_instance_ids` e só depois cobra `_affordable_nexus_cost`; docstring com a §14 corrigida e o porquê de ler a lista no instante (unidade mandada depois não ganha)
- [X] T022 [P] [US1] Em `server/apps/game/cards/mvp_catalog.py`: descrição do 1003 = "Só na declaração de ataque. Toda unidade aliada na zona de ataque ganha 3 de ataque, e você perde 8 de Nexus, sem cair abaixo de 1."
- [X] T023 [P] [US1] Em `server/apps/game/tests/test_spell_state_round_trip.py`: `fire_on_an_attacker` lança `CastSpellAction(one.user_id, hand_card(one, SACRIFICIAL_FIRE))` sem alvo e o docstring diz que o bônus vai a toda a zona
- [X] T024 [US1] Em `server/apps/game/tests/test_full_match.py` (depois do T013): atualizar o cabeçalho e o comentário de `SCRIPTED_SPELLS` — o FIRE fica fora do roteiro por ser só da declaração e sem alvo; o jogador automático não o reserva. Rodar o arquivo e confirmar verde

**Checkpoint**: `pytest server/apps/game/tests/test_sacrificial_fire.py server/apps/game/tests/test_spell_effect.py server/apps/game/tests/test_spell_effects.py server/apps/game/tests/test_mvp_catalog.py server/apps/game/tests/test_spell_state_round_trip.py server/apps/game/tests/test_full_match.py server/apps/game/tests/test_refusal_codes.py` verde e `mypy` limpo. A US1 é entregável sozinha.

---

## Phase 4: User Story 2 - A vez estoura sozinha: aviso aos 30s, ação automática aos 45s (Priority: P1)

**Goal**: o ticker existe, roda em todo worker, manda o aviso ao dono aos 30 s e aplica passar / **Atacar** / **Resolver** aos 45 s pelo mesmo caminho de toda jogada.

**Independent Test**: `ticker.tick(now)` com `FakeWallClock` em cada uma das três fases, conferindo o aviso só no socket do dono, a atualização nos dois sockets e `turn_timed_out` na descrição.

### Tests for User Story 2

- [X] T025 [US2] Criar `server/apps/game/tests/test_match_clock_ticker.py` com o arranjo comum (`FakeWallClock`, `FakeMatchStore(clock)`, `FakeMatchWakeQueue`, `get_channel_layer()` do `InMemoryChannelLayer`, sockets de `match_sockets.py` com o mesmo relógio) e os cenários da US2 da spec: aviso aos 30 s só nos sockets do dono (o oponente com `nothing_received`); estouro na Fase de Ação grava o passe, abre vez nova do oponente com 45 s, e os dois recebem `turn_timed_out` + `passed`; estouro na Declaração com duas unidades confirma o ataque com as duas; estouro na Defesa sem bloqueador resolve com tudo passando; com bloqueador, resolve com o bloqueio; estouro que dá o segundo passe chega como uma atualização já na rodada seguinte; **Resolver** automático que zera Nexus entrega a partida terminada e remove o membro do índice; vez que terminou aos 20 s não gera aviso aos 30 s. Cada tick antes do prazo não produz frame

### Implementation for User Story 2

- [X] T026 [US2] Criar `server/apps/game/match_timers/ticker.py` ([research.md D7](./research.md#d7-ticker-por-worker-com-lease), [D16](./research.md#d16-falhas-do-ticker)): `TICK_INTERVAL_SECONDS`, `WAKE_LEASE_MS`, `WAKE_BATCH_SIZE`; `MatchClockTicker(*, matches: TickerMatchStore, wake_queue: TickerWakeQueue, channel_layer: ChannelGroupSender, catalog, randomness, clock: WallClock)`; `async tick(now)` que reivindica e processa cada `ClaimedWake` isolando exceções por despertar; `async run()` com o laço e `asyncio.sleep`; o processamento de um despertar despachado com `match` sobre `ClockEvent` e `assert_never` — estouro por `mutate(ClockChange, renews_expiry=False)` e `deliver_match_update(origin=ClockOrigin(event))`, aviso por `mutate(TurnWarningMark, renews_expiry=False)` e `deliver_turn_warning`, `ClockEventNotDueError` e nada vencido por `release` com `clock_wake_at` do estado, partida ausente por `forget`, recusa do motor e falha inesperada em log JSON (`match_clock_refused`, `match_clock_contended`, `match_clock_failed`, `match_clock_fired`). Funções de até 20 linhas
- [X] T027 [US2] Criar `server/apps/game/match_timers/lifespan.py` ([research.md D8](./research.md#d8-o-lifespan-do-asgi-liga-o-ticker)): `MatchTimersLifespan(build_ticker: Callable[[], MatchClockTicker])`, app ASGI tipada com `asgiref.typing`, que em `lifespan.startup` cria a task de `run()` e responde `lifespan.startup.complete`, e em `lifespan.shutdown` cancela, espera e responde `lifespan.shutdown.complete`. Testes em `server/apps/game/tests/test_match_timers_lifespan.py` com `asgiref.testing.ApplicationCommunicator` e um `RecordingTicker` nomeado: startup chama `run`; shutdown cancela a task e responde completo
- [X] T028 [US2] Ligar em produção: `build_match_clock_ticker()` em `server/core/asgi.py` compondo `get_match_store()`, `MatchWakeQueue` sobre o mesmo cliente Redis do store, `get_channel_layer()`, `mvp_catalog()`, `SeededRandomSource()` e `SystemWallClock()`, e `"lifespan": MatchTimersLifespan(build_match_clock_ticker)` no `ProtocolTypeRouter`; expor o cliente Redis do store (ou uma `get_match_wake_queue()` com `@cache` em `server/apps/game/match/client.py`, reusando o mesmo `Redis.from_url`) e atualizar o docstring que cita `--lifespan off`; em `dockerfile` e `docker-compose.yml`, `--lifespan on`, trocando o comentário do `off` pelo do `on`

**Checkpoint**: T025 verde; `docker compose up` sobe sem `ValueError` de lifespan, e uma partida parada estoura sozinha.

---

## Phase 5: User Story 3 - O relógio é da vez, não da ação (Priority: P1)

**Goal**: provar pelo socket que só troca de mão e virada de rodada reiniciam o prazo.

**Independent Test**: jogadas espaçadas com `FakeWallClock.advance` e `ticker.tick`, conferindo `clock.turn.turn_number` e `remaining_ms` em cada `match_update` e o instante do estouro.

- [X] T029 [US3] Criar `server/apps/game/tests/test_match_consumer_clock.py` com os cenários da US3 da spec, jogando pelo socket e avançando o `FakeWallClock`: feitiço aos 40 s não reinicia, e o tick aos 45 s estoura; declarar aos 10 s, puxar aos 20 s, declarar aos 30 s, puxar aos 40 s → um só `turn_warning` e estouro aos 45 s do início; **Atacar** aos 20 s abre 45 s ao defensor; atribuir e remover bloqueador aos 10, 25 e 40 s → estouro aos 45 s do início da Defesa; **Resolver** aos 15 s abre vez nova do dono do token; B passando aos 44 s depois de A vira a rodada com `turn_number` novo em B e 45 s; estouro de B no segundo passe seguido de tick imediato não estoura de novo; jogar unidade aos 5 s dá 45 s ao oponente
- [X] T030 [US3] Se algum cenário do T029 falhar, corrigir em `server/apps/game/protocol/turn_clock.py` ou `server/apps/game/protocol/match_changes.py` (nunca no motor) e registrar a causa em "Registro da implementação" no fim deste arquivo

**Checkpoint**: T029 verde.

---

## Phase 6: User Story 4 - O relógio sobrevive a quem abandona, a workers e à corrida (Priority: P1)

**Goal**: estouro com o dono desconectado, com o worker que armou morto, contra a jogada real, e nunca numa vez que não é a dele.

**Independent Test**: dois tickers sobre o mesmo store fake, `InterleavedMatchStore` para as disputas, e Redis de verdade para o lease e a corrida repetida.

- [X] T031 [US4] Em `server/apps/game/tests/test_match_clock_ticker.py`, os cenários da US4 da spec: dono com todos os sockets fechados aos 5 s → estouro aos 45 s chega ao oponente; dois `MatchClockTicker` sobre o mesmo `FakeMatchStore`/`FakeMatchWakeQueue`, o primeiro só reivindica (chamar `claim_due` e não processar) e o segundo pega depois de `WAKE_LEASE_MS` → um estouro, uma atualização; `InterleavedMatchStore` com o passe do socket entrando entre a leitura e a gravação do estouro → um passe só, e o estouro não grava; estouro gravado antes do passe do socket → o socket recebe `not_your_priority`; feitiço entrando no meio do estouro na Declaração → os dois gravados, feitiço antes do **Atacar**; puxar a última unidade no meio → o estouro vê a Fase de Ação e passa; atribuir bloqueador no meio → **Resolver** com o bloqueio; `ClockChange` armada para a vez da rodada 3 aplicada na vez da rodada 4 do mesmo jogador → nada gravado, nenhum frame; dois ticks do mesmo instante em tickers diferentes → uma gravação
- [X] T032 [P] [US4] Em `server/apps/game/tests/test_match_wake_queue.py` (Redis): 100 repetições de `MatchStore.mutate` com `PlayerChange(PassAction)` e `mutate` com `ClockChange(TurnExpiry)` disparados juntos por `asyncio.gather` sobre uma vez vencida — em todas, exatamente um passe gravado (SC-004), `ClockEventNotDueError` ou `NotYourPriorityError` no perdedor, e o membro do índice no score da vez nova
- [X] T033 [US4] Se T031 ou T032 falharem, corrigir em `server/apps/game/match_timers/ticker.py`, `server/apps/game/match/wake_queue.py` ou `server/apps/game/protocol/match_changes.py` e registrar no fim deste arquivo

**Checkpoint**: T031 e T032 verdes.

---

## Phase 7: User Story 5 - Mulligan com relógio (Priority: P2)

**Goal**: 30 s por jogador desde a criação; estouro confirma sem troca; a segunda resposta por estouro abre a Rodada 1 com a vez 1.

**Independent Test**: partida criada pelo matchmaking com `FakeWallClock`, ticks aos 30 s com nenhuma, uma e as duas respostas.

- [X] T034 [US5] Em `server/apps/game/consumers/matchmaking.py` ([research.md D14](./research.md#d14-prazo-do-mulligan-na-criação)): `clock: WallClock | None = None` no construtor (default `SystemWallClock()`), e `open_match` faz `match.clock = opening_match_clock(self.clock.now_ms())` antes do `save`. No teste existente que instancia `MatchmakingConsumer.as_asgi` (`grep -rl "MatchmakingConsumer.as_asgi" server/apps/game/tests`), passar um `FakeWallClock` e conferir que a partida gravada tem `mulligan_expires_at_ms == now + 30_000`
- [X] T035 [US5] Em `server/apps/game/tests/test_match_clock_ticker.py`, os cenários da US5 da spec: A respondeu e B não → aos 30 s `mulligan_timed_out` + `mulligan_taken` com `swapped_count: 0` para B, partida na Rodada 1 com `clock.turn.turn_number == 1` e 45 s; nenhum respondeu → dois ticks confirmam os dois e a Rodada 1 abre; A respondeu aos 10 s → nada acontece a A; nenhum `turn_warning` antes dos 30 s; `InterleavedMatchStore` com o mulligan do socket de B entrando no meio do estouro → um mulligan só, e o do socket recebe `mulligan_already_taken` quando perde; A desistiu no mulligan → ticks aos 30 s não fazem nada e o membro sai do índice

**Checkpoint**: T034 e T035 verdes.

---

## Phase 8: User Story 6 - O cliente vê o prazo, e a reconexão vê o prazo real (Priority: P2)

**Goal**: `clock` em todo `match_start` e `match_update`, medido pelo servidor; reconexão com o tempo real.

**Independent Test**: conectar e reconectar em instantes diferentes da vez e do mulligan com `FakeWallClock`, lendo `payload["clock"]`.

- [X] T036 [US6] Em `server/apps/game/tests/test_match_consumer_clock.py`, os cenários da US6 da spec: B conecta aos 20 s da vez de A → `turn.holder_user_id == A`, `remaining_ms == 25_000`; A reconecta aos 40 s → `remaining_ms == 5_000` e `warning is True`; feitiço de A aos 25 s → `match_update` com `remaining_ms == 20_000` e o mesmo `turn_number`; mulligan aberto há 12 s com A respondido → B vê `mulligan_remaining_ms == 18_000` e A vê `null`; partida terminada → `turn` nulo e `mulligan_remaining_ms` nulo; `turn_warning` chega pelo socket do dono com `turn_number` e `remaining_ms == 15_000`; nenhum frame da partida contém chave terminada em `_at_ms`

**Checkpoint**: T036 verde.

---

## Phase 9: User Story 7 - O fim da partida para todo relógio, e a partida sem ninguém (Priority: P3)

**Goal**: nada de aviso ou estouro depois do fim; partida em que só há estouros expira 6h depois da última jogada real.

**Independent Test**: forfeit e Nexus a zero com prazos pendentes; `FakeMatchStore(clock)` avançando horas só com estouros; Redis de verdade para o TTL.

- [X] T037 [US7] Em `server/apps/game/tests/test_match_clock_ticker.py`, os cenários da US7 da spec: B desiste aos 20 s da vez de A → tick aos 45 s não produz frame e o membro não está no índice; **Resolver** que zera Nexus → nenhum tick posterior produz frame; partida sem socket, última jogada real há 5h, ticks de estouro por mais de 1h → `get_stored` devolve `None` às 6h da última jogada real e o tick seguinte chama `forget`; B joga enquanto as vezes de A estouram → cada jogada de B renova (`expiry_renewals` com `True`) e cada estouro não (`False`); partida só com estouros desde a criação some 6h depois da criação
- [X] T038 [P] [US7] Em `server/apps/game/tests/test_match_wake_queue.py` (Redis): `MatchStore` + `MatchWakeQueue` + `MatchClockTicker` com `InMemoryChannelLayer` e `FakeWallClock` — estouro processado não altera o `PTTL` da chave da partida (SC-012); depois de `DEL` na chave (a expiração simulada), o tick remove o membro do índice

**Checkpoint**: T037 e T038 verdes.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T039 Rodar `cd server && pytest && mypy && black --check .` e a suíte com Redis no container; registrar as contagens no fim deste arquivo
- [X] T040 [P] Conferir limites (≤500 linhas por arquivo, 4–20 por função nova, 2 níveis de indentação) em `server/apps/game/match_timers/`, `server/apps/game/protocol/`, `server/apps/game/match/store.py`, `server/apps/game/match/wake_queue.py` e `server/apps/game/consumers/match.py`, dividindo o que passar
- [X] T041 [P] Conferir [quickstart.md](./quickstart.md), [contracts/server_frames.md](./contracts/server_frames.md), [contracts/client_messages.md](./contracts/client_messages.md) e [data-model.md](./data-model.md) contra o implementado, corrigindo o documento onde divergir
- [X] T042 [P] Conferir que nenhum comentário existente foi apagado nos arquivos movidos ou editados (`git diff dev -- server/apps/game/consumers/match.py server/apps/game/protocol/match_changes.py server/apps/game/engine/ server/apps/game/cards/`), e que os docstrings de `server/apps/game/engine/__init__.py` e `server/apps/game/cards/effects.py` ainda descrevem o SACRIFICIAL FIRE e a §15 corretamente

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: nada antes
- **US1 (T014–T024)**: só T001; T024 depois de T013 se a Fase 2 estiver em andamento (mesmo arquivo)
- **Foundational (T002–T013)**: T001; bloqueia US2–US7
- **US2 (T025–T028)**: Fase 2
- **US3, US4, US5, US6, US7**: Fase 2 e US2 (todas usam o ticker)
- **Polish (T039–T042)**: todas as histórias desejadas

### Dentro da Fase 2

- T002 → T003 → T004 → {T005, T008, T009}
- T005 → {T006, T007}
- {T008, T009} → T010
- {T004, T009} → T011
- {T007, T010, T011} → T012
- T013 independente de tudo na fase

### Dentro das histórias

- US1: T014 → T017; {T015, T016, T017, T018} falhando → T019 → T020 → T021; T022 e T023 em paralelo com T019–T021
- US2: T025 → T026 → T027 → T028
- US3, US4, US5, US6, US7 escrevem em `test_match_clock_ticker.py` ou `test_match_consumer_clock.py`: sequenciais entre si na prática

### Parallel Opportunities

- US1 inteira em paralelo com a Fase 2
- Fase 2: T002 e T013; depois T005, T008 e T009; depois T006 e T007
- US4: T032 (Redis) em paralelo com T031
- US7: T038 (Redis) em paralelo com T037
- Polish: T040, T041 e T042

---

## Parallel Example: Fase 2 depois do T004

```bash
Task: "T005 Índice de despertar e expiração em server/apps/game/match/store.py"
Task: "T008 advance_match_clock em server/apps/game/protocol/turn_clock.py"
Task: "T009 due_clock_event e automatic_command em server/apps/game/protocol/clock_events.py"
```

## Parallel Example: User Story 1

```bash
Task: "T015 Tabela de alvo do 1003 em server/apps/game/tests/test_spell_effects.py"
Task: "T016 Descrição do FIRE em server/apps/game/tests/test_mvp_catalog.py"
Task: "T022 Descrição nova em server/apps/game/cards/mvp_catalog.py"
Task: "T023 fire_on_an_attacker sem alvo em server/apps/game/tests/test_spell_state_round_trip.py"
```

---

## Implementation Strategy

### MVP

1. T001
2. **US1** (T014–T024): correção de regra entregável sozinha, commit próprio
3. Fase 2 (T002–T013): o socket continua como na 009, com `clock` nos frames
4. **US2** (T025–T028): o relógio roda — é o MVP da Parte 2
5. Parar e validar pelo [quickstart.md](./quickstart.md), passos 1 a 5

### Incremental Delivery

1. US3 e US4 fecham as garantias P1 (relógio que não reinicia, abandono, workers, corrida)
2. US5 e US6 (P2): mulligan e o que o cliente vê
3. US7 (P3): fim e partida abandonada
4. Polish

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- Nenhuma tarefa altera regra do motor fora da US1
- Fakes novos têm nome e asserção de conformidade ao `Protocol` que imitam
- Commit por tarefa ou grupo lógico, com a mensagem terminando nas linhas de atribuição da sessão

## Registro da implementação (2026-09-11)

**Portas**: 867 testes locais (mais 52 erros de conexão, dos arquivos que só
rodam com Redis), 919 no container com Redis, mypy limpo em 194 arquivos, black
limpo. A base antes desta feature tinha 749 testes locais.

**Divergências do plano, e por quê**

- `match_timers/ports.py` ganhou um terceiro protocolo, `RunnableTicker`: o
  ciclo de vida só precisa de `run()`, e pedir `MatchClockTicker` faria o fake
  do teste de lifespan carregar Redis e channel layer para nada.
- `test_match_clock_ticker.py` passou de 500 linhas e foi dividido, como a
  constituição manda: o aviso e o estouro ficaram nele, o que o relógio aguenta
  (desconexão, workers, corridas, mulligan, abandono) foi para
  `test_match_clock_resilience.py`, e os passos comuns para `clock_boards.py` --
  mesmo papel de `match_sockets.py`.
- `MatchConsumer.user_group` passou a delegar a `match_delivery.match_user_group`.
  O ticker entrega ao mesmo grupo e não tem consumer de onde chamar a fórmula;
  duas cópias dela seriam duas verdades sobre um endereço.
- `match/client.py` ganhou `get_match_wake_queue()` e um `_match_redis()`
  cacheado: o índice e o store falam com a mesma base, e dois clientes seriam
  dois pools sem motivo.
- `test_matchmaking_clock.py` é arquivo novo. A tarefa previa ajustar um teste
  existente do `MatchmakingConsumer`, e não existia nenhum.
- `engine_sources.py` foi extraído de `test_full_match.py` para as duas
  varreduras do motor não repetirem a lista de arquivos.

**Achados**

- O teste do lifespan precisa mandar startup e shutdown em mensagens separadas,
  com uma volta do laço de eventos entre elas: enfileiradas juntas, a task do
  ticker é cancelada antes de chegar a rodar, e o teste reprovaria o que em
  produção funciona.
- `advance_match_clock` não toca no relógio durante o mulligan, e isso está
  certo -- o prazo lá é por jogador. Um teste do índice tinha partido da
  premissa errada e foi corrigido, não o código.
- Nenhum cenário da US4 exigiu correção no ticker, na fila ou nas mudanças
  (T033): a guarda dentro da mutação e o compare-and-swap deram conta das
  corridas na primeira tentativa.

**Deploy**

- `dockerfile` e `docker-compose.yml` passaram a `--lifespan on`, e o
  `ProtocolTypeRouter` ganhou a chave `lifespan`. Com `off`, nenhuma partida
  parada estoura.
- Partidas gravadas antes deste deploy não têm `clock` no documento e deixam de
  ser lidas. Sem produção, o TTL de 6h as limpa.
