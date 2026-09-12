"""In-memory stand-in for MatchStore.

The consumer tests care about which match comes back, not about Redis, so they
inject this instead of paying for a round trip. The Redis contract itself --
the hash form, the compare-and-swap of `mutate`, o índice de despertar e o TTL
que o estouro não renova -- is covered by test_match_store.py.
"""

from copy import deepcopy

from apps.game.match import Match, clock_wake_at
from apps.game.match.store import (
    MATCH_TTL_SECONDS,
    MUTATE_ATTEMPTS,
    ConcurrentMatchWriteError,
    MatchChange,
    MatchNotFoundError,
    StoredMatch,
)
from apps.game.match_timers import TickerMatchStore
from apps.game.wall_clock import EpochMillis, WallClock

MILLIS_PER_SECOND = 1000


class FakeMatchStore:
    """Same surface as MatchStore, backed by dicts.

    O que ele preserva é o contrato visível: a mutação aplicada, a exceção de
    dentro dela deixando o estado guardado intacto, a versão de escrita crescendo
    1 a cada gravação como o `HINCRBY` do store de verdade, o índice de
    despertar acompanhando o estado, e a expiração que só a jogada real renova.

    O compare-and-swap é imitado de verdade desde a feature 010: a mutação roda
    sobre uma cópia, e `_between_read_and_write` é o ponto onde
    `InterleavedMatchStore` põe uma jogada concorrente. Sem isso não daria para
    testar a corrida entre a jogada e o estouro do relógio sem Redis.

    `clock` é opcional porque a maior parte dos testes não fala de expiração;
    sem ele, partida gravada nunca expira.

    >>> store = FakeMatchStore()
    >>> await store.save(match)
    1
    >>> (await store.get_stored(match.match_id)).version
    1
    """

    def __init__(self, clock: WallClock | None = None) -> None:
        self.matches: dict[str, StoredMatch] = {}
        self.wake_at: dict[str, EpochMillis] = {}
        self.expires_at_ms: dict[str, EpochMillis] = {}
        # Uma entrada por gravação de `mutate`, na ordem: é assim que um teste
        # afirma que o estouro do relógio não adiou a expiração da partida.
        self.expiry_renewals: list[bool] = []
        self._clock = clock

    async def save(self, match: Match) -> int:
        previous = self._live(match.match_id)
        version = previous.version + 1 if previous is not None else 1
        self._keep(match, version)
        self._renew_expiry(match.match_id)

        return version

    async def get(self, match_id: str) -> Match | None:
        stored = self._live(match_id)

        return stored.match if stored is not None else None

    async def get_stored(self, match_id: str) -> StoredMatch | None:
        return self._live(match_id)

    async def mutate(
        self, match_id: str, change: MatchChange, *, renews_expiry: bool = True
    ) -> StoredMatch:
        for _ in range(MUTATE_ATTEMPTS):
            read = self._require_live(match_id)
            # Cópia, e não o objeto guardado: no store de verdade a mutação roda
            # sobre um estado recém-desserializado, então uma recusa levantada
            # de dentro de `change` não chega ao que está gravado. Mutar o
            # objeto no lugar deixaria o fake mais permissivo que a coisa real.
            working = deepcopy(read.match)
            change(working)

            await self._between_read_and_write(match_id)

            current = self._require_live(match_id)

            if current.version == read.version:
                return self._write(working, current.version + 1, renews_expiry)

        raise ConcurrentMatchWriteError(match_id, MUTATE_ATTEMPTS)

    async def _between_read_and_write(self, match_id: str) -> None:
        """Gancho da disputa: aqui não acontece nada.

        `InterleavedMatchStore` o sobrescreve para deixar uma jogada alheia cair
        exatamente onde o compare-and-swap existe para proteger.
        """

    def forget(self, match_id: str) -> None:
        """A partida some, como a chave que expira no Redis depois do TTL.

        O membro do índice de despertar **fica**, como no Redis: a chave da
        partida expira sozinha e o sorted set não sabe disso. Quem limpa é o
        ticker, ao encontrar a partida ausente.
        """
        self.matches.pop(match_id, None)
        self.expires_at_ms.pop(match_id, None)

    def _write(self, match: Match, version: int, renews_expiry: bool) -> StoredMatch:
        stored = self._keep(match, version)
        self.expiry_renewals.append(renews_expiry)

        if renews_expiry:
            self._renew_expiry(match.match_id)

        return stored

    def _keep(self, match: Match, version: int) -> StoredMatch:
        """Grava o estado e reagenda o despertar, como os scripts Lua fazem."""
        stored = StoredMatch(match=match, version=version)
        self.matches[match.match_id] = stored
        wake_at = clock_wake_at(match.clock)

        if wake_at is None:
            self.wake_at.pop(match.match_id, None)
        else:
            self.wake_at[match.match_id] = wake_at

        return stored

    def _renew_expiry(self, match_id: str) -> None:
        if self._clock is None:
            return

        self.expires_at_ms[match_id] = EpochMillis(
            self._clock.now_ms() + MATCH_TTL_SECONDS * MILLIS_PER_SECOND
        )

    def _live(self, match_id: str) -> StoredMatch | None:
        """A partida, ou `None` se ela nunca existiu ou já expirou."""
        if self._has_expired(match_id):
            self.forget(match_id)

        return self.matches.get(match_id)

    def _require_live(self, match_id: str) -> StoredMatch:
        stored = self._live(match_id)

        if stored is None:
            raise MatchNotFoundError(match_id)

        return stored

    def _has_expired(self, match_id: str) -> bool:
        expires_at = self.expires_at_ms.get(match_id)

        if expires_at is None or self._clock is None:
            return False

        return self._clock.now_ms() >= expires_at


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição. Sem ela, o dia em que `TickerMatchStore`
# ganhar um método este fake fica para trás em silêncio. Não apague por parecer
# sobra.
FAKE_MATCH_STORE_MATCHES_THE_PROTOCOL: TickerMatchStore = FakeMatchStore()
