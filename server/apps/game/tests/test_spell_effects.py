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


def test_magic_barrier_protects_an_ally_until_the_round_ends() -> None:
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
        1002: (TargetKind.ALLIED_UNIT, EffectDuration.UNTIL_END_OF_ROUND),
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


def test_target_properties_read_the_same_twice() -> None:
    """O motor lê ao aceitar a jogada e de novo ao resolver a pilha.

    As duas leituras precisam concordar, senão um feitiço aceito com alvo válido
    poderia exigir outra coisa na resolução (Fluxo de Partida §5B e §6).
    """
    catalog = mvp_catalog()

    for spell in MVP_SPELLS:
        on_cast = catalog.card(spell.card_id)
        on_resolve = catalog.card(spell.card_id)

        assert isinstance(on_cast, Spell)
        assert isinstance(on_resolve, Spell)
        assert on_cast.effect == on_resolve.effect
        assert on_cast.effect.requires_target == on_resolve.effect.requires_target
        assert on_cast.effect.target_kind is on_resolve.effect.target_kind
        assert on_cast.effect.duration is on_resolve.effect.duration
