"""Empilhar, responder e resolver a pilha inteira em LIFO (§5B e §6).

Três blocos. O primeiro é a pilha enchendo, com feitiços dos dois jogadores na
ordem de lançamento. O segundo é `resolve_stack` chamada **direto**, sobre uma
pilha montada pelo motor -- é o que prova a §6 sem a cascata no caminho. O
terceiro é a cascata, em que dois passes resolvem tudo numa resposta só.

O exemplo canônico da §6 fecha o arquivo: ele é o teste que prova que a
revalidação por identificador é real, e não uma referência disfarçada.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import (
    CastSpellAction,
    NotYourPriorityError,
    PassAction,
    PlayUnitAction,
    submit_action,
    unit_max_health,
)
from apps.game.engine.stack_resolution import resolve_stack
from apps.game.match import Match, MatchPhase, STARTING_NEXUS, StackEntry
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    FRAGILE_UNIT,
    LIFE_POTION,
    MAGIC_BARRIER,
    SACRIFICIAL_FIRE,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    TOUGH_UNIT,
    bank_card,
    fake_spell_board,
    hand_card,
)

TOUGH_UNIT_HEALTH = 4
FRAGILE_UNIT_HEALTH = 2


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    return fake_spell_board(catalog=catalog)


def act(
    match: Match,
    catalog: CardCatalog,
    source: RandomSource,
    action: CastSpellAction | PassAction | PlayUnitAction,
) -> None:
    submit_action(match, action, catalog=catalog, randomness=source)


def both_pass(match: Match, catalog: CardCatalog, source: RandomSource) -> None:
    """Os dois passes consecutivos que disparam a saída da §5."""
    for _ in range(2):
        holder = match.priority_user_id
        assert holder is not None
        act(match, catalog, source, PassAction(holder))


# --------------------------------------------------------------------------
# A pilha enchendo (US2)
# --------------------------------------------------------------------------


def test_the_opponent_answers_on_top(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
    )

    assert [entry.caster_user_id for entry in match.stack] == [
        one.user_id,
        two.user_id,
    ]


def test_the_top_of_the_stack_is_the_last_cast(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Fim da lista é o topo: `append` empilha, e a resolução é LIFO."""
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    answer = hand_card(two, SUMMONED_AX)

    act(match, catalog, source, CastSpellAction(two.user_id, answer, bank_card(one)))

    assert match.stack[-1].card.card_instance_id == answer


def test_three_spells_keep_the_cast_order(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD, LIFE_POTION),
        hand_two=(MAGIC_BARRIER,),
    )
    one, two = match.players
    first = hand_card(one, SOMEONES_SHIELD)
    second = hand_card(two, MAGIC_BARRIER)
    third = hand_card(one, LIFE_POTION)

    act(match, catalog, source, CastSpellAction(one.user_id, first, bank_card(one)))
    act(match, catalog, source, CastSpellAction(two.user_id, second, bank_card(two)))
    act(match, catalog, source, CastSpellAction(one.user_id, third))

    assert [entry.card.card_instance_id for entry in match.stack] == [
        first,
        second,
        third,
    ]


def test_answering_without_priority_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    with pytest.raises(NotYourPriorityError):
        act(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
        )

    assert len(match.stack) == 1


def test_playing_a_unit_leaves_the_stack_intact(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Jogar unidade não usa a pilha e não a resolve (§5A)."""
    match = fake_spell_board(
        catalog=catalog, hand_one=(SOMEONES_SHIELD,), hand_two=(TOUGH_UNIT,)
    )
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    act(
        match,
        catalog,
        source,
        PlayUnitAction(two.user_id, hand_card(two, TOUGH_UNIT)),
    )

    assert len(match.stack) == 1
    assert match.consecutive_passes == 0


# --------------------------------------------------------------------------
# `resolve_stack` direto, sem a cascata (US3)
# --------------------------------------------------------------------------


def test_the_stack_empties(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    resolve_stack(match, catalog=catalog)

    assert match.stack == []


def test_the_effect_is_applied_on_resolution(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    unit = one.bank[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    resolve_stack(match, catalog=catalog)

    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH + 2


def test_the_card_goes_to_the_graveyard_of_its_caster(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one, two = match.players
    shield = hand_card(one, SOMEONES_SHIELD)
    act(match, catalog, source, CastSpellAction(one.user_id, shield, bank_card(one)))

    resolve_stack(match, catalog=catalog)

    assert [card.card_instance_id for card in one.graveyard] == [shield]
    assert two.graveyard == []


def test_the_whole_stack_resolves_top_down(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem devolver prioridade entre um feitiço e o seguinte."""
    match = fake_spell_board(
        catalog=catalog, hand_one=(LIFE_POTION,), hand_two=(SACRIFICIAL_FIRE,)
    )
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SACRIFICIAL_FIRE)),
    )

    resolve_stack(match, catalog=catalog)

    assert (one.nexus, two.nexus) == (STARTING_NEXUS + 5, STARTING_NEXUS - 8)


def test_a_fizzled_spell_does_nothing(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O alvo sumiu entre o lançamento e a resolução."""
    match = fake_spell_board(catalog=catalog, hand_one=(SOMEONES_SHIELD,))
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    orphan = one.bank.pop()

    resolve_stack(match, catalog=catalog)

    assert orphan.modifiers == []


def test_a_fizzled_card_still_goes_to_the_graveyard(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_spell_board(catalog=catalog, hand_one=(SOMEONES_SHIELD,))
    one = match.players[0]
    shield = hand_card(one, SOMEONES_SHIELD)
    act(match, catalog, source, CastSpellAction(one.user_id, shield, bank_card(one)))
    one.bank.pop()

    resolve_stack(match, catalog=catalog)

    assert [card.card_instance_id for card in one.graveyard] == [shield]


def test_an_untargeted_spell_never_fizzles(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Banco vazio dos dois lados, e LIFE POTION resolve do mesmo jeito."""
    match = fake_spell_board(
        catalog=catalog, hand_one=(LIFE_POTION,), bank_one=(), bank_two=()
    )
    one = match.players[0]
    one.nexus = 10
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )

    resolve_stack(match, catalog=catalog)

    assert one.nexus == 15


def test_the_priority_returns_to_whoever_opened_the_stack(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Quem abriu, não quem fechou."""
    one, two = match.players
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
    )

    resolve_stack(match, catalog=catalog)

    assert match.priority_user_id == one.user_id


def test_a_single_caster_gets_the_priority_back(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_spell_board(catalog=catalog, hand_one=(LIFE_POTION,))
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, LIFE_POTION)),
    )

    resolve_stack(match, catalog=catalog)

    assert match.priority_user_id == one.user_id


def test_the_pass_count_is_consumed_by_the_resolution(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    match.consecutive_passes = 2

    resolve_stack(match, catalog=catalog)

    assert match.consecutive_passes == 0


def test_the_round_does_not_close(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    resolve_stack(match, catalog=catalog)

    assert match.round_number == 1
    assert match.phase is MatchPhase.ACTION


def test_the_resolution_spends_no_energy_and_draws_nothing(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    before = (one.energy_current, len(one.hand), len(one.deck))

    resolve_stack(match, catalog=catalog)

    assert (one.energy_current, len(one.hand), len(one.deck)) == before


# --------------------------------------------------------------------------
# A cascata (US3)
# --------------------------------------------------------------------------


def test_two_passes_resolve_the_stack_in_one_response(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    unit = one.bank[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    both_pass(match, catalog, source)

    assert match.stack == []
    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH + 2


def test_the_caller_never_observes_the_resolution_phase(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Fase de passagem, como o Upkeep e o Fim de Rodada."""
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    both_pass(match, catalog, source)

    assert match.phase is MatchPhase.ACTION


def test_the_round_continues_after_the_resolution(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )

    both_pass(match, catalog, source)

    assert match.round_number == 1


def test_two_more_passes_then_close_the_round(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Com a pilha vazia, aí sim a §8 acontece."""
    one = match.players[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    both_pass(match, catalog, source)

    both_pass(match, catalog, source)

    assert match.round_number == 2


# --------------------------------------------------------------------------
# O exemplo canônico da §6 (US4)
# --------------------------------------------------------------------------


def canonical_example(catalog: CardCatalog, source: RandomSource) -> Match:
    """A joga buff de vida em X; B responde com dano em X; os dois passam.

    X é MORTEM, com 2 de vida: os 3 de dano do SUMMONED AX a matam mesmo com o
    buff de +2, se ele chegasse -- e ele não chega, porque resolve depois.
    """
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD,),
        hand_two=(SUMMONED_AX,),
        bank_one=(FRAGILE_UNIT,),
    )
    one, two = match.players

    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
    )
    both_pass(match, catalog, source)

    return match


def test_the_canonical_target_dies(catalog: CardCatalog, source: RandomSource) -> None:
    match = canonical_example(catalog, source)
    one = match.players[0]

    assert one.bank == []


def test_the_canonical_target_goes_to_the_graveyard_of_its_owner(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = canonical_example(catalog, source)
    one, two = match.players

    assert len(one.graveyard) == 2
    assert len(two.graveyard) == 1


def test_the_canonical_buff_fizzles(catalog: CardCatalog, source: RandomSource) -> None:
    """O alvo não existe mais quando o buff resolve: nenhum modificador em
    lugar nenhum."""
    match = canonical_example(catalog, source)
    one, two = match.players

    assert [unit.modifiers for unit in one.bank] == []
    assert [unit.modifiers for unit in two.bank] == [[]]


def test_the_canonical_cards_reach_their_casters_graveyards(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Cada carta no cemitério de quem a lançou -- a que resolveu e a que
    fizzlou."""
    match = canonical_example(catalog, source)
    one, two = match.players

    assert [card.card_id for card in one.graveyard] == [FRAGILE_UNIT, SOMEONES_SHIELD]
    assert [card.card_id for card in two.graveyard] == [SUMMONED_AX]
    assert match.stack == []


def test_a_lower_spell_fizzles_when_the_upper_one_kills_the_target(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Dois feitiços de dano na mesma unidade: o de cima mata, o de baixo fizzla.

    A pilha é montada à mão porque a prioridade alterna a cada ação, e um mesmo
    jogador não consegue empilhar dois feitiços de alvo inimigo em sequência.
    É a resolução que está sob teste, não o caminho até ela.
    """
    match = fake_spell_board(
        catalog=catalog, hand_one=(SUMMONED_AX, SUMMONED_AX), bank_two=(FRAGILE_UNIT,)
    )
    one, two = match.players
    lower, upper = one.hand
    target = bank_card(two)
    match.stack = [
        StackEntry(
            card=lower, caster_user_id=one.user_id, target_card_instance_id=target
        ),
        StackEntry(
            card=upper, caster_user_id=one.user_id, target_card_instance_id=target
        ),
    ]
    one.hand = []

    resolve_stack(match, catalog=catalog)

    assert two.bank == []
    assert [card.card_instance_id for card in one.graveyard] == [
        upper.card_instance_id,
        lower.card_instance_id,
    ]


def test_the_lower_spell_applied_nothing_when_it_fizzled(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A unidade morta levou 3 de dano, não 6: o segundo AX não chegou nela."""
    match = fake_spell_board(
        catalog=catalog, hand_one=(SUMMONED_AX, SUMMONED_AX), bank_two=(FRAGILE_UNIT,)
    )
    one, two = match.players
    lower, upper = one.hand
    target = bank_card(two)
    dead = two.bank[0]
    match.stack = [
        StackEntry(
            card=lower, caster_user_id=one.user_id, target_card_instance_id=target
        ),
        StackEntry(
            card=upper, caster_user_id=one.user_id, target_card_instance_id=target
        ),
    ]
    one.hand = []

    resolve_stack(match, catalog=catalog)

    assert dead.damage_taken == 3


def test_a_surviving_target_does_not_fizzle_the_lower_spell(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A unidade sobrevive ao de cima, e o de baixo é aplicado."""
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD,),
        hand_two=(SUMMONED_AX,),
        bank_one=(TOUGH_UNIT,),
    )
    one, two = match.players
    unit = one.bank[0]
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
    )
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
    )

    both_pass(match, catalog, source)

    assert unit.damage_taken == 3
    assert unit_max_health(unit, catalog=catalog) == TOUGH_UNIT_HEALTH + 2


def test_a_barrier_cast_above_the_damage_protects_the_unit(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """B mira a unidade de A; A responde com MAGIC BARRIER nela.

    A barreira está **acima** do dano na pilha, então resolve primeiro, e o dano
    não entra. O feitiço de dano não fizzla: o alvo estava em campo e o efeito
    foi aplicado -- aplicar 0 é o resultado certo.
    """
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(MAGIC_BARRIER,),
        hand_two=(SUMMONED_AX,),
        bank_one=(FRAGILE_UNIT,),
    )
    one, two = match.players
    unit = one.bank[0]
    match.priority_user_id = two.user_id
    act(
        match,
        catalog,
        source,
        CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
    )
    act(
        match,
        catalog,
        source,
        CastSpellAction(one.user_id, hand_card(one, MAGIC_BARRIER), bank_card(one)),
    )

    both_pass(match, catalog, source)

    assert unit.damage_taken == 0
    assert len(one.bank) == 1
    assert len(two.graveyard) == 1
