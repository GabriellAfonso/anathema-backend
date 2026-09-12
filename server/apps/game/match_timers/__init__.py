"""O relógio da vez rodando: quem olha os prazos vencidos e age por eles (§15).

Não é consumer -- não tem socket -- e não é protocolo -- faz I/O. Aqui moram o
laço que roda em todo worker do uvicorn, o ciclo de vida que o liga e o desliga,
e as duas portas estreitas que o laço pede de quem guarda partida e de quem
guarda despertar.

A regra do relógio não mora aqui: quando começa uma vez é de
`protocol/turn_clock.py`, o que venceu é de `protocol/clock_events.py`, e a
gravação é do `MatchStore`. Este pacote só junta as peças e as põe para rodar.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`.
"""

from .lifespan import MatchTimersLifespan
from .ports import TickerMatchStore, TickerWakeQueue
from .ticker import (
    TICK_INTERVAL_SECONDS,
    WAKE_BATCH_SIZE,
    WAKE_LEASE_MS,
    MatchClockTicker,
)

__all__ = [
    "TickerMatchStore",
    "TickerWakeQueue",
    "MatchClockTicker",
    "MatchTimersLifespan",
    "TICK_INTERVAL_SECONDS",
    "WAKE_LEASE_MS",
    "WAKE_BATCH_SIZE",
]
