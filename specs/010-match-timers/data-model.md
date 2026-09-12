# Data Model: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Feature**: `010-match-timers` | **Date**: 2026-09-11

## Parte 1 — SACRIFICIAL FIRE (`cards/effects.py`)

| Campo | Antes | Depois |
|---|---|---|
| `SacrificeNexusForAttack.target_kind` | `ALLIED_ATTACKER` | `NONE` |
| `SacrificeNexusForAttack.declaration_only` | `True` | `True` |
| `TargetKind` | `NONE`, `ALLIED_UNIT`, `ENEMY_UNIT`, `ALLIED_ATTACKER` | `NONE`, `ALLIED_UNIT`, `ENEMY_UNIT` |

Efeito: para cada `card_instance_id` em `combat.attacker_card_instance_ids` no
instante, `AttackModifier(amount=3, duration=PERMANENT)` na unidade; depois
`nexus = max(nexus - 8, 1)`.

## Tempo (`wall_clock.py`)

| Nome | Forma |
|---|---|
| `EpochMillis` | `NewType` de `int`, milissegundos desde a época |
| `WallClock` | `Protocol`: `now_ms() -> EpochMillis` |
| `SystemWallClock` | `time.time_ns() // 1_000_000` |

## Relógio da partida (`match/match_clock.py`)

```text
TurnDeadline (frozen)
  turn_number: int            ≥ 1; +1 a cada vez nova da partida
  holder_user_id: int         quem deve a jogada
  round_number: int           a rodada em que a vez abriu
  warns_at_ms: EpochMillis    abertura + 30_000
  expires_at_ms: EpochMillis  abertura + 45_000
  warning_sent: bool

MatchClock (frozen)
  turn: TurnDeadline | None
  mulligan_expires_at_ms: EpochMillis | None

IDLE_MATCH_CLOCK = MatchClock(turn=None, mulligan_expires_at_ms=None)
```

`Match.clock: MatchClock = IDLE_MATCH_CLOCK`.

### Estados

| Fase da partida | `turn` | `mulligan_expires_at_ms` |
|---|---|---|
| `MULLIGAN` | `None` | criação + 30_000 (ou `None` em partida montada por teste) |
| `ACTION`, `DECLARATION`, `COMBAT` | a vez atual | `None` |
| `FINISHED` | `None` | `None` |

### Transições (`protocol/turn_clock.advance_match_clock`)

| Depois da mudança | Efeito |
|---|---|
| `FINISHED` | `IDLE_MATCH_CLOCK` |
| `MULLIGAN` | nenhum |
| fase que espera jogador, `turn is None` | `turn_number = 1` |
| fase que espera jogador, `(holder, round)` ≠ `(priority_user_id, round_number)` | `turn_number + 1` |
| fase que espera jogador, par igual | nenhum |

### Despertar (`clock_wake_at`)

| Relógio | Próximo instante |
|---|---|
| `turn`, `warning_sent = False` | `warns_at_ms` |
| `turn`, `warning_sent = True` | `expires_at_ms` |
| `mulligan_expires_at_ms` | ele |
| nada | `None` |

## Documento (`match/documents.py`)

`MatchDocument` ganha:

```text
clock: MatchClockDocument

MatchClockDocument
  turn: TurnDeadlineDocument | None
  mulligan_expires_at_ms: int | None

TurnDeadlineDocument
  turn_number: int
  holder_user_id: int
  round_number: int
  warns_at_ms: int
  expires_at_ms: int
  warning_sent: bool
```

## Redis (`match/store.py`, `match/wake_queue.py`)

| Chave | Tipo | Conteúdo | Quem escreve |
|---|---|---|---|
| `match:{match_id}` | hash | `state`, `version` (sem mudança) | `SAVE_SCRIPT`, `SWAP_SCRIPT` |
| `match:wake` | sorted set | membro `match_id`, score `clock_wake_at` ou lease | os dois scripts acima; `claim_due`, `release`, `forget` |

`mutate(match_id, change, *, renews_expiry: bool = True) -> StoredMatch`.
`renews_expiry=False` grava sem `EXPIRE`.

`ClaimedWake(match_id: str, lease_until_ms: EpochMillis)`.

## Eventos de relógio (`protocol/clock_events.py`)

| Braço | Campos | Vence quando |
|---|---|---|
| `TurnWarning` | `turn_number`, `holder_user_id` | `now ≥ warns_at_ms` e `warning_sent` falso e `now < expires_at_ms` |
| `TurnExpiry` | `turn_number`, `holder_user_id` | `now ≥ expires_at_ms` |
| `MulliganExpiry` | `user_id` | fase `MULLIGAN`, jogador sem resposta, `now ≥ mulligan_expires_at_ms` |

`ClockEventNotDueError(match_id, event, now)`: a guarda da tentativa fresca
não confirmou o evento. Nunca vira recusa de cliente.

## Mudanças (`protocol/match_changes.py`)

| Classe | Faz | `renews_expiry` |
|---|---|---|
| `PlayerChange` | guarda o antes; `apply_command`; `advance_match_clock` | `True` |
| `ClockChange` | guarda o antes; guarda do evento; `automatic_command`; `apply_command`; `advance_match_clock` | `False` |
| `TurnWarningMark` | guarda do evento; `warning_sent = True` | `False` |

## Origem (`protocol/match_frames.py`)

`ChangeOrigin = PlayerOrigin | ClockOrigin(event: TurnExpiry | MulliganExpiry)`.

## Frames

Ver [contracts/server_frames.md](./contracts/server_frames.md).

```text
TurnClockView      = { turn_number: int, holder_user_id: int, remaining_ms: int, warning: bool }
ClockView          = { turn: TurnClockView | None, mulligan_remaining_ms: int | None }
MatchStartPayload  = { version, view, clock: ClockView }
MatchUpdatePayload = { version, view, events, clock: ClockView }
TurnWarningPayload = { turn_number: int, holder_user_id: int, remaining_ms: int }
```

## Eventos novos (`protocol/match_events.py`)

| `kind` | Campos | Posição |
|---|---|---|
| `turn_timed_out` | `user_id`, `turn_number` | primeiro da lista, antes de `passed` / `attack_confirmed` / `defense_ended` |
| `mulligan_timed_out` | `user_id` | primeiro da lista, antes de `mulligan_taken` |
