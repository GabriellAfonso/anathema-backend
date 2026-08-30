"""MatchmakingQueue runs against a real Redis: the property under test is that
the Lua pairing step is indivisible, and only the real server can show that.
Uses a throwaway database so it never touches app data.
"""

import asyncio

import pytest

from redis.asyncio import Redis

from apps.game.matchmaking.queue import MatchmakingQueue

from apps.game.matchmaking.queue import MatchmakingQueue


@pytest.fixture
def queue(redis: Redis) -> MatchmakingQueue:
    return MatchmakingQueue(redis, key="test:matchmaking:queue")


async def test_first_player_waits(queue: MatchmakingQueue) -> None:
    assert await queue.join(1) is None
    assert await queue.size() == 1


async def test_second_player_completes_the_pair(queue: MatchmakingQueue) -> None:
    await queue.join(1)

    assert await queue.join(2) == (1, 2)


async def test_pair_leaves_the_queue(queue: MatchmakingQueue) -> None:
    await queue.join(1)
    await queue.join(2)

    assert await queue.size() == 0


async def test_pairing_is_first_in_first_out(queue: MatchmakingQueue) -> None:
    await queue.join(1)
    await queue.join(2)
    await queue.join(3)

    assert await queue.join(4) == (3, 4)


async def test_rejoining_does_not_duplicate_the_player(queue: MatchmakingQueue) -> None:
    """A reconnect must not leave the player in the list twice -- otherwise the
    next join pairs them against themselves."""
    await queue.join(1)

    assert await queue.join(1) is None
    assert await queue.size() == 1


async def test_leave_removes_the_player(queue: MatchmakingQueue) -> None:
    await queue.join(1)

    await queue.leave(1)

    assert await queue.size() == 0
    assert await queue.join(2) is None


async def test_concurrent_joins_pair_everyone_exactly_once(queue: MatchmakingQueue) -> None:
    """The race the Lua script exists to close: with a read-modify-write the
    interleaving either drops a player or hands the same player to two
    matches."""
    players = list(range(1, 101))

    results = await asyncio.gather(*(queue.join(p) for p in players))

    pairs = [r for r in results if r is not None]
    matched = [player for pair in pairs for player in pair]

    assert len(pairs) == 50
    assert sorted(matched) == players
    assert await queue.size() == 0
