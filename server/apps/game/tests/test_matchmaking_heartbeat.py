"""O ping no socket de matchmaking: pong em todo momento, e a fila intocada.

Feature 013, FR-008, SC-005 e research D9. O cliente liga o mesmo detector de
queda nos dois sockets; se a fila recusasse o ping, o jogador receberia uma
recusa a cada 10s durante toda a espera, e o detector nunca armaria ali.

Tudo passa pelo `connect` e pelo `receive` de verdade, com a fila e os decks em
memória. Nenhum teste chega a parear dois jogadores: o pareamento chama
`profile_for`, que toca o banco, e este pacote não toca banco. O `match_found`
chega pelo channel layer, que é como ele chega de verdade ao socket que não fechou
o par.
"""

import pytest
from channels.layers import get_channel_layer

from apps.game.cards import Deck, get_card_catalog, starter_deck
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.tests.fake_chosen_deck import fake_chosen_deck
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.heartbeat_sockets import (
    expect_ping_burst_answered,
    expect_pong,
)
from apps.game.tests.match_sockets import next_refusal_code
from apps.game.tests.matchmaking_sockets import open_matchmaking_socket
from apps.game.tests.websocket_test_client import WebsocketTestClient

PLAYER_ONE = 7
THEIR_DECK_ID = 1
NOBODYS_DECK_ID = 999
BURST = 50
PING: dict[str, object] = {"type": "ping"}


@pytest.fixture
def deck() -> Deck:
    return starter_deck(get_card_catalog())


@pytest.fixture
def decks(deck: Deck) -> FakePlayerDeckSource:
    return FakePlayerDeckSource({(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(deck)})


@pytest.fixture
def queue() -> FakeMatchmakingQueue:
    return FakeMatchmakingQueue()


async def player_socket(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> WebsocketTestClient:
    return await open_matchmaking_socket(
        FakePlayerUser(PLAYER_ONE), queue=queue, decks=decks
    )


async def test_a_ping_before_join_queue_is_answered_and_joins_nothing(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    client = await player_socket(queue, decks)

    await client.send_json_to(PING)

    await expect_pong(client, {})
    assert await client.nothing_received()
    assert await queue.size() == 0
    assert decks.asked == []
    await client.disconnect()


async def test_a_ping_while_queued_keeps_the_place_and_the_deck(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    """O primeiro pong é só a garantia de que o `join_queue` já foi processado:
    o consumer atende as mensagens em ordem. A medição é o segundo ping."""
    client = await player_socket(queue, decks)
    await client.send_json_to(
        {"type": "join_queue", "payload": {"deck_id": THEIR_DECK_ID}}
    )
    await client.send_json_to(PING)
    await expect_pong(client, {})
    waiting = list(queue.waiting)
    asked = list(decks.asked)

    await client.send_json_to(PING)

    await expect_pong(client, {})
    assert await client.nothing_received(), "nenhum match_found sozinho na fila"
    assert queue.waiting == waiting
    assert [entry.user_id for entry in queue.waiting] == [PLAYER_ONE]
    assert decks.asked == asked
    await client.disconnect()


async def test_a_ping_after_a_refused_join_is_answered_and_joins_nothing(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    client = await player_socket(queue, decks)
    await client.send_json_to(
        {"type": "join_queue", "payload": {"deck_id": NOBODYS_DECK_ID}}
    )
    assert await next_refusal_code(client) == "deck_not_found"
    asked = list(decks.asked)

    await client.send_json_to(PING)

    await expect_pong(client, {})
    assert await queue.size() == 0
    assert decks.asked == asked
    await client.disconnect()


async def test_a_ping_after_match_found_is_answered(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    client = await player_socket(queue, decks)
    await get_channel_layer().group_send(
        MatchmakingConsumer.user_group(PLAYER_ONE),
        {
            "type": "client_event",
            "event": "match_found",
            "payload": {"match_id": "m-1"},
        },
    )
    assert (await client.receive_json_from())["type"] == "match_found"

    await client.send_json_to(PING)

    await expect_pong(client, {})
    assert await queue.size() == 0
    await client.disconnect()


async def test_a_burst_of_pings_is_answered_in_order(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    client = await player_socket(queue, decks)

    await expect_ping_burst_answered(client, BURST)

    assert await client.nothing_received(), "nenhuma recusa no meio da rajada"
    assert await queue.size() == 0
    await client.disconnect()
