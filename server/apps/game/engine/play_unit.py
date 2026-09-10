"""A ação A da §5: jogar uma unidade da mão.

Quatro perguntas, nesta ordem, e a ordem é parte da regra:

    1. a carta citada está na mão do autor
    2. a carta é uma unidade
    3. a energia atual cobre o custo
    4. o banco tem menos de 6 unidades

A carta precisa ser resolvida antes das duas últimas: sem ela não há custo a
citar na recusa de energia, e não há tipo a citar na recusa de feitiço.

As quatro acontecem **antes** da primeira atribuição. É a ordem que garante que
uma recusa deixa o estado idêntico, e não um rollback que alguém teria de manter
completo -- o campo que um rollback esquecesse não daria erro, daria partida em
estado que nenhuma regra produziria.

A unidade entra pronta e sem dano: não existe doença de invocação (§5A), e
`BankUnit(card=card)` já nasce assim. Não usa a pilha, resolve na hora.
"""

from apps.game.cards import CardCatalog, CardType, Unit
from apps.game.match import BankUnit, CardInstanceId, Match, MatchCard, PlayerState

from .player_action import CardNotInHandError, IllegalActionError, PlayUnitAction

# Fluxo de Partida §12. Mora aqui, e não em `player_state.py`, porque aplicar o
# teto é regra -- e aquele arquivo diz isso de si mesmo, nomeando este ponto: "o
# de banco ao jogar unidade (§5A)".
MAX_BANK_SIZE = 6


class CardIsNotAUnitError(IllegalActionError):
    """Usaram a ação de jogar unidade com uma carta que é feitiço.

    Recusa e não roteamento: jogar feitiço é a ação B da §5, com pilha e alvo, e
    usar a ação errada não é atalho para ela.

    >>> raise CardIsNotAUnitError(CardInstanceId(3), CardId(1001), CardType.SPELL)
    CardIsNotAUnitError: card instance 3 (card 1001) is a spell: expected a unit
    """

    def __init__(self, card: MatchCard, card_type: CardType) -> None:
        super().__init__(
            f"card instance {card.card_instance_id} (card {card.card_id}) "
            f"is a {card_type}: expected a unit"
        )
        self.card_instance_id = card.card_instance_id
        self.card_type = card_type


class NotEnoughEnergyError(IllegalActionError):
    """Custo maior que a energia atual. Cita os dois números.

    >>> raise NotEnoughEnergyError(7, CardInstanceId(3), 3, 1)
    NotEnoughEnergyError: user 7 cannot pay card instance 3: costs 3 energy, has 1
    """

    def __init__(
        self, user_id: int, card_instance_id: CardInstanceId, cost: int, available: int
    ) -> None:
        super().__init__(
            f"user {user_id} cannot pay card instance {card_instance_id}: "
            f"costs {cost} energy, has {available}"
        )
        self.user_id = user_id
        self.card_instance_id = card_instance_id
        self.cost = cost
        self.available = available


class BankIsFullError(IllegalActionError):
    """O banco chegou ao teto da §12. Cita o limite.

    >>> raise BankIsFullError(7, 6)
    BankIsFullError: bank of user 7 holds 6 units: expected fewer than 6 to play
    another
    """

    def __init__(self, user_id: int, bank_size: int) -> None:
        super().__init__(
            f"bank of user {user_id} holds {bank_size} units: "
            f"expected fewer than {MAX_BANK_SIZE} to play another"
        )
        self.user_id = user_id
        self.bank_size = bank_size


def play_unit(
    match: Match,
    actor: PlayerState,
    action: PlayUnitAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5A: desconta a energia, tira a carta da mão, põe a unidade no banco.

    Recebe o `actor` que `ensure_action_allowed` já buscou, em vez de buscá-lo de
    novo -- assim não sobra um segundo lugar de onde `NotAParticipantError`
    pudesse escapar.

    Zera a contagem de passes, inclusive quando o oponente já tinha passado uma
    vez: a §5 conta passes **consecutivos**, e uma jogada quebra a sequência.

    >>> play_unit(match, actor, PlayUnitAction(7, CardInstanceId(3)),
    ...           catalog=catalog)
    >>> actor.bank[-1].card.card_instance_id
    3
    """
    card = _card_in_hand(actor, action.card_instance_id)
    unit = _as_unit(card, catalog)

    _ensure_enough_energy(actor, card, unit)
    _ensure_bank_has_room(actor)

    actor.energy_current -= unit.energy
    actor.hand.remove(card)
    actor.bank.append(BankUnit(card=card))
    match.consecutive_passes = 0


def _card_in_hand(actor: PlayerState, card_instance_id: CardInstanceId) -> MatchCard:
    """Guarda 1: a carta citada está na mão **do autor**.

    A mão consultada é sempre a de quem age, então citar a carta do oponente cai
    aqui, na mesma recusa de uma carta que não existe -- que é o que ela é, do
    ponto de vista de quem está jogando.
    """
    for card in actor.hand:
        if card.card_instance_id == card_instance_id:
            return card

    raise CardNotInHandError(
        card_instance_id,
        actor.user_id,
        [held.card_instance_id for held in actor.hand],
    )


def _as_unit(card: MatchCard, catalog: CardCatalog) -> Unit:
    """Guarda 2: o molde da carta é uma unidade.

    `isinstance` e não comparação de faixa de `card_id`: a faixa é convenção de
    alocação e `cards/card.py` proíbe explicitamente derivar tipo dela.
    """
    template = catalog.card(card.card_id)

    if not isinstance(template, Unit):
        raise CardIsNotAUnitError(card, template.card_type)

    return template


def _ensure_enough_energy(actor: PlayerState, card: MatchCard, unit: Unit) -> None:
    """Guarda 3: `energia >= custo`. Igual passa, e deixa a energia em 0."""
    if actor.energy_current >= unit.energy:
        return

    raise NotEnoughEnergyError(
        actor.user_id, card.card_instance_id, unit.energy, actor.energy_current
    )


def _ensure_bank_has_room(actor: PlayerState) -> None:
    """Guarda 4: `banco < 6`. Com 5 a jogada passa e o banco vai a 6."""
    if len(actor.bank) < MAX_BANK_SIZE:
        return

    raise BankIsFullError(actor.user_id, len(actor.bank))
