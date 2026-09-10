"""A alternância da §5: passar, a troca de prioridade e a saída da fase.

O teste central deste arquivo é
`test_a_unit_played_between_two_passes_does_not_close_the_round`: é ele que pega
uma contagem de passes que some em vez de contar **consecutivos**. Com a soma
simples a rodada fecharia no meio de uma troca de jogadas, e o placar de energia
de ninguém acusaria.
"""

from apps.game.cards import CardId, Unit
from apps.game.engine import PassAction, PlayUnitAction, submit_action
from apps.game.engine.round_cycle import CONSECUTIVE_PASSES_TO_EXIT
from apps.game.match import Match, MatchPhase
from apps.game.randomness import RandomSource
from apps.game.tests.fake_card_catalog import FakeCardCatalog
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource

CHEAP_UNIT = Unit(
    card_id=CardId(2), name="CHEAP", energy=1, attack=3, health=4, image="cheap_card"
)
CATALOG = FakeCardCatalog([CHEAP_UNIT])

DECK_CARD_IDS = [31, 32, 33, 34, 35, 36]


def match_in_action_phase(round_number: int = 1) -> Match:
    """Partida na Fase de Ação com deck, mão jogável e energia dos dois lados."""
    match = fake_new_match()

    match.round_number = round_number
    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = PLAYER_ONE
    match.phase = MatchPhase.ACTION

    for player in match.players:
        player.deck = fake_cards(match, DECK_CARD_IDS)
        player.hand = fake_cards(match, [CHEAP_UNIT.card_id, CHEAP_UNIT.card_id])
        player.energy_max = round_number
        player.energy_current = round_number

    return match


def source() -> RandomSource:
    return ScriptedRandomSource()


def act_pass(match: Match) -> None:
    assert match.priority_user_id is not None
    submit_action(
        match,
        PassAction(actor_user_id=match.priority_user_id),
        catalog=CATALOG,
        randomness=source(),
    )


def act_play(match: Match) -> None:
    assert match.priority_user_id is not None
    actor = match.player(match.priority_user_id)
    submit_action(
        match,
        PlayUnitAction(
            actor_user_id=actor.user_id,
            card_instance_id=actor.hand[0].card_instance_id,
        ),
        catalog=CATALOG,
        randomness=source(),
    )


# --- Passar ------------------------------------------------------------------


def test_passing_raises_the_consecutive_pass_count() -> None:
    match = match_in_action_phase()

    act_pass(match)

    assert match.consecutive_passes == 1


def test_passing_hands_the_priority_to_the_opponent() -> None:
    match = match_in_action_phase()

    act_pass(match)

    assert match.priority_user_id == PLAYER_TWO


def test_one_pass_leaves_the_match_in_the_action_phase() -> None:
    match = match_in_action_phase()

    act_pass(match)

    assert match.phase is MatchPhase.ACTION


def test_passing_touches_no_card_zone_energy_or_nexus() -> None:
    match = match_in_action_phase()
    zones = [
        (list(p.deck), list(p.hand), list(p.bank), list(p.graveyard))
        for p in match.players
    ]
    energies = [(p.energy_max, p.energy_current, p.nexus) for p in match.players]

    act_pass(match)

    assert [
        (list(p.deck), list(p.hand), list(p.bank), list(p.graveyard))
        for p in match.players
    ] == zones
    assert [
        (p.energy_max, p.energy_current, p.nexus) for p in match.players
    ] == energies


# --- A alternância -----------------------------------------------------------


def test_nobody_chains_two_actions_in_a_row() -> None:
    """A prioridade troca a cada ação, então dois passes são de dois jogadores.

    A segunda ação é uma jogada, e não um passe, de propósito: dois passes
    fechariam a rodada, e a prioridade que o teste leria seria a que o Upkeep
    repôs -- não a que a alternância entregou.
    """
    match = match_in_action_phase()

    act_pass(match)
    after_the_pass = match.priority_user_id
    act_play(match)

    assert after_the_pass == PLAYER_TWO
    assert match.priority_user_id == PLAYER_ONE
    assert match.round_number == 1


def test_playing_a_unit_also_hands_the_priority_over() -> None:
    match = match_in_action_phase()

    act_play(match)

    assert match.priority_user_id == PLAYER_TWO


def test_two_consecutive_passes_close_the_round() -> None:
    match = match_in_action_phase(round_number=1)

    act_pass(match)
    act_pass(match)

    assert match.round_number == 2
    assert match.phase is MatchPhase.ACTION


def test_a_unit_played_between_two_passes_does_not_close_the_round() -> None:
    """Passar, jogar, passar, passar: a rodada fecha só no último passe."""
    match = match_in_action_phase(round_number=1)

    act_pass(match)
    act_play(match)
    assert match.round_number == 1

    act_pass(match)
    assert match.round_number == 1

    act_pass(match)
    assert match.round_number == 2


def test_playing_a_unit_after_one_pass_resets_the_count() -> None:
    match = match_in_action_phase()

    act_pass(match)
    act_play(match)

    assert match.consecutive_passes == 0


def test_the_exit_needs_exactly_two_consecutive_passes() -> None:
    match = match_in_action_phase(round_number=1)

    for _ in range(CONSECUTIVE_PASSES_TO_EXIT - 1):
        act_pass(match)

    assert match.round_number == 1


def test_players_can_alternate_units_until_a_bank_fills_up() -> None:
    """Seis jogadas de um lado enchem o banco; a sétima é recusada."""
    match = match_in_action_phase(round_number=6)
    for player in match.players:
        player.hand = fake_cards(match, [CHEAP_UNIT.card_id] * 7)

    for _ in range(12):
        act_play(match)

    assert len(match.players[0].bank) == 6
    assert len(match.players[1].bank) == 6
