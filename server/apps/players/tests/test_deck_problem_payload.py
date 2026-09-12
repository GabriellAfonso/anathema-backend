"""Cada problema de deck vira JSON com chave estável e valores ofensores."""

from typing import get_args

from apps.game.cards import (
    CardId,
    DeckProblem,
    TooManyCopies,
    UnknownDeckCard,
    WrongDeckSize,
)
from apps.players.services.deck_problem_payload import (
    deck_problem_payload,
    deck_problems_payload,
)


def test_wrong_deck_size_names_what_was_found_and_what_is_required() -> None:
    payload = deck_problem_payload(WrongDeckSize(found=12, required=40))

    assert payload["kind"] == "wrong_deck_size"
    assert payload["found"] == 12
    assert payload["required"] == 40


def test_too_many_copies_names_the_card_and_the_count() -> None:
    """A recusa que a spec exige nominalmente: a carta e quantas vezes ela
    apareceu, não um "deck inválido" genérico."""
    payload = deck_problem_payload(TooManyCopies(card_id=CardId(12), count=4, limit=3))

    assert payload["kind"] == "too_many_copies"
    assert payload["card_id"] == 12
    assert payload["count"] == 4
    assert payload["limit"] == 3


def test_unknown_card_names_the_identifier() -> None:
    payload = deck_problem_payload(UnknownDeckCard(CardId(9999)))

    assert payload["kind"] == "unknown_card"
    assert payload["card_id"] == 9999


def test_the_message_is_the_one_the_rules_already_wrote() -> None:
    """O mesmo texto no HTTP e no websocket: quem o escreve é quem conhece a
    regra, e não esta tradução."""
    problem = TooManyCopies(card_id=CardId(12), count=4, limit=3)

    assert deck_problem_payload(problem)["message"] == problem.message


def test_all_problems_come_out_together_and_in_order() -> None:
    problems = (
        WrongDeckSize(found=39, required=40),
        TooManyCopies(card_id=CardId(12), count=4, limit=3),
        UnknownDeckCard(CardId(9999)),
    )

    kinds = [payload["kind"] for payload in deck_problems_payload(problems)]

    assert kinds == ["wrong_deck_size", "too_many_copies", "unknown_card"]


def test_every_problem_in_the_union_has_a_payload() -> None:
    """Asserção estática virada em teste: um braço novo em `DeckProblem` sem
    tradução é erro de mypy no `assert_never`, mas quem roda só o pytest
    também precisa ver a falha."""
    translated: dict[type[DeckProblem], DeckProblem] = {
        WrongDeckSize: WrongDeckSize(found=1, required=40),
        TooManyCopies: TooManyCopies(card_id=CardId(1), count=4, limit=3),
        UnknownDeckCard: UnknownDeckCard(CardId(1)),
    }

    assert set(get_args(DeckProblem)) == set(translated)

    for problem in translated.values():
        assert deck_problem_payload(problem)["kind"]
