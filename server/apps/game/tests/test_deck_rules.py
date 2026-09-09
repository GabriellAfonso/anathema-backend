"""Validação de deck: aceitar 40 cartas legais, recusar nomeando o problema."""

import pytest

from apps.game.cards.card import CardId
from apps.game.cards.deck_rules import (
    DECK_SIZE,
    MAX_COPIES_PER_CARD,
    Deck,
    InvalidDeckError,
    TooManyCopies,
    UnknownDeckCard,
    WrongDeckSize,
    deck_problems,
    ensure_valid_deck,
)
from apps.game.cards.mvp_catalog import MVP_UNITS, mvp_catalog


def _valid_deck() -> Deck:
    """40 cartas: 3 cópias de 13 unidades mais 1 de uma décima quarta."""
    thirteen = [unit.card_id for unit in MVP_UNITS[:13]]
    deck = thirteen * MAX_COPIES_PER_CARD

    return [*deck, MVP_UNITS[13].card_id]


def test_a_legal_deck_has_no_problems() -> None:
    deck = _valid_deck()

    assert len(deck) == DECK_SIZE
    assert deck_problems(deck, mvp_catalog()) == ()


def test_a_short_deck_names_the_count_and_the_requirement() -> None:
    deck = _valid_deck()[:-1]

    problems = deck_problems(deck, mvp_catalog())

    assert problems == (WrongDeckSize(found=39, required=40),)
    assert "39" in problems[0].message
    assert "40" in problems[0].message


def test_an_empty_deck_is_refused_with_its_real_count() -> None:
    problems = deck_problems([], mvp_catalog())

    assert WrongDeckSize(found=0, required=40) in problems


def test_a_fourth_copy_names_the_card_and_the_count() -> None:
    """3 cópias passam, a quarta é o problema."""
    over_limit = MVP_UNITS[0].card_id
    deck = [*_valid_deck()[:-1], over_limit]

    problems = deck_problems(deck, mvp_catalog())

    assert problems == (
        TooManyCopies(card_id=over_limit, count=4, limit=MAX_COPIES_PER_CARD),
    )
    assert str(over_limit) in problems[0].message
    assert "4" in problems[0].message


def test_an_unknown_card_id_is_named() -> None:
    ghost = CardId(9999)
    deck = [*_valid_deck()[:-1], ghost]

    problems = deck_problems(deck, mvp_catalog())

    assert problems == (UnknownDeckCard(card_id=ghost),)
    assert "9999" in problems[0].message


def test_an_unknown_card_is_reported_once_not_once_per_copy() -> None:
    deck = [*_valid_deck()[:-3], CardId(9999), CardId(9999), CardId(9999)]

    problems = deck_problems(deck, mvp_catalog())

    assert problems == (UnknownDeckCard(card_id=CardId(9999)),)


def test_a_deck_with_several_faults_reports_all_of_them() -> None:
    """Parar no primeiro problema esconderia os outros dois."""
    deck = [CardId(9999)] * 41

    problems = deck_problems(deck, mvp_catalog())

    assert WrongDeckSize(found=41, required=40) in problems
    assert TooManyCopies(card_id=CardId(9999), count=41, limit=3) in problems
    assert UnknownDeckCard(card_id=CardId(9999)) in problems


def test_ensure_valid_deck_accepts_a_legal_deck_in_silence() -> None:
    """Sem asserção de retorno: o contrato é não levantar."""
    ensure_valid_deck(_valid_deck(), mvp_catalog())


def test_ensure_valid_deck_raises_with_every_problem_attached() -> None:
    deck = [CardId(9999)] * 41

    with pytest.raises(InvalidDeckError) as raised:
        ensure_valid_deck(deck, mvp_catalog())

    assert len(raised.value.problems) == 3
    assert "9999" in str(raised.value)
    assert "41" in str(raised.value)
