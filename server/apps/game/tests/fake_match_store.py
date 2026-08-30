"""In-memory stand-in for MatchStore.

The consumer tests care about which match comes back, not about Redis, so they
inject this instead of paying for a round trip. The Redis contract itself is
covered by test_match_store.py.
"""

from apps.game.match.models import Match
from apps.players.services.player_queries import PlayerData


class FakeMatchStore:
    """Same surface as MatchStore, backed by a dict.

    >>> store = FakeMatchStore()
    >>> match = await store.create({"user_id": 7}, {"user_id": 9})
    >>> await store.get(match.match_id) is match
    True
    """

    def __init__(self) -> None:
        self.matches: dict[str, Match] = {}

    async def create(self, player1: PlayerData, player2: PlayerData) -> Match:
        match = Match.start(player1, player2)
        await self.save(match)

        return match

    async def save(self, match: Match) -> None:
        self.matches[match.match_id] = match

    async def get(self, match_id: str) -> Match | None:
        return self.matches.get(match_id)
