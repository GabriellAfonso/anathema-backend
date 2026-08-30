"""The auth gate in BaseConsumer.connect must stop the subclass cold.

Before the on_connect/on_disconnect hooks, a rejected socket kept running the
subclass body: group_add on a dead channel, then a send that uvicorn answers
with `RuntimeError: Unexpected ASGI message 'websocket.send', after sending
'websocket.close'.`
"""

import pytest
from channels.layers import get_channel_layer

from apps.game.consumers.base import BaseConsumer
from apps.game.tests.fake_users import FakeAnonymousUser, FakePlayerUser
from apps.game.tests.websocket_test_client import WebsocketTestClient


class RecordingConsumer(BaseConsumer):
    """Appends every hook it runs to a list the test owns."""

    group_prefix = "test"

    def __init__(
        self, *args: object, calls: list[str] | None = None, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.calls = calls if calls is not None else []

    async def on_connect(self) -> None:
        self.calls.append("on_connect")

    async def on_disconnect(self, code: int) -> None:
        self.calls.append("on_disconnect")


@pytest.fixture
def calls() -> list[str]:
    return []


def connect_as(user: FakePlayerUser | FakeAnonymousUser, calls: list[str]) -> WebsocketTestClient:
    client = WebsocketTestClient(
        RecordingConsumer.as_asgi(calls=calls), "/ws/test/"
    )
    client.scope["user"] = user
    return client


async def test_authenticated_socket_is_accepted(calls: list[str]) -> None:
    client = connect_as(FakePlayerUser(7), calls)

    connected, _ = await client.connect()

    assert connected
    await client.disconnect()


async def test_authenticated_socket_runs_on_connect(calls: list[str]) -> None:
    client = connect_as(FakePlayerUser(7), calls)

    await client.connect()

    assert calls == ["on_connect"]
    await client.disconnect()


async def test_unauthenticated_socket_is_rejected_with_4001(calls: list[str]) -> None:
    client = connect_as(FakeAnonymousUser(), calls)

    connected, code = await client.connect()

    assert not connected
    assert code == 4001
    await client.disconnect()


async def test_missing_user_is_rejected(calls: list[str]) -> None:
    """JWTAuthMiddleware always sets a user, but a raw ASGI scope may not."""
    client = WebsocketTestClient(
        RecordingConsumer.as_asgi(calls=calls), "/ws/test/"
    )

    connected, code = await client.connect()

    assert not connected
    assert code == 4001
    await client.disconnect()


async def test_rejected_socket_never_runs_on_connect(calls: list[str]) -> None:
    """The regression: the subclass body used to run against a closed socket."""
    client = connect_as(FakeAnonymousUser(), calls)

    await client.connect()
    await client.disconnect()

    assert calls == []


async def test_rejected_socket_never_runs_on_disconnect(calls: list[str]) -> None:
    """Cleanup must not undo group membership the socket never had."""
    client = connect_as(FakeAnonymousUser(), calls)

    await client.connect()
    await client.disconnect()

    assert "on_disconnect" not in calls


async def test_accepted_socket_runs_on_disconnect(calls: list[str]) -> None:
    client = connect_as(FakePlayerUser(7), calls)
    await client.connect()

    await client.disconnect()

    assert calls == ["on_connect", "on_disconnect"]


async def test_accepted_socket_joins_its_per_user_group(calls: list[str]) -> None:
    client = connect_as(FakePlayerUser(7), calls)
    await client.connect()

    await get_channel_layer().group_send(
        RecordingConsumer.user_group(7),
        {"type": "client_event", "event": "ping", "payload": {}},
    )

    assert await client.receive_json_from() == {
        "type": "ping",
        "payload": {},
    }
    await client.disconnect()


async def test_group_payload_arrives_as_an_object(calls: list[str]) -> None:
    """Regression: the envelope used to json.dumps the payload, so the client
    had to parse the frame and then parse the payload string again."""
    client = connect_as(FakePlayerUser(7), calls)
    await client.connect()

    await get_channel_layer().group_send(
        RecordingConsumer.user_group(7),
        {
            "type": "client_event",
            "event": "match_found",
            "payload": {"match_id": "m-1", "opponent": {"nickname": "two"}},
        },
    )

    frame = await client.receive_json_from()

    assert frame["payload"] == {"match_id": "m-1", "opponent": {"nickname": "two"}}
    await client.disconnect()


async def test_disconnect_leaves_the_per_user_group(calls: list[str]) -> None:
    client = connect_as(FakePlayerUser(7), calls)
    await client.connect()
    await client.disconnect()

    layer = get_channel_layer()

    assert layer.groups.get(RecordingConsumer.user_group(7), {}) == {}
