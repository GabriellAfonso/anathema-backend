"""Os frames que o socket de partida manda, montados para o dono do socket.

**Nunca uma visão pronta atravessa para outro jogador.** Estas funções recebem o
`user_id` do destinatário e montam para ele; quem distribui chama uma vez por
jogador. Mandar o frame de um ao grupo da partida entregaria a mão dele ao
outro -- é a armadilha que a spec desta feature nomeia.

`version` é a versão de escrita do `MatchStore`: cresce 1 a cada gravação, em
qualquer worker, e é o que deixa o cliente descartar uma atualização que chegou
depois de uma mais nova.
"""

from typing import TypedDict

from apps.game.match import Match, PlayerView, build_player_view

from .commands import ClientCommand
from .match_events import MatchEvent, describe_change


class MatchStartPayload(TypedDict):
    """O `match_start`: a partida como está agora, ao conectar ou reconectar."""

    version: int
    view: PlayerView


class MatchUpdatePayload(TypedDict):
    """O `match_update`: a partida depois de uma mudança aceita, e o que
    aconteceu nela."""

    version: int
    view: PlayerView
    events: list[MatchEvent]


def match_start_payload(match: Match, version: int, user_id: int) -> MatchStartPayload:
    """>>> match_start_payload(match, 4, 7)["version"]
    4
    """
    return {"version": version, "view": build_player_view(match, user_id)}


def match_update_payload(
    before: Match,
    after: Match,
    version: int,
    command: ClientCommand,
    user_id: int,
) -> MatchUpdatePayload:
    """>>> match_update_payload(before, after, 5, PassAction(9), 7)["events"][0]
    {'kind': 'passed', 'user_id': 9}
    """
    return {
        "version": version,
        "view": build_player_view(after, user_id),
        "events": describe_change(before, after, command, recipient_user_id=user_id),
    }
