"""O que entra no `mutate`: o comando, a partida de antes, e o relógio da vez.

Três mudanças, uma por origem -- a jogada do socket, o estouro do relógio e a
marca do aviso. As duas primeiras guardam a partida de antes da tentativa que
valeu, e todas terminam em `advance_match_clock`: é o único ponto onde a vez é
aberta, e por isso não existe caminho de gravação que esqueça o relógio.

O consumer e o ticker usam as mesmas classes daqui, e é isso que faz o estouro
passar pelo mesmo caminho de toda jogada (§15): a mesma porta do motor, a mesma
gravação atômica, a mesma descrição do que aconteceu.
"""

from copy import deepcopy
from dataclasses import replace

from apps.game.cards import CardCatalog
from apps.game.match import Match, TurnDeadline
from apps.game.randomness import RandomSource
from apps.game.wall_clock import EpochMillis, WallClock

from .clock_events import (
    ClockEventNotDueError,
    ClockExpiry,
    TurnWarning,
    automatic_command,
    ensure_clock_event_due,
)
from .commands import ClientCommand, apply_command
from .turn_clock import advance_match_clock


class RecordedChange:
    """A partida de antes da tentativa que valeu.

    `MatchStore.mutate` pode reaplicar a mudança sobre uma leitura fresca quando
    outro worker escreveu no meio. Cada tentativa sobrescreve `before`, então o
    que sobra quando `mutate` devolve é o antes da tentativa gravada -- e é dele
    que a descrição do que aconteceu precisa (FR-037 da feature 009).
    """

    def __init__(self) -> None:
        self.before: Match | None = None

    def recorded_before(self) -> Match:
        """A partida de antes da tentativa gravada.

        Recusa nomeada em vez de `assert` -- que some com `-O` -- para o caso
        impossível de `mutate` devolver sem ter chamado a mudança.
        """
        if self.before is None:
            raise RuntimeError(
                f"no state recorded for {self!r}: expected mutate to run the change"
            )

        return self.before

    def _record(self, match: Match) -> None:
        self.before = deepcopy(match)


class PlayerChange(RecordedChange):
    """A jogada que chegou por um socket.

    >>> change = PlayerChange(command, catalog=catalog, randomness=source, clock=clock)
    >>> await matches.mutate(match_id, change)
    """

    def __init__(
        self,
        command: ClientCommand,
        *,
        catalog: CardCatalog,
        randomness: RandomSource,
        clock: WallClock,
    ) -> None:
        super().__init__()
        self.command = command
        self.catalog = catalog
        self.randomness = randomness
        self.clock = clock

    def __call__(self, match: Match) -> None:
        self._record(match)
        apply_command(
            match, self.command, catalog=self.catalog, randomness=self.randomness
        )
        advance_match_clock(match, self.clock.now_ms())


class ClockChange(RecordedChange):
    """O estouro do relógio, como se o jogador tivesse mandado a jogada (§15).

    A guarda roda **dentro** da mutação, sobre a leitura fresca de cada
    tentativa: se a vez já é outra, ou se o prazo ainda não venceu, levantar
    aborta sem gravar nada. É assim que o estouro atrasado não faz nada e que a
    corrida com a jogada real tem um vencedor só.

    O comando é escolhido pela fase de **agora**, e guardado para a descrição do
    que aconteceu.

    >>> change = ClockChange(expiry, catalog=catalog, randomness=source, now=now)
    >>> await matches.mutate(match_id, change, renews_expiry=False)
    """

    def __init__(
        self,
        event: ClockExpiry,
        *,
        catalog: CardCatalog,
        randomness: RandomSource,
        now: EpochMillis,
    ) -> None:
        super().__init__()
        self.event = event
        self.catalog = catalog
        self.randomness = randomness
        self.now = now
        self.command: ClientCommand | None = None

    def applied_command(self) -> ClientCommand:
        """O comando que a tentativa gravada aplicou."""
        if self.command is None:
            raise RuntimeError(
                f"no command applied for {self.event!r}: expected mutate to run "
                f"the change"
            )

        return self.command

    def __call__(self, match: Match) -> None:
        ensure_clock_event_due(match, self.event, self.now)
        self._record(match)

        self.command = automatic_command(match, self.event)
        apply_command(
            match, self.command, catalog=self.catalog, randomness=self.randomness
        )
        advance_match_clock(match, self.now)


class TurnWarningMark:
    """Marca o aviso da vez como mandado, e nada mais.

    Não passa pelo motor e não descreve nada: o aviso não é jogada. A marca é
    gravada **antes** de o frame sair, para que uma jogada que chegue no meio
    não traga o aviso de volta, e é gravada sem renovar a expiração da partida.

    >>> await matches.mutate(match_id, TurnWarningMark(warning, now), renews_expiry=False)
    """

    def __init__(self, event: TurnWarning, now: EpochMillis) -> None:
        self.event = event
        self.now = now

    def __call__(self, match: Match) -> None:
        ensure_clock_event_due(match, self.event, self.now)
        turn = self._warned_turn(match)
        match.clock = replace(match.clock, turn=turn)

    def _warned_turn(self, match: Match) -> TurnDeadline:
        """A vez com a marca. A guarda já provou que ela existe."""
        turn = match.clock.turn

        if turn is None:
            raise ClockEventNotDueError(match.match_id, self.event, self.now)

        return replace(turn, warning_sent=True)
