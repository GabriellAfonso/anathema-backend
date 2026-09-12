"""O que venceu no relógio de uma partida, e a ação que o estouro manda (§15).

Puro. O laço lê o estado gravado e pergunta aqui o que venceu; a mesma pergunta
é refeita **dentro** da mutação, sobre a leitura fresca de cada tentativa do
compare-and-swap. É isso que resolve, com um mecanismo só, as duas corridas que
a spec nomeia: a jogada real chegando no mesmo instante do estouro, e o estouro
atrasado chegando depois de a vez já ter ido e voltado.

Um estouro vale só para a vez em que foi armado. Como a identidade da vez é o
`turn_number`, e como ele muda sempre que a vez troca de mão ou a rodada vira,
comparar o evento com o que está vencido agora responde as duas perguntas de uma
vez.
"""

from dataclasses import dataclass
from typing import assert_never

from apps.game.engine import ConfirmAttackAction, EndDefenseWindowAction, PassAction
from apps.game.match import Match, MatchPhase, TurnDeadline
from apps.game.wall_clock import EpochMillis

from .commands import ClientCommand, MulliganCommand


@dataclass(frozen=True, slots=True)
class TurnWarning:
    """Os 30s da vez passaram e o aviso ainda não saiu (§15)."""

    turn_number: int
    holder_user_id: int


@dataclass(frozen=True, slots=True)
class TurnExpiry:
    """Os 45s da vez passaram: a ação automática da fase entra."""

    turn_number: int
    holder_user_id: int


@dataclass(frozen=True, slots=True)
class MulliganExpiry:
    """Os 30s do mulligan daquele jogador passaram sem resposta (§3, §15)."""

    user_id: int


# O que vira gravação. O aviso fica de fora porque ele não é jogada: marca o
# estado e manda um frame, sem passar pelo motor.
ClockExpiry = TurnExpiry | MulliganExpiry
ClockEvent = TurnWarning | ClockExpiry


class ClockEventNotDueError(Exception):
    """O evento armado não é o que está vencido agora.

    Não é recusa de cliente: nunca chega a socket nenhum, e por isso não está no
    catálogo de códigos. Levantada de dentro da mudança, aborta a gravação sem
    tocar a partida -- que é como o estouro atrasado não faz nada.

    >>> raise ClockEventNotDueError("m-1", TurnExpiry(3, 7), EpochMillis(10))
    ClockEventNotDueError: clock event TurnExpiry(turn_number=3, holder_user_id=7)
    is not due in match 'm-1' at 10: expected it to be what the stored clock owes now
    """

    def __init__(self, match_id: str, event: ClockEvent, now: EpochMillis) -> None:
        super().__init__(
            f"clock event {event!r} is not due in match {match_id!r} at {now}: "
            f"expected it to be what the stored clock owes now"
        )
        self.match_id = match_id
        self.event = event
        self.now = now


def due_clock_event(match: Match, now: EpochMillis) -> ClockEvent | None:
    """O que esta partida deve ao relógio neste instante, ou `None`.

    >>> due_clock_event(match, EpochMillis(45_000))
    TurnExpiry(turn_number=1, holder_user_id=7)
    """
    turn = match.clock.turn

    if turn is not None:
        return _due_turn_event(turn, now)

    return _due_mulligan_event(match, now)


def ensure_clock_event_due(match: Match, event: ClockEvent, now: EpochMillis) -> None:
    """A mesma pergunta, sobre a leitura fresca da tentativa que vai gravar.

    Igualdade e não "ainda existe": a vez que voltou ao mesmo jogador tem outro
    `turn_number`, e um aviso já mandado deixa de ser o que está vencido.

    >>> ensure_clock_event_due(match, TurnExpiry(1, 7), EpochMillis(45_000))
    """
    if due_clock_event(match, now) != event:
        raise ClockEventNotDueError(match.match_id, event, now)


def automatic_command(match: Match, event: ClockExpiry) -> ClientCommand:
    """A ação que o estouro manda ao motor, como se o jogador a tivesse mandado.

    >>> automatic_command(match, TurnExpiry(1, 7))
    PassAction(actor_user_id=7)
    """
    match event:
        case MulliganExpiry():
            return MulliganCommand(user_id=event.user_id, card_instance_ids=())
        case TurnExpiry():
            return _automatic_turn_command(match, event)
        case _:
            assert_never(event)


def _due_turn_event(turn: TurnDeadline, now: EpochMillis) -> ClockEvent | None:
    """O estouro tem precedência: vencidos os dois, o aviso não tem mais função
    -- é o caso de um worker que ficou fora do ar durante a vez inteira."""
    if now >= turn.expires_at_ms:
        return TurnExpiry(turn.turn_number, turn.holder_user_id)

    if now >= turn.warns_at_ms and not turn.warning_sent:
        return TurnWarning(turn.turn_number, turn.holder_user_id)

    return None


def _due_mulligan_event(match: Match, now: EpochMillis) -> MulliganExpiry | None:
    """O primeiro jogador que ainda não respondeu, quando o prazo venceu.

    Um por vez: cada estouro é uma gravação, e a partida que ainda deve o outro
    mulligan continua vencida no índice, então o despertar seguinte o pega.
    """
    expires_at = match.clock.mulligan_expires_at_ms

    if expires_at is None or now < expires_at or match.phase is not MatchPhase.MULLIGAN:
        return None

    awaiting = match.awaiting_mulligan_user_ids

    return MulliganExpiry(awaiting[0]) if awaiting else None


def _automatic_turn_command(match: Match, event: TurnExpiry) -> ClientCommand:
    """A fase de **agora** decide a ação (§15), não a de quando foi armada.

    O atacante que puxa a última unidade no instante do estouro devolve a
    partida à Fase de Ação, e aí o estouro é passar.
    """
    if match.phase is MatchPhase.DECLARATION:
        return ConfirmAttackAction(actor_user_id=event.holder_user_id)

    if match.phase is MatchPhase.COMBAT:
        return EndDefenseWindowAction(actor_user_id=event.holder_user_id)

    return PassAction(actor_user_id=event.holder_user_id)
