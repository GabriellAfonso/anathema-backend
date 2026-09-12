# Research: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Feature**: `010-match-timers` | **Date**: 2026-09-11

Nenhuma dúvida técnica ficou aberta. A única decisão de produto — o que encerra
uma partida em que ninguém joga — foi respondida na spec (opção A). Abaixo, as
decisões e o que foi descartado.

---

## D1. SACRIFICIAL FIRE sem alvo

**Decision**: `SacrificeNexusForAttack.target_kind = TargetKind.NONE`, e
`TargetKind.ALLIED_ATTACKER` sai do enum. Em `spell_cast_guards.py`,
`_expected_owner` volta a conhecer só `ALLIED_UNIT`, e
`_ensure_attacking_when_asked` sai — com ela o import de
`UnitIsNotAttackingError`, que continua existindo em `blocker_pairing.py`.

Em `spell_effect.py`, o braço do FIRE deixa de pedir `_targeted` e chama
`_sacrifice_nexus_for_attack(match, caster, effect)`, que:

1. lê `match.ongoing_combat().attacker_card_instance_ids` — o combate existe,
   porque a guarda de momento já exigiu a Declaração;
2. acrescenta `AttackModifier(amount=3, duration=effect.duration)` a cada
   `match.bank_unit(...)` dessa lista;
3. só então cobra `_affordable_nexus_cost`.

A lista é lida no instante do efeito, então uma unidade mandada depois não
ganha nada (FR-003) sem nenhuma marca a guardar.

A recusa de alvo a mais já existe: `_validated_target` recusa com
`SpellTakesNoTargetError` (`spell_takes_no_target`) todo feitiço `NONE` que
recebe alvo, antes de olhar o alvo. A guarda de momento vem antes da de alvo,
então o FIRE com alvo fora da Declaração continua recebendo
`spell_only_in_declaration`.

Descrição nova em `mvp_catalog.py`: "Só na declaração de ataque. Toda unidade
aliada na zona de ataque ganha 3 de ataque, e você perde 8 de Nexus, sem cair
abaixo de 1."

Testes que mudam de expectativa: `test_sacrificial_fire.py` (cabeçalho, alvo,
recusa de alvo), `test_spell_effect.py` (o braço sem alvo, várias unidades na
zona), `test_spell_effects.py` (`target_kind` do 1003), `test_mvp_catalog.py`
(descrição), `fake_spell_board.py`, `test_full_match.py` e
`test_spell_state_round_trip.py` (`fire_on_an_attacker` lança sem alvo).

**Alternatives considered**: manter `ALLIED_ATTACKER` sem uso (descartado: tipo
de alvo sem feitiço é estado que nenhum teste exercita, e a spec pede que saia);
guardar no combate quem estava na zona no lançamento (descartado: o efeito é
imediato, e a lista do instante já é a resposta).

---

## D2. Tempo injetado: `WallClock`

**Decision**: `apps/game/wall_clock.py`, no formato de `randomness.py`, e único
módulo do projeto que importa `time`:

- `EpochMillis = NewType("EpochMillis", int)`
- `class WallClock(Protocol): def now_ms(self) -> EpochMillis`
- `class SystemWallClock` — `time.time_ns() // 1_000_000`

`tests/fake_wall_clock.py`: `FakeWallClock(start_ms)` com `advance(seconds)` e
a asserção estática de conformidade ao `Protocol`, como o
`ScriptedRandomSource`.

Milissegundos inteiros desde a época: atravessam o JSON sem conversão, somam
sem fuso, e cabem exatos no score de um sorted set (double até 2⁵³).

**Alternatives considered**: `datetime` com fuso (descartado: precisa de
conversão na ida e na volta do documento e do score); `time.monotonic`
(descartado: não é comparável entre processos, e o prazo é compartilhado entre
workers); `TIME` do Redis como autoridade (descartado: o instante precisa estar
disponível dentro da mudança síncrona de `mutate`, e hoje todos os workers rodam
no mesmo host — registrado como caminho se houver hosts sem NTP).

---

## D3. O estado do relógio mora no documento da partida

**Decision**: `apps/game/match/match_clock.py`:

```text
TurnDeadline(frozen)
  turn_number: int         ≥ 1, cresce 1 a cada vez nova
  holder_user_id: int
  round_number: int
  warns_at_ms: EpochMillis
  expires_at_ms: EpochMillis
  warning_sent: bool

MatchClock(frozen)
  turn: TurnDeadline | None
  mulligan_expires_at_ms: EpochMillis | None
```

`Match.clock: MatchClock`, com default `IDLE_MATCH_CLOCK` (os dois `None`):
`start_match` do motor continua construindo `Match` sem saber que o campo
existe. O documento ganha `clock: MatchClockDocument`, obrigatório.

Nenhum módulo de `engine/` lê ou escreve `clock`. Quem escreve é o transporte,
dentro da mudança de `mutate`.

**Alternatives considered**: campo separado no hash do Redis (descartado: o
`mutate` precisaria ler e gravar dois campos, e a atomicidade com o estado
teria de ser refeita à mão); um estado só do ticker em memória (descartado:
morre com o worker, FR-030); `asyncio.sleep` por vez no worker que gravou
(descartado: morre com o worker e com a conexão).

---

## D4. Vez nova derivada do estado depois da mudança

**Decision**: `protocol/turn_clock.py`:

```text
TURN_WARNING_MS  = 30_000   # §12: 30s
TURN_EXPIRY_MS   = 45_000   # §12: 30s + 15s
MULLIGAN_EXPIRY_MS = 30_000 # §12

opening_match_clock(now) -> MatchClock          # mulligan_expires_at = now + 30s
advance_match_clock(match, now) -> None         # troca match.clock se preciso
```

`advance_match_clock`, chamada no fim de **toda** mudança:

| Estado depois | Relógio |
|---|---|
| `FINISHED` | `IDLE_MATCH_CLOCK` |
| `MULLIGAN` | inalterado |
| `ACTION`, `DECLARATION`, `COMBAT`, e `turn` é `None` ou `(holder_user_id, round_number) != (priority_user_id, round_number)` | vez nova: `turn_number` seguinte (ou 1), aviso em `now + 30s`, estouro em `now + 45s`, `warning_sent = False`; `mulligan_expires_at_ms = None` |
| as mesmas fases, com o par igual | inalterado |

A spec define vez nova como "outro jogador ou outra rodada". O par
`(dono, rodada)` é literalmente isso. Uma mudança só pode tirar a vez de alguém
e devolver na mesma rodada se passar por outro jogador, e toda mudança é
avaliada sozinha — então o par nunca esconde uma troca.

Transições conferidas contra o motor: jogar unidade e passar trocam o dono;
**Atacar** passa ao defensor; **Resolver** devolve ao dono do token, que é o
atacante; o segundo passe vira a rodada e devolve a vez a quem passou (a §8
troca o token para ele e a §4 dá a prioridade ao dono do token) — muda a
rodada; declarar ataque e puxar o último atacante ficam no mesmo dono e na
mesma rodada.

**Alternatives considered**: lista de ações que reiniciam (descartado: a
virada de rodada vem de uma cascata, não de uma ação, e a lista teria de
conhecer a §4 e a §8); comparar o antes e o depois da mutação (descartado: o
relógio gravado já é o antes, e não precisa de cópia).

---

## D5. Índice de despertar atômico com a gravação

**Decision**: sorted set `match:wake` (com o `key_prefix` do store), membro
`match_id`, score = `clock_wake_at(match.clock)`:

| Relógio | Score |
|---|---|
| `turn` com `warning_sent = False` | `warns_at_ms` |
| `turn` com `warning_sent = True` | `expires_at_ms` |
| só `mulligan_expires_at_ms` | ele |
| nenhum dos dois | membro removido |

`SAVE_SCRIPT` e `SWAP_SCRIPT` recebem a chave do índice e o score (ou `-1` para
remover), e fazem `ZADD`/`ZREM` na mesma execução Lua que faz o `HSET`. O swap
só toca o índice quando a troca é aceita.

`clock_wake_at` é pura e mora em `match_clock.py`: o store já conhece `Match`
pela serialização, e o score é derivado do estado que ele está gravando.

**Alternatives considered**: `ZADD` depois do `mutate` devolver (descartado: um
worker que morre entre a gravação e o `ZADD` deixa uma vez que nunca estoura);
varrer as chaves de partida (descartado: `SCAN` em todo o DB a cada volta);
reagendar só no ticker (descartado: a vez aberta por uma jogada precisa do
despertar dela na hora, não na próxima passada).

---

## D6. Estouro não renova a expiração

**Decision**: `MatchStore.mutate(match_id, change, *, renews_expiry: bool = True)`.
O `SWAP_SCRIPT` recebe o TTL em `ARGV`; quando `renews_expiry` é falso recebe `0`
e pula o `EXPIRE`. `HSET` numa chave existente preserva o TTL que ela tem.

Jogada, mulligan e desistência do socket usam o default. `ClockChange` e a marca
de aviso passam `renews_expiry=False`. A criação (`save`) sempre define o TTL.

A partida expira; o membro do índice fica. O ticker encontra a partida ausente e
remove o membro (FR-034a).

`FakeMatchStore` guarda, por partida, o instante em que expira segundo um
`WallClock` injetado, e `get_stored` devolve `None` depois dele.

**Alternatives considered**: não gravar nada no estouro (impossível: o estouro é
uma jogada gravada); um campo "última jogada real" com expiração lógica
(descartado: duplicaria o TTL que o Redis já faz).

---

## D7. Ticker por worker, com lease

**Decision**: `match_timers/ticker.py`:

```text
TICK_INTERVAL_SECONDS = 0.5
WAKE_LEASE_MS = 5_000
WAKE_BATCH_SIZE = 50

MatchClockTicker(matches, wake_queue, channel_layer, catalog, randomness, clock)
  async run()        # laço: tick(clock.now_ms()), sleep(TICK_INTERVAL_SECONDS)
  async tick(now)    # reivindica e processa os vencidos
```

`match/wake_queue.py`, `MatchWakeQueue(redis, key_prefix)`:

- `claim_due(now, lease_ms, limit) -> list[ClaimedWake]` — Lua:
  `ZRANGEBYSCORE key -inf now LIMIT 0 limit`, e para cada um
  `ZADD key XX now+lease member`. `ClaimedWake(match_id, lease_until_ms)`.
- `release(claimed, wake_at) -> None` — Lua: só se o score ainda é
  `lease_until_ms`, faz `ZADD` com `wake_at` ou `ZREM` se `None`. Se o score
  mudou, uma gravação reagendou no meio e ela vale.
- `forget(match_id) -> None` — `ZREM`, para partida que expirou.

Processar um despertar:

1. `get_stored`; ausente → `forget`.
2. `due_clock_event(match, now)`; nada vencido → `release` com o score do estado.
3. `TurnExpiry` ou `MulliganExpiry` → `mutate(ClockChange, renews_expiry=False)`
   e entrega da atualização com origem relógio. A gravação reescreve o score, e
   o lease some com ela.
4. `TurnWarning` → `mutate(marca warning_sent, renews_expiry=False)` e entrega
   do aviso.
5. `ClockEventNotDueError` → `release` com o score do estado relido.

O lease não protege estado — quem protege é o compare-and-swap. Ele só evita
que quatro workers façam o mesmo trabalho ao mesmo tempo. Um worker que morre
depois de reivindicar atrasa o evento em até 5 s; o próximo worker o pega.

**Alternatives considered**: um processo separado (`manage.py run_match_clock`)
num serviço próprio do compose (descartado: um ponto único de falha a mais para
implantar, quando quatro workers já estão de pé e dão redundância de graça);
`BZPOPMIN` bloqueante (descartado: remove o membro antes de processar, e um
worker que morre perde o evento); trava por partida com tempo de vida
(descartado pelo mesmo argumento de `store.py`: o tempo de vida é uma segunda
coisa a acertar).

---

## D8. O lifespan do ASGI liga o ticker

**Decision**: `match_timers/lifespan.py`, `MatchTimersLifespan(build_ticker)`:
uma app ASGI que responde ao escopo `lifespan`. Em `lifespan.startup` cria a
task de `ticker.run()` e responde `startup.complete`; em `lifespan.shutdown`
cancela a task, espera, e responde `shutdown.complete`.

`core/asgi.py` acrescenta `"lifespan": MatchTimersLifespan(build_match_clock_ticker)`
ao `ProtocolTypeRouter`. `build_match_clock_ticker` é a composição: lê
`get_match_store()`, `get_channel_layer()`, `mvp_catalog()`,
`SeededRandomSource()` e `SystemWallClock()` uma vez.

`dockerfile` e `docker-compose.yml` trocam `--lifespan off` por
`--lifespan on`, e o comentário que explica o `off` dá lugar ao que explica o
`on`. O docstring de `get_match_store` que cita `--lifespan off` é atualizado.
Com `--workers 4`, cada worker roda o seu ticker; com `--reload`, um.

**Alternatives considered**: iniciar o ticker na primeira conexão de socket
(descartado: um worker sem conexão não processaria nada, e a spec quer estouro
com todo mundo desconectado).

---

## D9. A guarda do estouro roda dentro da mutação

**Decision**: `protocol/clock_events.py`:

```text
TurnExpiry(turn_number, holder_user_id)
TurnWarning(turn_number, holder_user_id)
MulliganExpiry(user_id)
ClockEvent = TurnExpiry | TurnWarning | MulliganExpiry

due_clock_event(match, now) -> ClockEvent | None
ensure_clock_event_due(match, event, now) -> None   # levanta ClockEventNotDueError
```

`due_clock_event`: estouro da vez tem precedência sobre aviso (vencidos os dois,
pula o aviso); mulligan devolve o primeiro jogador que não respondeu.

`ensure_clock_event_due`, rodada sobre a leitura fresca de cada tentativa:

- vez: `clock.turn` existe, `turn_number` é o armado, e `now ≥` o instante do
  evento; para o aviso, também `warning_sent` falso;
- mulligan: fase `MULLIGAN`, o jogador ainda não respondeu, e
  `now ≥ mulligan_expires_at_ms`.

`ClockEventNotDueError` não é `IllegalActionError`: nunca chega a cliente, e o
teste que varre o catálogo de códigos não o encontra.

Corridas, todas por este mecanismo mais o compare-and-swap:

| Disputa | Resultado |
|---|---|
| jogada que termina a vez vence | o estouro relê, a vez mudou, não grava |
| estouro vence | a jogada relê e recebe a recusa de sempre (`not_your_priority`, `mulligan_already_taken`) |
| feitiço, mandar/puxar, bloqueio vence | a vez é a mesma; o estouro grava em seguida |
| estouro atrasado para vez velha | `turn_number` diferente, não grava |
| dois workers no mesmo estouro | um grava; o outro relê a vez nova e não grava |

**Alternatives considered**: guardar no índice o `turn_number` junto do membro
(descartado: o membro mudaria a cada vez, e a gravação precisaria remover o
antigo); conferir a vez só antes do `mutate` (descartado: a retentativa do
compare-and-swap aplicaria o estouro sobre um estado que ele não armou).

---

## D10. A ação automática é a da fase de agora

**Decision**: `automatic_command(match, event) -> ClientCommand`, dentro da
mesma tentativa que passou pela guarda:

| Evento | Fase | Comando |
|---|---|---|
| `TurnExpiry` | `ACTION` | `PassAction(holder)` |
| `TurnExpiry` | `DECLARATION` | `ConfirmAttackAction(holder)` |
| `TurnExpiry` | `COMBAT` | `EndDefenseWindowAction(holder)` |
| `MulliganExpiry` | `MULLIGAN` | `MulliganCommand(user_id, ())` |

Aplicado por `apply_command`, a mesma função do socket. O fim do setup na
segunda resposta e a cascata da virada de rodada vêm de graça.

---

## D11. Aviso: marca gravada, frame depois

**Decision**: o aviso grava `warning_sent = True` (sem renovar a expiração) e só
então manda o frame. A gravação move o score para `expires_at_ms`. Uma jogada
aos 40 s não reabre o aviso, porque `warning_sent` já está gravado.

A gravação cria uma versão sem `match_update`. O contrato da 009 só pede que a
versão cresça; o cliente compara versões para ordenar e não conta com
continuidade.

Um worker que morre entre a gravação e o frame perde o aviso daquela vez. O
estouro não se perde, e a reconexão vê o tempo restante.

**Alternatives considered**: mandar e depois gravar (descartado: um worker que
perde a disputa com uma jogada que troca a vez teria mandado aviso de vez que
já terminou); não gravar a marca e mover só o score (descartado: toda gravação
reescreve o score a partir do estado, e uma jogada aos 40 s traria o aviso de
volta).

---

## D12. `clock` ao lado da visão, e o frame `turn_warning`

**Decision**: `protocol/match_frames.py`:

```text
TurnClockView     = { turn_number, holder_user_id, remaining_ms, warning: bool }
ClockView         = { turn: TurnClockView | None, mulligan_remaining_ms: int | None }
MatchStartPayload = { version, view, clock }
MatchUpdatePayload= { version, view, events, clock }
TurnWarningPayload= { turn_number, holder_user_id, remaining_ms }
```

`remaining_ms = max(expires_at_ms - now, 0)`, com `now` lido na montagem de cada
frame. `warning = remaining_ms ≤ 15_000`, derivado e não lido de `warning_sent`:
quem reconecta aos 40 s vê o aviso valendo mesmo que o frame tenha se perdido.

`mulligan_remaining_ms` é do destinatário: número enquanto a fase é `MULLIGAN` e
ele não respondeu; `None` em qualquer outro caso.

`build_player_view` não muda: a visão é derivada da partida, e o tempo restante
não é da partida — é da partida **e** do instante. Mesmo argumento que tirou a
`version` de dentro da visão na 009.

`turn_warning` sai só para o grupo de usuário do dono da vez, pela mensagem de
channel layer `match.turn_warning` com `match_id`; o handler do consumer confere
o `match_id`, como `match_update` já faz.

---

## D13. Eventos de origem

**Decision**: `match_events.py` ganha dois eventos, prefixados à lista quando a
mudança veio do relógio:

- `{"kind": "turn_timed_out", "user_id", "turn_number"}` antes de `passed`,
  `attack_confirmed` ou `defense_ended`;
- `{"kind": "mulligan_timed_out", "user_id"}` antes de `mulligan_taken`.

`ChangeOrigin = PlayerOrigin | ClockOrigin(event)` chega a
`match_update_payload`, que monta
`origin_events(origin) + describe_change(...)`. `describe_change` não muda.
Jogada do socket continua produzindo exatamente a lista de hoje (FR-018).

**Alternatives considered**: campo `origin` em todo evento de jogada
(descartado: onze `TypedDict` mudariam para um caso só); campo `origin` no topo
do payload (descartado: mudaria a forma de todo `match_update`, e o evento já é
o lugar onde o cliente lê "o que aconteceu").

---

## D14. Prazo do mulligan na criação

**Decision**: `MatchmakingConsumer` recebe `clock: WallClock` por `as_asgi`, e
`open_match` faz `match.clock = opening_match_clock(clock.now_ms())` antes do
`save`. O `save` já grava o índice com esse prazo.

---

## D15. A mudança e a entrega, compartilhadas entre consumer e ticker

**Decision**:

- `protocol/match_changes.py` — `RecordedChange` sai de `consumers/match.py`.
  `PlayerChange(command, catalog, randomness, clock)` guarda o antes, aplica o
  comando e chama `advance_match_clock`. `ClockChange(event, catalog, randomness,
  now)` guarda o antes, passa pela guarda, escolhe o comando, aplica e chama
  `advance_match_clock`; expõe `applied_command` para a descrição.
  `TurnWarningMark(event, now)` passa pela guarda e marca `warning_sent`.
- `consumers/match_delivery.py` — `deliver_match_update(channel_layer, before,
  stored, command, origin, now)` e `deliver_turn_warning(channel_layer, stored,
  now)`. Os dois endereçam `MatchConsumer.user_group`, nunca o grupo da partida.

---

## D16. Falhas do ticker

**Decision**:

| Situação | Efeito | Log |
|---|---|---|
| partida ausente | `forget` | não |
| `ClockEventNotDueError` | `release` com o score do estado | não |
| recusa do motor à ação automática | nenhuma gravação, nenhum frame; `release` com o score do estado | `match_clock_refused`, JSON, `error` |
| `ConcurrentMatchWriteError` | lease vence, outro tick tenta | `match_clock_contended`, JSON |
| qualquer outra exceção num despertar | o despertar seguinte da volta continua; o laço não morre | `match_clock_failed`, JSON com traceback |
| estouro aplicado | entrega | `match_clock_fired`, JSON, `info` |

Uma recusa do motor que se repita volta a ser tentada a cada vez que o score
vence — o log repetido é o sinal do bug, e a partida não é alterada.

---

## D17. O motor intocado, verificado

**Decision**: `test_engine_reads_no_time.py` percorre os módulos de
`apps/game/engine/` com `ast` e falha se algum importa `time`, `datetime`,
`apps.game.wall_clock` ou `apps.game.match.match_clock`, ou lê o atributo
`clock`. É a forma verificável de FR-040.
