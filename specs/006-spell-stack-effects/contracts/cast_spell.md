# Contrato — lançar feitiço (§5B)

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

`apps.game.engine.cast_spell` e as adições a
`apps.game.engine.player_action`, reexportadas por `apps.game.engine`.
Assinaturas são o contrato; corpos são da implementação.

A razão do desenho está em [research.md](../research.md) D3, D4, D5 e D16.

---

## 1. O braço novo da união

```python
class ActionKind(StrEnum):
    PLAY_UNIT = "play_unit"
    PASS = "pass"
    CAST_SPELL = "cast_spell"          # NOVO


@dataclass(frozen=True, slots=True)
class CastSpellAction:
    """Lançar um feitiço da mão (§5B).

    `target_card_instance_id` é anulável porque a ausência de alvo é estado
    legítimo de três dos cinco feitiços do MVP, não campo esquecido. Mesma
    forma e mesma razão de `StackEntry.target_card_instance_id`, cujo docstring
    já separa as duas perguntas: `None` é "não mira nada", nunca "o alvo
    sumiu".

    >>> CastSpellAction(actor_user_id=7, card_instance_id=CardInstanceId(3),
    ...                 target_card_instance_id=CardInstanceId(11))
    """

    action_kind: ClassVar[ActionKind] = ActionKind.CAST_SPELL
    # `{ACTION}` e não `{ACTION, COMBAT}`: o feitiço do defensor da §7.2 resolve
    # imediatamente, sem pilha, e é outra ação -- não esta com uma fase a mais.
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None


PlayerAction = PlayUnitAction | PassAction | CastSpellAction
```

`ensure_action_allowed` **não muda de assinatura nem de ordem**. Foi para isto
que a feature 005 a escreveu como escreveu.

---

## 2. A guarda comum ganha um caso, não uma posição

```python
class MatchIsOverError(PhaseForbidsActionError):
    """A partida acabou (§10). Nenhuma ação é aceita, de nenhum jogador.

    Subclasse e não irmã: a afirmação é literalmente verdadeira -- a fase proíbe
    a ação --, e quem já escrevia `except PhaseForbidsActionError` continua
    pegando o caso.

    Levantada de dentro da **terceira** guarda, não antes dela. A ordem da
    feature 005 -- participante, prioridade, fase -- é contrato e não muda: um
    `user_id` de fora agindo numa partida terminada recebe
    `NotAParticipantError`, porque a guarda 1 é sobre identidade.

    >>> raise MatchIsOverError(ActionKind.PASS, outcome, "m-1")
    MatchIsOverError: action 'pass' is not allowed in match 'm-1': the match is
    over, defeated user_ids [7]
    """

    def __init__(
        self, action_kind: ActionKind, outcome: MatchOutcome | None, match_id: str
    ) -> None: ...
```

Ordem final das guardas comuns, inalterada em relação à feature 005:

1. o autor joga esta partida → `NotAParticipantError`
2. o autor tem a prioridade → `NotYourPriorityError`
3. a fase permite esta ação → `MatchIsOverError` se `FINISHED`, senão
   `PhaseForbidsActionError`

---

## 3. As duas guardas que sobem de `play_unit.py`

Jogar unidade e lançar feitiço fazem estas duas identicamente. Elas passam a ser
funções de `player_action.py`, e `NotEnoughEnergyError` vai junto para o lado da
definição que a levanta (research D16).

```python
def card_in_hand(actor: PlayerState, card_instance_id: CardInstanceId) -> MatchCard:
    """A carta citada, na mão **do autor**, ou `CardNotInHandError`.

    A mão consultada é sempre a de quem age, então citar a carta do oponente cai
    na mesma recusa de uma carta que não existe -- que é o que ela é, do ponto
    de vista de quem joga.

    >>> card_in_hand(actor, CardInstanceId(3)).card_id
    1001
    """


def ensure_enough_energy(actor: PlayerState, card: MatchCard, cost: int) -> None:
    """Guarda de energia. `energia >= custo`: igual passa e deixa a energia em 0.

    Recebe o custo como `int` e não a carta do catálogo: é o único campo lido, e
    `Unit` e `Spell` não têm base comum.

    >>> ensure_enough_energy(actor, card, 5)
    """
```

`play_unit.py` passa a chamá-las e perde as cópias privadas. `test_play_unit.py`
não muda: ele importa as recusas de `apps.game.engine`, que continua
reexportando as duas.

---

## 4. A regra da §5B

```python
def cast_spell(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5B: desconta a energia, tira a carta da mão, empilha o feitiço.

    **O efeito não acontece aqui.** Nenhum Nexus, modificador, dano, banco ou
    cemitério muda no lançamento; quem aplica é a Resolução de Pilha (§6).

    Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit`.

    Zera a contagem de passes, inclusive quando o oponente já tinha passado uma
    vez: a §5 conta passes **consecutivos**, e uma jogada quebra a sequência.

    A prioridade **não** é trocada aqui -- quem troca é `submit_action`, depois
    de toda ação. É o que dá ao oponente a chance de responder no topo.

    >>> cast_spell(match, actor, action, catalog=catalog)
    >>> match.stack[-1].caster_user_id
    7
    """
```

Quatro guardas específicas, **nesta ordem**, todas antes da primeira
atribuição:

| # | Pergunta | Recusa |
|---|---|---|
| 1 | a carta citada está na mão do autor? | `CardNotInHandError` |
| 2 | a carta é um feitiço? | `CardIsNotASpellError` |
| 3 | `energia_atual >= custo`? | `NotEnoughEnergyError` |
| 4 | o alvo casa com o que o efeito declara? | as quatro da seção 5 |

A ordem é regra: sem a carta resolvida não há custo a citar na recusa de
energia, e sem o efeito não há `TargetKind` a citar na recusa de alvo.

Aceita, na ordem:

```python
actor.energy_current -= spell.energy
actor.hand.remove(card)
match.stack.append(
    StackEntry(
        card=card,
        caster_user_id=actor.user_id,
        target_card_instance_id=action.target_card_instance_id,
    )
)
match.consecutive_passes = 0
```

---

## 5. As recusas de alvo

Todas `IllegalActionError`. Uma classe por pergunta, para que o cliente distinga
os casos sem interpretar texto (FR-060).

```python
class CardIsNotASpellError(IllegalActionError):
    """Usaram a ação de lançar feitiço com uma carta que é unidade.

    Simétrica de `CardIsNotAUnitError`, e recusa pelo mesmo motivo: usar a ação
    errada não é atalho para a certa.

    >>> raise CardIsNotASpellError(card, CardType.UNIT)
    CardIsNotASpellError: card instance 3 (card 15) is a unit: expected a spell
    """


class SpellTakesNoTargetError(IllegalActionError):
    """O efeito não aceita alvo e a jogada mandou um.

    Recusa e não parâmetro ignorado: um alvo que o efeito não sabe usar é jogada
    mal formada, e ignorá-lo esconderia um cliente quebrado.

    >>> raise SpellTakesNoTargetError(card, CardInstanceId(11))
    SpellTakesNoTargetError: card instance 3 (card 1004) takes no target:
    got card instance 11
    """


class SpellNeedsTargetError(IllegalActionError):
    """O efeito exige alvo e a jogada não mandou. Cita o tipo esperado.

    >>> raise SpellNeedsTargetError(card, TargetKind.ENEMY_UNIT)
    SpellNeedsTargetError: card instance 3 (card 1005) needs a target:
    expected an 'enemy_unit'
    """


class WrongSpellTargetSideError(IllegalActionError):
    """O alvo está em campo, no banco errado.

    "Aliado" e "inimigo" são relativos a **quem lança**, e é essa relatividade
    que a recusa cita. Distinta de `SpellTargetNotOnBattlefieldError` de
    propósito: uma é uma tela que ofereceu um alvo que a carta não aceita, a
    outra é uma tela desatualizada, e colapsá-las esconde qual está quebrada.

    >>> raise WrongSpellTargetSideError(CardInstanceId(11), TargetKind.ALLIED_UNIT, 9)
    WrongSpellTargetSideError: card instance 11 belongs to user 9: expected an
    'allied_unit' of the caster
    """


class SpellTargetNotOnBattlefieldError(IllegalActionError):
    """O alvo não está em banco nenhum, no momento do lançamento.

    **Não é fizzle.** Fizzle é o alvo sumir *entre* o lançamento e a resolução, e
    consome a jogada; isto a rejeita. Mesmo fato, momentos diferentes, respostas
    opostas.

    >>> raise SpellTargetNotOnBattlefieldError(CardInstanceId(11))
    SpellTargetNotOnBattlefieldError: card instance 11 is not on the
    battlefield: expected a unit in a bank
    """
```

---

## 6. A tabela de decisão do alvo

| `effect.target_kind` | ação mandou alvo? | onde o alvo está | resultado |
|---|---|---|---|
| `NONE` | não | — | aceita |
| `NONE` | sim | qualquer | `SpellTakesNoTargetError` |
| `ALLIED_UNIT` | não | — | `SpellNeedsTargetError` |
| `ALLIED_UNIT` | sim | banco do lançador | aceita |
| `ALLIED_UNIT` | sim | banco do oponente | `WrongSpellTargetSideError` |
| `ALLIED_UNIT` | sim | banco nenhum | `SpellTargetNotOnBattlefieldError` |
| `ENEMY_UNIT` | não | — | `SpellNeedsTargetError` |
| `ENEMY_UNIT` | sim | banco do oponente | aceita |
| `ENEMY_UNIT` | sim | banco do lançador | `WrongSpellTargetSideError` |
| `ENEMY_UNIT` | sim | banco nenhum | `SpellTargetNotOnBattlefieldError` |

O `target_kind` vem de `effect.target_kind`, campo estruturado do catálogo.
Nenhuma decisão lê `Spell.description` (FR-015).

---

## 7. Garantias

- **Uma recusa não muda nada.** As quatro guardas acontecem antes da primeira
  atribuição, e é a ordem — não um rollback — que garante estado idêntico campo
  a campo, contadores inclusive.
- **O lançamento não aplica efeito.** É o que separa a §5B da §6, e é afirmado
  lendo o estado inteiro depois de lançar.
- **A entrada da pilha guarda identificador.** Nunca uma referência ao
  `BankUnit` — a nota de implementação da §6 proíbe explicitamente, e é o que
  torna o fizzle possível.
- **Nenhum contador avança.** Nem `next_card_instance_id` nem
  `next_roll_ordinal`: lançar feitiço não cunha carta e não sorteia nada.
