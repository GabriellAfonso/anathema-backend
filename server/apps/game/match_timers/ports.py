"""O que o laço do relógio precisa do armazenamento e do índice, e nada além.

Dois `Protocol` estreitos, e não `MatchStore` e `MatchWakeQueue` direto: é o que
deixa o ticker rodar contra `FakeMatchStore` e `FakeMatchWakeQueue` num teste
sem Redis, sem `cast` nenhum e sem herança. Mesma escolha de `RandomSource`,
`CardCatalog` e `WallClock`.

Só os métodos que o laço chama entram. Um método a mais aqui seria um método a
mais para todo substituto de teste imitar sem necessidade.
"""

from typing import Protocol

from apps.game.match.store import MatchChange, StoredMatch
from apps.game.match.wake_queue import ClaimedWake
from apps.game.wall_clock import EpochMillis


class TickerMatchStore(Protocol):
    """A partida gravada, e a mutação atômica sobre ela."""

    async def get_stored(self, match_id: str) -> StoredMatch | None:
        """A partida e a versão, ou `None` se ela não existe mais."""
        ...

    async def mutate(
        self, match_id: str, change: MatchChange, *, renews_expiry: bool = True
    ) -> StoredMatch:
        """Aplica a mudança dentro do compare-and-swap e devolve o que gravou."""
        ...


class RunnableTicker(Protocol):
    """O que o ciclo de vida do ASGI precisa do ticker: um laço que roda."""

    async def run(self) -> None:
        """Roda até a task ser cancelada."""
        ...


class TickerWakeQueue(Protocol):
    """O índice de despertar, do lado de quem o consome."""

    async def claim_due(
        self, now: EpochMillis, *, lease_ms: int, limit: int
    ) -> list[ClaimedWake]:
        """As partidas cujo despertar venceu, reivindicadas por este worker."""
        ...

    async def release(self, claimed: ClaimedWake, wake_at: EpochMillis | None) -> None:
        """Devolve ao índice o que não rendeu gravação."""
        ...

    async def forget(self, match_id: str) -> None:
        """Tira do índice a partida que não existe mais."""
        ...
