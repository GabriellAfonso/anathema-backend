"""As duas portas do ciclo: o primeiro empurrão e a cascata.

O teste central deste arquivo é
`test_a_single_pass_delivers_the_whole_next_round`: é ele que pega uma
implementação que execute um passo por chamada e devolva a partida em
`ROUND_END`. Essa implementação passa em todo teste de fase isolada -- o Upkeep
recarrega, o Fim de Rodada varre -- e trava na primeira partida real, porque
ninguém dá o empurrão seguinte.

O par `test_the_stack_branch_of_the_exit_is_wired` e
`test_the_stack_stays_empty_across_ten_rounds` guarda a costura que esta feature
deixa de propósito: a saída da §5 decide por `STACK_RESOLUTION`, e a cascata não
sabe atravessá-lo. O primeiro afirma que o encaixe existe para a feature de
pilha; o segundo, que nada nesta feature o alcança.
"""

import pytest

from apps.game.cards import CardId, EffectDuration, Unit
from apps.game.engine import (
    MatchNotAwaitingUpkeepError,
    PassAction,
    begin_round_cycle,
    submit_action,
)
from apps.game.engine.upkeep import MAX_ENERGY
from apps.game.match import (
    AttackModifier,
    BankUnit,
    Match,
    MatchPhase,
    StackEntry,
    match_from_document,
    to_match_document,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_card_catalog import FakeCardCatalog
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import (
    fake_match_in_action_phase,
    fake_match_ready_for_upkeep,
    fake_started_match,
)
from apps.game.tests.match_snapshot import match_snapshot

CHEAP_UNIT = Unit(
    card_id=CardId(2), name="CHEAP", energy=1, attack=3, health=4, image="cheap_card"
)
CATALOG = FakeCardCatalog([CHEAP_UNIT])

SETUP_HAND_WITH_TOKEN = 4
SETUP_HAND_WITHOUT_TOKEN = 5


def source() -> RandomSource:
    return ScriptedRandomSource()


def match_in_action_phase(round_number: int = 1) -> Match:
    """Partida montada à mão na Fase de Ação, com deck para vários Upkeeps."""
    match = fake_new_match()

    match.round_number = round_number
    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = PLAYER_ONE
    match.phase = MatchPhase.ACTION

    for player in match.players:
        player.deck = fake_cards(match, list(range(31, 61)))
        player.energy_max = round_number
        player.energy_current = round_number

    return match


def act_pass(match: Match) -> None:
    assert match.priority_user_id is not None
    submit_action(
        match,
        PassAction(actor_user_id=match.priority_user_id),
        catalog=CATALOG,
        randomness=source(),
    )


# --- O primeiro empurrão -----------------------------------------------------


def test_the_first_push_opens_round_one_in_the_action_phase() -> None:
    match = fake_match_ready_for_upkeep()

    begin_round_cycle(match, randomness=source())

    assert match.phase is MatchPhase.ACTION
    assert match.round_number == 1


def test_the_first_push_gives_one_energy_to_both_sides() -> None:
    match = fake_match_ready_for_upkeep()

    begin_round_cycle(match, randomness=source())

    assert [player.energy_max for player in match.players] == [1, 1]
    assert [player.energy_current for player in match.players] == [1, 1]


def test_the_first_push_gives_one_more_card_to_each_hand() -> None:
    match = fake_match_ready_for_upkeep()
    hands_before = [len(player.hand) for player in match.players]

    begin_round_cycle(match, randomness=source())

    assert sorted(hands_before) == [SETUP_HAND_WITH_TOKEN, SETUP_HAND_WITHOUT_TOKEN]
    assert [len(player.hand) for player in match.players] == [
        size + 1 for size in hands_before
    ]


def test_priority_starts_with_the_token_holder() -> None:
    match = fake_match_ready_for_upkeep()

    begin_round_cycle(match, randomness=source())

    assert match.priority_user_id == match.token_holder_user_id


def test_a_second_push_is_refused_naming_the_phase() -> None:
    """O Upkeep da Rodada 1 roda uma vez só."""
    match = fake_match_in_action_phase()
    before = match_snapshot(match)

    with pytest.raises(MatchNotAwaitingUpkeepError, match="action") as refused:
        begin_round_cycle(match, randomness=source())

    assert refused.value.phase is MatchPhase.ACTION
    assert match_snapshot(match) == before


def test_pushing_a_match_still_in_the_mulligan_is_refused() -> None:
    match = fake_started_match()
    before = match_snapshot(match)

    with pytest.raises(MatchNotAwaitingUpkeepError, match="mulligan"):
        begin_round_cycle(match, randomness=source())

    assert match_snapshot(match) == before


# --- A cascata ---------------------------------------------------------------


def test_a_single_pass_delivers_the_whole_next_round() -> None:
    """Um passe vira a rodada inteira, e o chamador lê o estado já estabilizado."""
    match = match_in_action_phase(round_number=1)
    act_pass(match)
    hands_before = [len(player.hand) for player in match.players]

    act_pass(match)

    assert match.round_number == 2
    assert match.phase is MatchPhase.ACTION
    assert match.consecutive_passes == 0
    assert [player.energy_current for player in match.players] == [2, 2]
    assert [len(player.hand) for player in match.players] == [
        size + 1 for size in hands_before
    ]
    assert match.token_holder_user_id == PLAYER_TWO


def test_the_caller_never_sees_an_automatic_phase() -> None:
    match = match_in_action_phase()

    for _ in range(6):
        act_pass(match)
        assert match.phase is MatchPhase.ACTION


def test_ten_rounds_run_without_the_match_stalling() -> None:
    match = match_in_action_phase(round_number=1)

    for _ in range(20):
        act_pass(match)

    assert match.round_number == 11
    assert match.phase is MatchPhase.ACTION


def test_the_energy_stops_at_ten_and_stays_there() -> None:
    match = match_in_action_phase(round_number=1)

    for _ in range(24):
        act_pass(match)

    assert match.round_number == 13
    assert [player.energy_max for player in match.players] == [MAX_ENERGY, MAX_ENERGY]


def test_the_token_changes_hands_every_round() -> None:
    match = match_in_action_phase()
    holders = [match.token_holder_user_id]

    for _ in range(3):
        act_pass(match)
        act_pass(match)
        holders.append(match.token_holder_user_id)

    assert holders == [PLAYER_ONE, PLAYER_TWO, PLAYER_ONE, PLAYER_TWO]


def test_the_sweep_happens_before_the_token_changes_hands() -> None:
    """A ordem da cascata é a §8 inteira e só então a §4 da rodada nova."""
    match = match_in_action_phase()
    match.players[0].bank = [BankUnit(card=card) for card in fake_cards(match, [15])]
    match.players[0].bank[0].modifiers = [
        AttackModifier(amount=2, duration=EffectDuration.UNTIL_END_OF_ROUND)
    ]

    act_pass(match)
    act_pass(match)

    assert match.players[0].bank[0].modifiers == []
    assert match.token_holder_user_id == PLAYER_TWO


def test_the_upkeep_draw_happens_with_the_round_already_raised() -> None:
    match = match_in_action_phase(round_number=4)

    act_pass(match)
    act_pass(match)

    assert match.round_number == 5
    assert [player.energy_max for player in match.players] == [5, 5]


def test_a_cascade_with_both_hands_full_still_settles() -> None:
    match = match_in_action_phase()
    for player in match.players:
        player.hand = fake_cards(match, list(range(70, 80)))

    act_pass(match)
    act_pass(match)

    assert match.phase is MatchPhase.ACTION
    assert [len(player.hand) for player in match.players] == [10, 10]


def test_no_nexus_changes_across_ten_rounds() -> None:
    match = match_in_action_phase()
    nexus_before = [player.nexus for player in match.players]

    for _ in range(20):
        act_pass(match)

    assert [player.nexus for player in match.players] == nexus_before


def test_nothing_reaches_the_graveyard_across_ten_rounds() -> None:
    match = match_in_action_phase()

    for _ in range(20):
        act_pass(match)

    assert [player.graveyard for player in match.players] == [[], []]


# --- A costura da pilha ------------------------------------------------------


def test_the_stack_stays_empty_across_ten_rounds() -> None:
    """Nada nesta feature empilha, e é isso que torna a costura inalcançável."""
    match = match_in_action_phase()

    for _ in range(20):
        act_pass(match)
        assert match.stack == []


def test_the_stack_branch_of_the_exit_is_wired() -> None:
    """Com um feitiço posto à mão, dois passes levam a `STACK_RESOLUTION`.

    A cascata para ali de propósito: a feature que enche a pilha é a que precisa
    saber esvaziá-la (§6). O encaixe existe agora para que a saída da §5 não
    precise ser reescrita depois -- e este teste é o que garante que ele continua
    ligado.
    """
    match = match_in_action_phase()
    pending = fake_cards(match, [1001])[0]
    match.stack = [StackEntry(card=pending, caster_user_id=PLAYER_ONE)]

    act_pass(match)
    act_pass(match)

    assert match.phase is MatchPhase.STACK_RESOLUTION
    assert match.round_number == 1


# --- Round-trip pelo Redis ---------------------------------------------------


def test_a_match_in_mid_round_survives_the_round_trip() -> None:
    match = match_in_action_phase()
    match.players[0].bank = [BankUnit(card=card) for card in fake_cards(match, [15])]
    match.players[0].bank[0].damage_taken = 2
    match.players[0].bank[0].modifiers = [
        AttackModifier(amount=2, duration=EffectDuration.PERMANENT)
    ]
    act_pass(match)

    rebuilt = match_from_document(to_match_document(match))

    assert to_match_document(rebuilt) == to_match_document(match)


def test_a_match_that_just_turned_the_round_survives_the_round_trip() -> None:
    match = match_in_action_phase()
    act_pass(match)
    act_pass(match)

    rebuilt = match_from_document(to_match_document(match))

    assert to_match_document(rebuilt) == to_match_document(match)
    assert rebuilt.round_number == 2
