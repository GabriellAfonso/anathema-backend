"""O contrato do catálogo: carga, busca e imutabilidade."""

import dataclasses

import pytest

from apps.game.cards.card import CardId, CardType, Spell, Unit
from apps.game.cards.catalog import (
    CardIdOutOfRangeError,
    DuplicateCardIdError,
    FrozenCardCatalog,
    UnknownCardError,
)
from apps.game.cards.effects import DamageUnit
from apps.game.cards.mvp_catalog import mvp_catalog


def _unit(card_id: int) -> Unit:
    return Unit(
        card_id=CardId(card_id),
        name="SAMPLE UNIT",
        energy=1,
        attack=1,
        health=1,
        image="sample_unit_card",
    )


def _spell(card_id: int) -> Spell:
    return Spell(
        card_id=CardId(card_id),
        name="SAMPLE SPELL",
        energy=1,
        description="Causa 1 de dano à unidade inimiga alvo.",
        effect=DamageUnit(amount=1),
        image="sample_spell_card",
    )


def test_duplicate_card_id_fails_the_load() -> None:
    """Catálogo ambíguo não pode subir: a segunda carta com o mesmo id é erro."""
    with pytest.raises(DuplicateCardIdError) as raised:
        FrozenCardCatalog([_unit(1), _unit(1)])

    assert "1" in str(raised.value)
    assert raised.value.card_id == 1


def test_unit_above_its_range_fails_the_load() -> None:
    """Unidade vive de 1 a 1000; 1001 é faixa de feitiço."""
    with pytest.raises(CardIdOutOfRangeError) as raised:
        FrozenCardCatalog([_unit(1001)])

    assert "1001" in str(raised.value)
    assert raised.value.card_type is CardType.UNIT


def test_spell_below_its_range_fails_the_load() -> None:
    """Feitiço começa em 1001; 1000 ainda é faixa de unidade."""
    with pytest.raises(CardIdOutOfRangeError) as raised:
        FrozenCardCatalog([_spell(1000)])

    assert "1000" in str(raised.value)
    assert raised.value.card_type is CardType.SPELL


def test_card_by_id_returns_a_unit() -> None:
    catalog = mvp_catalog()

    john_copper = catalog.card(CardId(1))

    assert isinstance(john_copper, Unit)
    assert john_copper.name == "JOHN COPPER"
    assert john_copper.card_type is CardType.UNIT
    assert john_copper.energy == 5
    assert john_copper.attack == 7
    assert john_copper.health == 5
    assert john_copper.image == "john_card"


def test_card_by_id_returns_a_spell() -> None:
    catalog = mvp_catalog()

    life_potion = catalog.card(CardId(1004))

    assert isinstance(life_potion, Spell)
    assert life_potion.name == "LIFE POTION"
    assert life_potion.card_type is CardType.SPELL
    assert life_potion.energy == 4
    assert life_potion.description
    assert life_potion.image == "life_potion"


def test_unknown_card_id_names_what_was_asked() -> None:
    """Recusa genérica não serve: quem depurar precisa do identificador."""
    catalog = mvp_catalog()

    with pytest.raises(UnknownCardError) as raised:
        catalog.card(CardId(9999))

    assert "9999" in str(raised.value)
    assert raised.value.card_id == 9999


def test_a_card_from_the_catalog_cannot_be_changed() -> None:
    """Buff em partida recai na instância em campo, nunca no molde."""
    catalog = mvp_catalog()
    john_copper = catalog.card(CardId(1))
    assert isinstance(john_copper, Unit)

    with pytest.raises(dataclasses.FrozenInstanceError):
        john_copper.health = 99  # type: ignore[misc]

    still_there = catalog.card(CardId(1))
    assert isinstance(still_there, Unit)
    assert still_there.health == 5
