"""As três mudanças que entram no `mutate`, e o que cada uma grava.

A guarda do estouro roda **dentro** da mudança, sobre o estado que a tentativa
leu: é ela que faz o estouro atrasado não gravar nada, e é aqui que isso é
provado sem socket e sem Redis.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import PassAction
from apps.game.match import Match, MatchClock, TurnDeadline
from apps.game.protocol import (
    ClockChange,
    ClockEventNotDueError,
    MulliganCommand,
    MulliganExpiry,
    PlayerChange,
    TurnExpiry,
    TurnWarning,
    TurnWarningMark,
    opening_match_clock,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    PLAYER_ONE,
    PLAYER_TWO,
    fake_combat_board,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.match_snapshot import match_snapshot
from apps.game.wall_clock import EpochMillis

START_MS = EpochMillis(1_000_000)
WARNS_AT = EpochMillis(START_MS + 30_000)
EXPIRES_AT = EpochMillis(START_MS + 45_000)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def a_turn(*, turn_number: int = 1, warning_sent: bool = False) -> TurnDeadline:
    return TurnDeadline(
        turn_number=turn_number,
        holder_user_id=PLAYER_ONE,
        round_number=1,
        warns_at_ms=WARNS_AT,
        expires_at_ms=EXPIRES_AT,
        warning_sent=warning_sent,
    )


def waiting_board(catalog: CardCatalog, turn: TurnDeadline) -> Match:
    match = fake_combat_board(catalog=catalog, bank_one=(DARK_AGE,))
    match.clock = MatchClock(turn=turn)

    return match


# --- A jogada do socket ------------------------------------------------------


def test_the_player_change_records_the_state_before_it(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = waiting_board(catalog, a_turn())
    before = match_snapshot(match)
    change = PlayerChange(
        PassAction(PLAYER_ONE),
        catalog=catalog,
        randomness=source,
        clock=FakeWallClock(START_MS),
    )

    change(match)

    assert match_snapshot(change.recorded_before()) == before


def test_the_player_change_opens_the_next_turn(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = waiting_board(catalog, a_turn())
    clock = FakeWallClock(START_MS)
    clock.advance(20)

    PlayerChange(
        PassAction(PLAYER_ONE), catalog=catalog, randomness=source, clock=clock
    )(match)

    turn = match.clock.turn
    assert turn is not None
    assert (turn.turn_number, turn.holder_user_id) == (2, PLAYER_TWO)
    assert turn.expires_at_ms == START_MS + 20_000 + 45_000


def test_a_change_that_is_never_run_has_no_recorded_state(
    catalog: CardCatalog, source: RandomSource
) -> None:
    change = PlayerChange(
        PassAction(PLAYER_ONE),
        catalog=catalog,
        randomness=source,
        clock=FakeWallClock(START_MS),
    )

    with pytest.raises(RuntimeError):
        change.recorded_before()


# --- O estouro ---------------------------------------------------------------


def test_the_clock_change_plays_the_automatic_command(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = waiting_board(catalog, a_turn())
    change = ClockChange(
        TurnExpiry(1, PLAYER_ONE), catalog=catalog, randomness=source, now=EXPIRES_AT
    )

    change(match)

    assert change.applied_command() == PassAction(PLAYER_ONE)
    assert match.consecutive_passes == 1
    assert match.priority_user_id == PLAYER_TWO


def test_the_clock_change_opens_the_next_turn_from_the_expiry_instant(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = waiting_board(catalog, a_turn())

    ClockChange(
        TurnExpiry(1, PLAYER_ONE), catalog=catalog, randomness=source, now=EXPIRES_AT
    )(match)

    turn = match.clock.turn
    assert turn is not None
    assert turn.expires_at_ms == EXPIRES_AT + 45_000


def test_a_late_expiry_changes_nothing(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A vez já foi e voltou ao mesmo jogador: o estouro velho não a passa."""
    match = waiting_board(catalog, a_turn(turn_number=5))
    before = match_snapshot(match)
    change = ClockChange(
        TurnExpiry(4, PLAYER_ONE), catalog=catalog, randomness=source, now=EXPIRES_AT
    )

    with pytest.raises(ClockEventNotDueError):
        change(match)

    assert match_snapshot(match) == before


def test_an_expiry_before_the_deadline_changes_nothing(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = waiting_board(catalog, a_turn())
    before = match_snapshot(match)

    with pytest.raises(ClockEventNotDueError):
        ClockChange(
            TurnExpiry(1, PLAYER_ONE),
            catalog=catalog,
            randomness=source,
            now=EpochMillis(EXPIRES_AT - 1),
        )(match)

    assert match_snapshot(match) == before


def test_the_mulligan_expiry_answers_without_swapping(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(START_MS)
    hand = [card.card_instance_id for card in match.player(PLAYER_ONE).hand]
    change = ClockChange(
        MulliganExpiry(PLAYER_ONE),
        catalog=catalog,
        randomness=source,
        now=EpochMillis(START_MS + 30_000),
    )

    change(match)

    assert change.applied_command() == MulliganCommand(PLAYER_ONE, ())
    assert match.player(PLAYER_ONE).mulligan_taken is True
    assert [card.card_instance_id for card in match.player(PLAYER_ONE).hand] == hand


# --- A marca do aviso --------------------------------------------------------


def test_the_warning_mark_only_marks(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    TurnWarningMark(TurnWarning(1, PLAYER_ONE), WARNS_AT)(match)

    turn = match.clock.turn
    assert turn is not None
    assert turn.warning_sent is True
    assert (match.priority_user_id, match.consecutive_passes) == (PLAYER_ONE, 0)


def test_the_warning_mark_refuses_a_warning_already_sent(
    catalog: CardCatalog,
) -> None:
    match = waiting_board(catalog, a_turn(warning_sent=True))
    before = match_snapshot(match)

    with pytest.raises(ClockEventNotDueError):
        TurnWarningMark(TurnWarning(1, PLAYER_ONE), WARNS_AT)(match)

    assert match_snapshot(match) == before
