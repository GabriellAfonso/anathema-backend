from apps.game.match.client import get_match_store
from apps.game.match.models import Match
from apps.game.match.store import MatchStore
from apps.game.matchmaking.client import get_matchmaking_queue
from apps.game.matchmaking.queue import MatchmakingQueue
from apps.players.services.player_queries import PlayerData, get_player_public_data

from .base import BaseConsumer, ClientEventMessage


class MatchmakingConsumer(BaseConsumer):
    group_prefix = "matchmaking"

    def __init__(
        self,
        *args: object,
        queue: MatchmakingQueue | None = None,
        matches: MatchStore | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire both with MatchmakingConsumer.as_asgi(queue=..., matches=...).
        self.queue = queue or get_matchmaking_queue()
        self.matches = matches or get_match_store()

    async def on_connect(self) -> None:
        await self.join_queue()

    async def on_disconnect(self, code: int) -> None:
        await self.queue.leave(self.user_id)

    async def join_queue(self) -> None:
        """Entra na fila; cria a partida se esse join fechou um par."""
        pair = await self.queue.join(self.user_id)

        if not pair:
            return

        player1 = await get_player_public_data(pair[0])
        player2 = await get_player_public_data(pair[1])

        if player1 is None or player2 is None:
            await self.send_error(
                "matchmaking_failed",
                f"no profile for one of the paired users {pair}",
            )
            return

        match = await self.matches.create(player1, player2)

        await self.announce_match(match, player1, player2)
        await self.announce_match(match, player2, player1)

    async def announce_match(
        self, match: Match, player: PlayerData, opponent: PlayerData
    ) -> None:
        """Avisa um jogador do pareamento, do ponto de vista dele."""
        message: ClientEventMessage = {
            "type": "client_event",
            "event": "match_found",
            "payload": {
                "self": player,
                "opponent": opponent,
                "match_id": match.match_id,
            },
        }

        await self.channel_layer.group_send(self.user_group(player["user_id"]), message)
