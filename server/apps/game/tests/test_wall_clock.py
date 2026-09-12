"""O relógio do sistema e o relógio que o teste dita."""

import time

from apps.game.tests.fake_wall_clock import DEFAULT_START_MS, FakeWallClock
from apps.game.wall_clock import NANOS_PER_MILLI, SystemWallClock


def test_the_system_clock_sits_between_two_readings() -> None:
    """Milissegundos da época de verdade, e não um contador do processo."""
    before = time.time_ns() // NANOS_PER_MILLI

    now = SystemWallClock().now_ms()

    assert before <= now <= time.time_ns() // NANOS_PER_MILLI


def test_the_system_clock_moves_forward() -> None:
    clock = SystemWallClock()
    first = clock.now_ms()

    time.sleep(0.002)

    assert clock.now_ms() >= first


def test_the_fake_clock_starts_where_it_was_told() -> None:
    assert FakeWallClock(42).now_ms() == 42
    assert FakeWallClock().now_ms() == DEFAULT_START_MS


def test_advancing_adds_milliseconds_and_returns_the_new_instant() -> None:
    clock = FakeWallClock(1_000)

    assert clock.advance(1.5) == 2_500
    assert clock.now_ms() == 2_500


def test_advancing_accumulates() -> None:
    clock = FakeWallClock(0)

    clock.advance(30)
    clock.advance(15)

    assert clock.now_ms() == 45_000


def test_setting_puts_the_clock_on_an_exact_instant() -> None:
    clock = FakeWallClock()

    assert clock.set_ms(7) == 7
    assert clock.now_ms() == 7
