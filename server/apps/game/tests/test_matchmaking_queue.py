"""MatchmakingQueue runs against a real Redis: the property under test is that
the Lua pairing step is indivisible, and only the real server can show that.
Uses a throwaway database so it never touches app data.

Since feature 011 the entry carries the deck, and the same script writes it.
The second property under test is therefore that the deck comes back out of the
pair exactly as it went in -- what was validated on the way in is what the match
uses.
"""

import asyncio

import pytest

from redis.asyncio import Redis

from apps.game.cards import CardId, Deck
from apps.game.matchmaking.queue import (
    MatchmakingQueue,
    QueuedDeckMissingError,
    QueueEntry,
)

# Listas curtas e distintas: o que está sob teste é o transporte da lista, não
# as três regras de deck -- a fila não valida nada.
ONE_DECK: Deck = (CardId(1), CardId(1), CardId(2))
TWO_DECK: Deck = (CardId(5), CardId(7))
OTHER_DECK: Deck = (CardId(9),)


@pytest.fixture
def queue(redis: Redis) -> MatchmakingQueue:
    return MatchmakingQueue(redis, key="test:matchmaking:queue")


def entry(user_id: int, deck: Deck = ONE_DECK) -> QueueEntry:
    return QueueEntry(user_id=user_id, deck=deck)


async def test_first_player_waits(queue: MatchmakingQueue) -> None:
    assert await queue.join(entry(1)) is None
    assert await queue.size() == 1


async def test_second_player_completes_the_pair(queue: MatchmakingQueue) -> None:
    await queue.join(entry(1))

    pair = await queue.join(entry(2, TWO_DECK))

    assert pair is not None
    assert (pair[0].user_id, pair[1].user_id) == (1, 2)


async def test_each_deck_comes_back_with_its_own_player(
    queue: MatchmakingQueue,
) -> None:
    """O que a feature 011 existe para garantir: a lista validada na entrada é
    a que sai no par, e é a de quem a mandou."""
    await queue.join(entry(1, ONE_DECK))

    pair = await queue.join(entry(2, TWO_DECK))

    assert pair == (
        QueueEntry(user_id=1, deck=ONE_DECK),
        QueueEntry(user_id=2, deck=TWO_DECK),
    )


async def test_the_deck_keeps_its_repetition_and_order(
    queue: MatchmakingQueue,
) -> None:
    repeated: Deck = (CardId(3), CardId(1), CardId(3), CardId(3))
    await queue.join(entry(1, repeated))

    pair = await queue.join(entry(2))

    assert pair is not None
    assert pair[0].deck == repeated


async def test_pair_leaves_the_queue(queue: MatchmakingQueue) -> None:
    await queue.join(entry(1))
    await queue.join(entry(2))

    assert await queue.size() == 0


async def test_pairing_is_first_in_first_out(queue: MatchmakingQueue) -> None:
    await queue.join(entry(1))
    await queue.join(entry(2))
    await queue.join(entry(3))

    pair = await queue.join(entry(4))

    assert pair is not None
    assert (pair[0].user_id, pair[1].user_id) == (3, 4)


async def test_rejoining_does_not_duplicate_the_player(
    queue: MatchmakingQueue,
) -> None:
    """A reconnect must not leave the player in the list twice -- otherwise the
    next join pairs them against themselves."""
    await queue.join(entry(1))

    assert await queue.join(entry(1)) is None
    assert await queue.size() == 1


async def test_rejoining_with_another_deck_replaces_the_first(
    queue: MatchmakingQueue,
) -> None:
    """Vale o deck da entrada mais recente."""
    await queue.join(entry(1, ONE_DECK))
    await queue.join(entry(1, OTHER_DECK))

    pair = await queue.join(entry(2))

    assert pair is not None
    assert pair[0].deck == OTHER_DECK


async def test_leave_removes_the_player(queue: MatchmakingQueue) -> None:
    await queue.join(entry(1))

    await queue.leave(1)

    assert await queue.size() == 0
    assert await queue.join(entry(2)) is None


async def test_leave_strands_no_deck(queue: MatchmakingQueue, redis: Redis) -> None:
    """Sair da fila tira a entrada inteira: lugar na fila e deck ao lado."""
    await queue.join(entry(1))

    await queue.leave(1)

    assert await redis.hlen("test:matchmaking:queue:decks") == 0


async def test_a_completed_pair_strands_no_deck(
    queue: MatchmakingQueue, redis: Redis
) -> None:
    await queue.join(entry(1))
    await queue.join(entry(2))

    assert await redis.hlen("test:matchmaking:queue:decks") == 0


async def test_a_pair_without_a_deck_is_refused_naming_both_players(
    queue: MatchmakingQueue, redis: Redis
) -> None:
    """Estado impossível pelo script, e mesmo assim nomeado: parear meia
    partida jogaria o erro em `start_match`, longe de quem o causou."""
    await queue.join(entry(1))
    await redis.hdel("test:matchmaking:queue:decks", "1")

    with pytest.raises(QueuedDeckMissingError) as refused:
        await queue.join(entry(2))

    assert refused.value.user_ids == (1, 2)


async def test_concurrent_joins_pair_everyone_exactly_once(
    queue: MatchmakingQueue,
) -> None:
    """The race the Lua script exists to close: with a read-modify-write the
    interleaving either drops a player or hands the same player to two
    matches."""
    players = list(range(1, 101))

    results = await asyncio.gather(*(queue.join(entry(p)) for p in players))

    pairs = [r for r in results if r is not None]
    matched = [paired.user_id for pair in pairs for paired in pair]

    assert len(pairs) == 50
    assert sorted(matched) == players
    assert await queue.size() == 0


async def test_concurrent_joins_never_mix_up_the_decks(
    queue: MatchmakingQueue,
) -> None:
    """Sob corrida, cada jogador continua saindo com o deck que mandou."""
    players = list(range(1, 101))

    results = await asyncio.gather(
        *(queue.join(entry(p, (CardId(p),))) for p in players)
    )

    for pair in [r for r in results if r is not None]:
        for paired in pair:
            assert paired.deck == (CardId(paired.user_id),)
