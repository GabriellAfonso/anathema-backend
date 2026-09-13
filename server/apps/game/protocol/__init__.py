"""O protocolo do socket de partida: a ponte entre o cliente e o motor.

Transporte puro, sem I/O. `consumers/match.py` recebe o frame, e é daqui que
saem as respostas que ele precisa:

- `client_messages` -- o JSON do cliente vira comando, ou recusa de forma
- `commands` -- o comando vira chamada às portas do motor
- `turn_clock` e `clock_events` -- quando começa vez nova, e o que o relógio
  deve agora (§15)
- `match_changes` -- a mudança que entra no `mutate`, com o antes guardado
- `match_events` e `match_frames` -- a mudança gravada vira o frame de cada
  jogador, montado para ele
- `refusal_codes` -- toda recusa vira um código estável
- `matchmaking_refusals` -- os códigos do socket de matchmaking (feature 011)
- `heartbeat` -- o ping dos dois sockets, que não é jogada (feature 013)

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`.
"""

from .clock_events import (
    ClockEvent,
    ClockEventNotDueError,
    ClockExpiry,
    MulliganExpiry,
    TurnExpiry,
    TurnWarning,
    automatic_command,
    due_clock_event,
    ensure_clock_event_due,
)
from .client_messages import MalformedMessageError, parse_client_message
from .commands import ClientCommand, ForfeitCommand, MulliganCommand, apply_command
from .heartbeat import PING, PONG, is_ping, pong_payload
from .match_changes import ClockChange, PlayerChange, RecordedChange, TurnWarningMark
from .match_events import (
    ChangeOrigin,
    ClockOrigin,
    MatchEvent,
    PlayerOrigin,
    describe_change,
    origin_events,
)
from .match_frames import (
    ClockView,
    MatchStartPayload,
    MatchUpdatePayload,
    TurnClockView,
    TurnWarningPayload,
    clock_view,
    match_start_payload,
    match_update_payload,
    turn_warning_payload,
)
from .matchmaking_refusals import (
    DECK_NOT_FOUND,
    DECK_NOT_SPECIFIED,
    INVALID_DECK,
)
from . import refusal_codes
from .refusal_codes import (
    CONCURRENT_MATCH_WRITE,
    INTERNAL_ERROR,
    MALFORMED_MESSAGE,
    MATCH_NOT_FOUND,
    UNKNOWN_MESSAGE_TYPE,
    Refusal,
    refusal_for,
)
from .turn_clock import (
    MULLIGAN_EXPIRY_MS,
    TURN_EXPIRY_MS,
    TURN_WARNING_MS,
    MatchHasNoPriorityError,
    advance_match_clock,
    opening_match_clock,
)

__all__ = [
    "MalformedMessageError",
    "parse_client_message",
    "ClientCommand",
    "MulliganCommand",
    "ForfeitCommand",
    "apply_command",
    # Relógio da vez (§15)
    "TURN_WARNING_MS",
    "TURN_EXPIRY_MS",
    "MULLIGAN_EXPIRY_MS",
    "opening_match_clock",
    "advance_match_clock",
    "MatchHasNoPriorityError",
    "TurnWarning",
    "TurnExpiry",
    "MulliganExpiry",
    "ClockEvent",
    "ClockExpiry",
    "ClockEventNotDueError",
    "due_clock_event",
    "ensure_clock_event_due",
    "automatic_command",
    # Mudanças que entram no `mutate`
    "RecordedChange",
    "PlayerChange",
    "ClockChange",
    "TurnWarningMark",
    # Eventos e frames
    "MatchEvent",
    "describe_change",
    "ChangeOrigin",
    "PlayerOrigin",
    "ClockOrigin",
    "origin_events",
    "MatchStartPayload",
    "MatchUpdatePayload",
    "TurnClockView",
    "ClockView",
    "TurnWarningPayload",
    "match_start_payload",
    "match_update_payload",
    "clock_view",
    "turn_warning_payload",
    # Recusas
    "Refusal",
    "refusal_codes",
    "refusal_for",
    "MALFORMED_MESSAGE",
    "UNKNOWN_MESSAGE_TYPE",
    "MATCH_NOT_FOUND",
    # Recusas do socket de matchmaking (feature 011)
    "DECK_NOT_SPECIFIED",
    "DECK_NOT_FOUND",
    "INVALID_DECK",
    "CONCURRENT_MATCH_WRITE",
    "INTERNAL_ERROR",
    # Heartbeat dos dois sockets (feature 013)
    "PING",
    "PONG",
    "is_ping",
    "pong_payload",
]
