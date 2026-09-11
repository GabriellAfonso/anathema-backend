"""A §5B: jogar feitiço resolve na hora e não passa a vez.

Fluxo de Partida, corrigido em 2026-09-11: o feitiço resolve na hora. O efeito acontece
na jogada, a carta vai ao cemitério, os passes zeram, e quem jogou continua com
a prioridade — pode jogar outro feitiço, quantos a energia pagar. A vez só passa
com jogar unidade, declarar ataque ou passar.

O teste que carrega o arquivo é `test_both_phases_give_the_same_state`: cada um
dos cinco efeitos, jogado na Fase de Ação e na janela do defensor a partir do
mesmo tabuleiro, deixa os dois jogadores iguais campo a campo. É ele que segura
a promessa de que jogar feitiço é uma ação só.

As recusas estão em `test_cast_spell_refusals.py`, e o que o feitiço do defensor
muda no combate, em `test_spell_in_combat.py`.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, mvp_catalog
from apps.game.engine import (
    CastSpellAction,
    PassAction,
    PlayUnitAction,
    submit_action,
)
from apps.game.match import (
    HealthModifier,
    Match,
    MatchPhase,
    STARTING_NEXUS,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import MORTEM, declare_combat, in_graveyard
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    FRAGILE_UNIT,
    LIFE_POTION,
    MAGIC_BARRIER,
    PLENTY_OF_ENERGY,
    PLAYER_ONE,
    PLAYER_TWO,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    bank_card,
    fake_spell_board,
    hand_card,
)
from apps.game.tests.match_snapshot import match_snapshot

# `mvp_catalog`: SOMEONE'S SHIELD custa 2, LIFE POTION 4, SUMMONED AX 5; LIFE
# POTION cura 5.
SHIELD_COST = 2
POTION_COST = 4
AX_COST = 5
POTION_HEAL = 5


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    return fake_spell_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD, SUMMONED_AX, LIFE_POTION),
        bank_two=(FRAGILE_UNIT,),
    )


def act(
    match: Match,
    catalog: CardCatalog,
    source: RandomSource,
    action: CastSpellAction | PassAction | PlayUnitAction,
) -> None:
    """Toda jogada entra pela porta única do motor, nunca por `cast_spell`."""
    submit_action(match, action, catalog=catalog, randomness=source)


def shield_own_unit(match: Match, catalog: CardCatalog, source: RandomSource) -> None:
    """O primeiro jogador joga SOMEONE'S SHIELD na própria unidade."""
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )


# --------------------------------------------------------------------------
# O efeito, na jogada
# --------------------------------------------------------------------------


def test_the_effect_happens_on_the_cast(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem nenhum passe: o efeito já está na unidade."""
    two = match.players[1]
    target = bank_card(two)
    one = match.players[0]

    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), target),
    )

    assert in_graveyard(two, target)
    assert match.consecutive_passes == 0


def test_the_killed_unit_and_the_spell_card_land_in_their_graveyards(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A unidade morta vai ao cemitério do dono, e a carta do feitiço ao de quem
    jogou. Nada fica em lugar nenhum entre a mão e o cemitério."""
    one, two = match.players
    ax = hand_card(one, SUMMONED_AX)
    target = bank_card(two)

    act(match, catalog, source, CastSpellAction(one.user_id, ax, target))

    assert [card.card_instance_id for card in two.graveyard] == [target]
    assert [card.card_instance_id for card in one.graveyard] == [ax]
    assert ax not in [card.card_instance_id for card in one.hand]


def test_the_energy_is_spent(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    shield_own_unit(match, catalog, source)

    assert match.players[0].energy_current == PLENTY_OF_ENERGY - SHIELD_COST


def test_energy_exactly_equal_to_the_cost_is_accepted(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A guarda é `energia >= custo`: igual passa e deixa a energia em 0."""
    match.players[0].energy_current = SHIELD_COST

    shield_own_unit(match, catalog, source)

    assert match.players[0].energy_current == 0


def test_an_untargeted_spell_resolves_on_the_cast(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]

    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )

    assert one.nexus == STARTING_NEXUS + POTION_HEAL


def test_a_permanent_modifier_is_there_on_the_cast(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """SOMEONE'S SHIELD escreve o modificador na jogada, sem esperar passe."""
    unit = match.players[0].bank[0]

    shield_own_unit(match, catalog, source)

    assert [type(modifier) for modifier in unit.modifiers] == [HealthModifier]


def test_an_enemy_target_is_accepted(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players

    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
    )

    assert one.energy_current == PLENTY_OF_ENERGY - AX_COST


def test_the_opponent_side_is_otherwise_untouched(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    two = match.players[1]
    before = (len(two.hand), len(two.bank), two.energy_current, two.nexus)

    shield_own_unit(match, catalog, source)

    assert (len(two.hand), len(two.bank), two.energy_current, two.nexus) == before


# --------------------------------------------------------------------------
# A vez
# --------------------------------------------------------------------------


def test_the_spell_keeps_the_turn_in_both_phases() -> None:
    """Feitiço não gasta a vez (§5B), na Fase de Ação e nas duas janelas do
    combate, e é a mesma ação nas três."""
    assert CastSpellAction.keeps_priority
    assert CastSpellAction.allowed_phases == frozenset(
        {MatchPhase.ACTION, MatchPhase.DECLARATION, MatchPhase.COMBAT}
    )


def test_the_priority_stays_with_the_caster(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    shield_own_unit(match, catalog, source)

    assert match.priority_user_id == PLAYER_ONE
    assert match.phase is MatchPhase.ACTION


def test_a_second_spell_in_the_same_turn_is_accepted(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    shield_own_unit(match, catalog, source)

    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )

    assert one.energy_current == PLENTY_OF_ENERGY - SHIELD_COST - POTION_COST
    assert match.priority_user_id == PLAYER_ONE


def test_a_unit_after_a_spell_gives_the_turn_back(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Feitiço não gasta a vez; unidade gasta."""
    match = fake_spell_board(catalog=catalog, hand_one=(SOMEONES_SHIELD, MORTEM))
    one = match.players[0]

    shield_own_unit(match, catalog, source)
    act(match, catalog, source, PlayUnitAction(one.user_id, hand_card(one, MORTEM)))

    assert match.priority_user_id == PLAYER_TWO


def test_the_pass_count_is_reset(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    match.consecutive_passes = 1

    shield_own_unit(match, catalog, source)

    assert match.consecutive_passes == 0


def test_a_pass_after_a_spell_does_not_close_the_round(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """B passa, A joga feitiço e passa: a rodada continua, e B recebe a vez para
    reagir ao que o feitiço fez. Sem a zeragem, o passe de A fecharia a rodada."""
    match = fake_spell_board(catalog=catalog, hand_two=(LIFE_POTION,))
    one, two = match.players

    act(match, catalog, source, PassAction(one.user_id))
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, LIFE_POTION)),
    )
    act(match, catalog, source, PassAction(two.user_id))

    assert match.consecutive_passes == 1
    assert match.priority_user_id == one.user_id
    assert (match.round_number, match.phase) == (1, MatchPhase.ACTION)


def test_passing_still_works_with_an_empty_hand(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Mão vazia não trava a partida."""
    match = fake_spell_board(catalog=catalog, hand_one=(), hand_two=())
    one = match.players[0]

    act(match, catalog, source, PassAction(one.user_id))

    assert match.consecutive_passes == 1


# --------------------------------------------------------------------------
# As duas fases, mesmo resultado
# --------------------------------------------------------------------------


def test_both_phases_give_the_same_state(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Cada um dos cinco efeitos, jogado na Fase de Ação e na janela do
    defensor a partir do mesmo tabuleiro — e os dois jogadores iguais campo a
    campo.

    Herdeiro de `test_both_paths_give_the_same_state` da feature 007, que
    comparava os dois caminhos de lançamento de antes. Com um só, o que sobra para divergir é um
    `if` de fase dentro de `cast_spell`, e é isso que este teste impede.

    SACRIFICIAL FIRE fica de fora: a §14 da nota, corrigida em 2026-09-11, o
    restringe à declaração e o proíbe ao defensor. A regra dele está em
    `test_sacrificial_fire.py`.
    """
    for card_id, needs_ally, needs_enemy in (
        (SOMEONES_SHIELD, True, False),
        (MAGIC_BARRIER, True, False),
        (LIFE_POTION, False, False),
        (SUMMONED_AX, False, True),
    ):
        in_action = _apply_in_action_phase(
            catalog, source, card_id, needs_ally, needs_enemy
        )
        in_combat = _apply_in_combat(catalog, source, card_id, needs_ally, needs_enemy)

        assert _comparable(in_action) == _comparable(in_combat), card_id


def _board_for(catalog: CardCatalog, card_id: CardId) -> Match:
    """O segundo jogador segura a carta, e os dois têm MORTEM no banco."""
    return fake_spell_board(
        catalog=catalog,
        hand_one=(),
        hand_two=(card_id,),
        bank_one=(MORTEM,),
        bank_two=(MORTEM,),
    )


def _cast_by_the_second_player(
    match: Match,
    catalog: CardCatalog,
    source: RandomSource,
    card_id: CardId,
    target_side: tuple[bool, bool],
) -> None:
    needs_ally, needs_enemy = target_side
    two, one = match.players[1], match.players[0]
    target = bank_card(two) if needs_ally else bank_card(one) if needs_enemy else None

    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, card_id), target),
    )


def _apply_in_action_phase(
    catalog: CardCatalog,
    source: RandomSource,
    card_id: CardId,
    needs_ally: bool,
    needs_enemy: bool,
) -> Match:
    """A §5B: o segundo jogador tem a vez na Fase de Ação."""
    match = _board_for(catalog, card_id)
    match.priority_user_id = PLAYER_TWO

    _cast_by_the_second_player(
        match, catalog, source, card_id, (needs_ally, needs_enemy)
    )

    return match


def _apply_in_combat(
    catalog: CardCatalog,
    source: RandomSource,
    card_id: CardId,
    needs_ally: bool,
    needs_enemy: bool,
) -> Match:
    """A §7.2: o segundo jogador é o defensor, com a janela aberta."""
    match = _board_for(catalog, card_id)
    declare_combat(match, 0)

    _cast_by_the_second_player(
        match, catalog, source, card_id, (needs_ally, needs_enemy)
    )

    return match


def _comparable(match: Match) -> object:
    """As zonas, os Nexus e os bancos. Fase, token e combate ficam de fora: é o
    que as duas fases têm de diferente por definição, e o que está sob teste é o
    **efeito**."""
    return match_snapshot(match)["players"]
