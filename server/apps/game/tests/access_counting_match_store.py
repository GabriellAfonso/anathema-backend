"""Um `FakeMatchStore` que conta quem foi lido e gravado.

O `FakeMatchStore` sozinho prova "não gravou": a versão não sobe e
`expiry_renewals` não cresce. "Não leu" ele não prova, e o ping promete as duas
coisas (feature 013, FR-007). Subclasse nomeada, e não `monkeypatch`: o mesmo
movimento de `InterleavedMatchStore`.

O socket de partida lê a partida uma vez no gate, ao conectar. Por isso o teste
chama `forget_accesses` depois de conectar e antes do que quer medir.
"""

from collections import Counter

from apps.game.match import Match
from apps.game.match.store import MatchChange, StoredMatch
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.wall_clock import WallClock


class AccessCountingMatchStore(FakeMatchStore):
    """`FakeMatchStore` que anota cada leitura e gravação pelo nome do método.

    >>> matches = AccessCountingMatchStore(clock)
    >>> await matches.get_stored("m-1")
    >>> matches.accesses["get_stored"]
    1
    """

    def __init__(self, clock: WallClock | None = None) -> None:
        super().__init__(clock)
        self.accesses: Counter[str] = Counter()

    def forget_accesses(self) -> None:
        """Zera a contagem, depois de o gate do socket ter lido a partida.

        >>> matches.forget_accesses()
        """
        self.accesses.clear()

    async def save(self, match: Match) -> int:
        self.accesses["save"] += 1

        return await super().save(match)

    async def get(self, match_id: str) -> Match | None:
        self.accesses["get"] += 1

        return await super().get(match_id)

    async def get_stored(self, match_id: str) -> StoredMatch | None:
        self.accesses["get_stored"] += 1

        return await super().get_stored(match_id)

    async def mutate(
        self, match_id: str, change: MatchChange, *, renews_expiry: bool = True
    ) -> StoredMatch:
        self.accesses["mutate"] += 1

        return await super().mutate(match_id, change, renews_expiry=renews_expiry)
