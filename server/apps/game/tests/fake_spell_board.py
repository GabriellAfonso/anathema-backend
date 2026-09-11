"""Um tabuleiro pronto para exercitar a §5B e a §6, com as cartas reais do MVP.

Diferente de `fake_match_state.py`, que preenche zonas com `card_id` soltos
para exercitar a serialização: aqui as cartas são as do catálogo do MVP, porque
o que está sob teste são os **números** que elas declaram -- 2 de vida, 3 de
dano, 8 de Nexus, 5 de cura, 3 de ataque.

Também diferente de `fake_setup.py`, que passa pelo setup da §3 com deck
embaralhado: uma pilha de feitiços precisa de cartas específicas em mãos
específicas, e sortear até que elas apareçam seria teste que depende da
semente.

A partida sai na Fase de Ação, com o primeiro jogador na prioridade, energia de
sobra dos dois lados e a rodada em 1.
"""

from apps.game.cards import CardCatalog, CardId
from apps.game.match import (
    BankUnit,
    CardInstanceId,
    Match,
    MatchCard,
    MatchPhase,
    PlayerState,
)
from apps.game.tests.fake_match_state import PLAYER_ONE, PLAYER_TWO, fake_new_match

# Os cinco feitiços do MVP, pelos `card_id` de `mvp_catalog`.
SOMEONES_SHIELD = CardId(1001)
MAGIC_BARRIER = CardId(1002)
SACRIFICIAL_FIRE = CardId(1003)
LIFE_POTION = CardId(1004)
SUMMONED_AX = CardId(1005)

# Unidades escolhidas pela vida, que é o que os testes de dano medem.
# KRONOS tem 4, MORTEM tem 2, THE O'JAYS tem 5.
TOUGH_UNIT = CardId(4)
FRAGILE_UNIT = CardId(3)
STURDY_UNIT = CardId(16)

# Energia alta o bastante para lançar qualquer um dos cinco sem que o custo
# entre no caminho de um teste que não é sobre custo. O teto da §12 é 10.
PLENTY_OF_ENERGY = 10


def fake_spell_board(
    *,
    catalog: CardCatalog,
    hand_one: tuple[CardId, ...] = (SOMEONES_SHIELD, SUMMONED_AX),
    hand_two: tuple[CardId, ...] = (SUMMONED_AX, MAGIC_BARRIER),
    bank_one: tuple[CardId, ...] = (TOUGH_UNIT,),
    bank_two: tuple[CardId, ...] = (TOUGH_UNIT,),
) -> Match:
    """Partida na Fase de Ação com as cartas pedidas em cada mão e banco.

    `catalog` entra por parâmetro e não é usado aqui: quem monta o estado não
    precisa do molde, mas quem chama precisa passar o mesmo catálogo ao motor,
    e recebê-lo aqui deixa isso explícito na assinatura do teste.

    >>> match = fake_spell_board(catalog=mvp_catalog())
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """
    match = fake_new_match()
    one, two = match.players

    _fill_side(match, one, hand=hand_one, bank=bank_one)
    _fill_side(match, two, hand=hand_two, bank=bank_two)
    _open_action_phase(match)

    return match


def hand_card(player: PlayerState, card_id: CardId) -> CardInstanceId:
    """O identificador da primeira cópia daquela carta na mão do jogador.

    Os testes miram cópias, não `card_id`, e este é o tradutor entre as duas
    coisas.

    >>> hand_card(one, SOMEONES_SHIELD)
    1
    """
    for card in player.hand:
        if card.card_id == card_id:
            return card.card_instance_id

    raise LookupError(
        f"card {card_id} is not in the hand of user {player.user_id}: "
        f"expected one of {[held.card_id for held in player.hand]}"
    )


def bank_card(player: PlayerState, index: int = 0) -> CardInstanceId:
    """O identificador da unidade naquela posição do banco.

    >>> bank_card(one)
    3
    """
    return player.bank[index].card.card_instance_id


def _fill_side(
    match: Match,
    player: PlayerState,
    *,
    hand: tuple[CardId, ...],
    bank: tuple[CardId, ...],
) -> None:
    """Mão e banco de um lado, cada carta com identidade cunhada pela partida."""
    player.hand = [
        MatchCard(match.mint_card_instance_id(), card_id) for card_id in hand
    ]
    player.bank = [
        BankUnit(card=MatchCard(match.mint_card_instance_id(), card_id))
        for card_id in bank
    ]
    player.energy_max = PLENTY_OF_ENERGY
    player.energy_current = PLENTY_OF_ENERGY


def _open_action_phase(match: Match) -> None:
    """A partida como o Upkeep da §4 a deixaria: token no primeiro, prioridade
    nele, passes zerados, Fase de Ação."""
    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = PLAYER_ONE
    match.consecutive_passes = 0
    match.phase = MatchPhase.ACTION


__all__ = [
    "PLAYER_ONE",
    "PLAYER_TWO",
    "SOMEONES_SHIELD",
    "MAGIC_BARRIER",
    "SACRIFICIAL_FIRE",
    "LIFE_POTION",
    "SUMMONED_AX",
    "TOUGH_UNIT",
    "FRAGILE_UNIT",
    "STURDY_UNIT",
    "PLENTY_OF_ENERGY",
    "fake_spell_board",
    "hand_card",
    "bank_card",
]
