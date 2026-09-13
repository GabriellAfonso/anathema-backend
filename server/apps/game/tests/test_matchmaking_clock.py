"""A partida nasce com o prazo de mulligan armado (§3, §15).

O prazo conta da **criação**, e não da conexão de cada jogador: o relógio não
pode depender de socket aberto, e é aqui que o `match_found` sai para os dois.
Sem isto, quem nunca abre o socket prende o outro no mulligan para sempre.

O consumer é montado direto, com o channel layer em memória do `conftest.py`:
`open_match` é o passo que interessa, e chegar nele pela fila faria o teste
passar pelo banco por causa de `get_player_public_data`.
"""

from typing import cast

import pytest

from apps.game.cards import get_card_catalog, starter_deck
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.engine import MatchEntry
from apps.game.match import Match
from apps.game.match.store import MatchStore
from apps.game.protocol import MULLIGAN_EXPIRY_MS
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_chosen_deck import fake_chosen_deck
from apps.game.tests.fake_player_data import fake_player_data
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_wall_clock import FakeWallClock
from channels.layers import get_channel_layer

PLAYER_ONE = 7
PLAYER_TWO = 9


@pytest.fixture
def clock() -> FakeWallClock:
    return FakeWallClock()


@pytest.fixture
def matches(clock: FakeWallClock) -> FakeMatchStore:
    return FakeMatchStore(clock)


def consumer(matches: FakeMatchStore, clock: FakeWallClock) -> MatchmakingConsumer:
    """O consumer com as dependências do teste, sem passar pelo socket.

    O `cast` existe porque aqui o consumer é construído direto, e o parâmetro
    pede `MatchStore`. Pelo socket, o mesmo fake entra por `as_asgi(**kwargs)`,
    que o Channels declara como `object` -- a checagem some, o fake é o mesmo.
    """
    built = MatchmakingConsumer(
        matches=cast(MatchStore, matches),
        catalog=get_card_catalog(),
        randomness=ScriptedRandomSource(),
        clock=clock,
    )
    built.channel_layer = get_channel_layer()

    return built


def match_entry(user_id: int, nickname: str) -> MatchEntry:
    """Perfil e deck juntos, como a fila os entrega desde a feature 011.

    O deck é o derivado do catálogo: o que está sob teste aqui é o prazo do
    mulligan, e uma lista específica não mudaria nada.
    """
    return MatchEntry(
        profile=fake_player_data(user_id, nickname),
        deck=fake_chosen_deck(starter_deck(get_card_catalog())),
    )


async def opened_match(matches: FakeMatchStore, clock: FakeWallClock) -> Match:
    await consumer(matches, clock).open_match(
        match_entry(PLAYER_ONE, "one"), match_entry(PLAYER_TWO, "two")
    )
    saved = list(matches.matches.values())
    assert len(saved) == 1

    return saved[0].match


async def test_a_new_match_carries_the_mulligan_deadline(
    matches: FakeMatchStore, clock: FakeWallClock
) -> None:
    match = await opened_match(matches, clock)

    assert match.clock.mulligan_expires_at_ms == clock.now_ms() + MULLIGAN_EXPIRY_MS


async def test_a_new_match_has_no_turn_yet(
    matches: FakeMatchStore, clock: FakeWallClock
) -> None:
    """Vez existe a partir da Rodada 1; no mulligan o prazo é por jogador."""
    match = await opened_match(matches, clock)

    assert match.clock.turn is None


async def test_the_new_match_is_in_the_wake_up_index(
    matches: FakeMatchStore, clock: FakeWallClock
) -> None:
    """Sem isto, nenhum worker olharia para o mulligan que ninguém responde."""
    match = await opened_match(matches, clock)

    assert matches.wake_at[match.match_id] == clock.now_ms() + MULLIGAN_EXPIRY_MS
