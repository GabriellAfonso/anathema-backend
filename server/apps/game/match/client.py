"""Process-wide handles to the match store and to its wake-up index."""

from functools import cache

from django.conf import settings
from redis.asyncio import Redis

from .store import MatchStore
from .wake_queue import MatchWakeQueue


@cache
def get_match_store() -> MatchStore:
    """Default store for the running process.

    Cached for the same reason as the matchmaking queue: redis-py holds a
    connection pool per client, and consumers take the store as an argument, so
    tests inject their own.
    """
    return MatchStore(_match_redis())


@cache
def get_match_wake_queue() -> MatchWakeQueue:
    """Índice de despertar do processo, sobre a mesma base do store (§15).

    O score é mantido pelos scripts do `MatchStore`, então os dois precisam
    falar com o mesmo Redis e com o mesmo prefixo de chave.
    """
    return MatchWakeQueue(_match_redis())


@cache
def _match_redis() -> Redis:
    """O cliente Redis das partidas, um por processo.

    Um só para o store e para o índice: redis-py mantém um pool por cliente, e
    dois clientes para a mesma base seriam dois pools sem motivo.
    """
    return Redis.from_url(settings.MATCH_REDIS_URL)
