"""In-memory stand-in for MatchStore.

The consumer tests care about which match comes back, not about Redis, so they
inject this instead of paying for a round trip. The Redis contract itself --
the hash form and the compare-and-swap of `mutate` -- is covered by
test_match_store.py.
"""

from copy import deepcopy

from apps.game.match import Match
from apps.game.match.store import MatchChange, MatchNotFoundError, StoredMatch


class FakeMatchStore:
    """Same surface as MatchStore, backed by a dict.

    `mutate` não disputa com ninguém aqui: um dict num processo só não tem a
    corrida que o compare-and-swap existe para resolver. O que ele preserva é
    o contrato visível -- a mutação aplicada, a exceção de dentro dela deixando
    o estado guardado intacto, e a versão de escrita crescendo 1 a cada
    gravação, como o `HINCRBY` do store de verdade.

    >>> store = FakeMatchStore()
    >>> await store.save(match)
    1
    >>> (await store.get_stored(match.match_id)).version
    1
    """

    def __init__(self) -> None:
        self.matches: dict[str, StoredMatch] = {}

    async def save(self, match: Match) -> int:
        previous = self.matches.get(match.match_id)
        version = previous.version + 1 if previous is not None else 1
        self.matches[match.match_id] = StoredMatch(match=match, version=version)

        return version

    async def get(self, match_id: str) -> Match | None:
        stored = self.matches.get(match_id)

        return stored.match if stored is not None else None

    async def get_stored(self, match_id: str) -> StoredMatch | None:
        return self.matches.get(match_id)

    async def mutate(self, match_id: str, change: MatchChange) -> StoredMatch:
        stored = self.matches.get(match_id)

        if stored is None:
            raise MatchNotFoundError(match_id)

        # Cópia, e não o objeto guardado: no store de verdade a mutação roda
        # sobre um estado recém-desserializado, então uma recusa levantada de
        # dentro de `change` não chega ao que está gravado. Mutar o objeto no
        # lugar deixaria o fake mais permissivo que a coisa real.
        working = deepcopy(stored.match)
        change(working)
        version = await self.save(working)

        return StoredMatch(match=working, version=version)

    def forget(self, match_id: str) -> None:
        """A partida some, como a chave que expira no Redis depois do TTL."""
        del self.matches[match_id]
