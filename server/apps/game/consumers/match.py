from urllib.parse import parse_qs

from apps.game.match.client import get_match_store
from apps.game.match.models import Match
from apps.game.match.store import MatchStore

from .base import BaseConsumer

# Close codes in the private 4000-4999 range, mirroring HTTP: 4001 is the auth
# gate in BaseConsumer, so the match gate continues the 44xx series.
MATCH_ID_MISSING = 4400
NOT_A_PARTICIPANT = 4403
MATCH_NOT_FOUND = 4404


class MatchConsumer(BaseConsumer):
    group_prefix = "match"

    match: Match | None = None

    def __init__(
        self, *args: object, matches: MatchStore | None = None, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire a store with MatchConsumer.as_asgi(matches=...).
        self.matches = matches or get_match_store()

    async def on_connect(self) -> None:
        """Só deixa entrar quem joga a partida pedida."""
        match_id = self.get_match_id()

        if not match_id:
            await self.reject(MATCH_ID_MISSING, "expected ?matchId=<uuid>, got none")
            return

        match = await self.matches.get(match_id)

        if match is None:
            await self.reject(MATCH_NOT_FOUND, f"no live match {match_id!r}")
            return

        if not match.has_player(self.user_id):
            await self.reject(
                NOT_A_PARTICIPANT,
                f"user {self.user_id} does not play match {match_id!r}",
            )
            return

        self.match = match

        await self.send_event(type='match_start', payload={})

    def get_match_id(self) -> str | None:
        query_string: str = self.scope["query_string"].decode()
        match_ids = parse_qs(query_string).get("matchId")

        return match_ids[0] if match_ids else None

    async def reject(self, code: int, reason: str) -> None:
        """Fecha com o motivo legível antes do código.

        O close vem depois do accept de propósito: um close antes do handshake
        chega ao browser como 1006, sem código nem texto.
        """
        await self.send_error('match_denied', reason)
        await self.close(code=code)
