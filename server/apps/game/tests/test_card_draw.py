"""O movimento de compra: tirar do topo do deck e pôr na mão.

Todo o resto do jogo compra por aqui -- o setup, o mulligan, a compensação da
§3 e o Upkeep da §9 quando entrar. Se este movimento estiver errado, está
errado em quatro lugares de uma vez.
"""

import pytest

from apps.game.cards import CardId
from apps.game.engine import EmptyDeckError, draw_from_deck_top
from apps.game.match import Match, PlayerState
from apps.game.tests.fake_match_state import fake_cards, fake_new_match

TOP = CardId(15)
BELOW = CardId(22)


@pytest.fixture
def match() -> Match:
    return fake_new_match()


@pytest.fixture
def player(match: Match) -> PlayerState:
    state = match.players[0]
    state.deck = fake_cards(match, [TOP, BELOW])

    return state


def test_the_card_comes_from_the_top_of_the_deck(player: PlayerState) -> None:
    """Topo é `deck[0]`, como `player_state.py` fixou."""
    drawn = draw_from_deck_top(player)

    assert drawn.card_id == TOP


def test_the_card_goes_to_the_end_of_the_hand(player: PlayerState) -> None:
    player.hand = []

    drawn = draw_from_deck_top(player)

    assert player.hand == [drawn]


def test_the_deck_loses_exactly_the_drawn_card(player: PlayerState) -> None:
    drawn = draw_from_deck_top(player)

    assert len(player.deck) == 1
    assert drawn not in player.deck


def test_the_identifier_does_not_change_when_the_card_moves(
    player: PlayerState,
) -> None:
    """Trocar de zona não cunha identidade nova: a carta é a mesma."""
    born = player.deck[0].card_instance_id

    assert draw_from_deck_top(player).card_instance_id == born


def test_drawing_does_not_mint_a_new_identifier(
    match: Match, player: PlayerState
) -> None:
    counter_before = match.next_card_instance_id

    draw_from_deck_top(player)

    assert match.next_card_instance_id == counter_before


def test_an_empty_deck_is_refused_naming_the_owner(player: PlayerState) -> None:
    """Não acontece no setup nem na §9, que reseta o deck antes. Chegar aqui é
    bug de chamador, e a mensagem precisa dizer de quem era o deck."""
    player.deck = []

    with pytest.raises(EmptyDeckError, match=str(player.user_id)):
        draw_from_deck_top(player)
