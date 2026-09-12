"""Store em que uma jogada alheia cai entre a leitura e a gravação.

Subclasse nomeada, e não monkeypatch: a interferência tem nome, e o que ela
ocupa é exatamente o ponto que o compare-and-swap protege. É o irmão em memória
do `AlwaysStaleMatchStore` de `test_match_store.py`, e existe para os cenários
da §15 em que a jogada do socket e o estouro do relógio chegam no mesmo
instante.

A jogada alheia roda **uma vez só**: se rodasse em toda tentativa, a disputa
nunca convergiria e o teste provaria só o limite de tentativas.
"""

from collections.abc import Awaitable, Callable

from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.wall_clock import WallClock


class InterleavedMatchStore(FakeMatchStore):
    """`FakeMatchStore` com uma jogada concorrente entre a leitura e a escrita.

    >>> store = InterleavedMatchStore(lambda: play_the_pass(store))
    >>> await store.mutate(match_id, change)
    """

    def __init__(
        self,
        interloper: Callable[[], Awaitable[None]],
        clock: WallClock | None = None,
    ) -> None:
        super().__init__(clock)
        self._interloper: Callable[[], Awaitable[None]] | None = interloper

    async def _between_read_and_write(self, match_id: str) -> None:
        interloper, self._interloper = self._interloper, None

        if interloper is not None:
            await interloper()
