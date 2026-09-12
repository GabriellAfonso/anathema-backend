"""Os passos que todo teste do relógio da vez repete (§15).

Não é fake: não substitui I/O nenhum -- o store, o índice e o channel layer já
são os fakes de sempre. Aqui ficam o tabuleiro com a vez aberta, a partida
esperando mulligan, o ticker montado e os dois sockets, que dois arquivos de
teste montariam igual.

É o mesmo papel de `match_sockets.py` para os testes do protocolo.
"""

from channels.layers import get_channel_layer

from apps.game.cards import CardCatalog, CardId
from apps.game.match import Match
from apps.game.match_timers import MatchClockTicker
from apps.game.protocol import advance_match_clock, opening_match_clock
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    fake_combat_board,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_match_wake_queue import FakeMatchWakeQueue
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.match_sockets import open_match_socket, saved
from apps.game.tests.websocket_test_client import WebsocketTestClient

# Os prazos da §12, em segundos, para os testes adiantarem o relógio falso.
WARNING_SECONDS = 30
EXPIRY_SECONDS = 45
MULLIGAN_SECONDS = 30


def ticker_over(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> MatchClockTicker:
    """Um worker olhando aquele store, com o índice sobre ele.

    >>> ticker_over(matches, clock, catalog)
    """
    return MatchClockTicker(
        matches=matches,
        wake_queue=FakeMatchWakeQueue(matches),
        channel_layer=get_channel_layer(),
        catalog=catalog,
        randomness=ScriptedRandomSource(),
        clock=clock,
    )


async def with_a_turn(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    *,
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (SKILLET,),
) -> Match:
    """Partida na Fase de Ação, vez do primeiro jogador aberta agora."""
    match = fake_combat_board(catalog=catalog, bank_one=bank_one, bank_two=bank_two)
    advance_match_clock(match, clock.now_ms())

    return await saved(matches, match)


async def awaiting_mulligan(matches: FakeMatchStore, clock: FakeWallClock) -> Match:
    """Partida recém-criada, com o prazo de mulligan armado agora (§3)."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(clock.now_ms())

    return await saved(matches, match)


async def both_sockets(
    matches: FakeMatchStore, clock: FakeWallClock, match: Match
) -> tuple[WebsocketTestClient, WebsocketTestClient]:
    """Os dois jogadores conectados, com o mesmo relógio do ticker."""
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id, clock=clock)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id, clock=clock)

    return one, two


async def close(*clients: WebsocketTestClient) -> None:
    for client in clients:
        await client.disconnect()


async def stored(matches: FakeMatchStore, match: Match) -> Match:
    """A partida como está gravada agora, falhando o teste se ela sumiu."""
    live = await matches.get(match.match_id)
    assert live is not None

    return live


__all__ = [
    "WARNING_SECONDS",
    "EXPIRY_SECONDS",
    "MULLIGAN_SECONDS",
    "ticker_over",
    "with_a_turn",
    "awaiting_mulligan",
    "both_sockets",
    "close",
    "stored",
]
