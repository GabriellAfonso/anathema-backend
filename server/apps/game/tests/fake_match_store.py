"""In-memory stand-in for MatchStore.

The consumer tests care about which match comes back, not about Redis, so they
inject this instead of paying for a round trip. The Redis contract itself --
the hash form and the compare-and-swap of `mutate` -- is covered by
test_match_store.py.
"""

from copy import deepcopy

from apps.game.match import Match
from apps.game.match.store import MatchChange, MatchNotFoundError


class FakeMatchStore:
    """Same surface as MatchStore, backed by a dict.

    `mutate` não disputa com ninguém aqui: um dict num processo só não tem a
    corrida que o compare-and-swap existe para resolver. O que ele preserva é
    o contrato visível -- a mutação aplicada, e a exceção de dentro dela
    deixando o estado guardado intacto.

    >>> store = FakeMatchStore()
    >>> await store.save(match)
    >>> await store.get(match.match_id) is match
    True
    """

    def __init__(self) -> None:
        self.matches: dict[str, Match] = {}

    async def save(self, match: Match) -> None:
        self.matches[match.match_id] = match

    async def get(self, match_id: str) -> Match | None:
        return self.matches.get(match_id)

    async def mutate(self, match_id: str, change: MatchChange) -> Match:
        stored = self.matches.get(match_id)

        if stored is None:
            raise MatchNotFoundError(match_id)

        # Cópia, e não o objeto guardado: no store de verdade a mutação roda
        # sobre um estado recém-desserializado, então uma recusa levantada de
        # dentro de `change` não chega ao que está gravado. Mutar o objeto no
        # lugar deixaria o fake mais permissivo que a coisa real.
        working = deepcopy(stored)
        change(working)
        await self.save(working)

        return working
