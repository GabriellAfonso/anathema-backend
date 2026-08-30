"""Process-wide handle to the matchmaking queue."""

from functools import cache

from django.conf import settings
from redis.asyncio import Redis

from .queue import MatchmakingQueue


@cache
def get_matchmaking_queue() -> MatchmakingQueue:
    """Default queue for the running process.

    Cached because redis-py holds a connection pool per client, and uvicorn
    runs with `--lifespan off`, so there is no ASGI startup hook to build one
    in. Consumers take the queue as an argument, so tests inject their own
    instead of reaching for this.
    """
    return MatchmakingQueue(Redis.from_url(settings.MATCHMAKING_REDIS_URL))
