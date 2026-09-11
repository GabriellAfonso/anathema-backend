# Contrato: A janela do defensor (§7.2)

**Feature**: 007-combat-phase
**Módulos**: `apps/game/engine/blocker_pairing.py`,
`apps/game/engine/spell_cast_guards.py`,
`apps/game/engine/cast_combat_spell.py`

A única exceção à alternância da §5 em todo o jogo. O defensor age quantas vezes
quiser, em qualquer ordem, e a prioridade não sai dele.

---

## 1. A prioridade que não troca

`apps/game/engine/player_action.py` (EDITADO) — os quatro braços da janela:

```python
@dataclass(frozen=True, slots=True)
class AssignBlockerAction:
    action_kind: ClassVar[ActionKind] = ActionKind.ASSIGN_BLOCKER
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.COMBAT})
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    blocker_card_instance_id: CardInstanceId
    attacker_card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class RemoveBlockerAction:
    ...
    actor_user_id: int
    blocker_card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class CastCombatSpellAction:
    ...
    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None


@dataclass(frozen=True, slots=True)
class EndDefenseWindowAction:
    ...
    actor_user_id: int
```

Os quatro declaram `allowed_phases = {COMBAT}` e `keeps_priority = True`.

`apps/game/engine/round_cycle.py` (EDITADO) — a única mudança na alternância:

```python
def _pass_priority(match: Match, action: PlayerAction) -> None:
    """A prioridade passa ao oponente do autor, depois de qualquer ação (§5).

    O `return` é a janela do defensor da §7.2, a única exceção do jogo: ele age
    quantas vezes quiser sem devolver a vez. A exceção é propriedade da **ação**,
    como `allowed_phases` já é, e por isso não vaza para a Fase de Ação -- os
    quatro braços da §5 declaram `keeps_priority = False`.
    """
    if action.keeps_priority:
        return

    match.priority_user_id = match.opponent_of(action.actor_user_id).user_id
```

**Duas linhas.** É a feature inteira do lado da alternância.

---

## 2. Quem pode agir na janela

Não existe guarda "o autor é o defensor". As duas guardas comuns já resolvem:

| Quem | O que tenta | Recusa | Por quê |
|---|---|---|---|
| atacante | qualquer ação | `NotYourPriorityError` | a prioridade é do defensor (guarda 2) |
| defensor | ação da §5 (`play_unit`, `cast_spell`, `pass`, `declare_attack`) | `PhaseForbidsActionError` | `{ACTION}` não contém `COMBAT` (guarda 3) |
| qualquer um, fora do combate | ação da janela | `PhaseForbidsActionError` | `{COMBAT}` não contém `ACTION` (guarda 3) |
| qualquer um, partida terminada | qualquer ação | `MatchIsOverError` | feature 006, inalterada |

FR-022, FR-023 e FR-024 saem daí, sem uma guarda nova.

---

## 3. Atribuir e remover bloqueador

`apps/game/engine/blocker_pairing.py` (NOVO)

```python
def assign_blocker(match: Match, actor: PlayerState, action: AssignBlockerAction) -> None
def remove_blocker(match: Match, actor: PlayerState, action: RemoveBlockerAction) -> None
```

Sem `catalog`: nenhuma das duas lê molde de carta.

### Guardas de `assign_blocker`, na ordem

| # | Pergunta | Recusa | FR |
|---|---|---|---|
| 1 | O bloqueador está no banco do autor? | `BlockerNotInBankError` | FR-029 |
| 2 | O alvo está atacando? | `UnitIsNotAttackingError` | FR-030 |
| 3 | O bloqueador já cobre alguém? | `BlockerAlreadyBlockingError` | FR-027 |
| 4 | O atacante já tem bloqueador? | `AttackerAlreadyBlockedError` | FR-028 |

1 e 2 antes de 3 e 4: as duas primeiras perguntam se as unidades citadas existem
onde deveriam, as duas últimas perguntam sobre o pareamento. Citar uma unidade
inexistente é erro mais básico que violar a regra 1:1.

**A guarda 2 pergunta duas coisas numa**: o identificador está em
`attacker_card_instance_ids`? Não pergunta se ele ainda está em campo. Um
atacante que morreu por feitiço na janela sai do banco mas continua na lista, e
bloqueá-lo é recusado por não fazer sentido — a recusa correta é a que a spec
pede nos Edge Cases, e a revalidação de campo é da resolução, não daqui. Por
isso a guarda 2 consulta `combat.is_attacking()` **e** `match.bank_unit()`: a
lista diz que foi declarado, o banco diz que ainda existe, e as duas precisam
valer.

### Guarda de `remove_blocker`

| # | Pergunta | Recusa | FR |
|---|---|---|---|
| 1 | Esse bloqueador está atribuído a alguém? | `BlockerNotAssignedError` | FR-032 |

### As recusas

```
BlockerNotInBankError: card instance 11 is not in the bank of user 9:
expected one of [4, 6]

UnitIsNotAttackingError: card instance 8 is not attacking in match 'm-1':
expected one of [3, 5]

BlockerAlreadyBlockingError: card instance 4 already blocks card instance 3:
expected an unassigned blocker

AttackerAlreadyBlockedError: card instance 3 is already blocked by card
instance 4: expected an unblocked attacker

BlockerNotAssignedError: card instance 6 is not blocking anything in match
'm-1': expected one of [4]
```

### O efeito

```python
# assign_blocker
combat.blocks.append(
    BlockAssignment(
        blocker_card_instance_id=action.blocker_card_instance_id,
        attacker_card_instance_id=action.attacker_card_instance_id,
    )
)

# remove_blocker
combat.blocks = [
    block for block in combat.blocks
    if block.blocker_card_instance_id != action.blocker_card_instance_id
]
```

Nada mais. Nem energia, nem carta, nem dano, nem Nexus, nem passes, nem
prioridade, nem fase (FR-033).

O `combat` das duas vem de `match.ongoing_combat()`, o estreitamento que mora no
pacote de estado — ver [data-model.md §1](../data-model.md).

---

## 4. As guardas de lançamento, compartilhadas

`apps/game/engine/spell_cast_guards.py` (NOVO — recebe de `cast_spell.py`)

```python
@dataclass(frozen=True, slots=True)
class ValidatedSpellCast:
    card: MatchCard
    spell: Spell
    target: BankUnit | None


def validated_spell_cast(
    match: Match,
    actor: PlayerState,
    card_instance_id: CardInstanceId,
    target_card_instance_id: CardInstanceId | None,
    *,
    catalog: CardCatalog,
) -> ValidatedSpellCast:
    """As quatro guardas da §5B, na ordem, sem aplicar nem empilhar nada."""
```

As quatro perguntas, na ordem que `cast_spell.py` já documenta:

1. a carta citada está na mão do autor (`card_in_hand`);
2. a carta é um feitiço (`CardIsNotASpellError`);
3. a energia atual cobre o custo (`ensure_enough_energy`);
4. o alvo casa com o que o efeito declara (`SpellTakesNoTargetError`,
   `SpellNeedsTargetError`, `SpellTargetNotOnBattlefieldError`,
   `WrongSpellTargetSideError`).

As cinco recusas de feitiço **mudam de arquivo** e nada mais: mesma mensagem,
mesma hierarquia, mesma ordem. `test_cast_spell.py` passa sem alteração, e é
essa a prova. Ver [research.md D10](../research.md).

A porta devolve o `BankUnit` do alvo em vez de só validar o lado, e com isso
`cast_spell._owner_of` desaparece — `Match.bank_unit()` já faz a varredura.

`cast_spell.py` (EDITADO) encolhe para a regra da §5B:

```python
def cast_spell(match, actor, action, *, catalog) -> None:
    validated = validated_spell_cast(
        match, actor, action.card_instance_id,
        action.target_card_instance_id, catalog=catalog,
    )

    actor.energy_current -= validated.spell.energy
    actor.hand.remove(validated.card)
    match.stack.append(StackEntry(...))
    match.consecutive_passes = 0
```

---

## 5. O feitiço que resolve na hora

`apps/game/engine/cast_combat_spell.py` (NOVO)

```python
def cast_combat_spell(
    match: Match, actor: PlayerState, action: CastCombatSpellAction, *, catalog: CardCatalog
) -> None:
    """A §7.2: as mesmas guardas da §5B, e o efeito **agora**.

    Não empilha e não devolve a vez: o atacante é espectador, e não existe
    intervalo entre validar o alvo e aplicá-lo -- por isso este caminho nunca
    fizzla (FR-043).
    """
    validated = validated_spell_cast(
        match, actor, action.card_instance_id,
        action.target_card_instance_id, catalog=catalog,
    )

    actor.energy_current -= validated.spell.energy
    actor.hand.remove(validated.card)
    apply_spell_effect(
        match, actor, validated.spell.effect, validated.target, catalog=catalog
    )
    actor.graveyard.append(validated.card)
```

**O cemitério vem depois do efeito**, e não antes. É a ordem de
`stack_resolution._resolve_top`, e SC-008 exige resultado idêntico campo a campo
entre os dois caminhos — inclusive a ordem do cemitério, em que uma unidade
morta pelo efeito precisa entrar antes da carta do feitiço. Ver
[research.md D11](../research.md).

`apply_spell_effect` é chamado **sem nenhum parâmetro dizendo de onde veio**
(FR-039). Ele já faz o que o combate precisa e nada além: aplica o efeito,
apura a §10 dentro de `change_nexus` quando o efeito mexe em Nexus, e varre as
unidades mortas.

`consecutive_passes` não é tocado: já está em 0 desde a declaração, e a limpeza
o zera de novo.

### O que o defensor consegue fazer, e que a resolução vai encontrar

| Feitiço | Efeito na janela | O que muda na §7.3 |
|---|---|---|
| SUMMONED AX | 3 de dano numa unidade inimiga | pode matar um atacante — o bloqueador dele fica órfão |
| SOMEONE'S SHIELD | +2 de vida numa unidade aliada | um bloqueador sobrevive à troca |
| MAGIC BARRIER | imunidade numa unidade aliada | um bloqueador não recebe dano, e o atacante recebe o dele |
| LIFE POTION | +5 de Nexus do lançador | o dano não bloqueado precisa de mais para derrubar |
| SACRIFICIAL FIRE | −8 de Nexus e +3 de ataque em todas as unidades do lançador | os bloqueadores batem mais forte, e o defensor com 8 ou menos **se derrota ali** |

A última linha é FR-062 acontecendo: a partida vai a `FINISHED` dentro de
`change_nexus`, e a ação seguinte — inclusive a que encerraria a janela — é
recusada com `MatchIsOverError`. O dano do combate nunca resolve, e o
`CombatState` fica congelado onde parou. Ver [research.md D21](../research.md).

---

## Cenários de aceitação cobertos

US2 inteira (cenários 1 a 12) e US3 inteira (cenários 1 a 9).

FRs: FR-019 a FR-046, e FR-076 a FR-080 na parte destas ações.
