"""O índice de despertar contra Redis de verdade (§15).

O que está sob teste aqui só é observável com o Redis: o score que os scripts do
`MatchStore` mantêm junto do estado, o lease que impede dois workers de pegarem
o mesmo despertar, e o release que não sobrescreve uma gravação que chegou no
meio. Usa a base descartável do `conftest.py`.
"""

import asyncio

import pytest
from channels.layers import get_channel_layer
from redis.asyncio import Redis

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import PassAction, forfeit
from apps.game.match import Match, clock_wake_at
from apps.game.match.store import MatchStore
from apps.game.match.wake_queue import ClaimedWake, MatchWakeQueue
from apps.game.match_timers import MatchClockTicker
from apps.game.protocol import (
    ClockChange,
    PlayerChange,
    TurnExpiry,
    advance_match_clock,
    opening_match_clock,
)
from apps.game.tests.fake_finished_match_recorder import (
    FakeFinishedMatchRecorder,
)
from apps.game.tests.fake_combat_board import PLAYER_ONE, PLAYER_TWO, fake_combat_board
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.wall_clock import EpochMillis

KEY_PREFIX = "test:match"
NOW = EpochMillis(1_700_000_000_000)
LEASE_MS = 5_000
BATCH = 50

# Cem porque o que está sob teste é uma corrida: uma passada só provaria a ordem
# que o laço de eventos escolheu daquela vez.
RACE_REPETITIONS = 100


@pytest.fixture
def store(redis: Redis) -> MatchStore:
    return MatchStore(redis, key_prefix=KEY_PREFIX)


@pytest.fixture
def queue(redis: Redis) -> MatchWakeQueue:
    return MatchWakeQueue(redis, key_prefix=KEY_PREFIX)


def match_awaiting_mulligan() -> Match:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(NOW)

    return match


def match_with_a_turn() -> Match:
    match = fake_combat_board(catalog=mvp_catalog())
    advance_match_clock(match, NOW)

    return match


async def claim(queue: MatchWakeQueue, now: EpochMillis) -> list[ClaimedWake]:
    return await queue.claim_due(now, lease_ms=LEASE_MS, limit=BATCH)


# --- O score que o store mantém ----------------------------------------------


async def test_saving_a_match_schedules_its_wake_up(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()

    await store.save(match)

    deadline = clock_wake_at(match.clock)
    assert deadline is not None
    assert [one.match_id for one in await claim(queue, deadline)] == [match.match_id]


async def test_a_match_without_deadlines_is_not_in_the_index(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    await store.save(fake_started_match(PLAYER_ONE, PLAYER_TWO))

    assert await claim(queue, EpochMillis(NOW + 10_000_000)) == []


async def test_a_wake_up_that_has_not_come_is_not_claimed(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()
    await store.save(match)
    deadline = clock_wake_at(match.clock)
    assert deadline is not None

    assert await claim(queue, EpochMillis(deadline - 1)) == []


async def test_a_write_moves_the_score_to_the_new_deadline(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    """A vez nova reagenda o despertar dentro da mesma gravação.

    O passe troca a vez de mão, e é isso que move o score -- uma gravação que
    não troca a vez deixa o prazo onde está, que é a regra da §15.
    """
    match = match_with_a_turn()
    await store.save(match)
    later = EpochMillis(NOW + 20_000)

    await store.mutate(match.match_id, _pass_of(PLAYER_ONE, mvp_catalog(), later))

    assert await claim(queue, EpochMillis(later + 30_000 - 1)) == []
    assert [
        one.match_id for one in await claim(queue, EpochMillis(later + 30_000))
    ] == [match.match_id]


async def test_a_finished_match_leaves_the_index(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_with_a_turn()
    await store.save(match)

    await store.mutate(match.match_id, _finish)

    assert await claim(queue, EpochMillis(NOW + 10_000_000)) == []


def _finish(match: Match) -> None:
    """Desistência e relógio parado: o que importa aqui é o índice."""
    forfeit(match, PLAYER_TWO)
    advance_match_clock(match, NOW)


# --- O lease -----------------------------------------------------------------


async def test_a_claimed_wake_up_does_not_come_back_before_the_lease(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()
    await store.save(match)
    deadline = clock_wake_at(match.clock)
    assert deadline is not None
    await claim(queue, deadline)

    assert await claim(queue, EpochMillis(deadline + LEASE_MS - 1)) == []


async def test_a_claimed_wake_up_comes_back_after_the_lease(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    """O worker que morre depois de reivindicar atrasa o evento, não o perde."""
    match = match_awaiting_mulligan()
    await store.save(match)
    deadline = clock_wake_at(match.clock)
    assert deadline is not None
    await claim(queue, deadline)

    assert [
        one.match_id for one in await claim(queue, EpochMillis(deadline + LEASE_MS))
    ] == [match.match_id]


async def test_the_limit_is_respected(store: MatchStore, queue: MatchWakeQueue) -> None:
    for _ in range(3):
        await store.save(match_awaiting_mulligan())
    deadline = EpochMillis(NOW + 30_000)

    claimed = await queue.claim_due(deadline, lease_ms=LEASE_MS, limit=2)

    assert len(claimed) == 2


async def test_two_workers_never_claim_the_same_wake_up(
    store: MatchStore, redis: Redis
) -> None:
    """Dois tickers, uma partida: o despertar sai para um só."""
    match = match_awaiting_mulligan()
    await store.save(match)
    deadline = EpochMillis(NOW + 30_000)
    first = MatchWakeQueue(redis, key_prefix=KEY_PREFIX)
    second = MatchWakeQueue(redis, key_prefix=KEY_PREFIX)

    claims = await asyncio.gather(claim(first, deadline), claim(second, deadline))

    assert sorted(len(one) for one in claims) == [0, 1]


# --- Devolver ao índice ------------------------------------------------------


async def test_release_reschedules_the_wake_up(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()
    await store.save(match)
    deadline = EpochMillis(NOW + 30_000)
    claimed = (await claim(queue, deadline))[0]
    later = EpochMillis(deadline + 60_000)

    await queue.release(claimed, later)

    assert await claim(queue, EpochMillis(later - 1)) == []
    assert [one.match_id for one in await claim(queue, later)] == [match.match_id]


async def test_release_with_no_deadline_removes_the_member(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()
    await store.save(match)
    claimed = (await claim(queue, EpochMillis(NOW + 30_000)))[0]

    await queue.release(claimed, None)

    assert await claim(queue, EpochMillis(NOW + 10_000_000)) == []


async def test_release_does_not_overwrite_a_write_that_landed_in_between(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    """A gravação que chegou no meio já agendou o que vale."""
    match = match_awaiting_mulligan()
    await store.save(match)
    claimed = (await claim(queue, EpochMillis(NOW + 30_000)))[0]
    written_at = EpochMillis(NOW + 40_000)
    await store.mutate(
        match.match_id, lambda live: advance_match_clock(live, written_at)
    )

    await queue.release(claimed, EpochMillis(NOW + 10_000_000))

    assert [
        one.match_id for one in await claim(queue, EpochMillis(written_at + 30_000))
    ] == [match.match_id]


async def test_forget_takes_the_match_out_of_the_index(
    store: MatchStore, queue: MatchWakeQueue
) -> None:
    match = match_awaiting_mulligan()
    await store.save(match)

    await queue.forget(match.match_id)

    assert await claim(queue, EpochMillis(NOW + 10_000_000)) == []


# --- A corrida entre a jogada real e o estouro (SC-004) ----------------------


async def test_a_hundred_races_between_a_pass_and_its_expiry_lose_no_write(
    store: MatchStore,
) -> None:
    """Os dois chegam no mesmo instante, e exatamente um passe é gravado.

    Cem repetições porque o que está sob teste é uma corrida: uma passada só
    provaria a ordem que o laço de eventos escolheu daquela vez.
    """
    catalog = mvp_catalog()
    expiry_at = EpochMillis(NOW + 45_000)

    for _ in range(RACE_REPETITIONS):
        match = match_with_a_turn()
        await store.save(match)

        await asyncio.gather(
            store.mutate(match.match_id, _pass_of(PLAYER_ONE, catalog)),
            store.mutate(
                match.match_id,
                ClockChange(
                    TurnExpiry(1, PLAYER_ONE),
                    catalog=catalog,
                    randomness=ScriptedRandomSource(),
                    now=expiry_at,
                ),
                renews_expiry=False,
            ),
            return_exceptions=True,
        )

        live = await store.get(match.match_id)
        assert live is not None
        assert live.consecutive_passes == 1
        assert live.priority_user_id == PLAYER_TWO


def _pass_of(
    user_id: int, catalog: CardCatalog, now: EpochMillis = NOW
) -> PlayerChange:
    """O passe daquele jogador, como o socket o mandaria naquele instante."""
    return PlayerChange(
        PassAction(user_id),
        catalog=catalog,
        randomness=ScriptedRandomSource(),
        clock=FakeWallClock(now),
    )


# --- O ticker sobre o Redis de verdade (SC-012) ------------------------------


async def test_a_timeout_over_redis_does_not_postpone_the_expiry(
    store: MatchStore, queue: MatchWakeQueue, redis: Redis
) -> None:
    match = match_with_a_turn()
    await store.save(match)
    key = f"{KEY_PREFIX}:{match.match_id}"
    await redis.expire(key, 3600)
    clock = FakeWallClock(NOW)
    ticker = _ticker_over(store, queue, clock)

    await ticker.tick(clock.advance(45))

    live = await store.get(match.match_id)
    assert live is not None
    assert live.consecutive_passes == 1
    assert 0 < await redis.ttl(key) <= 3600


async def test_the_ticker_cleans_the_index_of_a_match_that_expired(
    store: MatchStore, queue: MatchWakeQueue, redis: Redis
) -> None:
    match = match_with_a_turn()
    await store.save(match)
    await redis.delete(f"{KEY_PREFIX}:{match.match_id}")
    clock = FakeWallClock(NOW)
    ticker = _ticker_over(store, queue, clock)

    await ticker.tick(clock.advance(45))

    assert await claim(queue, EpochMillis(NOW + 10_000_000)) == []


def _ticker_over(
    store: MatchStore, queue: MatchWakeQueue, clock: FakeWallClock
) -> MatchClockTicker:
    return MatchClockTicker(
        matches=store,
        wake_queue=queue,
        channel_layer=get_channel_layer(),
        catalog=mvp_catalog(),
        randomness=ScriptedRandomSource(),
        clock=clock,
        recorder=FakeFinishedMatchRecorder(),
    )
