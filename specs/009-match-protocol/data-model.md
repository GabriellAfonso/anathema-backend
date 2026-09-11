# Data Model: Protocolo de partida

**Feature**: `009-match-protocol` | **Date**: 2026-09-11

## Comandos (`protocol/commands.py`)

`ClientCommand` = união fechada:

| Braço | Campos | Porta do motor |
|---|---|---|
| `PlayUnitAction` | `actor_user_id`, `card_instance_id` | `submit_action` |
| `CastSpellAction` | `actor_user_id`, `card_instance_id`, `target_card_instance_id?` | `submit_action` |
| `PassAction` | `actor_user_id` | `submit_action` |
| `DeclareAttackAction` | `actor_user_id`, `attacker_card_instance_ids` | `submit_action` |
| `WithdrawAttackerAction` | `actor_user_id`, `attacker_card_instance_id` | `submit_action` |
| `ConfirmAttackAction` | `actor_user_id` | `submit_action` |
| `AssignBlockerAction` | `actor_user_id`, `blocker_card_instance_id`, `attacker_card_instance_id` | `submit_action` |
| `RemoveBlockerAction` | `actor_user_id`, `blocker_card_instance_id` | `submit_action` |
| `EndDefenseWindowAction` | `actor_user_id` | `submit_action` |
| `MulliganCommand` | `user_id`, `card_instance_ids` | `record_mulligan` (+ `begin_round_cycle`) |
| `ForfeitCommand` | `user_id` | `forfeit` |

## Versão (`match/store.py`)

`StoredMatch(match: Match, version: int)`. `version` ≥ 1, cresce 1 a cada
escrita.

## Recusa

| Campo | Tipo |
|---|---|
| `code` | `str`, do catálogo de [refusal_codes.md](./contracts/refusal_codes.md) |
| `error` | `str`, legível, pode conter valores |

`MalformedMessageError(code, message)` é a exceção de forma.

## Frames (`protocol/match_frames.py`)

```text
MatchStartPayload  = { version: int, view: PlayerView }
MatchUpdatePayload = { version: int, view: PlayerView, events: list[MatchEvent] }
```

`match_start_payload(match, version, user_id)` e
`match_update_payload(before, after, version, command, user_id)` recebem partida
e versão separadas, e não `StoredMatch`: assim `protocol/` não importa
`match/store.py`, que importa o cliente Redis.

## Visão (`match/player_view.py`)

`PlayerSideView` e `OpponentSideView` ganham `mulligan_taken: bool`.

## Eventos (`protocol/match_events.py`)

Todo evento tem `kind`. Jogada:

| `kind` | Campos |
|---|---|
| `mulligan_taken` | `user_id`, `swapped_count` |
| `unit_played` | `user_id`, `card` |
| `spell_cast` | `user_id`, `card`, `target_card_instance_id` |
| `passed` | `user_id` |
| `attackers_sent` | `user_id`, `attacker_card_instance_ids` |
| `attacker_withdrawn` | `user_id`, `attacker_card_instance_id` |
| `attack_confirmed` | `user_id` |
| `blocker_assigned` | `user_id`, `blocker_card_instance_id`, `attacker_card_instance_id` |
| `blocker_removed` | `user_id`, `blocker_card_instance_id` |
| `defense_ended` | `user_id` |
| `forfeited` | `user_id` |

Consequências, nesta ordem:

| `kind` | Campos | Recorte |
|---|---|---|
| `unit_damaged` | `card_instance_id`, `amount` | público |
| `unit_died` | `user_id` (dono), `card` | público |
| `nexus_changed` | `user_id`, `amount` | público |
| `round_started` | `round_number`, `token_holder_user_id` | público; também quando o fim do setup abre a Rodada 1 |
| `cards_drawn` | `user_id`, `count`, `cards` | `cards` só para o próprio jogador; para o oponente, lista vazia |
| `match_finished` | `defeated_user_id`, `reason` | público |

`card` é `CardDocument` (`card_instance_id`, `card_id`) de uma carta que já é
pública no momento do evento (no banco ou no cemitério).
