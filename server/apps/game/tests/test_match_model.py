"""Match owns the rule of who is allowed to talk to it."""

import json

import pytest

from apps.game.match.models import Match
from apps.game.tests.fake_player_data import fake_player_data

PLAYER_ONE = 7
PLAYER_TWO = 8


@pytest.fixture
def match() -> Match:
    return Match.start(fake_player_data(PLAYER_ONE), fake_player_data(PLAYER_TWO))


def test_first_player_is_a_participant(match: Match) -> None:
    assert match.has_player(PLAYER_ONE)


def test_second_player_is_a_participant(match: Match) -> None:
    assert match.has_player(PLAYER_TWO)


def test_outsider_is_not_a_participant(match: Match) -> None:
    assert not match.has_player(99)


def test_missing_user_id_is_not_a_participant(match: Match) -> None:
    """A socket with no authenticated user must never pass the gate."""
    assert not match.has_player(None)


def test_as_dict_round_trips_through_from_dict(match: Match) -> None:
    """What the store writes to Redis must rebuild the same match."""
    rebuilt = Match.from_dict(json.loads(json.dumps(match.as_dict())))

    assert rebuilt.as_dict() == match.as_dict()


def test_from_dict_restores_integer_hand_keys(match: Match) -> None:
    """JSON keys come back as strings; a lookup by User.id would miss."""
    rebuilt = Match.from_dict(json.loads(json.dumps(match.as_dict())))

    assert rebuilt.hands == {PLAYER_ONE: [], PLAYER_TWO: []}
