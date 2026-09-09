"""Listagem do catálogo: tudo, só unidades, só feitiços."""

from apps.game.cards.card import Card, CardType, Spell, Unit
from apps.game.cards.catalog import FrozenCardCatalog
from apps.game.cards.mvp_catalog import MVP_UNITS, mvp_catalog


def test_all_cards_returns_the_whole_mvp() -> None:
    assert len(mvp_catalog().all_cards()) == 29


def test_all_cards_comes_back_ordered_by_card_id() -> None:
    card_ids = [card.card_id for card in mvp_catalog().all_cards()]

    assert card_ids == sorted(card_ids)


def test_units_returns_only_units() -> None:
    units = mvp_catalog().units()

    assert len(units) == 24
    assert all(unit.card_type is CardType.UNIT for unit in units)


def test_spells_returns_only_spells() -> None:
    spells = mvp_catalog().spells()

    assert len(spells) == 5
    assert all(spell.card_type is CardType.SPELL for spell in spells)


def test_the_two_listings_do_not_overlap() -> None:
    catalog = mvp_catalog()

    unit_ids = {unit.card_id for unit in catalog.units()}
    spell_ids = {spell.card_id for spell in catalog.spells()}

    assert not unit_ids & spell_ids
    assert len(unit_ids | spell_ids) == len(catalog.all_cards())


def test_a_catalog_without_spells_lists_an_empty_tuple() -> None:
    """Ausência de um tipo é resposta válida, não erro."""
    units_only: list[Card] = list(MVP_UNITS)

    catalog = FrozenCardCatalog(units_only)

    assert catalog.spells() == ()
    assert len(catalog.units()) == 24


def test_a_catalog_without_units_lists_an_empty_tuple() -> None:
    catalog = FrozenCardCatalog([])

    assert catalog.units() == ()
    assert catalog.all_cards() == ()


def test_listings_keep_the_concrete_card_types() -> None:
    """`units()` devolve `Unit`, não `Card` — quem chama quer ataque e vida."""
    catalog = mvp_catalog()

    assert all(isinstance(unit, Unit) for unit in catalog.units())
    assert all(isinstance(spell, Spell) for spell in catalog.spells())
