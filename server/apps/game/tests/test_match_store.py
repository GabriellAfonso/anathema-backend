"""MatchStore runs against a real Redis: what is under test is that a match
survives the round trip through JSON and comes back usable from another
process. Uses a throwaway database so it never touches app data.
"""

import pytest
from redis.asyncio import Redis

from apps.game.match.models import Match
from apps.game.match.store import MATCH_TTL_SECONDS, MatchStore
from apps.game.tests.fake_player_data import fake_player_data

PLAYER_ONE = fake_player_data(7, "one")
PLAYER_TWO = fake_player_data(9, "two")


@pytest.fixture
def store(redis: Redis) -> MatchStore:
    return MatchStore(redis, key_prefix="test:match")


async def stored_match(store: MatchStore, match: Match) -> Match:
    """Recarrega a partida, falhando o teste se ela sumiu do Redis."""
    reloaded = await store.get(match.match_id)
    assert reloaded is not None

    return reloaded


async def test_created_match_is_readable_again(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).match_id == match.match_id


async def test_unknown_match_is_none(store: MatchStore) -> None:
    assert await store.get("no-such-match") is None


async def test_players_survive_the_round_trip(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).players == [PLAYER_ONE, PLAYER_TWO]


async def test_participants_are_recognised_after_the_round_trip(
    store: MatchStore,
) -> None:
    """The gate in MatchConsumer reads this off a match it loaded from Redis."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    reloaded = await stored_match(store, match)

    assert reloaded.has_player(7)
    assert not reloaded.has_player(99)


async def test_hands_keep_integer_user_ids(store: MatchStore) -> None:
    """JSON stringifies object keys, so `hands[7]` would raise KeyError."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).hands == {7: [], 9: []}


async def test_state_lookup_works_after_the_round_trip(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).get_state_for_player(7) == {
        "your_hand": [],
        "board": {},
        "turn": 7,
    }


async def test_saved_state_replaces_the_stored_one(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)
    match.turn = 9

    await store.save(match)

    assert (await stored_match(store, match)).turn == 9


async def test_match_expires_so_abandoned_games_do_not_pile_up(
    store: MatchStore, redis: Redis
) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert await redis.ttl(f"test:match:{match.match_id}") == MATCH_TTL_SECONDS
