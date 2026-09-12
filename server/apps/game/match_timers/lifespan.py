"""O ciclo de vida do ASGI que liga e desliga o relógio da vez (§15).

O ticker não pode depender de socket aberto -- o caso que o relógio existe para
resolver é justamente o do jogador que fechou o jogo. Então ele sobe com o
worker, e não com a primeira conexão.

O uvicorn passa a rodar com `--lifespan on`, e o `ProtocolTypeRouter` ganha a
chave `lifespan` apontando para cá. Era por não existir nada neste escopo que o
projeto rodava com `--lifespan off`.

O ticker é construído na hora do startup, e não no import: o cliente Redis e o
channel layer nascem no processo que vai usá-los.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping

from .ports import RunnableTicker

# O protocolo lifespan do ASGI, sem depender dos tipos internos do asgiref: são
# três mensagens, e só duas interessam.
LifespanMessage = Mapping[str, object]
LifespanReceive = Callable[[], Awaitable[LifespanMessage]]
LifespanSend = Callable[[Mapping[str, object]], Awaitable[None]]

logger = logging.getLogger(__name__)


class MatchTimersLifespan:
    """App ASGI do escopo `lifespan`: startup liga o ticker, shutdown o desliga.

    >>> MatchTimersLifespan(build_match_clock_ticker)
    """

    def __init__(self, build_ticker: Callable[[], RunnableTicker]) -> None:
        self._build_ticker = build_ticker
        self._task: asyncio.Task[None] | None = None

    async def __call__(
        self,
        scope: Mapping[str, object],
        receive: LifespanReceive,
        send: LifespanSend,
    ) -> None:
        while True:
            message = await receive()

            if message["type"] == "lifespan.startup":
                self._start()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self._stop()
                await send({"type": "lifespan.shutdown.complete"})
                return

    def _start(self) -> None:
        """Uma task por worker. O laço só termina no cancelamento."""
        self._task = asyncio.create_task(self._build_ticker().run())
        logger.info(json.dumps({"event": "match_clock_started"}))

    async def _stop(self) -> None:
        """Cancela e espera: um worker que some no meio de uma volta deixaria o
        despertar reivindicado até o lease vencer."""
        task, self._task = self._task, None

        if task is None:
            return

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            logger.info(json.dumps({"event": "match_clock_stopped"}))
