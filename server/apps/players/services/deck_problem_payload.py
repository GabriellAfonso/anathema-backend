"""Um problema de deck da feature 001, na forma que o cliente lê.

O texto de `problem.message` é reaproveitado como está: a mesma recusa sai igual
no HTTP e no websocket, e quem a escreve continua sendo quem conhece a regra.
O que este módulo acrescenta é `kind`, a chave estável que o cliente compara --
a mensagem carrega os valores ofensores e por isso não serve de chave.

O contrato está em `specs/011-deck-catalog-api/contracts/http_decks.md`.
"""

from typing import assert_never

from apps.game.cards import (
    DeckProblem,
    TooManyCopies,
    UnknownDeckCard,
    WrongDeckSize,
)

DeckProblemPayload = dict[str, object]


def deck_problem_payload(problem: DeckProblem) -> DeckProblemPayload:
    """Um problema em JSON, com `kind`, os valores ofensores e a mensagem.

    Fecha com `assert_never`: um problema novo na feature 001 é erro de mypy
    aqui, e não uma recusa que chega ao cliente sem forma.

    >>> deck_problem_payload(UnknownDeckCard(CardId(9999)))["kind"]
    'unknown_card'
    """
    match problem:
        case WrongDeckSize():
            return _wrong_deck_size_payload(problem)
        case TooManyCopies():
            return _too_many_copies_payload(problem)
        case UnknownDeckCard():
            return _unknown_card_payload(problem)
        case _:
            assert_never(problem)


def deck_problems_payload(
    problems: tuple[DeckProblem, ...],
) -> list[DeckProblemPayload]:
    """Todos os problemas, na ordem em que a feature 001 os apurou.

    Uma recusa carrega todos de uma vez: um construtor de deck quer a lista
    inteira para pintar a tela, não o primeiro erro.

    >>> len(deck_problems_payload(deck_problems(deck, catalog)))
    3
    """
    return [deck_problem_payload(problem) for problem in problems]


def _wrong_deck_size_payload(problem: WrongDeckSize) -> DeckProblemPayload:
    return {
        "kind": "wrong_deck_size",
        "found": problem.found,
        "required": problem.required,
        "message": problem.message,
    }


def _too_many_copies_payload(problem: TooManyCopies) -> DeckProblemPayload:
    return {
        "kind": "too_many_copies",
        "card_id": int(problem.card_id),
        "count": problem.count,
        "limit": problem.limit,
        "message": problem.message,
    }


def _unknown_card_payload(problem: UnknownDeckCard) -> DeckProblemPayload:
    return {
        "kind": "unknown_card",
        "card_id": int(problem.card_id),
        "message": problem.message,
    }
