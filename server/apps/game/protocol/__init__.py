"""O protocolo do socket de partida: a ponte entre o cliente e o motor.

Transporte puro, sem I/O. `consumers/match.py` recebe o frame, e é daqui que
saem as quatro respostas que ele precisa:

- `client_messages` -- o JSON do cliente vira comando, ou recusa de forma
- `commands` -- o comando vira chamada às portas do motor
- `match_events` e `match_frames` -- a mudança gravada vira o frame de cada
  jogador, montado para ele
- `refusal_codes` -- toda recusa vira um código estável

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`.
"""

from .client_messages import MalformedMessageError, parse_client_message
from .commands import ClientCommand, ForfeitCommand, MulliganCommand, apply_command
from .match_events import MatchEvent, describe_change
from .match_frames import (
    MatchStartPayload,
    MatchUpdatePayload,
    match_start_payload,
    match_update_payload,
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

__all__ = [
    "MalformedMessageError",
    "parse_client_message",
    "ClientCommand",
    "MulliganCommand",
    "ForfeitCommand",
    "apply_command",
    "MatchEvent",
    "describe_change",
    "MatchStartPayload",
    "MatchUpdatePayload",
    "match_start_payload",
    "match_update_payload",
    "Refusal",
    "refusal_codes",
    "refusal_for",
    "MALFORMED_MESSAGE",
    "UNKNOWN_MESSAGE_TYPE",
    "MATCH_NOT_FOUND",
    "CONCURRENT_MATCH_WRITE",
    "INTERNAL_ERROR",
]
