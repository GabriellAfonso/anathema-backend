"""O eco do ping, pelo socket de verdade, igual nos dois sockets.

Feature 013, FR-003 a FR-006 e SC-002. A matriz inteira de payloads está em
`test_heartbeat.py`, contra a regra pura. Aqui fica o que só o socket prova: que
o eco atravessa o JSON de ida e de volta intacto, que o servidor não acrescenta
chave nenhuma, e que payload estranho não vira recusa.

O cliente põe um marcador no ping -- o instante em que mandou, por exemplo -- e
mede a latência pelo que volta, sem o servidor saber o que o marcador significa.
"""

import pytest

from apps.game.tests.heartbeat_sockets import (
    SOCKET_KINDS,
    expect_pong,
    open_accepted_socket,
)

NESTED: dict[str, object] = {"a": {"b": [1, {"c": None}], "d": "x"}, "e": 2.5}


@pytest.mark.parametrize("kind", SOCKET_KINDS)
async def test_a_marker_comes_back_in_the_pong(kind: str) -> None:
    client = await open_accepted_socket(kind)

    await client.send_json_to(
        {"type": "ping", "payload": {"sent_at_ms": 1726000000000}}
    )

    await expect_pong(client, {"sent_at_ms": 1726000000000})
    await client.disconnect()


@pytest.mark.parametrize("kind", SOCKET_KINDS)
async def test_a_nested_object_comes_back_unchanged(kind: str) -> None:
    client = await open_accepted_socket(kind)

    await client.send_json_to({"type": "ping", "payload": NESTED})

    await expect_pong(client, NESTED)
    await client.disconnect()


@pytest.mark.parametrize("kind", SOCKET_KINDS)
@pytest.mark.parametrize(
    "message",
    [
        pytest.param({"type": "ping"}, id="absent"),
        pytest.param({"type": "ping", "payload": None}, id="null"),
        pytest.param({"type": "ping", "payload": 42}, id="integer"),
        pytest.param({"type": "ping", "payload": "x"}, id="text"),
        pytest.param({"type": "ping", "payload": True}, id="boolean"),
        pytest.param({"type": "ping", "payload": [1, 2]}, id="list"),
    ],
)
async def test_a_payload_that_is_not_an_object_is_answered_with_empty(
    kind: str, message: dict[str, object]
) -> None:
    client = await open_accepted_socket(kind)

    await client.send_json_to(message)

    await expect_pong(client, {})
    assert await client.nothing_received(), "o ping nunca é recusado pelo payload"
    await client.disconnect()


@pytest.mark.parametrize("kind", SOCKET_KINDS)
async def test_extra_fields_are_ignored_and_nothing_is_added(kind: str) -> None:
    client = await open_accepted_socket(kind)

    await client.send_json_to(
        {"type": "ping", "payload": {"k": 1}, "user_id": 99, "extra": [1]}
    )

    await expect_pong(client, {"k": 1})
    await client.disconnect()
