"""A regra do ping, sem socket: o que é ping, e o que volta no pong.

A matriz inteira fica aqui porque a regra é pura. Os testes de socket
(`test_heartbeat_echo.py`, `test_match_consumer_heartbeat.py`,
`test_matchmaking_heartbeat.py`, `test_heartbeat_gates.py`) só provam o que
depende de socket.
"""

import pytest

from apps.game.protocol import PING, PONG, is_ping, pong_payload


def test_the_two_words_are_the_contract() -> None:
    """O cliente Unity casa com estes textos (contracts/heartbeat_messages.md)."""
    assert (PING, PONG) == ("ping", "pong")


@pytest.mark.parametrize(
    "content",
    [
        pytest.param({"type": "ping"}, id="bare"),
        pytest.param({"type": "ping", "payload": {"n": 1}}, id="with-payload"),
        pytest.param(
            {"type": "ping", "payload": 42, "extra": 1}, id="odd-payload-and-extra"
        ),
    ],
)
def test_a_ping_is_recognized_by_its_type_alone(content: dict[str, object]) -> None:
    assert is_ping(content)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param({"type": "pong"}, id="pong"),
        pytest.param({"type": "Ping"}, id="capitalized"),
        pytest.param({"type": "PING"}, id="upper"),
        pytest.param({"type": " ping"}, id="leading-space"),
        pytest.param({"type": "ping "}, id="trailing-space"),
        pytest.param({"payload": {}}, id="no-type"),
        pytest.param({"type": None}, id="null-type"),
        pytest.param({"type": 1}, id="number-type"),
    ],
)
def test_anything_else_is_not_a_ping(content: dict[str, object]) -> None:
    assert not is_ping(content)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"sent_at_ms": 1726000000000}, id="marker"),
        pytest.param({"a": {"b": [1, {"c": None}]}}, id="nested"),
        pytest.param({}, id="empty-object"),
    ],
)
def test_an_object_payload_comes_back_unchanged(payload: dict[str, object]) -> None:
    assert pong_payload({"type": PING, "payload": payload}) == payload


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(None, id="null"),
        pytest.param(42, id="integer"),
        pytest.param(4.2, id="float"),
        pytest.param("x", id="text"),
        pytest.param(True, id="boolean"),
        pytest.param([1, 2], id="list"),
    ],
)
def test_a_payload_that_is_not_an_object_becomes_empty(payload: object) -> None:
    assert pong_payload({"type": PING, "payload": payload}) == {}


def test_a_missing_payload_becomes_empty() -> None:
    assert pong_payload({"type": PING}) == {}
