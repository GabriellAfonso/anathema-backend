"""MatchStore runs against a real Redis: what is under test is that a match
survives the round trip through JSON and comes back usable from another
process. Uses a throwaway database so it never touches app data.
"""

import json

import pytest
from redis.asyncio import Redis

from apps.game.match import Match, MatchPhase, build_player_view
from apps.game.match.store import MATCH_TTL_SECONDS, MatchStore
from apps.game.tests.fake_match_state import fake_match_in_progress
from apps.game.tests.fake_player_data import fake_player_data

PLAYER_ONE = fake_player_data(7, "one")
PLAYER_TWO = fake_player_data(9, "two")
OUTSIDER = 99


@pytest.fixture
def store(redis: Redis) -> MatchStore:
    return MatchStore(redis, key_prefix="test:match")


async def stored_match(store: MatchStore, match: Match) -> Match:
    """Recarrega a partida, falhando o teste se ela sumiu do Redis."""
    reloaded = await store.get(match.match_id)
    assert reloaded is not None

    return reloaded


async def saved_in_progress(store: MatchStore) -> Match:
    """Uma partida com todas as zonas ocupadas, já gravada.

    O caminho de criação ainda produz zonas vazias — o setup da §3 é de outra
    feature —, e uma partida vazia sobrevive a qualquer serialização.
    """
    match = fake_match_in_progress()
    await store.save(match)

    return match


async def test_created_match_is_readable_again(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).match_id == match.match_id


async def test_unknown_match_is_none(store: MatchStore) -> None:
    assert await store.get("no-such-match") is None


async def test_public_profiles_survive_the_round_trip(store: MatchStore) -> None:
    """Quem reconecta precisa do apelido sem uma nova consulta ao banco."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    reloaded = await stored_match(store, match)

    assert [player.profile for player in reloaded.players] == [PLAYER_ONE, PLAYER_TWO]


async def test_participants_are_recognised_after_the_round_trip(
    store: MatchStore,
) -> None:
    """The gate in MatchConsumer reads this off a match it loaded from Redis."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    reloaded = await stored_match(store, match)

    assert reloaded.has_player(7)
    assert not reloaded.has_player(OUTSIDER)


async def test_a_created_match_starts_in_upkeep(store: MatchStore) -> None:
    """Válida e ainda não jogável: embaralhar e comprar é o setup da §3."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).phase is MatchPhase.UPKEEP


async def test_no_stored_json_object_is_keyed_by_user_id(
    store: MatchStore, redis: Redis
) -> None:
    """A armadilha do modelo anterior: chave de objeto JSON é sempre string, e
    `hands[7]` levantaria KeyError depois da volta.

    O formato novo não indexa nada por `user_id`, então não existe conversão a
    lembrar. A asserção é sobre o que está gravado, não sobre comportamento.
    """
    match = await saved_in_progress(store)

    raw = await redis.get(f"test:match:{match.match_id}")
    assert raw is not None

    assert not _numeric_keys(json.loads(raw))


async def test_user_ids_come_back_as_integers(store: MatchStore) -> None:
    """Eles continuam existindo; o que mudou é que são valores, não chaves."""
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert (await stored_match(store, match)).player(7).user_id == 7


async def test_a_full_match_comes_back_identical(store: MatchStore) -> None:
    match = await saved_in_progress(store)

    assert await stored_match(store, match) == match


async def test_card_identity_survives_the_round_trip(store: MatchStore) -> None:
    """Sem isto, um alvo na pilha apontaria para outra carta depois de a
    partida passar pelo Redis."""
    match = await saved_in_progress(store)

    reloaded = await stored_match(store, match)
    target = match.stack[0].target_card_instance_id
    assert target is not None

    assert reloaded.bank_unit(target) is not None


async def test_the_instance_counter_survives_the_round_trip(
    store: MatchStore,
) -> None:
    """Um contador de processo daria números repetidos entre workers."""
    match = await saved_in_progress(store)

    assert (
        await stored_match(store, match)
    ).next_card_instance_id == match.next_card_instance_id


async def test_the_player_view_works_after_the_round_trip(store: MatchStore) -> None:
    match = await saved_in_progress(store)

    view = build_player_view(await stored_match(store, match), 7)

    assert view["opponent"]["hand_size"] == len(match.player(9).hand)
    assert "hand" not in view["opponent"]


async def test_saved_state_replaces_the_stored_one(store: MatchStore) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)
    match.priority_user_id = 9

    await store.save(match)

    assert (await stored_match(store, match)).priority_user_id == 9


async def test_match_expires_so_abandoned_games_do_not_pile_up(
    store: MatchStore, redis: Redis
) -> None:
    match = await store.create(PLAYER_ONE, PLAYER_TWO)

    assert await redis.ttl(f"test:match:{match.match_id}") == MATCH_TTL_SECONDS


def _numeric_keys(node: object) -> list[str]:
    """Toda chave de objeto que pareça um identificador, em qualquer nível."""
    if isinstance(node, dict):
        here = [key for key in node if key.isdigit()]

        return here + [k for value in node.values() for k in _numeric_keys(value)]

    if isinstance(node, list):
        return [key for item in node for key in _numeric_keys(item)]

    return []
