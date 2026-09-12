"""Os frames que o socket de partida manda, montados para o dono do socket.

**Nunca uma visão pronta atravessa para outro jogador.** Estas funções recebem o
`user_id` do destinatário e montam para ele; quem distribui chama uma vez por
jogador. Mandar o frame de um ao grupo da partida entregaria a mão dele ao
outro -- é a armadilha que a spec da feature 009 nomeia.

`version` é a versão de escrita do `MatchStore`: cresce 1 a cada gravação, em
qualquer worker, e é o que deixa o cliente descartar uma atualização que chegou
depois de uma mais nova.

`clock` entra ao lado da visão, e não dentro dela, porque o tempo restante não é
da partida -- é da partida **e** do instante em que o frame foi montado. É o
mesmo argumento que manteve `version` fora da visão. O cliente recebe quanto
falta, e não um horário absoluto: assim o relógio do dispositivo dele pode estar
errado sem que o prazo fique.
"""

from typing import TypedDict

from apps.game.match import (
    Match,
    MatchPhase,
    PlayerView,
    TurnDeadline,
    build_player_view,
)
from apps.game.wall_clock import EpochMillis

from .commands import ClientCommand
from .match_events import ChangeOrigin, MatchEvent, describe_change, origin_events
from .turn_clock import TURN_EXPIRY_MS, TURN_WARNING_MS

# A janela do aviso: 15s entre o aviso da §12 e o estouro. `warning` é derivado
# do tempo restante, e não da marca gravada, para que quem reconecta aos 40s veja
# o aviso valendo mesmo que o frame dele tenha se perdido.
WARNING_WINDOW_MS = TURN_EXPIRY_MS - TURN_WARNING_MS


class TurnClockView(TypedDict):
    """A vez em curso, do ponto de vista de quem recebe o frame."""

    turn_number: int
    holder_user_id: int
    remaining_ms: int
    warning: bool


class ClockView(TypedDict):
    """Os prazos que o destinatário pode ver.

    `turn` é `None` no mulligan e na partida terminada.
    `mulligan_remaining_ms` é só o prazo **dele**, e só enquanto ele não
    respondeu: o do oponente não é dele para ver.
    """

    turn: TurnClockView | None
    mulligan_remaining_ms: int | None


class TurnWarningPayload(TypedDict):
    """O `turn_warning`, que só o dono da vez recebe."""

    turn_number: int
    holder_user_id: int
    remaining_ms: int


class MatchStartPayload(TypedDict):
    """O `match_start`: a partida como está agora, ao conectar ou reconectar."""

    version: int
    view: PlayerView
    clock: ClockView


class MatchUpdatePayload(TypedDict):
    """O `match_update`: a partida depois de uma mudança aceita, o que
    aconteceu nela, e quanto falta para a vez atual."""

    version: int
    view: PlayerView
    events: list[MatchEvent]
    clock: ClockView


def match_start_payload(
    match: Match, version: int, user_id: int, now: EpochMillis
) -> MatchStartPayload:
    """>>> match_start_payload(match, 4, 7, now)["version"]
    4
    """
    return {
        "version": version,
        "view": build_player_view(match, user_id),
        "clock": clock_view(match, user_id, now),
    }


def match_update_payload(
    before: Match,
    after: Match,
    version: int,
    command: ClientCommand,
    user_id: int,
    *,
    origin: ChangeOrigin,
    now: EpochMillis,
) -> MatchUpdatePayload:
    """>>> match_update_payload(before, after, 5, PassAction(9), 7,
    ...                        origin=PlayerOrigin(), now=now)["events"][0]
    {'kind': 'passed', 'user_id': 9}
    """
    return {
        "version": version,
        "view": build_player_view(after, user_id),
        "events": origin_events(origin)
        + describe_change(before, after, command, recipient_user_id=user_id),
        "clock": clock_view(after, user_id, now),
    }


def clock_view(match: Match, user_id: int, now: EpochMillis) -> ClockView:
    """Os prazos da partida recortados para aquele jogador.

    >>> clock_view(match, 7, now)["turn"]["remaining_ms"]
    25000
    """
    return {
        "turn": _turn_clock_view(match.clock.turn, now),
        "mulligan_remaining_ms": _mulligan_remaining_ms(match, user_id, now),
    }


def turn_warning_payload(turn: TurnDeadline, now: EpochMillis) -> TurnWarningPayload:
    """O aviso de que o tempo está acabando.

    >>> turn_warning_payload(turn, now)["remaining_ms"]
    15000
    """
    return {
        "turn_number": turn.turn_number,
        "holder_user_id": turn.holder_user_id,
        "remaining_ms": _remaining_ms(turn.expires_at_ms, now),
    }


def _turn_clock_view(
    turn: TurnDeadline | None, now: EpochMillis
) -> TurnClockView | None:
    if turn is None:
        return None

    remaining_ms = _remaining_ms(turn.expires_at_ms, now)

    return {
        "turn_number": turn.turn_number,
        "holder_user_id": turn.holder_user_id,
        "remaining_ms": remaining_ms,
        "warning": remaining_ms <= WARNING_WINDOW_MS,
    }


def _mulligan_remaining_ms(match: Match, user_id: int, now: EpochMillis) -> int | None:
    """O prazo do próprio mulligan, enquanto ele é a resposta que falta."""
    expires_at_ms = match.clock.mulligan_expires_at_ms

    if expires_at_ms is None or match.phase is not MatchPhase.MULLIGAN:
        return None

    if match.player(user_id).mulligan_taken:
        return None

    return _remaining_ms(expires_at_ms, now)


def _remaining_ms(deadline_ms: EpochMillis, now: EpochMillis) -> int:
    """Quanto falta, nunca negativo: prazo vencido é 0 até o estouro chegar."""
    return max(deadline_ms - now, 0)
