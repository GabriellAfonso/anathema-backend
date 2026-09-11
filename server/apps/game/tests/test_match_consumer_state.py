"""O `match_start` carrega o estado, e é isso que faz a reconexão funcionar.

Antes disto o frame saía com payload vazio: o cliente entrava na partida sem
mão, sem tabuleiro e sem saber de quem era o turno, e uma queda de rede não
tinha como ser recuperada -- só existia o estado que o cliente tinha em
memória. Reconectar passa a ser conectar de novo.

O outro eixo coberto aqui é o grupo da partida: sem ele a jogada de um jogador
nunca chegaria ao outro socket.
"""

from typing import cast

import pytest
from channels.layers import get_channel_layer

from apps.game.consumers.match import MatchConsumer
from apps.game.match import Match, MatchPhase
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_setup import fake_match_ready_for_upkeep
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.websocket_test_client import WebsocketTestClient

PLAYER_ONE = 7
PLAYER_TWO = 8


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore()


@pytest.fixture
async def match(matches: FakeMatchStore) -> Match:
    """Setup fechado: o token já foi sorteado, então existe dono do turno."""
    started = fake_match_ready_for_upkeep(PLAYER_ONE, PLAYER_TWO)
    await matches.save(started)

    return started


def connect_as(
    matches: FakeMatchStore, user_id: int, match_id: str
) -> WebsocketTestClient:
    client = WebsocketTestClient(
        MatchConsumer.as_asgi(matches=matches),
        "/ws/match/",
        query_string=f"matchId={match_id}",
    )
    client.scope["user"] = FakePlayerUser(user_id)
    return client


async def open_socket(
    matches: FakeMatchStore, user_id: int, match_id: str
) -> tuple[WebsocketTestClient, dict[str, object]]:
    """Conecta e devolve o socket junto do `match_start` que ele recebeu."""
    client = connect_as(matches, user_id, match_id)
    await client.connect()

    return client, await client.receive_json_from()


def state_of(frame: dict[str, object]) -> dict[str, object]:
    """A visão dentro do `match_start`, que desde a feature 009 vem junto da
    versão de escrita: `{"version": ..., "view": ...}`."""
    assert frame["type"] == "match_start"
    payload = cast(dict[str, object], frame["payload"])

    return cast(dict[str, object], payload["view"])


def side(state: dict[str, object], key: str) -> dict[str, object]:
    return cast(dict[str, object], state[key])


def card_ids(cards: object) -> list[int]:
    return [card["card_instance_id"] for card in cast(list[dict[str, int]], cards)]


async def test_match_start_carries_the_players_own_hand(
    matches: FakeMatchStore, match: Match
) -> None:
    client, frame = await open_socket(matches, PLAYER_ONE, match.match_id)

    hand = side(state_of(frame), "you")["hand"]

    assert card_ids(hand) == [
        card.card_instance_id for card in match.player(PLAYER_ONE).hand
    ]
    await client.disconnect()


async def test_match_start_carries_both_boards(
    matches: FakeMatchStore, match: Match
) -> None:
    """Tabuleiro é o banco dos dois lados: o cliente desenha os dois."""
    client, frame = await open_socket(matches, PLAYER_ONE, match.match_id)
    state = state_of(frame)

    assert side(state, "you")["bank"] == []
    assert side(state, "opponent")["bank"] == []
    await client.disconnect()


async def test_match_start_says_whose_turn_it_is(
    matches: FakeMatchStore, match: Match
) -> None:
    client, frame = await open_socket(matches, PLAYER_ONE, match.match_id)
    state = state_of(frame)

    assert state["priority_user_id"] == match.priority_user_id
    assert state["token_holder_user_id"] == match.token_holder_user_id
    assert state["phase"] == MatchPhase.UPKEEP
    await client.disconnect()


async def test_match_start_names_the_match_and_the_round(
    matches: FakeMatchStore, match: Match
) -> None:
    client, frame = await open_socket(matches, PLAYER_ONE, match.match_id)
    state = state_of(frame)

    assert state["match_id"] == match.match_id
    assert state["round_number"] == 1
    await client.disconnect()


async def test_reconnecting_returns_the_same_state(
    matches: FakeMatchStore, match: Match
) -> None:
    """O caso que a feature inteira existe para atender.

    Sem mensagem `resync`: o segundo socket é igual ao primeiro, e o servidor
    responde a mesma partida, na mesma versão.
    """
    first, opening = await open_socket(matches, PLAYER_ONE, match.match_id)
    await first.disconnect()

    second, after_reconnect = await open_socket(matches, PLAYER_ONE, match.match_id)

    assert state_of(after_reconnect) == state_of(opening)
    await second.disconnect()


async def test_each_player_gets_their_own_hand(
    matches: FakeMatchStore, match: Match
) -> None:
    one, one_frame = await open_socket(matches, PLAYER_ONE, match.match_id)
    two, two_frame = await open_socket(matches, PLAYER_TWO, match.match_id)

    one_hand = card_ids(side(state_of(one_frame), "you")["hand"])
    two_hand = card_ids(side(state_of(two_frame), "you")["hand"])

    assert one_hand != two_hand
    assert not set(one_hand) & set(two_hand)
    await one.disconnect()
    await two.disconnect()


async def test_the_opponent_hand_never_leaves_the_server(
    matches: FakeMatchStore, match: Match
) -> None:
    """Do outro lado sai a contagem, nunca a identidade das cartas."""
    client, frame = await open_socket(matches, PLAYER_ONE, match.match_id)
    opponent = side(state_of(frame), "opponent")

    assert "hand" not in opponent
    assert opponent["hand_size"] == len(match.player(PLAYER_TWO).hand)
    await client.disconnect()


async def test_both_sockets_join_the_same_match_group(
    matches: FakeMatchStore, match: Match
) -> None:
    """É por este grupo que a jogada de um jogador chega ao outro."""
    one, _ = await open_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_socket(matches, PLAYER_TWO, match.match_id)

    await get_channel_layer().group_send(
        MatchConsumer.match_group(match.match_id),
        {"type": "client_event", "event": "ping", "payload": {}},
    )

    assert await one.receive_json_from() == {"type": "ping", "payload": {}}
    assert await two.receive_json_from() == {"type": "ping", "payload": {}}
    await one.disconnect()
    await two.disconnect()


async def test_disconnect_leaves_the_match_group(
    matches: FakeMatchStore, match: Match
) -> None:
    client, _ = await open_socket(matches, PLAYER_ONE, match.match_id)
    await client.disconnect()

    layer = get_channel_layer()

    assert layer.groups.get(MatchConsumer.match_group(match.match_id), {}) == {}


async def test_a_rejected_socket_joins_no_match_group(
    matches: FakeMatchStore,
) -> None:
    """O socket recusado é aceito só para contar o motivo, então ele chega ao
    `on_disconnect` sem nunca ter entrado no grupo -- e o cleanup não pode
    tentar desfazer o que não houve."""
    client = connect_as(matches, PLAYER_ONE, "no-such-match")
    await client.connect()
    await client.receive_json_from()
    await client.receive_close_code()
    await client.disconnect()

    assert (
        get_channel_layer().groups.get(MatchConsumer.match_group("no-such-match"))
        is None
    )
