# Contract: códigos de recusa

**Feature**: `009-match-protocol`

Toda recusa chega **só ao socket que mandou**, sem fechar o socket:

```json
{"type": "message_refused", "payload": {"code": "not_enough_energy", "error": "user 7 cannot pay card instance 3: costs 5 energy, has 1"}}
```

O cliente casa com `code`. `error` é para gente, e pode mudar.

O conjunto é fechado. Um código novo entra neste arquivo junto com a exceção
que o produz.

## Forma e transporte

| Código | Quando |
|---|---|
| `malformed_message` | frame que não é JSON, JSON que não é objeto, frame binário, `type` ausente ou que não é texto, `payload` que não é objeto, campo faltando, campo de tipo errado |
| `unknown_message_type` | `type` texto que o socket não trata |
| `match_not_found` | a partida expirou do armazenamento |
| `concurrent_match_write` | a gravação não convergiu nas tentativas do compare-and-swap |
| `internal_error` | falha inesperada do servidor; `error` é genérico |

## Motor

| Código | Exceção |
|---|---|
| `not_your_priority` | `NotYourPriorityError` |
| `phase_forbids_action` | `PhaseForbidsActionError` |
| `match_is_over` | `MatchIsOverError` |
| `card_not_in_hand` | `CardNotInHandError` |
| `not_enough_energy` | `NotEnoughEnergyError` |
| `card_is_not_a_unit` | `CardIsNotAUnitError` |
| `bank_is_full` | `BankIsFullError` |
| `card_is_not_a_spell` | `CardIsNotASpellError` |
| `spell_takes_no_target` | `SpellTakesNoTargetError` |
| `spell_needs_target` | `SpellNeedsTargetError` |
| `wrong_spell_target_side` | `WrongSpellTargetSideError` |
| `spell_target_not_on_battlefield` | `SpellTargetNotOnBattlefieldError` |
| `spell_only_in_declaration` | `SpellOnlyInDeclarationError` |
| `not_the_token_holder` | `NotTheTokenHolderError` |
| `attack_token_already_consumed` | `AttackTokenAlreadyConsumedError` |
| `bank_has_no_units` | `BankHasNoUnitsError` |
| `no_attackers_selected` | `NoAttackersSelectedError` |
| `attacker_not_in_bank` | `AttackerNotInBankError` |
| `duplicate_attacker` | `DuplicateAttackerError` |
| `unit_already_attacking` | `UnitAlreadyAttackingError` |
| `unit_is_not_attacking` | `UnitIsNotAttackingError` |
| `blocker_not_in_bank` | `BlockerNotInBankError` |
| `blocker_already_blocking` | `BlockerAlreadyBlockingError` |
| `attacker_already_blocked` | `AttackerAlreadyBlockedError` |
| `blocker_not_assigned` | `BlockerNotAssignedError` |
| `mulligan_already_taken` | `MulliganAlreadyTakenError` |

A consulta é por **tipo exato**: `MatchIsOverError` é subclasse de
`PhaseForbidsActionError` e tem código próprio.
