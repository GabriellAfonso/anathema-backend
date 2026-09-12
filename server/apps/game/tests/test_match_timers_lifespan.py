"""O startup liga o relógio, o shutdown o desliga (§15).

Sem lifespan, o ticker só existiria dentro de um socket -- e um relógio que
depende de conexão aberta morre justamente com o jogador que abandonou.

O app é exercitado direto, com um `receive` e um `send` do próprio teste: o
protocolo lifespan é um laço sobre três mensagens, e o driver do asgiref não
acrescentaria nada a não ser tipos que o mypy não vê.
"""

import asyncio
from collections.abc import Mapping

from apps.game.match_timers import MatchTimersLifespan
from apps.game.match_timers.ports import RunnableTicker

STARTUP: Mapping[str, object] = {"type": "lifespan.startup"}
SHUTDOWN: Mapping[str, object] = {"type": "lifespan.shutdown"}


class RecordingTicker:
    """Ticker que registra o que aconteceu com o laço, em vez de rodá-lo.

    Fake nomeado: o que está sob teste é o ciclo de vida, e um `MatchClockTicker`
    de verdade traria Redis e channel layer para uma pergunta que não é sobre
    eles.
    """

    def __init__(self) -> None:
        self.started = False
        self.cancelled = False

    async def run(self) -> None:
        self.started = True

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class LifespanDriver:
    """O `receive`/`send` do escopo lifespan, uma mensagem por vez.

    Mensagem a mensagem, e não todas de uma vez, porque entre o startup e o
    shutdown o laço de eventos precisa de uma volta -- é nela que a task do
    ticker começa a rodar. Enfileirar as duas juntas cancelaria uma task que
    nunca chegou a entrar.
    """

    def __init__(self, lifespan: MatchTimersLifespan) -> None:
        self._incoming: asyncio.Queue[Mapping[str, object]] = asyncio.Queue()
        self.sent: list[Mapping[str, object]] = []
        self._app = asyncio.create_task(
            lifespan({"type": "lifespan"}, self._receive, self._send)
        )

    async def send_message(self, message: Mapping[str, object]) -> None:
        self._incoming.put_nowait(message)

        for _ in range(3):
            await asyncio.sleep(0)

    async def finish(self) -> None:
        await self._app

    async def _receive(self) -> Mapping[str, object]:
        return await self._incoming.get()

    async def _send(self, message: Mapping[str, object]) -> None:
        self.sent.append(message)


async def test_the_startup_runs_the_ticker() -> None:
    ticker = RecordingTicker()
    driver = LifespanDriver(MatchTimersLifespan(lambda: ticker))

    await driver.send_message(STARTUP)

    assert ticker.started is True
    assert driver.sent == [{"type": "lifespan.startup.complete"}]
    await driver.send_message(SHUTDOWN)
    await driver.finish()


async def test_the_shutdown_cancels_the_ticker_and_answers() -> None:
    ticker = RecordingTicker()
    driver = LifespanDriver(MatchTimersLifespan(lambda: ticker))
    await driver.send_message(STARTUP)

    await driver.send_message(SHUTDOWN)
    await driver.finish()

    assert ticker.cancelled is True
    assert driver.sent[-1] == {"type": "lifespan.shutdown.complete"}


async def test_a_shutdown_without_startup_still_answers() -> None:
    """Um worker que cai antes de subir não pode travar o desligamento."""
    driver = LifespanDriver(MatchTimersLifespan(RecordingTicker))

    await driver.send_message(SHUTDOWN)
    await driver.finish()

    assert driver.sent == [{"type": "lifespan.shutdown.complete"}]


# Asserção estática, como nos outros fakes: o dia em que o ciclo de vida pedir
# mais do ticker, este fake não fica para trás em silêncio.
RECORDING_TICKER_MATCHES_THE_PROTOCOL: RunnableTicker = RecordingTicker()
