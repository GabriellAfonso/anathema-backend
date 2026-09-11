"""A §5B: o feitiço sai da mão, desconta energia e fica na pilha sem efeito.

Duas metades. A primeira é o lançamento aceito -- e o que ele **não** faz, que é
tão contrato quanto o que faz. A segunda são as recusas, cada uma nomeando o
valor ofensor, e todas provando por `match_snapshot` que o estado ficou
idêntico.

A ordem das guardas é parte do contrato: um autor que falha em duas recebe a
recusa da primeira, sempre.
"""

import pytest

from apps.game.cards import CardCatalog, TargetKind, mvp_catalog
from apps.game.engine import (
    CardIsNotASpellError,
    CardNotInHandError,
    CastSpellAction,
    NotEnoughEnergyError,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    SpellNeedsTargetError,
    SpellTakesNoTargetError,
    SpellTargetNotOnBattlefieldError,
    WrongSpellTargetSideError,
    submit_action,
)
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchPhase,
    STARTING_NEXUS,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    LIFE_POTION,
    PLENTY_OF_ENERGY,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    TOUGH_UNIT,
    bank_card,
    fake_spell_board,
    hand_card,
)
from apps.game.tests.match_snapshot import match_snapshot

# `mvp_catalog`: SOMEONE'S SHIELD custa 2, SUMMONED AX custa 5, LIFE POTION 4.
SHIELD_COST = 2
AX_COST = 5


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    return fake_spell_board(
        catalog=catalog, hand_one=(SOMEONES_SHIELD, SUMMONED_AX, LIFE_POTION)
    )


def cast(
    match: Match,
    catalog: CardCatalog,
    source: RandomSource,
    action: CastSpellAction,
) -> None:
    """Toda jogada entra pela porta única do motor, nunca por `cast_spell`."""
    submit_action(match, action, catalog=catalog, randomness=source)


# --------------------------------------------------------------------------
# O lançamento aceito (US1)
# --------------------------------------------------------------------------


def test_the_spell_leaves_the_hand(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    shield = hand_card(one, SOMEONES_SHIELD)

    cast(match, catalog, source, CastSpellAction(one.user_id, shield, bank_card(one)))

    assert shield not in [card.card_instance_id for card in one.hand]


def test_the_spell_lands_on_top_of_the_stack(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    shield = hand_card(one, SOMEONES_SHIELD)

    cast(match, catalog, source, CastSpellAction(one.user_id, shield, bank_card(one)))

    assert [entry.card.card_instance_id for entry in match.stack] == [shield]


def test_the_energy_is_spent(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert one.energy_current == PLENTY_OF_ENERGY - SHIELD_COST


def test_energy_exactly_equal_to_the_cost_is_accepted(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A guarda é `energia >= custo`: igual passa e deixa a energia em 0."""
    one = match.players[0]
    one.energy_current = SHIELD_COST

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert one.energy_current == 0


def test_the_effect_does_not_happen_yet(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """O contrato da §5B: empilhar não é aplicar."""
    one, two = match.players
    unit = one.bank[0]

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert unit.modifiers == []
    assert unit.damage_taken == 0
    assert (one.nexus, two.nexus) == (STARTING_NEXUS, STARTING_NEXUS)
    assert (one.graveyard, two.graveyard) == ([], [])


def test_the_entry_records_the_caster(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert match.stack[0].caster_user_id == one.user_id


def test_the_entry_records_the_target_identifier(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Identificador, nunca referência: é o que torna o fizzle possível."""
    one = match.players[0]
    target = bank_card(one)

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), target),
    )

    assert match.stack[0].target_card_instance_id == target


def test_an_untargeted_spell_records_no_target(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )

    assert match.stack[0].target_card_instance_id is None


def test_the_priority_passes_to_the_opponent(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """É essa troca que dá ao oponente a chance de responder no topo."""
    one, two = match.players

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert match.priority_user_id == two.user_id


def test_the_pass_count_is_reset(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    match.consecutive_passes = 1

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert match.consecutive_passes == 0
    assert match.phase is MatchPhase.ACTION


def test_an_enemy_target_is_accepted(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
    )

    assert len(match.stack) == 1


def test_the_opponent_side_is_otherwise_untouched(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players
    before = (len(two.hand), len(two.bank), two.energy_current, two.nexus)

    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    assert (len(two.hand), len(two.bank), two.energy_current, two.nexus) == before


# --------------------------------------------------------------------------
# As recusas (US8)
# --------------------------------------------------------------------------


def test_an_untargeted_spell_refuses_a_target(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(SpellTakesNoTargetError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, LIFE_POTION), bank_card(one)),
        )

    assert "takes no target" in str(refusal.value)
    assert match_snapshot(match) == before


def test_a_targeted_spell_refuses_a_missing_target(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(SpellNeedsTargetError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD)),
        )

    assert refusal.value.expected is TargetKind.ALLIED_UNIT
    assert match_snapshot(match) == before


def test_an_allied_spell_refuses_an_enemy_unit(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """ "Aliado" é relativo a quem lança."""
    one, two = match.players
    before = match_snapshot(match)

    with pytest.raises(WrongSpellTargetSideError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(two)
            ),
        )

    assert refusal.value.expected is TargetKind.ALLIED_UNIT
    assert refusal.value.owner_user_id == two.user_id
    assert match_snapshot(match) == before


def test_an_enemy_spell_refuses_an_allied_unit(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(WrongSpellTargetSideError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(one)),
        )

    assert refusal.value.expected is TargetKind.ENEMY_UNIT
    assert match_snapshot(match) == before


def test_a_target_that_is_not_on_the_battlefield_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Recusa, e **não** fizzle: fizzle é o alvo sumir depois do lançamento."""
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(SpellTargetNotOnBattlefieldError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                one.user_id, hand_card(one, SOMEONES_SHIELD), CardInstanceId(999)
            ),
        )

    assert refusal.value.target_card_instance_id == CardInstanceId(999)
    assert match_snapshot(match) == before


def test_a_card_in_hand_is_not_a_valid_target(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Só unidade em banco é alvo."""
    one = match.players[0]

    with pytest.raises(SpellTargetNotOnBattlefieldError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                one.user_id,
                hand_card(one, SOMEONES_SHIELD),
                hand_card(one, LIFE_POTION),
            ),
        )


def test_not_enough_energy_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    one.energy_current = AX_COST - 1
    two = match.players[1]
    before = match_snapshot(match)

    with pytest.raises(NotEnoughEnergyError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
        )

    assert (refusal.value.cost, refusal.value.available) == (AX_COST, AX_COST - 1)
    assert match_snapshot(match) == before


def test_a_card_not_in_hand_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(CardNotInHandError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, CardInstanceId(999), bank_card(one)),
        )

    assert refusal.value.card_instance_id == CardInstanceId(999)
    assert match_snapshot(match) == before


def test_the_card_of_the_opponent_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A mão consultada é sempre a do autor da ação."""
    one, two = match.players

    with pytest.raises(CardNotInHandError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
        )


def test_a_unit_card_in_the_spell_action_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Simétrica da recusa que a §5A já dá a uma carta de feitiço."""
    match = fake_spell_board(catalog=catalog, hand_one=(TOUGH_UNIT,))
    one = match.players[0]
    before = match_snapshot(match)

    with pytest.raises(CardIsNotASpellError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, TOUGH_UNIT), bank_card(one)),
        )

    assert "expected a spell" in str(refusal.value)
    assert match_snapshot(match) == before


def test_a_player_without_priority_is_refused_first(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem prioridade **e** com alvo errado **e** sem energia: vence a
    prioridade. As guardas comuns vêm antes da regra específica."""
    one, two = match.players
    two.energy_current = 0
    before = match_snapshot(match)

    with pytest.raises(NotYourPriorityError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                two.user_id, hand_card(two, SUMMONED_AX), CardInstanceId(999)
            ),
        )

    assert match_snapshot(match) == before


def test_a_phase_that_forbids_the_action_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    match.phase = MatchPhase.MULLIGAN
    before = match_snapshot(match)

    with pytest.raises(PhaseForbidsActionError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)
            ),
        )

    assert refusal.value.phase is MatchPhase.MULLIGAN
    assert match_snapshot(match) == before


def test_a_refusal_never_advances_the_match_counters(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Nem identidade de carta nem sorteio: lançar feitiço não cunha nem
    sorteia nada."""
    one = match.players[0]
    before = (match.next_card_instance_id, match.next_roll_ordinal)

    with pytest.raises(SpellNeedsTargetError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD)),
        )

    assert (match.next_card_instance_id, match.next_roll_ordinal) == before


def test_a_refusal_leaves_the_stack_alone(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players
    cast(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    before = match_snapshot(match)

    with pytest.raises(SpellNeedsTargetError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX)),
        )

    assert match_snapshot(match) == before


def test_passing_still_works_with_an_empty_hand(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Mão vazia não trava a partida."""
    match = fake_spell_board(catalog=catalog, hand_one=(), hand_two=())
    one = match.players[0]

    submit_action(match, PassAction(one.user_id), catalog=catalog, randomness=source)

    assert match.consecutive_passes == 1
