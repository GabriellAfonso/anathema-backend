"""A entrega dos frames de partida aos grupos de usuário.

Duas entregas, e as duas endereçam o **grupo de usuário** de cada jogador, nunca
o grupo da partida: o frame de um contém a mão dele, e o grupo da partida o
entregaria ao outro.

Mora fora de `match.py` porque tem dois chamadores: o consumer, quando uma
jogada do socket é aceita, e o ticker do relógio (§15), que não tem socket
nenhum e precisa entregar a mesma coisa. O nome do grupo também mora aqui, pela
mesma razão -- e `MatchConsumer.user_group` o reusa, para que não existam duas
fórmulas do mesmo endereço.
"""

from collections.abc import Mapping
from typing import Protocol, TypedDict

from apps.game.match import Match
from apps.game.match.store import StoredMatch
from apps.game.protocol import (
    ChangeOrigin,
    ClientCommand,
    MatchUpdatePayload,
    TurnWarningPayload,
    match_update_payload,
    turn_warning_payload,
)
from apps.game.wall_clock import EpochMillis

MATCH_GROUP_PREFIX = "match"


class MatchUpdateMessage(TypedDict):
    """Mensagem de channel layer que leva o frame **já montado** para um jogador.

    Vai ao grupo de usuário dele, nunca ao grupo da partida: o payload contém a
    mão do destinatário. `match_id` deixa o socket de outra partida do mesmo
    usuário ignorá-la.
    """

    type: str
    match_id: str
    payload: MatchUpdatePayload


class TurnWarningMessage(TypedDict):
    """O aviso dos 30s, endereçado só a quem deve a jogada (§15)."""

    type: str
    match_id: str
    payload: TurnWarningPayload


class ChannelGroupSender(Protocol):
    """O que a entrega precisa do channel layer, e nada além.

    `Protocol` porque o Channels não traz tipos: assim o que atravessa a
    fronteira é declarado aqui, em vez de virar `Any` calado.
    """

    async def group_send(self, group: str, message: Mapping[str, object]) -> None:
        """Manda a mensagem a todos os canais daquele grupo."""
        ...


def match_user_group(user_id: int) -> str:
    """O grupo com todos os sockets de partida de um usuário.

    >>> match_user_group(7)
    'match.user.7'
    """
    return f"{MATCH_GROUP_PREFIX}.user.{user_id}"


async def deliver_match_update(
    channel_layer: ChannelGroupSender,
    before: Match,
    stored: StoredMatch,
    command: ClientCommand,
    *,
    origin: ChangeOrigin,
    now: EpochMillis,
) -> None:
    """Um frame por jogador, montado para ele, ao grupo de usuário dele.

    Todo socket do jogador naquela partida recebe, inclusive o que mandou -- a
    atualização é a confirmação da jogada.
    """
    for player in stored.match.players:
        message: MatchUpdateMessage = {
            "type": "match.update",
            "match_id": stored.match.match_id,
            "payload": match_update_payload(
                before,
                stored.match,
                stored.version,
                command,
                player.user_id,
                origin=origin,
                now=now,
            ),
        }
        await channel_layer.group_send(match_user_group(player.user_id), message)


async def deliver_turn_warning(
    channel_layer: ChannelGroupSender, stored: StoredMatch, now: EpochMillis
) -> None:
    """O aviso dos 30s aos sockets de quem deve a jogada.

    Sem vez aberta não há a quem avisar: a partida terminou ou voltou ao
    mulligan entre a marca e a entrega, e o aviso morre aqui.
    """
    turn = stored.match.clock.turn

    if turn is None:
        return

    message: TurnWarningMessage = {
        "type": "match.turn_warning",
        "match_id": stored.match.match_id,
        "payload": turn_warning_payload(turn, now),
    }
    await channel_layer.group_send(match_user_group(turn.holder_user_id), message)
