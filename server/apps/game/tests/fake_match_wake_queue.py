"""Índice de despertar em memória, sobre o mesmo `FakeMatchStore`.

O índice de verdade é mantido pelos scripts Lua do `MatchStore`, então o fake do
índice tem de olhar o mesmo lugar onde o fake do store escreve -- senão os dois
divergiriam e o teste provaria uma coisa que não existe.

A semântica do lease é a mesma do Redis: reivindicar empurra o score para o fim
do lease, e devolver só vale se ninguém mexeu no meio.
"""

from apps.game.match.wake_queue import ClaimedWake
from apps.game.match_timers import TickerWakeQueue
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.wall_clock import EpochMillis


class FakeMatchWakeQueue:
    """Mesma superfície de `MatchWakeQueue`, sobre `FakeMatchStore.wake_at`.

    >>> queue = FakeMatchWakeQueue(store)
    >>> await queue.claim_due(now, lease_ms=5000, limit=50)
    [ClaimedWake(match_id='m-1', lease_until_ms=1700000005000)]
    """

    def __init__(self, store: FakeMatchStore) -> None:
        self._store = store

    async def claim_due(
        self, now: EpochMillis, *, lease_ms: int, limit: int
    ) -> list[ClaimedWake]:
        lease_until = EpochMillis(now + lease_ms)
        due = self._due(now)[:limit]

        for match_id in due:
            self._store.wake_at[match_id] = lease_until

        return [
            ClaimedWake(match_id=match_id, lease_until_ms=lease_until)
            for match_id in due
        ]

    async def release(self, claimed: ClaimedWake, wake_at: EpochMillis | None) -> None:
        if self._store.wake_at.get(claimed.match_id) != claimed.lease_until_ms:
            return

        if wake_at is None:
            await self.forget(claimed.match_id)
            return

        self._store.wake_at[claimed.match_id] = wake_at

    async def forget(self, match_id: str) -> None:
        self._store.wake_at.pop(match_id, None)

    def _due(self, now: EpochMillis) -> list[str]:
        """Os vencidos, do mais antigo para o mais novo, como o Redis devolve."""
        ordered = sorted(self._store.wake_at.items(), key=lambda entry: entry[1])

        return [match_id for match_id, wake_at in ordered if wake_at <= now]


# Asserção estática, pela mesma razão do `FAKE_MATCH_STORE_MATCHES_THE_PROTOCOL`.
FAKE_WAKE_QUEUE_MATCHES_THE_PROTOCOL: TickerWakeQueue = FakeMatchWakeQueue(
    FakeMatchStore()
)
