"""O ping não abre exceção nos gates, e o que não é ping continua recusado.

Feature 013, FR-012 a FR-015 e research D3. Os gates aceitam o socket antes de
recusar, para o motivo chegar ao cliente, e fecham logo depois. Um ping que
chegue ali não recebe resposta nenhuma: frame depois do close é o
`RuntimeError` que `test_base_consumer_lifecycle.py` registra.

Parte destes testes já passava antes da feature e fica como guarda de regressão:
o gate da partida já ignorava mensagens, e `pong`, `Ping` e frame malformado já
eram recusados. O que falhava era o gate de autenticação do socket de
matchmaking: o ping caía no roteamento `handle_<type>` e saía
`unknown_message_type` **depois** do close.
"""

import pytest

from apps.game.consumers.base import UNAUTHENTICATED
from apps.game.consumers.match import (
    MATCH_ID_MISSING,
    MATCH_NOT_FOUND,
    NOT_A_PARTICIPANT,
    MatchConsumer,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_users import FakeAnonymousUser, FakePlayerUser
from apps.game.tests.heartbeat_sockets import SOCKET_KINDS, open_accepted_socket
from apps.game.tests.match_sockets import Frame, next_refusal_code, saved
from apps.game.tests.matchmaking_sockets import open_matchmaking_socket
from apps.game.tests.websocket_test_client import WebsocketTestClient

PLAYER_ONE = 7
PLAYER_TWO = 8
OUTSIDER = 99
PING: Frame = {"type": "ping"}
AUTH_DENIED: Frame = {
    "type": "auth_denied",
    "payload": {
        "error": "authentication required: FakeAnonymousUser is not authenticated"
    },
}


async def unopened_match_socket(
    matches: FakeMatchStore,
    user: FakePlayerUser | FakeAnonymousUser,
    query_string: str,
) -> WebsocketTestClient:
    """Socket de partida conectado, com os frames do gate ainda por ler."""
    client = WebsocketTestClient(
        MatchConsumer.as_asgi(matches=matches),
        "/ws/match/",
        query_string=query_string,
    )
    client.scope["user"] = user
    await client.connect()

    return client


async def expect_closed_without_reply(
    client: WebsocketTestClient, frame_type: str, close_code: int
) -> Frame:
    """O motivo do gate, o close code, e mais nada -- nem o pong."""
    frame = await client.receive_json_from()

    assert frame["type"] == frame_type, frame
    assert await client.receive_close_code() == close_code
    assert await client.nothing_received()

    await client.disconnect()

    return frame


# --- Gate de autenticação ------------------------------------------------------


async def test_a_ping_on_a_matchmaking_socket_denied_by_auth_gets_no_reply() -> None:
    client = await open_matchmaking_socket(
        FakeAnonymousUser(), queue=FakeMatchmakingQueue(), decks=FakePlayerDeckSource()
    )

    await client.send_json_to(PING)

    frame = await expect_closed_without_reply(client, "auth_denied", UNAUTHENTICATED)
    assert frame == AUTH_DENIED


async def test_a_ping_on_a_match_socket_denied_by_auth_gets_no_reply() -> None:
    client = await unopened_match_socket(
        FakeMatchStore(), FakeAnonymousUser(), "matchId=any"
    )

    await client.send_json_to(PING)

    frame = await expect_closed_without_reply(client, "auth_denied", UNAUTHENTICATED)
    assert frame == AUTH_DENIED


# --- Gate da partida -----------------------------------------------------------


@pytest.mark.parametrize(
    ("user_id", "query_string", "close_code"),
    [
        pytest.param(PLAYER_ONE, "", MATCH_ID_MISSING, id="no-match-id"),
        pytest.param(
            PLAYER_ONE, "matchId=no-such-match", MATCH_NOT_FOUND, id="unknown"
        ),
        pytest.param(OUTSIDER, None, NOT_A_PARTICIPANT, id="outsider"),
    ],
)
async def test_a_ping_on_a_socket_denied_by_the_match_gate_gets_no_reply(
    user_id: int, query_string: str | None, close_code: int
) -> None:
    """`None` no `query_string` é a partida de verdade, que o intruso não joga."""
    matches = FakeMatchStore()
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    query = f"matchId={match.match_id}" if query_string is None else query_string
    client = await unopened_match_socket(matches, FakePlayerUser(user_id), query)

    await client.send_json_to(PING)

    await expect_closed_without_reply(client, "match_denied", close_code)


# --- O que não é ping continua recusado ---------------------------------------


@pytest.mark.parametrize("kind", SOCKET_KINDS)
@pytest.mark.parametrize("message_type", ["pong", "Ping", "PING", " ping"])
async def test_what_only_looks_like_a_ping_is_an_unknown_type(
    kind: str, message_type: str
) -> None:
    client = await open_accepted_socket(kind)

    await client.send_json_to({"type": message_type})

    assert await next_refusal_code(client) == "unknown_message_type"
    await client.disconnect()


@pytest.mark.parametrize("kind", SOCKET_KINDS)
async def test_the_word_ping_outside_json_is_still_malformed(kind: str) -> None:
    client = await open_accepted_socket(kind)

    await client.send_raw_text("ping")

    assert await next_refusal_code(client) == "malformed_message"
    await client.disconnect()


@pytest.mark.parametrize("kind", SOCKET_KINDS)
async def test_a_binary_ping_is_still_malformed(kind: str) -> None:
    client = await open_accepted_socket(kind)

    await client.send_bytes(b'{"type": "ping"}')

    assert await next_refusal_code(client) == "malformed_message"
    await client.disconnect()
