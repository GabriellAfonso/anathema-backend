"""As regras de deck do MVP, e recusas que nomeiam o valor ofensor.

Um deck é uma lista, não um conjunto: repetição é esperada, até 3 entradas com o
mesmo `card_id`. Quem dá identidade a cada cópia na mão ou no banco é a camada
de partida — aqui a lista só é validada.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .card import CardId
from .catalog import CardCatalog, UnknownCardError

# Fluxo de Partida §12.
DECK_SIZE = 40

# Pedido do maintainer; ainda sem nota em `Decisões/`.
MAX_COPIES_PER_CARD = 3

Deck = Sequence[CardId]


@dataclass(frozen=True, slots=True)
class WrongDeckSize:
    """O deck não tem exatamente 40 cartas."""

    found: int
    required: int

    @property
    def message(self) -> str:
        return f"deck has {self.found} cards, expected exactly {self.required}"


@dataclass(frozen=True, slots=True)
class TooManyCopies:
    """Um `card_id` aparece mais vezes do que o limite permite."""

    card_id: CardId
    count: int
    limit: int

    @property
    def message(self) -> str:
        return (
            f"card_id {self.card_id} appears {self.count} times, "
            f"limit is {self.limit}"
        )


@dataclass(frozen=True, slots=True)
class UnknownDeckCard:
    """O deck cita uma carta que o catálogo não conhece."""

    card_id: CardId

    @property
    def message(self) -> str:
        return f"card_id {self.card_id} is not in the catalog"


DeckProblem = WrongDeckSize | TooManyCopies | UnknownDeckCard


class InvalidDeckError(Exception):
    """Recusa de deck. Guarda os problemas estruturados, além do texto."""

    def __init__(self, problems: tuple[DeckProblem, ...]) -> None:
        super().__init__("; ".join(problem.message for problem in problems))
        self.problems = problems


def deck_problems(deck: Deck, catalog: CardCatalog) -> tuple[DeckProblem, ...]:
    """Todos os problemas do deck, em uma passada. Tupla vazia = deck válido.

    Não levanta por deck ruim: deck ruim é resposta, não exceção. Um construtor
    de deck quer a lista para pintar a tela; quem precisa estourar usa
    `ensure_valid_deck`.

    >>> deck_problems([CardId(1)] * 40, catalog)
    (TooManyCopies(card_id=1, count=40, limit=3),)
    """
    copies = Counter(deck)
    problems: list[DeckProblem] = []

    if len(deck) != DECK_SIZE:
        problems.append(WrongDeckSize(found=len(deck), required=DECK_SIZE))

    problems.extend(_over_the_copy_limit(copies))
    problems.extend(_missing_from_catalog(copies, catalog))

    return tuple(problems)


def ensure_valid_deck(deck: Deck, catalog: CardCatalog) -> None:
    """Aceita o deck em silêncio, ou recusa com todos os problemas de uma vez.

    >>> ensure_valid_deck(valid_deck, catalog)     # nada acontece
    >>> ensure_valid_deck([], catalog)
    InvalidDeckError: deck has 0 cards, expected exactly 40
    """
    problems = deck_problems(deck, catalog)

    if problems:
        raise InvalidDeckError(problems)


def _over_the_copy_limit(copies: Counter[CardId]) -> list[TooManyCopies]:
    """Um problema por identificador excedente, não um por cópia."""
    return [
        TooManyCopies(card_id=card_id, count=count, limit=MAX_COPIES_PER_CARD)
        for card_id, count in sorted(copies.items())
        if count > MAX_COPIES_PER_CARD
    ]


def _missing_from_catalog(
    copies: Counter[CardId], catalog: CardCatalog
) -> list[UnknownDeckCard]:
    """Um problema por identificador desconhecido, não um por cópia."""
    return [
        UnknownDeckCard(card_id)
        for card_id in sorted(copies)
        if not _is_in_catalog(card_id, catalog)
    ]


def _is_in_catalog(card_id: CardId, catalog: CardCatalog) -> bool:
    try:
        catalog.card(card_id)
    except UnknownCardError:
        return False

    return True
