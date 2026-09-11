"""A ação B da §5: lançar um feitiço da mão.

Quatro perguntas, nesta ordem, e a ordem é parte da regra:

    1. a carta citada está na mão do autor
    2. a carta é um feitiço
    3. a energia atual cobre o custo
    4. o alvo casa com o que o efeito declara

A carta precisa ser resolvida antes da terceira -- sem ela não há custo a citar
na recusa de energia --, e o efeito antes da quarta -- sem ele não há
`TargetKind` a citar na recusa de alvo.

As quatro acontecem **antes** da primeira atribuição, como em `play_unit.py`. É
a ordem que garante que uma recusa deixa o estado idêntico, e não um rollback
que alguém teria de manter completo.

**O efeito não acontece aqui.** O feitiço vai para o topo da pilha e resolve
depois, quando os dois jogadores passarem (§6). É essa espera que dá ao oponente
a chance de responder, e é a única diferença entre esta ação e a §5A.

O motor decide exigência de alvo, tipo de alvo e duração pelos campos
estruturados do catálogo. Regra que dependa de `Spell.description` é bug, e
`cards/effects.py` diz isso de si mesmo.
"""

from apps.game.cards import CardCatalog, CardType, Spell, TargetKind
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchCard,
    PlayerState,
    StackEntry,
)

from .player_action import (
    CastSpellAction,
    IllegalActionError,
    card_in_hand,
    ensure_enough_energy,
)


class CardIsNotASpellError(IllegalActionError):
    """Usaram a ação de lançar feitiço com uma carta que é unidade.

    Simétrica de `CardIsNotAUnitError`, e recusa pelo mesmo motivo: usar a ação
    errada não é atalho para a certa.

    >>> raise CardIsNotASpellError(card, CardType.UNIT)
    CardIsNotASpellError: card instance 3 (card 15) is a unit: expected a spell
    """

    def __init__(self, card: MatchCard, card_type: CardType) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"is a {card_type}: expected a spell"
        )
        self.card_instance_id = card.card_instance_id
        self.card_type = card_type


class SpellTakesNoTargetError(IllegalActionError):
    """O efeito não aceita alvo e a jogada mandou um.

    Recusa e não parâmetro ignorado: um alvo que o efeito não sabe usar é
    jogada mal formada, e ignorá-lo esconderia um cliente quebrado.

    >>> raise SpellTakesNoTargetError(card, CardInstanceId(11))
    SpellTakesNoTargetError: card instance 3 (card 1004) takes no target: got
    card instance 11
    """

    def __init__(
        self, card: MatchCard, target_card_instance_id: CardInstanceId
    ) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"takes no target: got card instance {target_card_instance_id}"
        )
        self.card_instance_id = card.card_instance_id
        self.target_card_instance_id = target_card_instance_id


class SpellNeedsTargetError(IllegalActionError):
    """O efeito exige alvo e a jogada não mandou. Cita o tipo esperado.

    >>> raise SpellNeedsTargetError(card, TargetKind.ENEMY_UNIT)
    SpellNeedsTargetError: card instance 3 (card 1005) needs a target: expected
    an 'enemy_unit'
    """

    def __init__(self, card: MatchCard, expected: TargetKind) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"needs a target: expected an '{expected}'"
        )
        self.card_instance_id = card.card_instance_id
        self.expected = expected


class WrongSpellTargetSideError(IllegalActionError):
    """O alvo está em campo, no banco errado.

    "Aliado" e "inimigo" são relativos a **quem lança**, e é essa relatividade
    que a recusa cita.

    Distinta de `SpellTargetNotOnBattlefieldError` de propósito: uma é uma tela
    que ofereceu um alvo que a carta não aceita, a outra é uma tela
    desatualizada, e colapsá-las esconderia qual das duas está quebrada.

    >>> raise WrongSpellTargetSideError(CardInstanceId(11), TargetKind.ALLIED_UNIT, 9)
    WrongSpellTargetSideError: card instance 11 belongs to user 9: expected an
    'allied_unit' of the caster
    """

    def __init__(
        self,
        target_card_instance_id: CardInstanceId,
        expected: TargetKind,
        owner_user_id: int,
    ) -> None:
        super().__init__(
            f"card instance {target_card_instance_id} belongs to user "
            f"{owner_user_id}: expected an '{expected}' of the caster"
        )
        self.target_card_instance_id = target_card_instance_id
        self.expected = expected
        self.owner_user_id = owner_user_id


class SpellTargetNotOnBattlefieldError(IllegalActionError):
    """O alvo não está em banco nenhum, no momento do lançamento.

    **Não é fizzle.** Fizzle é o alvo sumir *entre* o lançamento e a resolução,
    e consome a jogada; isto a rejeita. Mesmo fato, momentos diferentes,
    respostas opostas.

    >>> raise SpellTargetNotOnBattlefieldError(CardInstanceId(11))
    SpellTargetNotOnBattlefieldError: card instance 11 is not on the
    battlefield: expected a unit in a bank
    """

    def __init__(self, target_card_instance_id: CardInstanceId) -> None:
        super().__init__(
            f"card instance {target_card_instance_id} is not on the "
            f"battlefield: expected a unit in a bank"
        )
        self.target_card_instance_id = target_card_instance_id


def cast_spell(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5B: desconta a energia, tira a carta da mão, empilha o feitiço.

    Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit`.

    Zera a contagem de passes, inclusive quando o oponente já tinha passado uma
    vez: a §5 conta passes **consecutivos**, e uma jogada quebra a sequência.

    A prioridade **não** é trocada aqui -- quem troca é `submit_action`, depois
    de toda ação. É essa troca que dá ao oponente a chance de responder no topo.

    >>> cast_spell(match, actor, action, catalog=catalog)
    >>> match.stack[-1].caster_user_id
    7
    """
    card = card_in_hand(actor, action.card_instance_id)
    spell = _as_spell(card, catalog)

    ensure_enough_energy(actor, card, spell.energy)
    _ensure_target_matches_effect(match, actor, action, card, spell)

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


def _as_spell(card: MatchCard, catalog: CardCatalog) -> Spell:
    """Guarda 2: o molde da carta é um feitiço.

    `isinstance` e não comparação de faixa de `card_id`: a faixa é convenção de
    alocação e `cards/card.py` proíbe derivar tipo dela.
    """
    template = catalog.card(card.card_id)

    if not isinstance(template, Spell):
        raise CardIsNotASpellError(card, template.card_type)

    return template


def _ensure_target_matches_effect(
    match: Match,
    actor: PlayerState,
    action: CastSpellAction,
    card: MatchCard,
    spell: Spell,
) -> None:
    """Guarda 4: o alvo casa com o que o efeito declara.

    Lê `effect.target_kind`, campo estruturado do catálogo, e nunca a descrição
    em português da carta.
    """
    expected = spell.effect.target_kind
    target_card_instance_id = action.target_card_instance_id

    if expected is TargetKind.NONE:
        _reject_unwanted_target(card, target_card_instance_id)
        return

    if target_card_instance_id is None:
        raise SpellNeedsTargetError(card, expected)

    _ensure_target_is_on_the_right_side(match, actor, target_card_instance_id, expected)


def _reject_unwanted_target(
    card: MatchCard, target_card_instance_id: CardInstanceId | None
) -> None:
    """Feitiço sem alvo que recebeu um."""
    if target_card_instance_id is None:
        return

    raise SpellTakesNoTargetError(card, target_card_instance_id)


def _ensure_target_is_on_the_right_side(
    match: Match,
    actor: PlayerState,
    target_card_instance_id: CardInstanceId,
    expected: TargetKind,
) -> None:
    """O alvo está no banco que o `TargetKind` manda, relativo ao lançador.

    Duas recusas diferentes porque são dois erros de cliente diferentes: o alvo
    no banco errado é uma tela que ofereceu o que a carta não aceita; o alvo em
    banco nenhum é uma tela desatualizada.
    """
    owner_user_id = _owner_of(match, target_card_instance_id)

    if owner_user_id is None:
        raise SpellTargetNotOnBattlefieldError(target_card_instance_id)

    if owner_user_id == _expected_owner(match, actor, expected):
        return

    raise WrongSpellTargetSideError(target_card_instance_id, expected, owner_user_id)


def _owner_of(match: Match, target_card_instance_id: CardInstanceId) -> int | None:
    """De quem é o banco em que o alvo está, ou `None` se ele não está em campo.

    `None` não é erro aqui: alvo fora de campo é uma das recusas previstas, e
    quem pergunta precisa distingui-la do banco errado.
    """
    for player in match.players:
        if any(
            unit.card.card_instance_id == target_card_instance_id
            for unit in player.bank
        ):
            return player.user_id

    return None


def _expected_owner(match: Match, actor: PlayerState, expected: TargetKind) -> int:
    """De quem o alvo teria de ser. "Aliado" e "inimigo" são relativos a quem
    lança, e é aqui que essa relatividade vira um `user_id`."""
    if expected is TargetKind.ALLIED_UNIT:
        return actor.user_id

    return match.opponent_of(actor.user_id).user_id
