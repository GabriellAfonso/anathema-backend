"""FIFO waiting queue for matchmaking, backed by a Redis list.

The pairing step is a Lua script because it is inherently multi-step -- enqueue,
check the pool, take two out -- and Redis runs a script as one indivisible unit.
Doing the same with separate commands leaves a window where two callers both
see a full pool and claim the same opponent.
"""

from redis.asyncio import Redis

# Enqueue and take a pair in a single indivisible step.
#
# KEYS[1] = queue key
# ARGV[1] = user id joining
#
# LREM first so a reconnecting player is not left twice in the list -- without
# it a player with two sockets can be matched against themselves. It also means
# a reconnect goes to the back of the queue, which is the fair reading.
#
# Returns nil while the player waits, or exactly two user ids once a pair forms.
PAIR_SCRIPT = """
redis.call('LREM', KEYS[1], 0, ARGV[1])
redis.call('RPUSH', KEYS[1], ARGV[1])
if redis.call('LLEN', KEYS[1]) < 2 then
    return nil
end
return redis.call('LPOP', KEYS[1], 2)
"""


class MatchmakingQueue:
    """Waiting players, keyed by `User.id` (see vault decision 0001).

    The Redis client is injected so tests can hand in their own connection.

    >>> queue = MatchmakingQueue(Redis.from_url("redis://localhost:6379/2"))
    >>> await queue.join(7)      # alone, waits
    None
    >>> await queue.join(9)      # pool is full, pair leaves the queue
    (7, 9)
    """

    def __init__(self, redis: Redis, key: str = "matchmaking:queue") -> None:
        self._redis = redis
        self._key = key
        self._pair = redis.register_script(PAIR_SCRIPT)

    async def join(self, user_id: int) -> tuple[int, int] | None:
        """Enter the queue, returning the pair if this join completed one."""
        pair = await self._pair(keys=[self._key], args=[user_id])

        if not pair:
            return None

        return (int(pair[0]), int(pair[1]))

    async def leave(self, user_id: int) -> None:
        """Drop out of the queue. LREM is already atomic on its own."""
        await self._redis.lrem(self._key, 0, str(user_id))

    async def size(self) -> int:
        """Players currently waiting. For diagnostics, not for pairing."""
        return int(await self._redis.llen(self._key))
