"""Process-wide handle to the match store."""

from functools import cache

from django.conf import settings
from redis.asyncio import Redis

from .store import MatchStore


@cache
def get_match_store() -> MatchStore:
    """Default store for the running process.

    Cached for the same reason as the matchmaking queue: redis-py holds a
    connection pool per client and `--lifespan off` leaves no startup hook.
    Consumers take the store as an argument, so tests inject their own.
    """
    return MatchStore(Redis.from_url(settings.MATCH_REDIS_URL))
