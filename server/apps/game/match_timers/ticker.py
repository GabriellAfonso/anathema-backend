"""O laço que faz o relógio da vez acontecer, em todo worker do uvicorn (§15).

A cada volta ele reivindica os despertares vencidos e age por eles: manda o
aviso dos 30s, ou aplica a ação automática dos 45s pela mesma porta do motor e
pela mesma gravação atômica de toda jogada.

Roda em todo worker de propósito. O lease do índice evita que os quatro façam o
mesmo trabalho, e o compare-and-swap garante que, se fizerem, só um grava. Um
worker que cai no meio de uma vez não leva o prazo com ele: o despertar está no
Redis, e o próximo worker o pega quando o lease vencer.

Nenhuma exceção de um despertar derruba a volta: o laço de uma partida ruim não
pode calar o relógio de todas as outras.
"""

import asyncio
import json
import logging

from apps.game.cards import CardCatalog
from apps.game.consumers.match_delivery import (
    ChannelGroupSender,
    deliver_match_update,
    deliver_turn_warning,
)
from apps.game.engine import IllegalActionError
from apps.game.match import clock_wake_at
from apps.game.match.store import ConcurrentMatchWriteError, MatchNotFoundError
from apps.game.match.wake_queue import ClaimedWake
from apps.game.protocol import (
    ClockChange,
    ClockEvent,
    ClockEventNotDueError,
    ClockExpiry,
    ClockOrigin,
    TurnWarning,
    TurnWarningMark,
    due_clock_event,
)
from apps.game.randomness import RandomSource
from apps.game.wall_clock import EpochMillis, WallClock

from .ports import TickerMatchStore, TickerWakeQueue

# Meio segundo entre as voltas: o aviso da §12 cai entre 30,0s e 30,5s do início
# da vez, e o estouro entre 45,0s e 45,5s -- dentro do que a spec pede.
TICK_INTERVAL_SECONDS = 0.5

# O lease não protege estado: quem protege é o compare-and-swap. Ele só evita
# trabalho repetido, e por isso pode ser curto -- é também o atraso máximo de um
# despertar cujo worker morreu depois de reivindicá-lo.
WAKE_LEASE_MS = 5_000

# Quantos despertares uma volta processa. Com dois jogadores por partida e uma
# vez de 45s, nem uma sala cheia enche isto.
WAKE_BATCH_SIZE = 50

logger = logging.getLogger(__name__)


class MatchClockTicker:
    """O relógio de todas as partidas, do ponto de vista de um worker.

    Dependências injetadas, como em todo o resto do projeto: o ponto de
    composição é `core/asgi.py`, e o teste passa os fakes.

    >>> ticker = MatchClockTicker(matches=store, wake_queue=queue, ...)
    >>> await ticker.tick(clock.now_ms())
    """

    def __init__(
        self,
        *,
        matches: TickerMatchStore,
        wake_queue: TickerWakeQueue,
        channel_layer: ChannelGroupSender,
        catalog: CardCatalog,
        randomness: RandomSource,
        clock: WallClock,
    ) -> None:
        self.matches = matches
        self.wake_queue = wake_queue
        self.channel_layer = channel_layer
        self.catalog = catalog
        self.randomness = randomness
        self.clock = clock

    async def run(self) -> None:
        """O laço, até a task ser cancelada no desligamento do worker."""
        while True:
            await self.tick(self.clock.now_ms())
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    async def tick(self, now: EpochMillis) -> None:
        """Uma volta: reivindica o que venceu e age por cada um.

        É este o método que os testes chamam -- o laço só o repete, e ninguém
        precisa esperar 45 segundos de verdade para exercitar o relógio.
        """
        claimed = await self.wake_queue.claim_due(
            now, lease_ms=WAKE_LEASE_MS, limit=WAKE_BATCH_SIZE
        )

        for wake in claimed:
            await self._process(wake, now)

    async def _process(self, wake: ClaimedWake, now: EpochMillis) -> None:
        """Um despertar, com a falha dele isolada do resto da volta."""
        try:
            await self._wake(wake, now)
        except Exception as failure:
            self._log_failure(wake, failure)

    async def _wake(self, wake: ClaimedWake, now: EpochMillis) -> None:
        stored = await self.matches.get_stored(wake.match_id)

        if stored is None:
            await self.wake_queue.forget(wake.match_id)
            return

        event = due_clock_event(stored.match, now)

        if event is None:
            await self.wake_queue.release(wake, clock_wake_at(stored.match.clock))
            return

        await self._act(wake, event, now)

    async def _act(
        self, wake: ClaimedWake, event: ClockEvent, now: EpochMillis
    ) -> None:
        if isinstance(event, TurnWarning):
            await self._warn(wake, event, now)
            return

        await self._expire(wake, event, now)

    async def _warn(
        self, wake: ClaimedWake, event: TurnWarning, now: EpochMillis
    ) -> None:
        """Grava a marca e **depois** manda o aviso.

        Nesta ordem porque o contrário mandaria aviso de uma vez que uma jogada
        concorrente já terminou. O preço é que um worker que morra entre as duas
        perde aquele aviso -- o estouro não se perde, e a reconexão mostra o
        tempo restante de verdade.
        """
        try:
            stored = await self.matches.mutate(
                wake.match_id, TurnWarningMark(event, now), renews_expiry=False
            )
        except (ClockEventNotDueError, ConcurrentMatchWriteError):
            await self._release(wake)
            return

        await deliver_turn_warning(self.channel_layer, stored, now)

    async def _expire(
        self, wake: ClaimedWake, event: ClockExpiry, now: EpochMillis
    ) -> None:
        """A ação automática da fase, pela porta de sempre."""
        change = ClockChange(
            event, catalog=self.catalog, randomness=self.randomness, now=now
        )

        try:
            stored = await self.matches.mutate(
                wake.match_id, change, renews_expiry=False
            )
        except ClockEventNotDueError:
            await self._release(wake)
            return
        except (IllegalActionError, ConcurrentMatchWriteError) as refused:
            self._log_refusal(wake, event, refused)
            await self._release(wake)
            return

        self._log_fired(wake, event)
        await deliver_match_update(
            self.channel_layer,
            change.recorded_before(),
            stored,
            change.applied_command(),
            origin=ClockOrigin(event),
            now=now,
        )

    async def _release(self, wake: ClaimedWake) -> None:
        """Devolve o despertar ao índice pelo estado que está gravado agora."""
        try:
            stored = await self.matches.get_stored(wake.match_id)
        except MatchNotFoundError:
            stored = None

        if stored is None:
            await self.wake_queue.forget(wake.match_id)
            return

        await self.wake_queue.release(wake, clock_wake_at(stored.match.clock))

    def _log_refusal(
        self, wake: ClaimedWake, event: ClockExpiry, refused: Exception
    ) -> None:
        """Recusa do motor a uma ação automática: não deveria acontecer, e por
        isso vira log com nome próprio em vez de sumir."""
        logger.error(
            json.dumps(
                {
                    "event": "match_clock_refused",
                    "match_id": wake.match_id,
                    "clock_event": type(event).__name__,
                    "error": type(refused).__name__,
                }
            )
        )

    def _log_failure(self, wake: ClaimedWake, failure: Exception) -> None:
        logger.error(
            json.dumps(
                {
                    "event": "match_clock_failed",
                    "match_id": wake.match_id,
                    "error": type(failure).__name__,
                }
            ),
            exc_info=failure,
        )

    def _log_fired(self, wake: ClaimedWake, event: ClockExpiry) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "match_clock_fired",
                    "match_id": wake.match_id,
                    "clock_event": type(event).__name__,
                }
            )
        )
