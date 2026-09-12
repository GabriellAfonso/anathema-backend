"""Os 5 efeitos do MVP, lidos como o motor de regras os lê.

Nenhum teste aqui toca `description`: se o motor precisasse dela para decidir,
precisaria interpretar português.
"""

from apps.game.cards.card import CardId, Spell
from apps.game.cards.effects import (
    BuffUnitHealth,
    DamageUnit,
    EffectDuration,
    PreventUnitDamage,
    RestoreNexus,
    SacrificeNexusForAttack,
    SpellEffect,
    TargetKind,
)
from apps.game.cards.mvp_catalog import MVP_SPELLS, mvp_catalog


def _effect_of(card_id: int) -> SpellEffect:
    spell = mvp_catalog().card(CardId(card_id))

    assert isinstance(spell, Spell)

    return spell.effect


def test_someones_shield_buffs_allied_health_forever() -> None:
    assert _effect_of(1001) == BuffUnitHealth(amount=2)


def test_magic_barrier_protects_an_ally_from_the_next_damage() -> None:
    assert _effect_of(1002) == PreventUnitDamage()


def test_sacrificial_fire_trades_nexus_for_attack() -> None:
    assert _effect_of(1003) == SacrificeNexusForAttack(nexus_cost=8, attack_bonus=3)


def test_life_potion_restores_nexus() -> None:
    assert _effect_of(1004) == RestoreNexus(amount=5)


def test_summoned_ax_damages_an_enemy_unit() -> None:
    assert _effect_of(1005) == DamageUnit(amount=3)


def test_every_spell_declares_target_and_duration() -> None:
    """A tabela *Efeitos do MVP* da spec, campo a campo."""
    expected = {
        1001: (TargetKind.ALLIED_UNIT, EffectDuration.PERMANENT),
        1002: (TargetKind.ALLIED_UNIT, EffectDuration.PERMANENT),
        1003: (TargetKind.NONE, EffectDuration.PERMANENT),
        1004: (TargetKind.NONE, EffectDuration.PERMANENT),
        1005: (TargetKind.ENEMY_UNIT, EffectDuration.PERMANENT),
    }
    catalog = mvp_catalog()

    for card_id, (target_kind, duration) in expected.items():
        spell = catalog.card(CardId(card_id))

        assert isinstance(spell, Spell)
        assert (spell.effect.target_kind, spell.effect.duration) == (
            target_kind,
            duration,
        )


def test_requires_target_follows_the_target_kind() -> None:
    """Derivado de `target_kind`, nos dois sentidos."""
    needs_target = {1001, 1002, 1005}

    for spell in MVP_SPELLS:
        assert spell.effect.requires_target == (spell.card_id in needs_target)


def test_no_effect_wants_a_target_it_cannot_name() -> None:
    """`requires_target=True` com `target_kind=NONE` seria estado impossível."""
    for spell in MVP_SPELLS:
        if spell.effect.target_kind is TargetKind.NONE:
            assert not spell.effect.requires_target


def test_only_sacrificial_fire_is_declaration_only() -> None:
    """§14: o único feitiço do MVP com momento próprio."""
    assert [spell.card_id for spell in MVP_SPELLS if spell.effect.declaration_only] == [
        1003
    ]
