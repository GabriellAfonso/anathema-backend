# Data Model: Feitiço imediato

**Feature**: `008-instant-spells` | **Date**: 2026-09-11

Esta feature não cria entidade. Ela tira uma — a entrada da pilha — e muda duas
propriedades de uma ação. O que segue é o estado **depois** da remoção, com o
que saiu marcado.

---

## Match (`match/match_state.py`)

| Campo | Tipo | Mudança |
|---|---|---|
| `match_id` | `str` | — |
| `players` | `tuple[PlayerState, PlayerState]` | — |
| `random_seed` | `RandomSeed` | — |
| `token_holder_user_id` | `int \| None` | — |
| `priority_user_id` | `int \| None` | — |
| `round_number` | `int` | — |
| `token_consumed` | `bool` | — |
| `phase` | `MatchPhase` | perde um valor, ver abaixo |
| `outcome` | `MatchOutcome \| None` | — |
| ~~`stack`~~ | ~~`list[StackEntry]`~~ | **removido** |
| `combat` | `CombatState \| None` | — |
| `consecutive_passes` | `int` | — |
| `next_card_instance_id` | `int` | — |
| `next_roll_ordinal` | `int` | — |

`Match.bank_unit()` fica. Os usuários dele são as guardas de lançamento, o
pareamento de bloqueio e o dano de combate.

### StackEntry (`match/spell_stack.py`) — **removido**

O arquivo inteiro sai. Não há entidade que o substitua: um feitiço não existe
entre ser jogado e resolver, porque não há "entre".

---

## MatchPhase

| Valor | Espera jogador? | Automática? | Mudança |
|---|---|---|---|
| `MULLIGAN` | sim (os dois) | não | — |
| `UPKEEP` | não | sim | — |
| `ACTION` | sim | não | — |
| ~~`STACK_RESOLUTION`~~ | — | — | **removido** |
| `COMBAT` | sim (o defensor) | não | — |
| `ROUND_END` | não | sim | — |
| `FINISHED` | não | não (terminal) | — |

### Transições da Fase de Ação

```text
ACTION ──(jogar feitiço)────────────> ACTION     prioridade fica, passes = 0
ACTION ──(jogar unidade)────────────> ACTION     prioridade troca, passes = 0
ACTION ──(declarar ataque)──────────> COMBAT     prioridade troca, passes = 0
ACTION ──(passar, passes < 2)───────> ACTION     prioridade troca, passes + 1
ACTION ──(passar, passes = 2)───────> ROUND_END ─> UPKEEP ─> ACTION   (cascata)
```

~~`ACTION ──(passar, passes = 2, pilha cheia)──> STACK_RESOLUTION`~~ — removida.

### Transições do Combate

```text
COMBAT ──(jogar feitiço)─────────────> COMBAT     prioridade fica com o defensor
COMBAT ──(atribuir/remover bloqueio)─> COMBAT     prioridade fica com o defensor
COMBAT ──(encerrar a janela)─────────> ACTION     prioridade com o dono do token
```

Idênticas às da feature 007, exceto que o feitiço é `CastSpellAction`.

A transição para `FINISHED` por feitiço existe hoje só pelo SACRIFICIAL FIRE, e
a segunda correção da nota a remove (§10, §14). Esta feature não a toca.

---

## PlayerAction (`engine/player_action.py`, `engine/combat_action.py`)

União fechada de **sete** braços (eram oito).

| Braço | Campos | `allowed_phases` | `keeps_priority` | Mudança |
|---|---|---|---|---|
| `PlayUnitAction` | `actor_user_id`, `card_instance_id` | `{ACTION}` | `False` | — |
| `CastSpellAction` | `actor_user_id`, `card_instance_id`, `target_card_instance_id: CardInstanceId \| None = None` | `{ACTION, COMBAT}` | **`True`** | fases e prioridade mudam |
| `DeclareAttackAction` | `actor_user_id`, `attacker_card_instance_ids` | `{ACTION}` | `False` | — |
| `PassAction` | `actor_user_id` | `{ACTION}` | `False` | — |
| `AssignBlockerAction` | `actor_user_id`, `blocker_card_instance_id`, `attacker_card_instance_id` | `{COMBAT}` | `True` | — |
| `RemoveBlockerAction` | `actor_user_id`, `blocker_card_instance_id` | `{COMBAT}` | `True` | — |
| ~~`CastCombatSpellAction`~~ | — | — | — | **removido** |
| `EndDefenseWindowAction` | `actor_user_id` | `{COMBAT}` | `True` | — |

`CastSpellAction` continua morando em `player_action.py`: é a ação B da §5, e é
lá que a união é montada.

## ActionKind (`engine/action_kind.py`)

`play_unit`, `cast_spell`, `pass`, `declare_attack`, `assign_blocker`,
`remove_blocker`, `end_defense_window`. ~~`cast_combat_spell`~~ sai.

---

## MatchDocument (`match/documents.py`)

Perde a chave `stack`. Todas as outras chaves ficam, com os mesmos tipos.

### StackEntryDocument — **removido**

## PlayerView (`match/player_view.py`)

Perde a chave `stack`. `you`, `opponent`, `combat`, `outcome` e os campos de
rodada ficam como estão.

---

## Recusas

| Recusa | Mudança |
|---|---|
| `StackIsNotEmptyError` | **removida** |
| `CardIsNotASpellError`, `SpellTakesNoTargetError`, `SpellNeedsTargetError`, `WrongSpellTargetSideError`, `SpellTargetNotOnBattlefieldError` | ficam; agora valem igual nas duas fases |
| `NotYourPriorityError`, `PhaseForbidsActionError`, `MatchIsOverError`, `CardNotInHandError`, `NotEnoughEnergyError` | ficam |
| as de declaração de ataque (6) e de bloqueio (5) | ficam |

## Validação da ação de feitiço

Na ordem, e a primeira que falha é a recusa:

1. o autor joga a partida (`NotAParticipantError`)
2. o autor tem a prioridade (`NotYourPriorityError`)
3. a partida não acabou (`MatchIsOverError`)
4. a fase está em `{ACTION, COMBAT}` (`PhaseForbidsActionError`)
5. a carta está na mão do autor (`CardNotInHandError`)
6. a carta é feitiço (`CardIsNotASpellError`)
7. a energia cobre o custo (`NotEnoughEnergyError`)
8. o alvo casa com o efeito, nesta ordem: proibido quando o efeito não mira
   (`SpellTakesNoTargetError`), exigido quando mira (`SpellNeedsTargetError`),
   em campo (`SpellTargetNotOnBattlefieldError`), do lado certo
   (`WrongSpellTargetSideError`)

As quatro primeiras são as guardas comuns da feature 005, sem mudança. As
quatro últimas são `validated_spell_cast`, sem mudança de ordem.
