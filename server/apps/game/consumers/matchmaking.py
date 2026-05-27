from .base import BaseConsumer
from django.core.cache import cache
import uuid
from apps.players.services.player_queries import get_player_public_data

from apps.game.match.manager import MatchManager

MATCHMAKING_QUEUE_KEY = "matchmaking_queue"


class MatchmakingConsumer(BaseConsumer):

    async def connect(self):
        await super().connect()
        await self.join_queue()

    async def disconnect(self, code):
        await self.leave_queue()
        await super().disconnect(code)

    async def join_queue(self):
        """Adiciona o jogador à fila e tenta criar um match"""
        queue = cache.get(MATCHMAKING_QUEUE_KEY, [])
        queue.append(self.user.id)
        cache.set(MATCHMAKING_QUEUE_KEY, queue, timeout=None)

        # se houver pelo menos 2 jogadores, cria um match
        if len(queue) >= 2:
            player1 = await get_player_public_data(queue.pop(0))
            player2 = await get_player_public_data(queue.pop(0))
            cache.set(MATCHMAKING_QUEUE_KEY, queue, timeout=None)

            match = MatchManager.create_match(player1, player2)

            # Envia evento para os dois jogadores conectarem ao MatchConsumer
            channel_1 = cache.get(f"user_channel:{player1["id"]}")
            channel_2 = cache.get(f"user_channel:{player2["id"]}")

            await self.channel_layer.send(
                channel_1,
                {
                    "type": "client_event",
                    "event": "match_found",
                    "payload": {
                        "self": player1,
                        "opponent": player2,
                        "match_id": match.id,
                    }
                }
            )
            await self.channel_layer.send(
                channel_2,
                {
                    "type": "client_event",
                    "event": "match_found",
                    "payload": {
                        "self": player2,
                        "opponent": player1,
                        "match_id": match.id,
                    }
                }
            )

    async def handle_match_found():
        print('partida achada kk')

    async def leave_queue(self):
        """Remove o jogador da fila caso desconecte antes de parear"""
        queue = cache.get(MATCHMAKING_QUEUE_KEY, [])
        if self.user.id in queue:
            queue.remove(self.user.id)
            cache.set(MATCHMAKING_QUEUE_KEY, queue, timeout=None)
