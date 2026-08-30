"""Partidas vivas no Redis, para todo worker do uvicorn ler a mesma.

O dict de classe que isto substitui vivia em um processo só: com `--workers 4`
a partida criada pelo worker do matchmaking era invisível para o worker onde o
socket de partida do jogador caía, e o gate de participante fecha isso com
4404.

Leitura e escrita são comandos separados, então um read-modify-write (jogar uma
carta) ainda não é atômico -- não existe caminho de mutação até os handlers de
gameplay entrarem. Quando entrarem, a mutação vai precisar de script Lua, como
o pareamento da fila.
"""

import json
from typing import cast

from redis.asyncio import Redis

from apps.players.services.player_queries import PlayerData

from .models import Match, MatchState

# Partida abandonada não pode ficar para sempre no Redis. Longo o bastante para
# um jogo lento ou uma reconexão nunca perderem o estado.
MATCH_TTL_SECONDS = 6 * 60 * 60


class MatchStore:
    """Partidas endereçadas por `match_id`. Cliente Redis injetado.

    >>> store = MatchStore(Redis.from_url("redis://localhost:6379/3"))
    >>> match = await store.create({"user_id": 7}, {"user_id": 9})
    >>> (await store.get(match.match_id)).turn
    7
    """

    def __init__(self, redis: Redis, key_prefix: str = "match") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    async def create(self, player1: PlayerData, player2: PlayerData) -> Match:
        """Cria a partida e publica o estado inicial."""
        match = Match.start(player1, player2)
        await self.save(match)

        return match

    async def get(self, match_id: str) -> Match | None:
        """Partida pelo id, ou None se nunca existiu ou já expirou."""
        state = await self._redis.get(self._key(match_id))

        if state is None:
            return None

        # A fronteira JSON é o único ponto onde o formato não é verificável:
        # o que sai do Redis é `Any` até alguém afirmar o contrário.
        return Match.from_dict(cast(MatchState, json.loads(state)))

    async def save(self, match: Match) -> None:
        """Grava o estado, renovando o TTL: partida em uso não expira."""
        await self._redis.set(
            self._key(match.match_id),
            json.dumps(match.as_dict()),
            ex=MATCH_TTL_SECONDS,
        )

    def _key(self, match_id: str) -> str:
        return f"{self._key_prefix}:{match_id}"
