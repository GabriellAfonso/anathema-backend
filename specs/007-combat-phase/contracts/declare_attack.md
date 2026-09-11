# Contrato: Declarar ataque (§5C, §7.1)

**Feature**: 007-combat-phase | **Módulo**: `apps/game/engine/declare_attack.py`

A quarta e última ação da Fase de Ação. Entra como um braço novo da união, sem
que `ensure_action_allowed` nem `submit_action` mudem de forma.

---

## A ação

`apps/game/engine/player_action.py` (EDITADO)

```python
class ActionKind(StrEnum):
    PLAY_UNIT = "play_unit"
    CAST_SPELL = "cast_spell"
    PASS = "pass"
    DECLARE_ATTACK = "declare_attack"          # NOVO
    ASSIGN_BLOCKER = "assign_blocker"          # NOVO
    REMOVE_BLOCKER = "remove_blocker"          # NOVO
    CAST_COMBAT_SPELL = "cast_combat_spell"    # NOVO
    END_DEFENSE_WINDOW = "end_defense_window"  # NOVO


@dataclass(frozen=True, slots=True)
class DeclareAttackAction:
    action_kind: ClassVar[ActionKind] = ActionKind.DECLARE_ATTACK
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})
    keeps_priority: ClassVar[bool] = False

    actor_user_id: int
    attacker_card_instance_ids: tuple[CardInstanceId, ...]
```

`tuple` e não `list`: a ação é `frozen=True`, e uma lista dentro dela seria um
campo imutável apontando para um conteúdo mutável. Também preserva a ordem, que
FR-018 exige guardar e proíbe usar no resultado.

`keeps_priority` é declarada nos oito braços, sem default — ver
[research.md D5](../research.md). Os quatro da §5 declaram `False`.

---

## A porta

```python
def declare_attack(
    match: Match, actor: PlayerState, action: DeclareAttackAction
) -> None:
```

Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit` e
`cast_spell`. Não recebe `catalog`: nenhuma guarda desta ação lê molde de carta.

Chamada por `round_cycle._apply_action`, no braço novo do `match`.

---

## As guardas, na ordem

Antes destas, as três comuns da §5 (participante → prioridade → fase) já
correram. Nenhuma escrita acontece antes de todas as seis passarem.

| # | Pergunta | Recusa | FR |
|---|---|---|---|
| 1 | O autor é o dono do token? | `NotTheTokenHolderError` | FR-003 |
| 2 | O token está livre nesta rodada? | `AttackTokenAlreadyConsumedError` | FR-004 |
| 3 | A pilha está vazia? | `StackIsNotEmptyError` | FR-005 |
| 4 | O banco do autor tem alguma unidade? | `BankHasNoUnitsError` | FR-006 |
| 5 | A seleção tem ao menos uma unidade? | `NoAttackersSelectedError` | FR-007 |
| 6 | Cada unidade citada está no banco do autor, uma vez só? | `AttackerNotInBankError`, `DuplicateAttackerError` | FR-008, FR-009 |

A ordem é parte do contrato: as guardas gerais e baratas vêm antes, e a que cita
uma unidade específica vem por último — é a mesma disciplina de `cast_spell`, em
que a carta precisa ser resolvida antes de se poder citar o custo dela.

**4 antes de 5** de propósito. São fatos diferentes: o banco vazio é "não há o
que atacar", e a seleção vazia é "há, e você não escolheu nada". Colapsá-las
esconderia qual dos dois cliente está quebrado.

---

## As recusas

Todas herdam de `IllegalActionError`, moram neste módulo (como `BankIsFullError`
mora em `play_unit.py`) e citam o valor ofensor (FR-079).

```
NotTheTokenHolderError: user 9 cannot declare an attack in match 'm-1':
the attack token belongs to user 7

AttackTokenAlreadyConsumedError: user 7 already attacked in round 3 of match
'm-1': the attack token comes back in the next upkeep

StackIsNotEmptyError: match 'm-1' has 2 pending spells: expected an empty stack
to declare an attack

BankHasNoUnitsError: bank of user 7 is empty: expected at least 1 unit to
declare an attack

NoAttackersSelectedError: user 7 selected no attackers: expected at least 1 of
the 3 units in the bank

AttackerNotInBankError: card instance 11 is not in the bank of user 7:
expected one of [3, 5, 8]

DuplicateAttackerError: card instance 5 is selected twice as an attacker:
expected each unit at most once
```

`AttackerNotInBankError` cobre três casos de cliente numa recusa só, e é o que
ela é do ponto de vista de quem joga: a unidade do oponente, a carta que está na
mão e a unidade que já morreu — nenhuma delas está no banco do autor.

---

## O efeito

```python
actor.bank              # NÃO MUDA
actor.hand              # NÃO MUDA
actor.energy_current    # NÃO MUDA
match.token_consumed = True
match.combat = CombatState(attacker_card_instance_ids=[...])
match.phase = MatchPhase.COMBAT
match.consecutive_passes = 0
```

Os dois últimos campos do par `(combat, phase)` são escritos por
`_enter_combat`, o único ponto do módulo que os escreve — a invariante I1 vale
porque existe um lugar só onde ela pode ser quebrada, que é o argumento de
`victory._finish_match`.

A prioridade **não** é trocada aqui. Quem troca é `submit_action`, depois de
toda ação, e `keeps_priority = False` deixa a troca acontecer: a prioridade vai
para o oponente do autor, que é exatamente o defensor.

`consecutive_passes = 0` pela razão que `play_unit` e `cast_spell` já escrevem —
a §5 conta passes **consecutivos**, e uma jogada quebra a sequência. A
consequência que carrega a feature está em [research.md D7](../research.md):
com os passes em 0, `_exit_action_phase` fica inerte durante todo o combate sem
que uma linha dela mude.

---

## Depois da ação, dentro de `submit_action`

| Passo | O que acontece |
|---|---|
| `_pass_priority` | prioridade → defensor (`keeps_priority` é `False`) |
| `_exit_action_phase` | passes em 0, então não faz nada |
| `_settle` | `COMBAT` não está em `_AUTOMATIC_PHASES`, então o laço não roda |

A partida retorna **em Combate, esperando o defensor**. É o único ponto do jogo
em que `submit_action` devolve a partida fora da Fase de Ação sem ela ter
acabado, e é o que FR-070 descreve.

---

## Cenários de aceitação cobertos

US1 inteira: cenários 1 a 11 da spec.

FRs: FR-001 a FR-012, FR-018 (a ordem é preservada), FR-076 a FR-080 (na parte
desta ação).
