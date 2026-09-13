"""FIFO waiting queue for matchmaking, backed by a Redis list plus a deck hash.

The pairing step is a Lua script because it is inherently multi-step -- enqueue,
store the deck, check the pool, take two out -- and Redis runs a script as one
indivisible unit. Doing the same with separate commands leaves a window where
two callers both see a full pool and claim the same opponent, or where a player
is in the list with no deck beside them.

**The deck travels with the entry.** The pair closes later, possibly in another
worker, so re-reading the deck at pairing time would let an edit between the
join and the pair produce a match different from the one that was validated --
or no match at all, if the deck was deleted. What was validated on the way in is
what the match uses.

Since feature 012 the entry carries the deck's **name** as well, so the match
record can say which deck a player won with after that deck has been renamed or
deleted. That is why the hash value is a JSON object and no longer a bare array.

The list still holds bare user ids, and the decks live in a parallel hash. That
is deliberate: `LREM` removes **by exact value**, and it is what keeps a
reconnecting player from sitting in the list twice. A JSON blob per entry would
break it -- a player rejoining with a different deck would no longer match the
value already in the list, and could be paired against themselves.
"""

import json
from dataclasses import dataclass

from redis.asyncio import Redis

from apps.game.cards import CardId
from apps.game.match import ChosenDeck

# Enqueue with the deck and take a pair in a single indivisible step.
#
# KEYS[1] = queue key          KEYS[2] = deck hash key
# ARGV[1] = user id joining    ARGV[2] = that player's deck, as a JSON object
#
# LREM first so a reconnecting player is not left twice in the list -- without
# it a player with two sockets can be matched against themselves. It also means
# a reconnect goes to the back of the queue, which is the fair reading, and the
# HSET that follows makes the newest join's deck the one that counts.
#
# The deck is stored before the pool is measured, so the pair that this very
# join completes always finds both decks in the hash.
#
# Returns nil while the player waits, or two user ids and their two decks once
# a pair forms.
PAIR_SCRIPT = """
redis.call('LREM', KEYS[1], 0, ARGV[1])
redis.call('RPUSH', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
if redis.call('LLEN', KEYS[1]) < 2 then
    return nil
end
local pair = redis.call('LPOP', KEYS[1], 2)
local decks = redis.call('HMGET', KEYS[2], pair[1], pair[2])
redis.call('HDEL', KEYS[2], pair[1], pair[2])
return {pair[1], pair[2], decks[1], decks[2]}
"""

# Leaving takes the whole entry: the place in the line and the deck beside it.
# Two commands, one script, so a leave can never strand a deck in the hash.
#
# KEYS[1] = queue key   KEYS[2] = deck hash key
# ARGV[1] = user id leaving
LEAVE_SCRIPT = """
redis.call('LREM', KEYS[1], 0, ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
"""


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """A player waiting, and the deck they were validated with.

    The two travel together for the same reason `MatchEntry` keeps profile and
    deck together: with them apart, handing one player's deck to the other is a
    mistake no type catches.

    >>> QueueEntry(user_id=7, deck=ChosenDeck("Agro", (CardId(1),))).user_id
    7
    """

    user_id: int
    deck: ChosenDeck


class QueuedDeckMissingError(Exception):
    """A pair came out of the queue with no deck for one of the two.

    Impossible state: the script writes the deck before it measures the pool,
    and only deletes it when the pair leaves. Raising names both players, so
    whoever reads the log knows which entry to look for.

    >>> raise QueuedDeckMissingError(7, 9)
    QueuedDeckMissingError: paired users (7, 9) came out of the queue without
    both decks
    """

    def __init__(self, first_user_id: int, second_user_id: int) -> None:
        super().__init__(
            f"paired users ({first_user_id}, {second_user_id}) came out of the "
            "queue without both decks"
        )
        self.user_ids = (first_user_id, second_user_id)


class MatchmakingQueue:
    """Waiting players and their decks, keyed by `User.id` (vault decision 0001).

    The Redis client is injected so tests can hand in their own connection.

    >>> queue = MatchmakingQueue(Redis.from_url("redis://localhost:6379/2"))
    >>> await queue.join(QueueEntry(7, deck))      # alone, waits
    None
    >>> await queue.join(QueueEntry(9, other))     # pool is full, pair leaves
    (QueueEntry(user_id=7, ...), QueueEntry(user_id=9, ...))
    """

    def __init__(self, redis: Redis, key: str = "matchmaking:queue") -> None:
        self._redis = redis
        self._key = key
        # Derived from the queue key so a test that namespaces one namespaces
        # both -- two keys that could drift apart would be a trap.
        self._deck_key = f"{key}:decks"
        self._pair = redis.register_script(PAIR_SCRIPT)
        self._leave = redis.register_script(LEAVE_SCRIPT)

    async def join(self, entry: QueueEntry) -> tuple[QueueEntry, QueueEntry] | None:
        """Enter the queue with a deck, returning the pair this join completed.

        Rejoining replaces the previous entry: the most recent deck is the one
        that counts.

        >>> await queue.join(QueueEntry(7, deck)) is None
        True
        """
        paired = await self._pair(
            keys=[self._key, self._deck_key],
            args=[entry.user_id, _encoded_deck(entry.deck)],
        )

        if not paired:
            return None

        return _paired_entries(paired)

    async def leave(self, user_id: int) -> None:
        """Drop out of the queue, deck and all."""
        await self._leave(keys=[self._key, self._deck_key], args=[user_id])

    async def size(self) -> int:
        """Players currently waiting. For diagnostics, not for pairing."""
        return int(await self._redis.llen(self._key))


def _encoded_deck(deck: ChosenDeck) -> str:
    """The deck as Redis stores it.

    The wire format lives here, not in the caller: the key layout is the
    wrapper's business, the way the Lua scripts are.

    An object and not a bare array since feature 012, so the name rides along.
    The queue list itself still holds bare user ids -- `LREM` removes by exact
    value, and that is what keeps a reconnecting player from sitting in the list
    twice.
    """
    return json.dumps({"name": deck.name, "card_ids": [int(c) for c in deck.card_ids]})


def _decoded_deck(encoded: bytes | str) -> ChosenDeck:
    """The deck as it went in: name, identifiers and order intact."""
    stored = json.loads(encoded)

    return ChosenDeck(
        name=stored["name"],
        card_ids=tuple(CardId(card_id) for card_id in stored["card_ids"]),
    )


def _paired_entries(paired: list[bytes | str]) -> tuple[QueueEntry, QueueEntry]:
    """The script's four values back into two entries.

    A missing deck raises instead of pairing half a match: `start_match` would
    refuse an empty deck anyway, and far from whoever caused it.
    """
    first_user_id, second_user_id = int(paired[0]), int(paired[1])

    if paired[2] is None or paired[3] is None:
        raise QueuedDeckMissingError(first_user_id, second_user_id)

    return (
        QueueEntry(user_id=first_user_id, deck=_decoded_deck(paired[2])),
        QueueEntry(user_id=second_user_id, deck=_decoded_deck(paired[3])),
    )
