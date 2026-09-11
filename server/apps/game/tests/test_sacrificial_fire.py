"""O SACRIFICIAL FIRE pela porta do motor: a regra própria da §14.

Fluxo de Partida, corrigido em 2026-09-11: só na declaração de ataque, só pelo
atacante, com alvo numa unidade própria na zona de ataque, e o Nexus nunca cai
abaixo de 1. O que o efeito faz, sozinho, está em `test_spell_effect.py`; aqui
fica o momento e o alvo, que são guardas de lançamento.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, EffectDuration, TargetKind, mvp_catalog
from apps.game.engine import (
    CastSpellAction,
    DeclareAttackAction,
    SpellNeedsTargetError,
    SpellOnlyInDeclarationError,
    UnitIsNotAttackingError,
    WrongSpellTargetSideError,
    submit_action,
)
from apps.game.match import (
    AttackModifier,
    CardInstanceId,
    Match,
    MatchPhase,
    STARTING_NEXUS,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    SACRIFICIAL_FIRE,
    bank_card,
    declare_combat,
    fake_combat_board,
    hand_card,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.match_snapshot import match_snapshot

FIRE_NEXUS_COST = 8
FIRE_ATTACK_BONUS = 3


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def declaring(
    catalog: CardCatalog, source: RandomSource, *, bank_one: tuple[CardId, ...]
) -> Match:
    """O dono do token com FIRE na mão e a primeira unidade na zona de ataque."""
    match = fake_combat_board(
        catalog=catalog,
        hand_one=(SACRIFICIAL_FIRE,),
        bank_one=bank_one,
        bank_two=(KHRAS,),
    )
    submit_action(
        match,
        DeclareAttackAction(PLAYER_ONE, (bank_card(match.player(PLAYER_ONE)),)),
        catalog=catalog,
        randomness=source,
    )

    return match


def fire(
    match: Match,
    target: CardInstanceId | None,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    actor_user_id: int = PLAYER_ONE,
) -> None:
    actor = match.player(actor_user_id)
    submit_action(
        match,
        CastSpellAction(
            actor_user_id,
            hand_card(actor, SACRIFICIAL_FIRE),
            target,
        ),
        catalog=catalog,
        randomness=source,
    )


def test_the_attacker_fires_on_a_unit_in_the_attack_zone(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    one = match.player(PLAYER_ONE)

    fire(match, bank_card(one), catalog=catalog, source=source)

    assert one.bank[0].modifiers == [
        AttackModifier(amount=FIRE_ATTACK_BONUS, duration=EffectDuration.PERMANENT)
    ]
    assert one.nexus == STARTING_NEXUS - FIRE_NEXUS_COST
    assert (match.phase, match.priority_user_id) == (MatchPhase.DECLARATION, PLAYER_ONE)


def test_fire_with_low_nexus_leaves_one(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    one = match.player(PLAYER_ONE)
    one.nexus = 3

    fire(match, bank_card(one), catalog=catalog, source=source)

    assert (one.nexus, match.is_over) == (1, False)


def test_fire_in_the_action_phase_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_combat_board(catalog=catalog, hand_one=(SACRIFICIAL_FIRE,))
    before = match_snapshot(match)

    with pytest.raises(SpellOnlyInDeclarationError) as refusal:
        fire(
            match,
            bank_card(match.player(PLAYER_ONE)),
            catalog=catalog,
            source=source,
        )

    assert refusal.value.phase is MatchPhase.ACTION
    assert match_snapshot(match) == before


def test_the_defender_cannot_fire_in_the_defense_window(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A vez é do defensor na defesa, e a recusa é de momento, não de vez."""
    match = fake_combat_board(catalog=catalog, hand_two=(SACRIFICIAL_FIRE,))
    declare_combat(match, 0)
    before = match_snapshot(match)

    with pytest.raises(SpellOnlyInDeclarationError):
        fire(
            match,
            bank_card(match.player(PLAYER_TWO)),
            catalog=catalog,
            source=source,
            actor_user_id=PLAYER_TWO,
        )

    assert match_snapshot(match) == before


def test_fire_on_a_unit_left_in_the_bank_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Aliada, mas fora da zona de ataque."""
    match = declaring(catalog, source, bank_one=(DARK_AGE, MORTEM))
    left_behind = bank_card(match.player(PLAYER_ONE), 1)
    before = match_snapshot(match)

    with pytest.raises(UnitIsNotAttackingError) as refusal:
        fire(match, left_behind, catalog=catalog, source=source)

    assert refusal.value.card_instance_id == left_behind
    assert match_snapshot(match) == before


def test_fire_on_an_enemy_unit_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    before = match_snapshot(match)

    with pytest.raises(WrongSpellTargetSideError) as refusal:
        fire(
            match,
            bank_card(match.player(PLAYER_TWO)),
            catalog=catalog,
            source=source,
        )

    assert refusal.value.expected is TargetKind.ALLIED_ATTACKER
    assert match_snapshot(match) == before


def test_fire_without_a_target_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    before = match_snapshot(match)

    with pytest.raises(SpellNeedsTargetError):
        fire(match, None, catalog=catalog, source=source)

    assert match_snapshot(match) == before
