"""Vida, dano e morte de uma unidade em campo.

As duas quantidades de vida têm nomes distintos porque a spec usa "vida
efetiva" com dois sentidos, e aqui as duas são medidas separadamente. A morte é
a mesma desigualdade escrita de dois jeitos, e os testes afirmam as duas formas.

Dano não é modificador: não expira, e a varredura da §8 não o toca. Isso é
afirmado em `test_spell_state_round_trip.py`, junto do resto da §8.
"""

import pytest

from apps.game.cards import CardCatalog, EffectDuration, mvp_catalog
from apps.game.engine import (
    bury_dead_units,
    deal_damage_to_unit,
    unit_has_damage_immunity,
    unit_is_dead,
    unit_max_health,
    unit_remaining_health,
)
from apps.game.match import (
    BankUnit,
    DamageImmunity,
    HealthModifier,
    Match,
    MatchCard,
)
from apps.game.tests.fake_spell_board import (
    FRAGILE_UNIT,
    TOUGH_UNIT,
    bank_card,
    fake_spell_board,
)

# `mvp_catalog`: KRONOS (TOUGH_UNIT) tem 4 de vida, MORTEM (FRAGILE_UNIT) tem 2.
TOUGH_UNIT_HEALTH = 4
FRAGILE_UNIT_HEALTH = 2


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    return fake_spell_board(catalog=catalog)


@pytest.fixture
def unit(match: Match) -> BankUnit:
    return match.players[0].bank[0]


def test_an_intact_unit_has_the_template_health(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH


def test_a_health_modifier_raises_the_maximum(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    unit.modifiers.append(HealthModifier(amount=2, duration=EffectDuration.PERMANENT))

    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH + 2


def test_damage_does_not_change_the_maximum(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    """Dano acumula na unidade; ele não reduz vida diretamente."""
    deal_damage_to_unit(unit, 3)

    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH


def test_damage_lowers_the_remaining_health(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    deal_damage_to_unit(unit, 3)

    assert unit_remaining_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH - 3


def test_a_unit_below_lethal_damage_survives(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    deal_damage_to_unit(unit, TOUGH_UNIT_HEALTH - 1)

    assert unit_is_dead(unit, catalog=catalog) is False


def test_damage_exactly_equal_to_the_maximum_kills(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    """A regra é o dano **alcançar** a vida máxima, não ultrapassá-la."""
    deal_damage_to_unit(unit, TOUGH_UNIT_HEALTH)

    assert unit_is_dead(unit, catalog=catalog) is True


def test_the_two_forms_of_the_death_rule_agree(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    """`dano >= máxima` e `restante <= 0` são a mesma desigualdade."""
    deal_damage_to_unit(unit, TOUGH_UNIT_HEALTH)

    by_maximum = unit.damage_taken >= unit_max_health(unit, catalog=catalog)
    by_remaining = unit_remaining_health(unit, catalog=catalog) <= 0

    assert by_maximum is by_remaining is True


def test_a_health_buff_saves_a_unit_at_lethal_damage(
    unit: BankUnit, catalog: CardCatalog
) -> None:
    """Somar vida sobe a máxima, e a unidade que morreria continua viva."""
    deal_damage_to_unit(unit, TOUGH_UNIT_HEALTH)
    unit.modifiers.append(HealthModifier(amount=2, duration=EffectDuration.PERMANENT))

    assert unit_is_dead(unit, catalog=catalog) is False


def test_a_health_buff_does_not_heal(unit: BankUnit, catalog: CardCatalog) -> None:
    """Somar vida **não é curar**: o dano acumulado continua onde estava."""
    deal_damage_to_unit(unit, 3)
    unit.modifiers.append(HealthModifier(amount=2, duration=EffectDuration.PERMANENT))

    assert unit.damage_taken == 3


def test_an_intact_unit_has_no_immunity(unit: BankUnit) -> None:
    assert unit_has_damage_immunity(unit) is False


def test_a_damage_immunity_is_seen(unit: BankUnit) -> None:
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND))

    assert unit_has_damage_immunity(unit) is True


def test_damage_does_not_enter_an_immune_unit(unit: BankUnit) -> None:
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.PERMANENT))

    deal_damage_to_unit(unit, 99)

    assert unit.damage_taken == 0


def test_the_barrier_breaks_on_the_damage_it_absorbs(unit: BankUnit) -> None:
    """§14: ignora o **próximo** dano, e some."""
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.PERMANENT))

    deal_damage_to_unit(unit, 2)

    assert unit_has_damage_immunity(unit) is False


def test_the_damage_after_the_barrier_enters(unit: BankUnit) -> None:
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.PERMANENT))

    deal_damage_to_unit(unit, 2)
    deal_damage_to_unit(unit, 3)

    assert unit.damage_taken == 3


def test_zero_damage_does_not_break_the_barrier(unit: BankUnit) -> None:
    """Dano de 0 não é dano: um atacante com ataque efetivo 0 não gasta a
    barreira."""
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.PERMANENT))

    deal_damage_to_unit(unit, 0)

    assert unit_has_damage_immunity(unit) is True


def test_the_barrier_leaves_the_other_modifiers_alone(unit: BankUnit) -> None:
    buff = HealthModifier(amount=2, duration=EffectDuration.PERMANENT)
    unit.modifiers.extend([buff, DamageImmunity(duration=EffectDuration.PERMANENT)])

    deal_damage_to_unit(unit, 5)

    assert unit.modifiers == [buff]


def test_an_immune_unit_does_not_die(unit: BankUnit, catalog: CardCatalog) -> None:
    unit.modifiers.append(DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND))

    deal_damage_to_unit(unit, 99)

    assert unit_is_dead(unit, catalog=catalog) is False


def test_burying_leaves_a_living_bank_alone(match: Match, catalog: CardCatalog) -> None:
    bury_dead_units(match, catalog=catalog)

    assert len(match.players[0].bank) == 1
    assert match.players[0].graveyard == []


def test_a_dead_unit_leaves_the_bank(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    deal_damage_to_unit(one.bank[0], TOUGH_UNIT_HEALTH)

    bury_dead_units(match, catalog=catalog)

    assert one.bank == []


def test_a_dead_unit_goes_to_the_graveyard_of_its_owner(
    match: Match, catalog: CardCatalog
) -> None:
    """Do **dono** da unidade, e não de quem causou o dano."""
    one, two = match.players
    dead_id = bank_card(two)
    deal_damage_to_unit(two.bank[0], TOUGH_UNIT_HEALTH)

    bury_dead_units(match, catalog=catalog)

    assert [card.card_instance_id for card in two.graveyard] == [dead_id]
    assert one.graveyard == []


def test_damage_and_modifiers_are_left_behind(
    match: Match, catalog: CardCatalog
) -> None:
    """O `MatchCard` que entra no cemitério não tem onde guardá-los."""
    one = match.players[0]
    one.bank[0].modifiers.append(
        HealthModifier(amount=1, duration=EffectDuration.PERMANENT)
    )
    deal_damage_to_unit(one.bank[0], 99)

    bury_dead_units(match, catalog=catalog)

    assert set(one.graveyard[0].__slots__) == {"card_instance_id", "card_id"}


def test_both_banks_are_swept(match: Match, catalog: CardCatalog) -> None:
    one, two = match.players
    deal_damage_to_unit(one.bank[0], TOUGH_UNIT_HEALTH)
    deal_damage_to_unit(two.bank[0], TOUGH_UNIT_HEALTH)

    bury_dead_units(match, catalog=catalog)

    assert (one.bank, two.bank) == ([], [])


def test_only_the_dead_copy_is_buried(catalog: CardCatalog) -> None:
    """Duas cópias intactas da mesma carta são iguais por `==`, e por isso a
    remoção compara por `card_instance_id`."""
    match = fake_spell_board(catalog=catalog, bank_one=(FRAGILE_UNIT, FRAGILE_UNIT))
    one = match.players[0]
    survivor_id = bank_card(one, 1)
    deal_damage_to_unit(one.bank[0], FRAGILE_UNIT_HEALTH)

    bury_dead_units(match, catalog=catalog)

    assert [unit.card.card_instance_id for unit in one.bank] == [survivor_id]


def test_burying_an_empty_bank_is_not_an_error(catalog: CardCatalog) -> None:
    match = fake_spell_board(catalog=catalog, bank_one=(), bank_two=())

    bury_dead_units(match, catalog=catalog)

    assert match.players[0].bank == []


def test_a_buried_card_keeps_its_identity(match: Match, catalog: CardCatalog) -> None:
    """Mudar de zona não cunha identidade nova."""
    one = match.players[0]
    dead_id = bank_card(one)
    deal_damage_to_unit(one.bank[0], TOUGH_UNIT_HEALTH)

    bury_dead_units(match, catalog=catalog)

    assert one.graveyard[0].card_instance_id == dead_id


def test_a_card_in_hand_is_untouched_by_the_sweep(
    match: Match, catalog: CardCatalog
) -> None:
    one = match.players[0]
    before = [card.card_instance_id for card in one.hand]

    bury_dead_units(match, catalog=catalog)

    assert [card.card_instance_id for card in one.hand] == before


def test_a_match_card_is_not_a_bank_unit(match: Match) -> None:
    """Sanidade do fake: o banco guarda `BankUnit`, a mão guarda `MatchCard`."""
    assert isinstance(match.players[0].bank[0], BankUnit)
    assert isinstance(match.players[0].hand[0], MatchCard)
