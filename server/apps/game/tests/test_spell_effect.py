"""Os cinco efeitos do MVP produzem o que a carta descreve, e nada além.

Testa o aplicador **direto**, sem passar por `submit_action`. É a fronteira
que `cast_spell` usa nas duas fases: o mesmo `apply_spell_effect`, com o alvo
que a guarda de lançamento acabou de validar.

Os números são os do catálogo do MVP, lidos dos campos estruturados do efeito.
Nenhum teste daqui lê `Spell.description`.

A comparação entre as duas fases está em
`test_cast_spell.py::test_both_phases_give_the_same_state`.
"""

import pytest

from apps.game.cards import (
    BuffUnitHealth,
    CardCatalog,
    CardId,
    DamageUnit,
    EffectDuration,
    PreventUnitDamage,
    RestoreNexus,
    SacrificeNexusForAttack,
    Spell,
    SpellEffect,
    mvp_catalog,
)
from apps.game.engine import (
    SpellEffectNeedsTargetError,
    apply_spell_effect,
    unit_has_damage_immunity,
    unit_max_health,
)
from apps.game.match import (
    AttackModifier,
    HealthModifier,
    Match,
    MatchPhase,
    STARTING_NEXUS,
)
from apps.game.tests.fake_spell_board import (
    FRAGILE_UNIT,
    LIFE_POTION,
    MAGIC_BARRIER,
    SACRIFICIAL_FIRE,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    TOUGH_UNIT,
    fake_spell_board,
)
from apps.game.tests.match_snapshot import match_snapshot

TOUGH_UNIT_HEALTH = 4
FRAGILE_UNIT_HEALTH = 2


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    return fake_spell_board(catalog=catalog)


def effect_of(catalog: CardCatalog, card_id: CardId) -> SpellEffect:
    """O efeito declarado pela carta, pelo campo estruturado do catálogo.

    Nunca por `Spell.description`: decisão de regra que dependa da descrição em
    português é bug, e `cards/effects.py` diz isso de si mesmo.
    """
    template = catalog.card(card_id)
    assert isinstance(template, Spell)

    return template.effect


# --------------------------------------------------------------------------
# SOMEONE'S SHIELD
# --------------------------------------------------------------------------


def test_shield_raises_the_maximum_health_by_two(
    match: Match, catalog: CardCatalog
) -> None:
    one = match.players[0]
    unit = one.bank[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SOMEONES_SHIELD), unit, catalog=catalog
    )

    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH + 2


def test_shield_leaves_accumulated_damage_alone(
    match: Match, catalog: CardCatalog
) -> None:
    """Somar vida **não é curar**."""
    one = match.players[0]
    unit = one.bank[0]
    unit.damage_taken = 3

    apply_spell_effect(
        match, one, effect_of(catalog, SOMEONES_SHIELD), unit, catalog=catalog
    )

    assert unit.damage_taken == 3


def test_shield_writes_a_permanent_modifier(match: Match, catalog: CardCatalog) -> None:
    """A duração vem do efeito, e é ela que faz a §8 não varrer isto."""
    one = match.players[0]
    unit = one.bank[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SOMEONES_SHIELD), unit, catalog=catalog
    )

    assert unit.modifiers == [
        HealthModifier(amount=2, duration=EffectDuration.PERMANENT)
    ]


def test_shield_changes_no_nexus(match: Match, catalog: CardCatalog) -> None:
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, SOMEONES_SHIELD), one.bank[0], catalog=catalog
    )

    assert (one.nexus, two.nexus) == (STARTING_NEXUS, STARTING_NEXUS)


# --------------------------------------------------------------------------
# MAGIC BARRIER
# --------------------------------------------------------------------------


def test_barrier_grants_damage_immunity(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    unit = one.bank[0]

    apply_spell_effect(
        match, one, effect_of(catalog, MAGIC_BARRIER), unit, catalog=catalog
    )

    assert unit_has_damage_immunity(unit) is True


def test_barrier_does_not_expire_with_the_round(
    match: Match, catalog: CardCatalog
) -> None:
    """§14: não expira no fim da rodada -- só o dano que ela absorve a tira."""
    one = match.players[0]
    unit = one.bank[0]

    apply_spell_effect(
        match, one, effect_of(catalog, MAGIC_BARRIER), unit, catalog=catalog
    )

    assert unit.modifiers[0].duration is EffectDuration.PERMANENT


def test_a_second_barrier_does_not_stack(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    unit = one.bank[0]

    for _ in range(2):
        apply_spell_effect(
            match, one, effect_of(catalog, MAGIC_BARRIER), unit, catalog=catalog
        )

    assert len(unit.modifiers) == 1


def test_damage_does_not_enter_a_barriered_unit(
    match: Match, catalog: CardCatalog
) -> None:
    one, two = match.players
    unit = two.bank[0]
    apply_spell_effect(
        match, two, effect_of(catalog, MAGIC_BARRIER), unit, catalog=catalog
    )

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), unit, catalog=catalog
    )

    assert unit.damage_taken == 0


def test_the_barrier_absorbs_one_ax_and_the_next_one_hits(
    match: Match, catalog: CardCatalog
) -> None:
    """E o feitiço que bate na barreira não é recusado: o alvo estava em campo,
    o efeito foi aplicado, e a barreira foi gasta."""
    one, two = match.players
    unit = two.bank[0]
    apply_spell_effect(
        match, two, effect_of(catalog, MAGIC_BARRIER), unit, catalog=catalog
    )

    for _ in range(2):
        apply_spell_effect(
            match, one, effect_of(catalog, SUMMONED_AX), unit, catalog=catalog
        )

    assert unit.damage_taken == 3
    assert unit_has_damage_immunity(unit) is False


# --------------------------------------------------------------------------
# SACRIFICIAL FIRE
# --------------------------------------------------------------------------


def test_fire_costs_the_caster_eight_nexus(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert one.nexus == STARTING_NEXUS - 8


def test_fire_gives_every_unit_of_the_caster_three_attack(
    catalog: CardCatalog,
) -> None:
    match = fake_spell_board(
        catalog=catalog, bank_one=(TOUGH_UNIT, FRAGILE_UNIT, TOUGH_UNIT)
    )
    one = match.players[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert [unit.modifiers for unit in one.bank] == [
        [AttackModifier(amount=3, duration=EffectDuration.PERMANENT)]
    ] * 3


def test_fire_leaves_the_opponent_units_alone(
    match: Match, catalog: CardCatalog
) -> None:
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert two.bank[0].modifiers == []


def test_fire_costs_the_nexus_with_no_units_on_the_field(
    catalog: CardCatalog,
) -> None:
    """A troca é indivisível: o custo acontece mesmo sem nada para buffar."""
    match = fake_spell_board(catalog=catalog, bank_one=())
    one = match.players[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert one.nexus == STARTING_NEXUS - 8


def test_fire_can_defeat_its_own_caster(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    one.nexus = 8

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert (one.nexus, match.is_over) == (0, True)


def test_a_self_defeating_fire_still_grants_the_attack_bonus(
    match: Match, catalog: CardCatalog
) -> None:
    """Indivisível nos dois sentidos: o buff vem antes do custo."""
    one = match.players[0]
    one.nexus = 8

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert one.bank[0].modifiers == [
        AttackModifier(amount=3, duration=EffectDuration.PERMANENT)
    ]


def test_a_self_defeating_fire_reaches_the_terminal_phase(
    match: Match, catalog: CardCatalog
) -> None:
    one = match.players[0]
    one.nexus = 5

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert match.phase is MatchPhase.FINISHED
    assert one.nexus == -3


def test_fire_with_nine_nexus_does_not_end_the_match(
    match: Match, catalog: CardCatalog
) -> None:
    one = match.players[0]
    one.nexus = 9

    apply_spell_effect(
        match, one, effect_of(catalog, SACRIFICIAL_FIRE), None, catalog=catalog
    )

    assert (one.nexus, match.is_over) == (1, False)


# --------------------------------------------------------------------------
# LIFE POTION
# --------------------------------------------------------------------------


def test_potion_restores_five_nexus(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    one.nexus = 10

    apply_spell_effect(
        match, one, effect_of(catalog, LIFE_POTION), None, catalog=catalog
    )

    assert one.nexus == 15


def test_potion_has_no_ceiling(match: Match, catalog: CardCatalog) -> None:
    """O 20 da §12 é o valor inicial, não um teto (esclarecimento de 006)."""
    one = match.players[0]

    apply_spell_effect(
        match, one, effect_of(catalog, LIFE_POTION), None, catalog=catalog
    )

    assert one.nexus == STARTING_NEXUS + 5


def test_potion_leaves_the_opponent_nexus_alone(
    match: Match, catalog: CardCatalog
) -> None:
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, LIFE_POTION), None, catalog=catalog
    )

    assert two.nexus == STARTING_NEXUS


def test_potion_does_not_end_the_match(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]

    apply_spell_effect(
        match, one, effect_of(catalog, LIFE_POTION), None, catalog=catalog
    )

    assert match.is_over is False


# --------------------------------------------------------------------------
# SUMMONED AX
# --------------------------------------------------------------------------


def test_ax_accumulates_three_damage(match: Match, catalog: CardCatalog) -> None:
    one, two = match.players
    unit = two.bank[0]

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), unit, catalog=catalog
    )

    assert unit.damage_taken == 3


def test_a_unit_that_survives_the_ax_stays_on_the_bank(
    match: Match, catalog: CardCatalog
) -> None:
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), two.bank[0], catalog=catalog
    )

    assert len(two.bank) == 1


def test_the_ax_kills_a_unit_whose_health_it_reaches(
    catalog: CardCatalog,
) -> None:
    """MORTEM tem 2 de vida; 3 de dano a alcança e ultrapassa."""
    match = fake_spell_board(catalog=catalog, bank_two=(FRAGILE_UNIT,))
    one, two = match.players
    dead_id = two.bank[0].card.card_instance_id

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), two.bank[0], catalog=catalog
    )

    assert two.bank == []
    assert [card.card_instance_id for card in two.graveyard] == [dead_id]


def test_the_dead_unit_goes_to_the_graveyard_of_its_owner(
    catalog: CardCatalog,
) -> None:
    """Do dono da unidade, não do lançador do feitiço que a matou."""
    match = fake_spell_board(catalog=catalog, bank_two=(FRAGILE_UNIT,))
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), two.bank[0], catalog=catalog
    )

    assert one.graveyard == []
    assert len(two.graveyard) == 1


def test_the_ax_kills_a_unit_already_damaged(
    match: Match, catalog: CardCatalog
) -> None:
    """KRONOS tem 4 de vida; 2 de dano acumulado mais 3 é 5, e ela morre."""
    one, two = match.players
    two.bank[0].damage_taken = 2

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), two.bank[0], catalog=catalog
    )

    assert two.bank == []


def test_a_shielded_unit_survives_damage_equal_to_its_template_health(
    match: Match, catalog: CardCatalog
) -> None:
    """A vida máxima inclui o modificador, e é ela que a morte compara."""
    one, two = match.players
    unit = two.bank[0]
    apply_spell_effect(
        match, two, effect_of(catalog, SOMEONES_SHIELD), unit, catalog=catalog
    )
    unit.damage_taken = TOUGH_UNIT_HEALTH

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), unit, catalog=catalog
    )

    assert unit.damage_taken == TOUGH_UNIT_HEALTH + 3
    assert two.bank == []


def test_the_ax_changes_no_nexus(match: Match, catalog: CardCatalog) -> None:
    one, two = match.players

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), two.bank[0], catalog=catalog
    )

    assert (one.nexus, two.nexus) == (STARTING_NEXUS, STARTING_NEXUS)


# --------------------------------------------------------------------------
# A fronteira do aplicador (US6)
# --------------------------------------------------------------------------


def test_the_applier_takes_no_origin_parameter() -> None:
    """FR-029: nada diz de que fase a chamada veio.

    Afirmado sobre a assinatura, e não sobre o comportamento, porque é a
    assinatura que impede alguém de acrescentar um ramo por fase.
    """
    from inspect import signature

    assert list(signature(apply_spell_effect).parameters) == [
        "match",
        "caster",
        "effect",
        "target",
        "catalog",
    ]


def test_the_applier_never_revalidates_the_target(
    match: Match, catalog: CardCatalog
) -> None:
    """Um alvo que já saiu de campo é aplicado assim mesmo: validar é da
    guarda de lançamento, que roda antes, na mesma jogada."""
    one, two = match.players
    orphan = two.bank.pop()

    apply_spell_effect(
        match, one, effect_of(catalog, SUMMONED_AX), orphan, catalog=catalog
    )

    assert orphan.damage_taken == 3


def test_an_effect_that_needs_a_target_refuses_without_one(
    match: Match, catalog: CardCatalog
) -> None:
    """Braço impossível vindo da §5B, e recusa nomeada em vez de `assert`."""
    one = match.players[0]

    with pytest.raises(SpellEffectNeedsTargetError) as refusal:
        apply_spell_effect(
            match, one, effect_of(catalog, SUMMONED_AX), None, catalog=catalog
        )

    assert "enemy_unit" in str(refusal.value)


def test_a_refused_effect_changes_nothing(match: Match, catalog: CardCatalog) -> None:
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(SpellEffectNeedsTargetError):
        apply_spell_effect(
            match, one, effect_of(catalog, SOMEONES_SHIELD), None, catalog=catalog
        )

    assert match_snapshot(match) == before


def test_every_mvp_effect_has_an_arm(match: Match, catalog: CardCatalog) -> None:
    """Os cinco despacham; nenhum cai no `assert_never`.

    A exaustividade em si é erro de mypy, não de runtime -- este teste só
    garante que os cinco do catálogo passam pelo despacho sem levantar.
    """
    one, two = match.players
    targets = {
        SOMEONES_SHIELD: one.bank[0],
        MAGIC_BARRIER: one.bank[0],
        SACRIFICIAL_FIRE: None,
        LIFE_POTION: None,
        SUMMONED_AX: two.bank[0],
    }

    for card_id, target in targets.items():
        apply_spell_effect(
            match, one, effect_of(catalog, card_id), target, catalog=catalog
        )

    assert len(targets) == 5


def test_the_effect_union_is_the_five_of_the_mvp(catalog: CardCatalog) -> None:
    """Lidos dos campos estruturados do catálogo, nunca da descrição."""
    effects = {type(spell.effect) for spell in catalog.spells()}

    assert effects == {
        BuffUnitHealth,
        PreventUnitDamage,
        DamageUnit,
        RestoreNexus,
        SacrificeNexusForAttack,
    }
