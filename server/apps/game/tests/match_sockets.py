"""Sockets de partida para os testes do protocolo, sobre o store em memória.

Não é fake: não substitui I/O nenhum -- o store e o channel layer já são os
fakes de sempre (`FakeMatchStore` e o `InMemoryChannelLayer` do `conftest.py`).
Aqui ficam só os passos que todo teste do protocolo repete: abrir o socket de um
jogador, mandar uma jogada, e ler a atualização ou a recusa que voltou.
"""

from dataclasses import asdict
from typing import cast

from apps.game.cards import mvp_catalog
from apps.game.consumers.match import MatchConsumer
from apps.game.engine import PlayerAction
from apps.game.match import Match
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.websocket_test_client import WebsocketTestClient
from apps.game.wall_clock import WallClock

Frame = dict[str, object]


async def open_match_socket(
    matches: FakeMatchStore,
    user_id: int,
    match_id: str,
    *,
    clock: WallClock | None = None,
) -> tuple[WebsocketTestClient, Frame]:
    """Conecta o jogador e devolve o socket com o `match_start` que chegou.

    `clock` é o mesmo relógio falso do teste quando o cenário fala de prazo: o
    socket mede o tempo restante com ele, como o ticker mede.
    """
    client = WebsocketTestClient(
        MatchConsumer.as_asgi(
            matches=matches,
            catalog=mvp_catalog(),
            randomness=ScriptedRandomSource(),
            clock=clock,
        ),
        "/ws/match/",
        query_string=f"matchId={match_id}",
    )
    client.scope["user"] = FakePlayerUser(user_id)
    await client.connect()

    start = await client.receive_json_from()
    assert start["type"] == "match_start", start

    return client, payload_of(start)


async def saved(matches: FakeMatchStore, match: Match) -> Match:
    await matches.save(match)

    return match


def payload_of(frame: Frame) -> Frame:
    return cast(Frame, frame["payload"])


def view_of(payload: Frame) -> Frame:
    return cast(Frame, payload["view"])


def side_of(view: Frame, key: str) -> Frame:
    return cast(Frame, view[key])


def event_kinds(payload: Frame) -> list[str]:
    return [str(event["kind"]) for event in cast(list[Frame], payload["events"])]


async def next_update(client: WebsocketTestClient) -> Frame:
    """A próxima atualização deste socket; falha se chegou outra coisa."""
    frame = await client.receive_json_from()
    assert frame["type"] == "match_update", frame

    return payload_of(frame)


async def next_turn_warning(client: WebsocketTestClient) -> Frame:
    """O próximo aviso dos 30s deste socket; falha se chegou outra coisa."""
    frame = await client.receive_json_from()
    assert frame["type"] == "turn_warning", frame

    return payload_of(frame)


async def next_refusal_code(client: WebsocketTestClient) -> str:
    """O código da próxima recusa deste socket; falha se chegou outra coisa."""
    frame = await client.receive_json_from()
    assert frame["type"] == "message_refused", frame

    return str(payload_of(frame)["code"])


def message_for(action: PlayerAction) -> Frame:
    """A mensagem que o cliente mandaria para esta ação.

    Monta pelo nome dos campos da própria ação: se o protocolo e a ação
    divergirem num nome, o teste que usa isto falha no parser.
    """
    fields = asdict(action)
    fields.pop("actor_user_id")
    payload = {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in fields.items()
    }

    return {"type": str(action.action_kind), "payload": payload}


__all__ = [
    "Frame",
    "open_match_socket",
    "saved",
    "payload_of",
    "view_of",
    "side_of",
    "event_kinds",
    "next_update",
    "next_turn_warning",
    "next_refusal_code",
    "message_for",
]
