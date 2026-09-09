"""Catálogo pequeno para injetar em teste, no lugar das 29 cartas reais.

Quem testa um consumidor do catálogo quer duas ou três cartas com valores que
cabem na cabeça, não a coleção inteira. O contrato do catálogo real está em
test_card_catalog.py.
"""

from collections.abc import Iterable

from apps.game.cards.card import Card, CardId, Spell, Unit
from apps.game.cards.catalog import CardCatalog, UnknownCardError
from apps.game.cards.effects import DamageUnit

# Cartas de amostra: valores redondos, sem relação com o balanceamento do MVP.
SAMPLE_UNIT = Unit(
    card_id=CardId(1),
    name="SAMPLE UNIT",
    energy=2,
    attack=3,
    health=4,
    image="sample_unit_card",
)

SAMPLE_SPELL = Spell(
    card_id=CardId(1001),
    name="SAMPLE SPELL",
    energy=1,
    description="Causa 1 de dano à unidade inimiga alvo.",
    effect=DamageUnit(amount=1),
    image="sample_spell_card",
)


class FakeCardCatalog:
    """Mesma superfície de `CardCatalog`, montada de uma lista curta.

    Não valida faixa nem duplicata: isso é contrato do catálogo real, e um fake
    que reimplementa validação vira uma segunda fonte de verdade.

    >>> catalog = FakeCardCatalog([SAMPLE_UNIT, SAMPLE_SPELL])
    >>> catalog.card(CardId(1)).name
    'SAMPLE UNIT'
    """

    def __init__(self, cards: Iterable[Card]) -> None:
        self._by_id: dict[CardId, Card] = {card.card_id: card for card in cards}

    def card(self, card_id: CardId) -> Card:
        found = self._by_id.get(card_id)

        if found is None:
            raise UnknownCardError(card_id)

        return found

    def all_cards(self) -> tuple[Card, ...]:
        return tuple(sorted(self._by_id.values(), key=lambda card: card.card_id))

    def units(self) -> tuple[Unit, ...]:
        return tuple(card for card in self.all_cards() if isinstance(card, Unit))

    def spells(self) -> tuple[Spell, ...]:
        return tuple(card for card in self.all_cards() if isinstance(card, Spell))


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição, e esta é a única do arquivo. Sem ela, o
# dia em que `CardCatalog` ganhar um método o fake fica para trás em silêncio e
# só quebra na cara de quem for injetá-lo. Não apague por parecer sobra.
FAKE_CARD_CATALOG_MATCHES_THE_PROTOCOL: CardCatalog = FakeCardCatalog([])
