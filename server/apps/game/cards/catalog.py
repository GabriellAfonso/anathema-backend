"""Acesso ao catálogo: uma interface, uma implementação congelada, erros que
dizem qual carta era.

O catálogo é somente leitura em tempo de execução. Buff, dano e morte recaem
sobre a instância da unidade em campo; duas partidas simultâneas leem o mesmo
catálogo sem interferir uma na outra.
"""

from collections.abc import Iterable
from typing import Protocol

from .card import (
    SPELL_ID_MIN,
    UNIT_ID_MAX,
    UNIT_ID_MIN,
    Card,
    CardId,
    CardType,
    Spell,
    Unit,
)


class CardCatalogError(Exception):
    """Base para tudo que o catálogo recusa."""


class UnknownCardError(CardCatalogError):
    """Pediram uma carta que não existe. A mensagem diz qual foi pedida."""

    def __init__(self, card_id: CardId) -> None:
        super().__init__(f"unknown card_id {card_id}: not in the catalog")
        self.card_id = card_id


class DuplicateCardIdError(CardCatalogError):
    """Dois moldes com o mesmo `card_id`. O catálogo não pode subir ambíguo."""

    def __init__(self, card_id: CardId) -> None:
        super().__init__(f"duplicate card_id {card_id}: each card needs its own")
        self.card_id = card_id


class CardIdOutOfRangeError(CardCatalogError):
    """`card_id` fora da faixa reservada para o tipo da carta."""

    def __init__(self, card_id: CardId, card_type: CardType, expected: str) -> None:
        super().__init__(
            f"card_id {card_id} is out of range for {card_type}: expected {expected}"
        )
        self.card_id = card_id
        self.card_type = card_type


class CardCatalog(Protocol):
    """A fonte única de verdade sobre quais cartas existem.

    Consumidores recebem isto por parâmetro; só o ponto de composição da
    aplicação constrói um catálogo concreto. É `Protocol` e não classe base para
    que um substituto de teste só precise dos métodos, sem herdar de nada.
    """

    def card(self, card_id: CardId) -> Card:
        """A carta, ou `UnknownCardError` citando o identificador pedido."""
        ...

    def all_cards(self) -> tuple[Card, ...]:
        """Todas as cartas, ordenadas por `card_id`."""
        ...

    def units(self) -> tuple[Unit, ...]:
        """Só as unidades, ordenadas por `card_id`."""
        ...

    def spells(self) -> tuple[Spell, ...]:
        """Só os feitiços, ordenados por `card_id`. Vazio é resposta válida."""
        ...


class FrozenCardCatalog:
    """Catálogo imutável, indexado por `card_id`.

    Valida na construção, alto e cedo: depois disso não existe estado inválido a
    checar em tempo de partida.

    >>> catalog = FrozenCardCatalog([john_copper, summoned_ax])
    >>> catalog.card(CardId(1)).name
    'JOHN COPPER'
    """

    def __init__(self, cards: Iterable[Card]) -> None:
        by_id: dict[CardId, Card] = {}

        for card in cards:
            _reject_duplicate(card, by_id)
            _reject_out_of_range(card)
            by_id[card.card_id] = card

        self._by_id = by_id

    def card(self, card_id: CardId) -> Card:
        """A carta com aquele `card_id`.

        Ausência é erro, nunca `None`: quem pede uma carta já decidiu que ela
        deveria existir.

        >>> catalog.card(CardId(1)).energy
        5
        """
        found = self._by_id.get(card_id)

        if found is None:
            raise UnknownCardError(card_id)

        return found

    def all_cards(self) -> tuple[Card, ...]:
        """Todas as cartas, ordenadas por `card_id`.

        Tupla e não lista: o chamador não tem como alterar a coleção.

        >>> len(catalog.all_cards())
        29
        """
        return tuple(sorted(self._by_id.values(), key=lambda card: card.card_id))

    def units(self) -> tuple[Unit, ...]:
        """Só as unidades.

        Filtra pelo tipo da carta, nunca comparando `card_id` com a faixa: a
        faixa é convenção de alocação e não pode virar contrato. `isinstance` é
        como esse filtro se escreve em Python quando o retorno precisa ser
        `tuple[Unit, ...]`.
        """
        return tuple(card for card in self.all_cards() if isinstance(card, Unit))

    def spells(self) -> tuple[Spell, ...]:
        """Só os feitiços. Mesma regra de filtro.

        Tupla vazia é resposta válida — um catálogo sem feitiço não é erro.
        """
        return tuple(card for card in self.all_cards() if isinstance(card, Spell))


def _reject_duplicate(card: Card, seen: dict[CardId, Card]) -> None:
    """Dois moldes com o mesmo `card_id` deixariam a busca ambígua."""
    if card.card_id in seen:
        raise DuplicateCardIdError(card.card_id)


def _reject_out_of_range(card: Card) -> None:
    """A faixa é convenção de alocação, conferida uma vez, na carga.

    Não é como se descobre o tipo de uma carta — `units()` e `spells()` filtram
    por tipo, nunca comparando `card_id` com 1000.
    """
    if card.card_type is CardType.UNIT:
        _reject_unit_out_of_range(card)
        return

    _reject_spell_out_of_range(card)


def _reject_unit_out_of_range(card: Card) -> None:
    """Unidade vive na faixa de baixo, com teto."""
    if UNIT_ID_MIN <= card.card_id <= UNIT_ID_MAX:
        return

    raise CardIdOutOfRangeError(
        card.card_id, card.card_type, f"{UNIT_ID_MIN} to {UNIT_ID_MAX}"
    )


def _reject_spell_out_of_range(card: Card) -> None:
    """Feitiço vive na faixa de cima, sem teto declarado."""
    if card.card_id >= SPELL_ID_MIN:
        return

    raise CardIdOutOfRangeError(
        card.card_id, card.card_type, f"{SPELL_ID_MIN} or above"
    )
