"""Socket de matchmaking para os testes, sobre a fila e os decks em memória.

Não é fake: não substitui I/O nenhum -- a fila, os decks e o store já são
`FakeMatchmakingQueue`, `FakePlayerDeckSource` e `FakeMatchStore`. Aqui fica só a
montagem que os testes do heartbeat repetiriam. É o mesmo papel de
`match_sockets.py` para o socket de partida.

Passa pelo `connect` e pelo `receive` de verdade, ao contrário do
`RecordingConsumer` de `test_matchmaking_join.py`: o ping mora no `receive`, e é
o `connect` que marca o socket como aceito.
"""

from apps.game.cards import get_card_catalog
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_users import FakeAnonymousUser, FakePlayerUser
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.websocket_test_client import WebsocketTestClient


async def open_matchmaking_socket(
    user: FakePlayerUser | FakeAnonymousUser,
    *,
    queue: FakeMatchmakingQueue,
    decks: FakePlayerDeckSource,
) -> WebsocketTestClient:
    """Conecta e devolve o socket, sem ler frame nenhum.

    Não lê de propósito: o socket recusado pelo gate de autenticação ainda tem o
    `auth_denied` e o close para entregar, e é isso que o teste do gate confere.

    >>> client = await open_matchmaking_socket(FakePlayerUser(7), queue=queue, decks=decks)
    """
    client = WebsocketTestClient(
        MatchmakingConsumer.as_asgi(
            queue=queue,
            matches=FakeMatchStore(),
            decks=decks,
            catalog=get_card_catalog(),
            randomness=ScriptedRandomSource(),
            clock=FakeWallClock(),
        ),
        "/ws/matchmaking/",
    )
    client.scope["user"] = user
    await client.connect()

    return client


__all__ = ["open_matchmaking_socket"]
