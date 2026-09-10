"""A compra da §9: a única porta pela qual uma carta sai do deck e entra na mão.

Todo o resto do jogo compra por aqui -- o setup, o mulligan, a compensação da
§3 e o Upkeep da §4 quando entrar. Se esta regra estiver errada, está errada em
todos eles de uma vez.

O que estes testes separam de uma implementação quase certa: a ordem entre as
duas guardas (mão cheia com deck vazio **não** reseta) e a guarda dentro do
laço da compra múltipla (comprar 3 com 8 na mão dá 10, não 11). Nenhuma das
duas aparece numa contagem de mão feita só no caso feliz.
"""

import pytest

from apps.game.engine import (
    MAX_HAND_SIZE,
    NegativeDrawCountError,
    draw_card,
    draw_cards,
)
from apps.game.match import BankUnit, Match, NotAParticipantError, PlayerState
from apps.game.tests.fake_match_state import (
    OUTSIDER,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource

TOP = 15
BELOW = 22
FULL_HAND = list(range(1, MAX_HAND_SIZE + 1))


@pytest.fixture
def match() -> Match:
    return fake_new_match()


@pytest.fixture
def source() -> ScriptedRandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def player(match: Match) -> PlayerState:
    """Duas cartas no deck, mão vazia: o caminho feliz da §9."""
    state = match.players[0]
    state.deck = fake_cards(match, [TOP, BELOW])

    return state


# --------------------------------------------------------------------------
# A compra normal (passo 3 da §9)
# --------------------------------------------------------------------------


def test_the_card_comes_from_the_top_of_the_deck(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Topo é `deck[0]`, como `player_state.py` fixou."""
    drawn = draw_card(match, player.user_id, randomness=source)

    assert drawn is not None
    assert drawn.card_id == TOP


def test_the_card_goes_to_the_end_of_the_hand(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    drawn = draw_card(match, player.user_id, randomness=source)

    assert player.hand == [drawn]


def test_the_deck_loses_exactly_the_drawn_card(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    drawn = draw_card(match, player.user_id, randomness=source)

    assert len(player.deck) == 1
    assert drawn not in player.deck


def test_the_identifier_does_not_change_when_the_card_moves(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Trocar de zona não cunha identidade nova: a carta é a mesma."""
    born = player.deck[0].card_instance_id
    drawn = draw_card(match, player.user_id, randomness=source)

    assert drawn is not None
    assert drawn.card_instance_id == born


def test_drawing_does_not_mint_a_new_identifier(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    counter_before = match.next_card_instance_id

    draw_card(match, player.user_id, randomness=source)

    assert match.next_card_instance_id == counter_before


def test_drawing_without_a_reset_consumes_no_randomness(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """O contador de sorteios só anda quando um reset acontece."""
    ordinal_before = match.next_roll_ordinal

    draw_card(match, player.user_id, randomness=source)

    assert match.next_roll_ordinal == ordinal_before
    assert source.rolls == []


def test_drawing_does_not_discard(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Nenhum caminho da §9 põe carta no cemitério."""
    player.graveyard = fake_cards(match, [31])
    player.bank = [BankUnit(card=card) for card in fake_cards(match, [32])]
    graveyard_before, bank_before = list(player.graveyard), list(player.bank)

    draw_card(match, player.user_id, randomness=source)

    assert player.graveyard == graveyard_before
    assert player.bank == bank_before


def test_the_opponent_is_not_touched(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """A compra é de um jogador só."""
    opponent = match.players[1]
    opponent.deck = fake_cards(match, [41, 42])
    deck_before = list(opponent.deck)

    draw_card(match, player.user_id, randomness=source)

    assert opponent.deck == deck_before
    assert opponent.hand == []


def test_a_user_id_from_outside_the_match_is_refused(
    match: Match, source: ScriptedRandomSource
) -> None:
    """Pedir a compra de quem não joga esta partida é bug, e levanta."""
    with pytest.raises(NotAParticipantError, match=str(OUTSIDER)):
        draw_card(match, OUTSIDER, randomness=source)


# --------------------------------------------------------------------------
# A guarda de mão (passo 1 da §9)
# --------------------------------------------------------------------------


def test_a_full_hand_does_not_draw(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Não é erro nem recusa: é uma compra que não aconteceu."""
    player.hand = fake_cards(match, FULL_HAND)

    assert draw_card(match, player.user_id, randomness=source) is None


def test_a_full_hand_leaves_every_zone_untouched(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Nada é queimado, nada vai para o cemitério, o deck não anda."""
    player.hand = fake_cards(match, FULL_HAND)
    player.graveyard = fake_cards(match, [31])
    hand_before = list(player.hand)
    deck_before = list(player.deck)
    graveyard_before = list(player.graveyard)

    draw_card(match, player.user_id, randomness=source)

    assert player.hand == hand_before
    assert player.deck == deck_before
    assert player.graveyard == graveyard_before


def test_a_full_hand_does_not_mint_a_new_identifier(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    player.hand = fake_cards(match, FULL_HAND)
    counter_before = match.next_card_instance_id

    draw_card(match, player.user_id, randomness=source)

    assert match.next_card_instance_id == counter_before


def test_nine_cards_in_hand_still_draws(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """A guarda impede a 11ª carta, não a 10ª."""
    player.hand = fake_cards(match, FULL_HAND[:-1])

    assert draw_card(match, player.user_id, randomness=source) is not None
    assert len(player.hand) == MAX_HAND_SIZE


def test_a_full_hand_with_an_empty_deck_does_not_reset(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """A ordem das guardas é a regra: a de mão é verificada antes do reset.

    Este é o teste que separa a ordem da §9 de qualquer outra ordem possível.
    Com o reset primeiro, o cemitério deste jogador seria embaralhado de volta
    ao deck sem que nenhuma carta fosse comprada.
    """
    player.hand = fake_cards(match, FULL_HAND)
    player.deck = []
    player.graveyard = fake_cards(match, [31, 32, 33])
    graveyard_before = list(player.graveyard)
    ordinal_before = match.next_roll_ordinal

    assert draw_card(match, player.user_id, randomness=source) is None
    assert player.graveyard == graveyard_before
    assert player.deck == []
    assert match.next_roll_ordinal == ordinal_before


# --------------------------------------------------------------------------
# O reset visto pela compra (passo 2 da §9)
# --------------------------------------------------------------------------


def test_an_empty_deck_resets_and_then_draws(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Uma chamada só: quem chamou vê uma compra normal."""
    player.hand = fake_cards(match, [41, 42])
    player.deck = []
    player.graveyard = fake_cards(match, [31, 32, 33, 34])

    drawn = draw_card(match, player.user_id, randomness=source)

    assert drawn is not None
    assert len(player.hand) == 3
    assert len(player.deck) == 3
    assert player.graveyard == []


def test_the_reset_uses_only_the_owner_graveyard(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Os dois cemitérios nunca se misturam."""
    player.deck = []
    player.graveyard = []
    opponent = match.players[1]
    opponent.graveyard = fake_cards(match, [31, 32, 33])
    opponent_before = list(opponent.graveyard)

    assert draw_card(match, player.user_id, randomness=source) is None
    assert opponent.graveyard == opponent_before


def test_the_reset_is_unlimited(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Nenhuma partida acaba por deck: só Nexus a 0 encerra (§9, §10).

    Cem resets encadeados, devolvendo a carta comprada ao cemitério a cada
    volta. Não existe contador nem teto que possa esgotar.
    """
    player.deck = []
    player.graveyard = fake_cards(match, [31])

    for _ in range(100):
        drawn = draw_card(match, player.user_id, randomness=source)

        assert drawn is not None
        player.graveyard.append(player.hand.pop())

    assert match.next_roll_ordinal == 101


# --------------------------------------------------------------------------
# Deck e cemitério vazios ao mesmo tempo -- defesa contra estado corrompido
# --------------------------------------------------------------------------


def test_an_empty_deck_and_an_empty_graveyard_do_not_draw(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Não há de onde comprar nem o que resetar, e mesmo assim não levanta.

    Inalcançável em partida legal: as 40 cartas de um jogador não cabem entre
    mão (teto de 10), banco (teto de 6) e pilha. Testado porque a alternativa
    -- levantar -- mataria a partida pelo motivo que a §9 proíbe.
    """
    player.deck = []
    player.hand = fake_cards(match, [41, 42])
    hand_before = list(player.hand)
    ordinal_before = match.next_roll_ordinal

    assert draw_card(match, player.user_id, randomness=source) is None
    assert player.hand == hand_before
    assert player.deck == []
    assert player.graveyard == []
    assert match.next_roll_ordinal == ordinal_before


# --------------------------------------------------------------------------
# Compra múltipla
# --------------------------------------------------------------------------


def test_drawing_many_returns_the_cards_in_the_order_they_entered(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    player.deck = fake_cards(match, [31, 32, 33])

    drawn = draw_cards(match, player.user_id, 3, randomness=source)

    assert [card.card_id for card in drawn] == [31, 32, 33]
    assert player.hand == drawn


def test_drawing_many_stops_at_the_hand_limit(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Comprar 3 com 8 na mão dá 10, não 11.

    É o teste que separa esta implementação de uma que verifique a guarda uma
    vez só, antes do laço.
    """
    player.hand = fake_cards(match, FULL_HAND[:-2])
    player.deck = fake_cards(match, [31, 32, 33, 34])

    drawn = draw_cards(match, player.user_id, 3, randomness=source)

    assert len(drawn) == 2
    assert len(player.hand) == MAX_HAND_SIZE
    assert len(player.deck) == 2


def test_drawing_many_with_a_full_hand_draws_nothing(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    player.hand = fake_cards(match, FULL_HAND)
    deck_before = list(player.deck)

    assert draw_cards(match, player.user_id, 3, randomness=source) == []
    assert player.deck == deck_before


def test_drawing_many_can_cross_a_reset(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """O reset acontece na carta em que o deck zerou, e o laço continua."""
    player.hand = fake_cards(match, [41, 42])
    player.deck = fake_cards(match, [31])
    player.graveyard = fake_cards(match, [51, 52, 53])

    drawn = draw_cards(match, player.user_id, 3, randomness=source)

    assert len(drawn) == 3
    assert len(player.hand) == 5
    assert player.graveyard == []


def test_drawing_zero_cards_is_valid_and_changes_nothing(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """Existe porque o mulligan de 0 cartas repõe 0."""
    deck_before = list(player.deck)

    assert draw_cards(match, player.user_id, 0, randomness=source) == []
    assert player.deck == deck_before
    assert player.hand == []


def test_a_negative_count_is_refused_naming_the_value(
    match: Match, player: PlayerState, source: ScriptedRandomSource
) -> None:
    """`range(-3)` é vazio, então sem a recusa isto passaria como "comprei 0"."""
    with pytest.raises(NegativeDrawCountError, match="-3"):
        draw_cards(match, player.user_id, -3, randomness=source)
