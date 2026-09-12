# Contract: frames do servidor — delta da feature 010

**Feature**: `010-match-timers` | **Socket**: `ws/match/?matchId=<uuid>`

Base: [009 server_frames.md](../../009-match-protocol/contracts/server_frames.md).
Tudo que está lá continua valendo. Abaixo, só o que muda.

## `clock` em `match_start` e `match_update`

```json
{"type": "match_start", "payload": {"version": 4, "view": { ... }, "clock": { ...ClockView... }}}
{"type": "match_update", "payload": {"version": 5, "view": { ... }, "events": [ ... ], "clock": { ...ClockView... }}}
```

### `ClockView`

```json
{
  "turn": {
    "turn_number": 12,
    "holder_user_id": 7,
    "remaining_ms": 25000,
    "warning": false
  },
  "mulligan_remaining_ms": null
}
```

| Campo | Significado |
|---|---|
| `turn` | `null` no mulligan e na partida terminada |
| `turn.turn_number` | identidade da vez; muda a cada vez nova, inclusive com o mesmo dono na rodada seguinte |
| `turn.holder_user_id` | quem deve a jogada; igual a `view.priority_user_id` |
| `turn.remaining_ms` | quanto falta para o estouro, medido pelo servidor ao montar o frame; nunca negativo |
| `turn.warning` | `true` quando `remaining_ms ≤ 15000` |
| `mulligan_remaining_ms` | só do destinatário: número enquanto a fase é `mulligan` e ele não respondeu; `null` no resto |

O cliente desenha o relógio a partir de `remaining_ms` e do instante em que
**recebeu** o frame, no relógio local dele. Nunca compara com um horário
absoluto.

Feitiço, mandar e puxar atacante e atribuir ou remover bloqueador produzem
`match_update` com o mesmo `turn_number` e `remaining_ms` menor.

## `turn_warning` — só aos sockets do dono da vez

```json
{"type": "turn_warning", "payload": {"turn_number": 12, "holder_user_id": 7, "remaining_ms": 15000}}
```

Mandado uma vez por vez, aos 30 s. Pode chegar repetido; o cliente ignora um
`turn_warning` cujo `turn_number` não é o da vez que ele está desenhando. Não
existe no mulligan. Não muda a partida.

A gravação que marca o aviso cria uma `version` que nenhum `match_update`
carrega. O cliente não conta com versões contínuas.

## Eventos novos

### `turn_timed_out`

Primeiro da lista quando a vez estourou. Vem seguido do evento da ação
automática.

```json
[
  {"kind": "turn_timed_out", "user_id": 9, "turn_number": 12},
  {"kind": "passed", "user_id": 9}
]
```

| Fase no estouro | Evento seguinte |
|---|---|
| `action` | `passed` |
| `declaration` | `attack_confirmed` |
| `combat` | `defense_ended` |

### `mulligan_timed_out`

```json
[
  {"kind": "mulligan_timed_out", "user_id": 9},
  {"kind": "mulligan_taken", "user_id": 9, "swapped_count": 0}
]
```

Jogada mandada pelo socket nunca traz `turn_timed_out` nem
`mulligan_timed_out`.

## Recusas

Nenhum código novo. O estouro não gera recusa. Uma jogada que perde a disputa
para o estouro recebe a recusa de sempre contra o estado que ele deixou —
normalmente `not_your_priority` ou `mulligan_already_taken`.
