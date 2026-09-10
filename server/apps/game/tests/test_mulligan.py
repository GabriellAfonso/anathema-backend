"""O mulligan da §3, e sobretudo a ordem das operações.

O teste central deste arquivo é `test_a_returned_card_cannot_come_back_in_the
_replacement_draw`: é ele que pega a troca de (b) por (c), que muda o jogo e
que nenhum teste de contagem percebe.
"""

import pytest

from apps.game.engine import (
    CardNotInHandError,
    MulliganAlreadyTakenError,
    record_mulligan,
)
from apps.game.match import CardInstanceId, Match, MatchPhase, NotAParticipantError
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match

PLAYER_ONE = 7
PLAYER_TWO = 9
OUTSIDER = 99

OPENING_HAND = 4
DECK_AFTER_OPENING_HAND = 36


@pytest.fixture
def match() -> Match:
    return fake_started_match(PLAYER_ONE, PLAYER_TWO)


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def hand_ids(match: Match, user_id: int) -> list[CardInstanceId]:
    return [card.card_instance_id for card in match.player(user_id).hand]


def deck_ids(match: Match, user_id: int) -> list[CardInstanceId]:
    return [card.card_instance_id for card in match.player(user_id).deck]


# --- A ordem das operações ------------------------------------------------


def test_a_returned_card_cannot_come_back_in_the_replacement_draw(
    match: Match, source: RandomSource
) -> None:
    """As escolhidas saem da mão, o jogador compra, e **só então** elas voltam
    ao deck. Invertendo (b) e (c), uma carta jogada fora pode ser recomprada."""
    returned = hand_ids(match, PLAYER_ONE)[:2]

    record_mulligan(match, PLAYER_ONE, returned, randomness=source)

    assert not set(returned) & set(hand_ids(match, PLAYER_ONE))


def test_the_returned_cards_are_back_in_the_deck(
    match: Match, source: RandomSource
) -> None:
    returned = hand_ids(match, PLAYER_ONE)[:2]

    record_mulligan(match, PLAYER_ONE, returned, randomness=source)

    assert set(returned) <= set(deck_ids(match, PLAYER_ONE))


def test_the_returned_card_keeps_the_identifier_it_had(
    match: Match, source: RandomSource
) -> None:
    """É a mesma carta voltando, não uma nova."""
    returned = match.player(PLAYER_ONE).hand[0]
    born = returned.card_instance_id

    record_mulligan(match, PLAYER_ONE, [born], randomness=source)

    assert returned in match.player(PLAYER_ONE).deck
    assert returned.card_instance_id == born


def test_the_mulligan_mints_no_new_identifier(
    match: Match, source: RandomSource
) -> None:
    counter_before = match.next_card_instance_id

    record_mulligan(match, PLAYER_ONE, hand_ids(match, PLAYER_ONE), randomness=source)

    assert match.next_card_instance_id == counter_before


@pytest.mark.parametrize("returned_count", [0, 1, 2, 3, 4])
def test_the_counts_hold_for_every_allowed_amount(
    match: Match, source: RandomSource, returned_count: int
) -> None:
    """Zero e quatro são escolhas válidas, e as duas pontas contam igual."""
    returned = hand_ids(match, PLAYER_ONE)[:returned_count]

    record_mulligan(match, PLAYER_ONE, returned, randomness=source)

    assert len(match.player(PLAYER_ONE).hand) == OPENING_HAND
    assert len(match.player(PLAYER_ONE).deck) == DECK_AFTER_OPENING_HAND


def test_returning_nothing_is_a_complete_answer(
    match: Match, source: RandomSource
) -> None:
    """Trocar 0 é diferente de ainda não ter respondido."""
    before = hand_ids(match, PLAYER_ONE)

    record_mulligan(match, PLAYER_ONE, [], randomness=source)

    assert hand_ids(match, PLAYER_ONE) == before
    assert match.awaiting_mulligan_user_ids == (PLAYER_TWO,)


def test_returning_the_whole_hand_replaces_it(
    match: Match, source: RandomSource
) -> None:
    before = hand_ids(match, PLAYER_ONE)

    record_mulligan(match, PLAYER_ONE, before, randomness=source)

    assert not set(before) & set(hand_ids(match, PLAYER_ONE))
    assert set(before) <= set(deck_ids(match, PLAYER_ONE))


# --- A espera -------------------------------------------------------------


def test_one_answer_does_not_close_the_setup(
    match: Match, source: RandomSource
) -> None:
    record_mulligan(match, PLAYER_ONE, [], randomness=source)

    assert match.phase is MatchPhase.MULLIGAN
    assert match.token_holder_user_id is None


def test_nobody_draws_the_fifth_card_before_both_answer(
    match: Match, source: RandomSource
) -> None:
    record_mulligan(match, PLAYER_ONE, [], randomness=source)

    for player in match.players:
        assert len(player.hand) == OPENING_HAND


def test_the_second_answer_closes_the_setup(match: Match, source: RandomSource) -> None:
    record_mulligan(match, PLAYER_ONE, [], randomness=source)
    record_mulligan(match, PLAYER_TWO, [], randomness=source)

    assert match.awaiting_mulligan_user_ids == ()
    assert match.phase is MatchPhase.UPKEEP


# --- As recusas -----------------------------------------------------------


def test_a_second_mulligan_from_the_same_player_is_refused(
    match: Match, source: RandomSource
) -> None:
    record_mulligan(match, PLAYER_ONE, [], randomness=source)

    with pytest.raises(MulliganAlreadyTakenError, match=f"user {PLAYER_ONE}"):
        record_mulligan(match, PLAYER_ONE, [], randomness=source)


def test_a_mulligan_after_the_setup_is_refused_the_same_way(
    match: Match, source: RandomSource
) -> None:
    """Com os dois marcados não sobra janela, e a pergunta é a mesma."""
    record_mulligan(match, PLAYER_ONE, [], randomness=source)
    record_mulligan(match, PLAYER_TWO, [], randomness=source)

    with pytest.raises(MulliganAlreadyTakenError):
        record_mulligan(match, PLAYER_TWO, [], randomness=source)


def test_a_stranger_is_refused_naming_the_user_id(
    match: Match, source: RandomSource
) -> None:
    with pytest.raises(NotAParticipantError, match=f"user {OUTSIDER}"):
        record_mulligan(match, OUTSIDER, [], randomness=source)


def test_a_card_outside_the_hand_is_refused_naming_the_card(
    match: Match, source: RandomSource
) -> None:
    from_the_deck = deck_ids(match, PLAYER_ONE)[0]

    with pytest.raises(CardNotInHandError, match=str(from_the_deck)):
        record_mulligan(match, PLAYER_ONE, [from_the_deck], randomness=source)


def test_the_opponents_card_is_refused(match: Match, source: RandomSource) -> None:
    theirs = hand_ids(match, PLAYER_TWO)[0]

    with pytest.raises(CardNotInHandError, match=str(theirs)):
        record_mulligan(match, PLAYER_ONE, [theirs], randomness=source)


def test_the_same_card_twice_is_refused(match: Match, source: RandomSource) -> None:
    """A segunda ocorrência já não está entre as cartas restantes -- que é o
    que ela é, e por isso cai na mesma recusa."""
    mine = hand_ids(match, PLAYER_ONE)[0]

    with pytest.raises(CardNotInHandError, match=str(mine)):
        record_mulligan(match, PLAYER_ONE, [mine, mine], randomness=source)


def test_a_refusal_leaves_the_state_exactly_as_it_was(
    match: Match, source: RandomSource
) -> None:
    """Validação inteira antes de qualquer mutação: mão, deck e a marca de
    quem já respondeu ficam intactos."""
    hand_before = hand_ids(match, PLAYER_ONE)
    deck_before = deck_ids(match, PLAYER_ONE)
    from_the_deck = deck_before[0]

    with pytest.raises(CardNotInHandError):
        record_mulligan(match, PLAYER_ONE, [from_the_deck], randomness=source)

    assert hand_ids(match, PLAYER_ONE) == hand_before
    assert deck_ids(match, PLAYER_ONE) == deck_before
    assert match.awaiting_mulligan_user_ids == (PLAYER_ONE, PLAYER_TWO)
