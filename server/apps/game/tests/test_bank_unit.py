"""A unidade no banco guarda o que diverge do molde, e nada mais.

Buff, dano e cura recaem sobre a instância. O molde do catálogo é
compartilhado por todas as partidas do servidor e nunca é tocado.
"""

import dataclasses

import pytest

from apps.game.cards import CardId, EffectDuration, Unit
from apps.game.match import (
    AttackModifier,
    BankUnit,
    DamageImmunity,
    HealthModifier,
    Match,
    UnitModifier,
)
from apps.game.tests.fake_card_catalog import SAMPLE_UNIT, FakeCardCatalog
from apps.game.tests.fake_match_state import fake_cards, fake_new_match

TWO_COPIES = [SAMPLE_UNIT.card_id, SAMPLE_UNIT.card_id]


@pytest.fixture
def match() -> Match:
    return fake_new_match()


@pytest.fixture
def catalog() -> FakeCardCatalog:
    return FakeCardCatalog([SAMPLE_UNIT])


@pytest.fixture
def twins(match: Match) -> list[BankUnit]:
    """Duas instâncias do mesmo molde, lado a lado no banco."""
    return [BankUnit(card=card) for card in fake_cards(match, TWO_COPIES)]


def test_a_unit_enters_play_undamaged(twins: list[BankUnit]) -> None:
    assert twins[0].damage_taken == 0


def test_a_unit_enters_play_without_modifiers(twins: list[BankUnit]) -> None:
    """Entra pronta: não existe doença de invocação (§5A)."""
    assert twins[0].modifiers == []


def test_a_unit_knows_which_template_it_came_from(twins: list[BankUnit]) -> None:
    assert twins[0].card.card_id == SAMPLE_UNIT.card_id


def test_damage_on_one_copy_does_not_touch_the_other(twins: list[BankUnit]) -> None:
    first, second = twins

    first.damage_taken = 3

    assert second.damage_taken == 0


def test_a_modifier_on_one_copy_does_not_touch_the_other(
    twins: list[BankUnit],
) -> None:
    first, second = twins

    first.modifiers.append(AttackModifier(amount=2, duration=EffectDuration.PERMANENT))

    assert second.modifiers == []


def test_damaging_a_unit_leaves_the_catalog_template_alone(
    twins: list[BankUnit], catalog: FakeCardCatalog
) -> None:
    """O molde é compartilhado por todas as partidas: alterá-lo daqui
    contaminaria partidas de outros jogadores."""
    twins[0].damage_taken = 3

    assert catalog.card(CardId(SAMPLE_UNIT.card_id)) == SAMPLE_UNIT


def test_the_catalog_template_refuses_to_be_written() -> None:
    """Não é disciplina, é `frozen=True`: a tentativa levanta."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        SAMPLE_UNIT.health = 1  # type: ignore[misc]


def test_the_unit_carries_no_attack_or_health_of_its_own(
    twins: list[BankUnit],
) -> None:
    """Efetivo é molde mais modificadores, calculado por quem precisa. Guardar
    o valor aqui criaria uma segunda fonte de verdade."""
    assert not hasattr(twins[0], "attack")
    assert not hasattr(twins[0], "health")


def test_permanent_and_temporary_modifiers_are_separable(
    twins: list[BankUnit],
) -> None:
    """É o que o Fim de Rodada (§8) precisa para varrer só os temporários."""
    unit = twins[0]
    unit.modifiers = [
        AttackModifier(amount=2, duration=EffectDuration.PERMANENT),
        DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND),
    ]

    assert _permanent(unit.modifiers) == [
        AttackModifier(amount=2, duration=EffectDuration.PERMANENT)
    ]


def test_attack_modifiers_of_opposite_signs_coexist(twins: list[BankUnit]) -> None:
    """Perder ataque é o mesmo tipo com sinal trocado — não um tipo novo, e
    não uma escrita num campo que teria de ser desfeita depois."""
    unit = twins[0]
    unit.modifiers = [
        AttackModifier(amount=2, duration=EffectDuration.PERMANENT),
        AttackModifier(amount=-3, duration=EffectDuration.UNTIL_END_OF_ROUND),
    ]

    stored = [m for m in unit.modifiers if isinstance(m, AttackModifier)]

    assert [modifier.amount for modifier in stored] == [2, -3]


def test_expiring_a_modifier_is_removing_it_from_the_list(
    twins: list[BankUnit],
) -> None:
    """Modificador é valor congelado: nada é editado no lugar, e o dano
    acumulado não é tocado pela expiração."""
    unit = twins[0]
    unit.damage_taken = 3
    unit.modifiers = [
        HealthModifier(amount=2, duration=EffectDuration.UNTIL_END_OF_ROUND)
    ]

    unit.modifiers = _permanent(unit.modifiers)

    assert (unit.modifiers, unit.damage_taken) == ([], 3)


def test_a_modifier_cannot_be_edited_in_place() -> None:
    modifier = AttackModifier(amount=2, duration=EffectDuration.PERMANENT)

    with pytest.raises(dataclasses.FrozenInstanceError):
        modifier.amount = 5  # type: ignore[misc]


def test_damage_immunity_has_no_amount_to_get_wrong() -> None:
    """Um campo de quantidade anulável deixaria existir estado sem
    significado."""
    assert not hasattr(DamageImmunity(duration=EffectDuration.PERMANENT), "amount")


def test_a_dead_unit_leaves_its_damage_behind(twins: list[BankUnit]) -> None:
    """Banco para cemitério é `graveyard.append(unit.card)`: o `MatchCard`
    atravessa e o `BankUnit` some, com o dano junto."""
    unit = twins[0]
    unit.damage_taken = 3
    graveyard = [unit.card]

    assert not hasattr(graveyard[0], "damage_taken")


def _permanent(modifiers: list[UnitModifier]) -> list[UnitModifier]:
    """O que o Fim de Rodada deixaria de pé. Varrer é de outra feature; aqui
    é só a prova de que a duração basta para decidir."""
    return [
        modifier
        for modifier in modifiers
        if modifier.duration is EffectDuration.PERMANENT
    ]


def test_the_sample_template_is_a_unit() -> None:
    """Guarda-corpo: se `SAMPLE_UNIT` virar feitiço, os testes acima param de
    significar o que dizem."""
    assert isinstance(SAMPLE_UNIT, Unit)
