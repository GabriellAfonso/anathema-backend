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

from .player_action import (
    IllegalActionError,
    PlayUnitAction,
    card_in_hand,
    ensure_enough_energy,
)

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
    card = card_in_hand(actor, action.card_instance_id)
    unit = _as_unit(card, catalog)

    ensure_enough_energy(actor, card, unit.energy)
    _ensure_bank_has_room(actor)

    actor.energy_current -= unit.energy
    actor.hand.remove(card)
    actor.bank.append(BankUnit(card=card))
    match.consecutive_passes = 0


def _as_unit(card: MatchCard, catalog: CardCatalog) -> Unit:
    """Guarda 2: o molde da carta é uma unidade.

    `isinstance` e não comparação de faixa de `card_id`: a faixa é convenção de
    alocação e `cards/card.py` proíbe explicitamente derivar tipo dela.
    """
    template = catalog.card(card.card_id)

    if not isinstance(template, Unit):
        raise CardIsNotAUnitError(card, template.card_type)

    return template


def _ensure_bank_has_room(actor: PlayerState) -> None:
    """Guarda 4: `banco < 6`. Com 5 a jogada passa e o banco vai a 6."""
    if len(actor.bank) < MAX_BANK_SIZE:
        return

    raise BankIsFullError(actor.user_id, len(actor.bank))
