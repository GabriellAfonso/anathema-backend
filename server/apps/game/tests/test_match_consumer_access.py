"""MatchConsumer must only let a participant into the match it asks for.

Before this gate any authenticated socket could open any `matchId`, and a
missing or unknown id left `self.match` as None for every later handler.
"""

import pytest

from apps.game.consumers.match import (
    MATCH_ID_MISSING,
    MATCH_NOT_FOUND,
    NOT_A_PARTICIPANT,
    MatchConsumer,
)
from apps.game.match.models import Match
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_player_data import fake_player_data
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.websocket_test_client import WebsocketTestClient

PLAYER_ONE = 7
PLAYER_TWO = 8
OUTSIDER = 99


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore()


@pytest.fixture
async def match(matches: FakeMatchStore) -> Match:
    return await matches.create(
        fake_player_data(PLAYER_ONE, "one"),
        fake_player_data(PLAYER_TWO, "two"),
    )


def connect_as(matches: FakeMatchStore, user_id: int, match_id: str | None) -> WebsocketTestClient:
    query_string = f"matchId={match_id}" if match_id is not None else ""
    client = WebsocketTestClient(
        MatchConsumer.as_asgi(matches=matches), "/ws/match/", query_string=query_string
    )
    client.scope["user"] = FakePlayerUser(user_id)
    return client


async def test_participant_gets_match_start(matches: FakeMatchStore, match: Match) -> None:
    client = connect_as(matches, PLAYER_ONE, match.match_id)
    await client.connect()

    assert await client.receive_json_from() == {
        "type": "match_start",
        "payload": {},
    }
    await client.disconnect()


async def test_both_players_get_in(matches: FakeMatchStore, match: Match) -> None:
    client = connect_as(matches, PLAYER_TWO, match.match_id)
    await client.connect()

    assert (await client.receive_json_from())["type"] == "match_start"
    await client.disconnect()


async def test_outsider_is_closed_with_not_a_participant(matches: FakeMatchStore, match: Match) -> None:
    client = connect_as(matches, OUTSIDER, match.match_id)
    await client.connect()

    await client.receive_json_from()

    assert await client.receive_close_code() == NOT_A_PARTICIPANT
    await client.disconnect()


async def test_outsider_is_told_why(matches: FakeMatchStore, match: Match) -> None:
    client = connect_as(matches, OUTSIDER, match.match_id)
    await client.connect()

    assert await client.receive_json_from() == {
        "type": "match_denied",
        "payload": {
            "error": f"user {OUTSIDER} does not play match '{match.match_id}'",
        },
    }
    await client.disconnect()


async def test_unknown_match_is_closed_with_not_found(matches: FakeMatchStore) -> None:
    client = connect_as(matches, PLAYER_ONE, "no-such-match")
    await client.connect()

    await client.receive_json_from()

    assert await client.receive_close_code() == MATCH_NOT_FOUND
    await client.disconnect()


async def test_missing_match_id_is_closed_with_bad_request(matches: FakeMatchStore) -> None:
    client = connect_as(matches, PLAYER_ONE, None)
    await client.connect()

    await client.receive_json_from()

    assert await client.receive_close_code() == MATCH_ID_MISSING
    await client.disconnect()
