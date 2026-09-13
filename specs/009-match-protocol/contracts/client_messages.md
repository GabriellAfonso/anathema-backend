# Contract: mensagens do cliente

**Feature**: `009-match-protocol` | **Socket**: `ws/match/?matchId=<uuid>`

Envelope: `{"type": "<espécie>", "payload": {...}}`. O autor é sempre o usuário
autenticado do socket; qualquer campo de autor no payload é ignorado. Campos a
mais são ignorados.

Identificador de carta: inteiro JSON ≥ 1 (não `true`/`false`, não texto, não
fracionário). É sempre `card_instance_id`, nunca `card_id`.

| `type` | `payload` | Quando |
|---|---|---|
| `mulligan` | `{"card_instance_ids": [int, ...]}` — lista, pode ser vazia | espera do mulligan |
| `forfeit` | `{}` ou ausente | a qualquer momento |
| `play_unit` | `{"card_instance_id": int}` | Fase de Ação |
| `cast_spell` | `{"card_instance_id": int, "target_card_instance_id": int \| null}` — alvo pode faltar | Fase de Ação, declaração, defesa |
| `pass` | `{}` ou ausente | Fase de Ação |
| `declare_attack` | `{"attacker_card_instance_ids": [int, ...]}` — lista, pode ser vazia (o motor recusa) | Fase de Ação, declaração |
| `withdraw_attacker` | `{"attacker_card_instance_id": int}` | declaração |
| `confirm_attack` | `{}` ou ausente | declaração |
| `assign_blocker` | `{"blocker_card_instance_id": int, "attacker_card_instance_id": int}` | defesa |
| `remove_blocker` | `{"blocker_card_instance_id": int}` | defesa |
| `end_defense_window` | `{}` ou ausente | defesa |

A coluna "Quando" é a regra do motor, não da forma: uma mensagem bem formada na
fase errada chega ao motor e recebe a recusa dele.

## Exemplos

```json
{"type": "mulligan", "payload": {"card_instance_ids": [3, 7]}}
{"type": "cast_spell", "payload": {"card_instance_id": 12, "target_card_instance_id": 40}}
{"type": "declare_attack", "payload": {"attacker_card_instance_ids": [21, 22]}}
{"type": "confirm_attack"}
```

## Recusas de forma

Ver [refusal_codes.md](./refusal_codes.md): `malformed_message` e
`unknown_message_type`.

## `ping` (feature 013)

`{"type": "ping", "payload": {...}}` existe neste socket e **não é recusado**,
em nenhuma fase. Não é jogada: não passa pelo parser desta tabela, não cria
versão e não gera `match_update`. O servidor responde `pong` só a este socket.
Ver [013 — heartbeat_messages.md](../../013-socket-heartbeat/contracts/heartbeat_messages.md).
