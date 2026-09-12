"""O SACRIFICIAL FIRE pela porta do motor: a regra própria da §14.

Fluxo de Partida §14: **sem alvo**. Só na declaração de ataque, só pelo
atacante, e todas as unidades dele que estão na zona de ataque naquele instante
ganham +3. Unidade mandada depois não ganha. O Nexus nunca cai abaixo de 1.

Até a feature 010 o motor pedia alvo -- uma unidade própria na zona -- e buffava
só ela. Era uma regra que a nota não diz, e os testes que a fixavam foram
corrigidos junto com o código.

O que o efeito faz, sozinho, está em `test_spell_effect.py`; aqui fica o
momento e a recusa de alvo, que são guardas de lançamento.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, EffectDuration, mvp_catalog
from apps.game.engine import (
    CastSpellAction,
    DeclareAttackAction,
    SpellOnlyInDeclarationError,
    SpellTakesNoTargetError,
    WithdrawAttackerAction,
    submit_action,
)
from apps.game.match import (
    AttackModifier,
    CardInstanceId,
    Match,
    MatchPhase,
    STARTING_NEXUS,
    UnitModifier,
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
BONUS = AttackModifier(amount=FIRE_ATTACK_BONUS, duration=EffectDuration.PERMANENT)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def declaring(
    catalog: CardCatalog,
    source: RandomSource,
    *,
    bank_one: tuple[CardId, ...],
    attackers: int = 1,
) -> Match:
    """O dono do token com FIRE na mão e as primeiras unidades na zona."""
    match = fake_combat_board(
        catalog=catalog,
        hand_one=(SACRIFICIAL_FIRE,),
        bank_one=bank_one,
        bank_two=(KHRAS,),
    )
    send(match, source, catalog=catalog, indexes=tuple(range(attackers)))

    return match


def send(
    match: Match,
    source: RandomSource,
    *,
    catalog: CardCatalog,
    indexes: tuple[int, ...],
) -> None:
    """Manda para a zona de ataque as unidades naquelas posições do banco."""
    one = match.player(PLAYER_ONE)
    submit_action(
        match,
        DeclareAttackAction(
            PLAYER_ONE, tuple(bank_card(one, index) for index in indexes)
        ),
        catalog=catalog,
        randomness=source,
    )


def fire(
    match: Match,
    target: CardInstanceId | None = None,
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


def bank_modifiers(match: Match) -> list[list[UnitModifier]]:
    """Os modificadores de cada unidade do banco do atacante, na ordem dele."""
    return [unit.modifiers for unit in match.player(PLAYER_ONE).bank]


# --- Sem alvo, toda a zona de ataque -----------------------------------------


def test_the_fire_buffs_every_unit_in_the_attack_zone(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE, MORTEM), attackers=2)
    one = match.player(PLAYER_ONE)

    fire(match, catalog=catalog, source=source)

    assert bank_modifiers(match) == [[BONUS], [BONUS]]
    assert one.nexus == STARTING_NEXUS - FIRE_NEXUS_COST
    assert (match.phase, match.priority_user_id) == (MatchPhase.DECLARATION, PLAYER_ONE)


def test_a_unit_sent_after_the_fire_gets_nothing(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """§14: a zona é lida no instante do lançamento."""
    match = declaring(catalog, source, bank_one=(DARK_AGE, MORTEM), attackers=1)

    fire(match, catalog=catalog, source=source)
    send(match, source, catalog=catalog, indexes=(1,))

    assert bank_modifiers(match) == [[BONUS], []]


def test_a_withdrawn_unit_keeps_the_bonus(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O +3 é permanente, e a §13 registra como pergunta em aberto que uma
    unidade puxada de volta fique com ele sem ter atacado."""
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    one = match.player(PLAYER_ONE)
    fire(match, catalog=catalog, source=source)

    submit_action(
        match,
        WithdrawAttackerAction(PLAYER_ONE, bank_card(one)),
        catalog=catalog,
        randomness=source,
    )

    assert (match.phase, bank_modifiers(match)) == (MatchPhase.ACTION, [[BONUS]])


def test_fire_with_low_nexus_leaves_one(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    one = match.player(PLAYER_ONE)
    one.nexus = 3

    fire(match, catalog=catalog, source=source)

    assert (one.nexus, match.is_over) == (1, False)


# --- Alvo: a carta não aceita nenhum -----------------------------------------


def test_fire_on_a_unit_in_the_attack_zone_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem alvo é sem alvo: mirar a unidade certa é a mesma recusa de mirar
    qualquer outra."""
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    attacking = bank_card(match.player(PLAYER_ONE))
    before = match_snapshot(match)

    with pytest.raises(SpellTakesNoTargetError) as refusal:
        fire(match, attacking, catalog=catalog, source=source)

    assert refusal.value.target_card_instance_id == attacking
    assert match_snapshot(match) == before


def test_fire_on_a_unit_left_in_the_bank_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE, MORTEM))
    left_behind = bank_card(match.player(PLAYER_ONE), 1)
    before = match_snapshot(match)

    with pytest.raises(SpellTakesNoTargetError):
        fire(match, left_behind, catalog=catalog, source=source)

    assert match_snapshot(match) == before


def test_fire_on_an_enemy_unit_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = declaring(catalog, source, bank_one=(DARK_AGE,))
    before = match_snapshot(match)

    with pytest.raises(SpellTakesNoTargetError):
        fire(
            match,
            bank_card(match.player(PLAYER_TWO)),
            catalog=catalog,
            source=source,
        )

    assert match_snapshot(match) == before


# --- Momento: só a declaração, só o atacante ---------------------------------


def test_fire_in_the_action_phase_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_combat_board(catalog=catalog, hand_one=(SACRIFICIAL_FIRE,))
    before = match_snapshot(match)

    with pytest.raises(SpellOnlyInDeclarationError) as refusal:
        fire(match, catalog=catalog, source=source)

    assert refusal.value.phase is MatchPhase.ACTION
    assert match_snapshot(match) == before


def test_the_momento_guard_comes_before_the_target_guard(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Fora da declaração, com alvo, a recusa continua sendo a de momento: a
    ordem das guardas da §5B é contrato da feature 006."""
    match = fake_combat_board(catalog=catalog, hand_one=(SACRIFICIAL_FIRE,))

    with pytest.raises(SpellOnlyInDeclarationError):
        fire(
            match,
            bank_card(match.player(PLAYER_ONE)),
            catalog=catalog,
            source=source,
        )


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
            catalog=catalog,
            source=source,
            actor_user_id=PLAYER_TWO,
        )

    assert match_snapshot(match) == before
