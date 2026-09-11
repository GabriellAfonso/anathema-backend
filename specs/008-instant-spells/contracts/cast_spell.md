# Contract: jogar feitiço

**Feature**: `008-instant-spells` | **Substitui**: `specs/006-spell-stack-effects/contracts/cast_spell.md`, `specs/006-spell-stack-effects/contracts/stack_resolution.md` e a parte de feitiço de `specs/007-combat-phase/contracts/defense_window.md`

A ação B da §5, na versão corrigida do Fluxo de Partida: resolve na hora, em
qualquer fase em que o jogador tem a vez, e não passa a vez.

## Porta

Não há porta nova. A ação entra por onde toda ação entra:

```python
from apps.game.engine import CastSpellAction, submit_action

submit_action(
    match,
    CastSpellAction(
        actor_user_id=7,
        card_instance_id=CardInstanceId(3),
        target_card_instance_id=CardInstanceId(11),  # ou omitido
    ),
    catalog=catalog,
    randomness=source,
)
```

`cast_spell` e `validated_spell_cast` **não** são exportados pelo pacote, pela
mesma razão de `play_unit` e `declare_attack`: quem os chama é `round_cycle`.

## A ação

```python
@dataclass(frozen=True, slots=True)
class CastSpellAction:
    action_kind: ClassVar[ActionKind] = ActionKind.CAST_SPELL          # "cast_spell"
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.ACTION, MatchPhase.COMBAT}
    )
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None
```

`target_card_instance_id is None` significa "não mira nada". Nunca significa
"o alvo sumiu" — esse estado não existe mais.

## Pré-condições

Na ordem. A primeira que falha levanta, e a partida fica **idêntica** à de antes
da chamada.

| # | Pergunta | Recusa |
|---|---|---|
| 1 | o autor joga a partida | `NotAParticipantError` |
| 2 | o autor tem a prioridade | `NotYourPriorityError` |
| 3 | a partida não acabou | `MatchIsOverError` |
| 4 | a fase é `ACTION` ou `COMBAT` | `PhaseForbidsActionError` |
| 5 | a carta está na mão do autor | `CardNotInHandError` |
| 6 | a carta é feitiço | `CardIsNotASpellError` |
| 7 | `energy_current >= custo` | `NotEnoughEnergyError` |
| 8a | efeito sem alvo não recebeu alvo | `SpellTakesNoTargetError` |
| 8b | efeito com alvo recebeu alvo | `SpellNeedsTargetError` |
| 8c | o alvo está no banco de alguém | `SpellTargetNotOnBattlefieldError` |
| 8d | o alvo está no banco que o efeito pede | `WrongSpellTargetSideError` |

No Combate, o atacante cai na 2: a prioridade é do defensor.

## Pós-condições (aceita)

Tudo dentro da mesma chamada a `submit_action`, nesta ordem:

1. `actor.energy_current -= custo`
2. a carta sai de `actor.hand`
3. o efeito é aplicado por `apply_spell_effect`, com o alvo resolvido na 8c
   - unidade com dano igual ou maior que a vida vai ao cemitério do dono aqui
   - Nexus alterado apura a §10 aqui
4. a carta vai ao fim de `actor.graveyard` — **depois** de qualquer unidade que o
   efeito matou
5. `match.consecutive_passes = 0`
6. `match.priority_user_id` **não muda**
7. `match.phase` não muda, exceto para `FINISHED` se o passo 3 encerrou a
   partida

Nada fica pendente em lugar nenhum da partida.

## Invariantes

- O mesmo feitiço, com o mesmo alvo, sobre o mesmo tabuleiro, produz o **mesmo
  estado** na Fase de Ação e na janela do defensor, exceto `phase` e `combat`.
- Depois de um feitiço aceito na Fase de Ação, a rodada não fecha sem o oponente
  receber a vez: os passes estão em 0, e fechar pede dois.
- Jogar feitiço nunca troca a prioridade. Jogar unidade, declarar ataque e
  passar sempre trocam.

## Exemplos

**Dano que mata, na Fase de Ação.** A tem a vez, 5 de energia, SUMMONED AX na
mão. B tem MORTEM (2 de vida) no banco.

| Depois de | energia de A | mão de A | banco de B | cemitério de B | cemitério de A | prioridade | passes |
|---|---|---|---|---|---|---|---|
| — | 5 | [AX] | [MORTEM] | [] | [] | A | 1 |
| A joga AX em MORTEM | 0 | [] | [] | [MORTEM] | [AX] | **A** | **0** |
| A passa | 0 | [] | [] | [MORTEM] | [AX] | B | 1 |
| B passa | — | — | — | — | — | rodada seguinte | — |

**Dois feitiços e um ataque na mesma vez.** A, dono do token, joga SOMEONE'S
SHIELD numa unidade própria, depois LIFE POTION, depois declara ataque. As três
jogadas são aceitas; a prioridade só passa a B na terceira.
