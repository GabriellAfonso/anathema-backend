"""O relógio gravado na partida: qual é o próximo despertar, e a ida e volta.

O despertar é o score do índice do `MatchStore`, e a ida e volta é o que faz o
prazo sobreviver ao worker que o armou -- as duas coisas que a §15 exige do
estado do relógio.
"""

import json

from apps.game.match import (
    IDLE_MATCH_CLOCK,
    MatchClock,
    MatchDocument,
    TurnDeadline,
    clock_wake_at,
    match_from_document,
    to_match_document,
)
from apps.game.tests.fake_match_state import fake_new_match
from apps.game.wall_clock import EpochMillis

NOW = EpochMillis(1_700_000_000_000)
WARNS_AT = EpochMillis(NOW + 30_000)
EXPIRES_AT = EpochMillis(NOW + 45_000)
MULLIGAN_EXPIRES_AT = EpochMillis(NOW + 30_000)


def a_turn(*, warning_sent: bool = False) -> TurnDeadline:
    return TurnDeadline(
        turn_number=3,
        holder_user_id=7,
        round_number=2,
        warns_at_ms=WARNS_AT,
        expires_at_ms=EXPIRES_AT,
        warning_sent=warning_sent,
    )


def round_trip(clock: MatchClock) -> MatchClock:
    """O relógio depois de passar pelo JSON, como o Redis o devolve."""
    match = fake_new_match()
    match.clock = clock
    document: MatchDocument = json.loads(json.dumps(to_match_document(match)))

    return match_from_document(document).clock


# --- Qual é o próximo despertar ----------------------------------------------


def test_a_match_without_deadlines_never_wakes() -> None:
    assert clock_wake_at(IDLE_MATCH_CLOCK) is None


def test_the_mulligan_deadline_is_the_wake_up() -> None:
    clock = MatchClock(mulligan_expires_at_ms=MULLIGAN_EXPIRES_AT)

    assert clock_wake_at(clock) == MULLIGAN_EXPIRES_AT


def test_a_turn_wakes_at_the_warning_first() -> None:
    assert clock_wake_at(MatchClock(turn=a_turn())) == WARNS_AT


def test_a_warned_turn_wakes_at_the_expiry() -> None:
    """Sem a marca, toda gravação traria o aviso de volta."""
    assert clock_wake_at(MatchClock(turn=a_turn(warning_sent=True))) == EXPIRES_AT


# --- Ida e volta pelo Redis --------------------------------------------------


def test_a_match_without_deadlines_survives_the_round_trip() -> None:
    assert round_trip(IDLE_MATCH_CLOCK) == IDLE_MATCH_CLOCK


def test_the_mulligan_deadline_survives_the_round_trip() -> None:
    clock = MatchClock(mulligan_expires_at_ms=MULLIGAN_EXPIRES_AT)

    assert round_trip(clock) == clock


def test_the_turn_survives_the_round_trip_field_by_field() -> None:
    clock = MatchClock(turn=a_turn())

    assert round_trip(clock) == clock


def test_the_warning_mark_survives_the_round_trip() -> None:
    clock = MatchClock(turn=a_turn(warning_sent=True))

    assert round_trip(clock).turn == a_turn(warning_sent=True)


def test_the_clock_travels_as_plain_json_values() -> None:
    """Instante é `int` no documento: nada de objeto de data a converter."""
    match = fake_new_match()
    match.clock = MatchClock(turn=a_turn())

    document = to_match_document(match)

    assert document["clock"]["turn"] == {
        "turn_number": 3,
        "holder_user_id": 7,
        "round_number": 2,
        "warns_at_ms": WARNS_AT,
        "expires_at_ms": EXPIRES_AT,
        "warning_sent": False,
    }
    assert document["clock"]["mulligan_expires_at_ms"] is None
