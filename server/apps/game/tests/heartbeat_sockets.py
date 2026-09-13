"""Um socket aceito de qualquer um dos dois tipos, para os testes que valem igual
nos dois (feature 013: o ping tem o mesmo comportamento em `ws/match/` e em
`ws/matchmaking/`).

Não é fake: monta, sobre os fakes de sempre, o socket que `match_sockets.py` e
`matchmaking_sockets.py` já sabem abrir. Os testes parametrizam por
`SOCKET_KINDS` em vez de repetir cada caso duas vezes.
"""

from apps.game.protocol import PING, PONG
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.match_sockets import Frame, open_match_socket, saved
from apps.game.tests.matchmaking_sockets import open_matchmaking_socket
from apps.game.tests.websocket_test_client import WebsocketTestClient

MATCH_SOCKET = "match"
MATCHMAKING_SOCKET = "matchmaking"
SOCKET_KINDS = (MATCH_SOCKET, MATCHMAKING_SOCKET)

PLAYER_ONE = 7
PLAYER_TWO = 8


async def open_accepted_socket(kind: str) -> WebsocketTestClient:
    """O socket aceito daquele tipo, sem frame pendente para ler.

    O de partida já consumiu o `match_start`; o de matchmaking não manda nada ao
    conectar.

    >>> client = await open_accepted_socket("match")
    """
    if kind == MATCHMAKING_SOCKET:
        return await open_matchmaking_socket(
            FakePlayerUser(PLAYER_ONE),
            queue=FakeMatchmakingQueue(),
            decks=FakePlayerDeckSource(),
        )

    if kind != MATCH_SOCKET:
        raise ValueError(f"socket kind is {kind!r}: expected one of {SOCKET_KINDS}")

    matches = FakeMatchStore()
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    client, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)

    return client


async def expect_pong(client: WebsocketTestClient, payload: Frame) -> None:
    """O próximo frame deste socket é o pong com exatamente aquele payload.

    Compara o frame inteiro: uma chave que o servidor acrescentasse ao pong
    (FR-006) reprovaria aqui.

    >>> await expect_pong(client, {"n": 1})
    """
    assert await client.receive_json_from() == {"type": PONG, "payload": payload}


async def expect_ping_burst_answered(client: WebsocketTestClient, count: int) -> None:
    """Manda `count` pings seguidos e exige `count` pongs, na mesma ordem (SC-001).

    Manda todos antes de ler o primeiro, para os pings se enfileirarem no
    consumer como uma rajada de verdade.

    >>> await expect_ping_burst_answered(client, 50)
    """
    for index in range(count):
        await client.send_json_to({"type": PING, "payload": {"n": index}})

    for index in range(count):
        await expect_pong(client, {"n": index})


__all__ = [
    "SOCKET_KINDS",
    "open_accepted_socket",
    "expect_pong",
    "expect_ping_burst_answered",
]
