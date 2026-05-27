from .base import BaseConsumer
from django.contrib.auth import get_user_model
from apps.game.match.manager import MatchManager
import json
from urllib.parse import parse_qs

User = get_user_model()


class MatchConsumer(BaseConsumer):

    async def connect(self):
        await super().connect()
        # opcional: print quando alguém conecta
        print(f"[MatchConsumer] {self.user.username} connected")
        self.player = self.user

        # Recupera a mesma instância da partida criada pelo matchmaking
        self.match_id = await self.get_match_id()
        self.match = MatchManager.get_match(self.match_id)

        # Registra esse consumer para enviar updates futuros
        MatchManager.register_consumer(self.player.id, self)

        await self.send_event(type='match_start', payload={})

    async def get_match_id(self):
        query_string = self.scope["query_string"].decode()
        params = parse_qs(query_string)

        return params.get("matchId", [None])[0]

    async def disconnect(self, code):
        await super().disconnect(code)
        print(f"[MatchConsumer] {self.user.username} disconnected")
