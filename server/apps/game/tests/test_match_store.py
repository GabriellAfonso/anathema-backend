"""MatchStore runs against a real Redis: what is under test is that a match
survives the round trip through JSON and comes back usable from another
process. Uses a throwaway database so it never touches app data.

O compare-and-swap de `mutate` também é contrato de Redis, e por isso mora
aqui e não num teste de unidade: o que ele promete só é observável com duas
escritas de verdade disputando a mesma chave.
"""

import asyncio
import json

import pytest
from redis.asyncio import Redis

from apps.game.engine import record_mulligan
from apps.game.match import Match, MatchPhase, build_player_view
from apps.game.cards import mvp_catalog
from apps.game.match.store import (
    MATCH_TTL_SECONDS,
    ConcurrentMatchWriteError,
    MatchChange,
    MatchNotFoundError,
    MatchStore,
)
from apps.game.protocol import MulliganCommand, apply_command
from apps.game.tests.fake_match_state import fake_match_in_progress
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match

PLAYER_ONE = 7
PLAYER_TWO = 9
OUTSIDER = 99


class AlwaysStaleMatchStore(MatchStore):
    """Store em que uma escrita alheia cai entre toda leitura e toda gravação.

    Subclasse, e não monkeypatch: a interferência tem nome, e o que ela
    substitui é exatamente o ponto que o compare-and-swap protege.
    """

    async def _swap_state(
        self, match_id: str, version: bytes | str, match: Match
    ) -> int:
        await self.save(match)

        return await super()._swap_state(match_id, version, match)


@pytest.fixture
def store(redis: Redis) -> MatchStore:
    return MatchStore(redis, key_prefix="test:match")


async def saved_new_match(store: MatchStore) -> Match:
    """Uma partida recém-montada pelo setup, já gravada."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    await store.save(match)

    return match


async def saved_in_progress(store: MatchStore) -> Match:
    """Uma partida com todas as zonas ocupadas, já gravada.

    A partida do setup tem deck e mão, mas não tem banco, cemitério nem
    modificador -- e zona vazia passa em qualquer serialização.
    """
    match = fake_match_in_progress()
    await store.save(match)

    return match


async def stored_match(store: MatchStore, match: Match) -> Match:
    """Recarrega a partida, falhando o teste se ela sumiu do Redis."""
    reloaded = await store.get(match.match_id)
    assert reloaded is not None

    return reloaded


async def test_saved_match_is_readable_again(store: MatchStore) -> None:
    match = await saved_new_match(store)

    assert (await stored_match(store, match)).match_id == match.match_id


async def test_unknown_match_is_none(store: MatchStore) -> None:
    assert await store.get("no-such-match") is None


async def test_public_profiles_survive_the_round_trip(store: MatchStore) -> None:
    """Quem reconecta precisa do apelido sem uma nova consulta ao banco."""
    match = await saved_new_match(store)

    reloaded = await stored_match(store, match)

    assert [player.profile for player in reloaded.players] == [
        player.profile for player in match.players
    ]


async def test_participants_are_recognised_after_the_round_trip(
    store: MatchStore,
) -> None:
    """The gate in MatchConsumer reads this off a match it loaded from Redis."""
    match = await saved_new_match(store)

    reloaded = await stored_match(store, match)

    assert reloaded.has_player(PLAYER_ONE)
    assert not reloaded.has_player(OUTSIDER)


async def test_a_created_match_waits_for_the_mulligan(store: MatchStore) -> None:
    """O setup da §3 para na espera: o Upkeep da Rodada 1 é de outra feature."""
    match = await saved_new_match(store)

    reloaded = await stored_match(store, match)

    assert reloaded.phase is MatchPhase.MULLIGAN
    assert reloaded.token_holder_user_id is None


async def test_the_pending_mulligan_survives_the_round_trip(
    store: MatchStore,
) -> None:
    """Sem isto, a partida volta do Redis sem saber de quem está esperando, e
    o setup trava com um jogador que já respondeu."""
    match = await saved_new_match(store)
    record_mulligan(match, PLAYER_ONE, [], randomness=ScriptedRandomSource())
    await store.save(match)

    reloaded = await stored_match(store, match)

    assert reloaded.awaiting_mulligan_user_ids == (PLAYER_TWO,)
    assert reloaded.phase is MatchPhase.MULLIGAN


async def test_the_seed_and_the_roll_counter_survive_the_round_trip(
    store: MatchStore,
) -> None:
    """É o par que deixa outro worker continuar a mesma sequência de sorteios."""
    match = await saved_new_match(store)

    reloaded = await stored_match(store, match)

    assert reloaded.random_seed == match.random_seed
    assert reloaded.next_roll_ordinal == match.next_roll_ordinal


async def test_no_stored_json_object_is_keyed_by_user_id(
    store: MatchStore, redis: Redis
) -> None:
    """A armadilha do modelo anterior: chave de objeto JSON é sempre string, e
    `hands[7]` levantaria KeyError depois da volta.

    O formato novo não indexa nada por `user_id`, então não existe conversão a
    lembrar. A asserção é sobre o que está gravado, não sobre comportamento.
    """
    match = await saved_in_progress(store)

    raw = await redis.hget(f"test:match:{match.match_id}", "state")
    assert raw is not None

    assert not _numeric_keys(json.loads(raw))


async def test_user_ids_come_back_as_integers(store: MatchStore) -> None:
    """Eles continuam existindo; o que mudou é que são valores, não chaves."""
    match = await saved_new_match(store)

    assert (await stored_match(store, match)).player(PLAYER_ONE).user_id == PLAYER_ONE


async def test_a_full_match_comes_back_identical(store: MatchStore) -> None:
    match = await saved_in_progress(store)

    assert await stored_match(store, match) == match


async def test_card_identity_survives_the_round_trip(store: MatchStore) -> None:
    """Sem isto, o alvo de um feitiço ou de um bloqueio apontaria para outra
    carta depois de a partida passar pelo Redis."""
    match = await saved_in_progress(store)

    reloaded = await stored_match(store, match)
    target = match.players[0].bank[0].card.card_instance_id

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
    match = await saved_new_match(store)
    match.consecutive_passes = 2

    await store.save(match)

    assert (await stored_match(store, match)).consecutive_passes == 2


async def test_match_expires_so_abandoned_games_do_not_pile_up(
    store: MatchStore, redis: Redis
) -> None:
    match = await saved_new_match(store)

    assert await redis.ttl(f"test:match:{match.match_id}") == MATCH_TTL_SECONDS


async def test_mutate_applies_the_change_and_stores_it(store: MatchStore) -> None:
    match = await saved_new_match(store)
    source = ScriptedRandomSource()

    await store.mutate(
        match.match_id,
        lambda live: record_mulligan(live, PLAYER_ONE, [], randomness=source),
    )

    assert (await stored_match(store, match)).awaiting_mulligan_user_ids == (
        PLAYER_TWO,
    )


async def test_save_returns_the_first_version(store: MatchStore) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    assert await store.save(match) == 1


async def test_get_stored_reads_the_match_and_its_version(store: MatchStore) -> None:
    match = await saved_new_match(store)

    stored = await store.get_stored(match.match_id)

    assert stored is not None
    assert (stored.match, stored.version) == (match, 1)


async def test_get_stored_of_an_unknown_match_is_none(store: MatchStore) -> None:
    assert await store.get_stored("no-such-match") is None


async def test_mutate_returns_the_written_match_and_version(
    store: MatchStore,
) -> None:
    """A versão devolvida é a posição da mudança que o socket de partida manda
    ao cliente (feature 009)."""
    match = await saved_new_match(store)

    first = await store.mutate(match.match_id, _bump_passes)
    second = await store.mutate(match.match_id, _bump_passes)

    assert (first.version, second.version) == (2, 3)
    assert second.match.consecutive_passes == 2


async def test_mutate_of_an_unknown_match_is_refused(store: MatchStore) -> None:
    with pytest.raises(MatchNotFoundError, match="no-such-match"):
        await store.mutate("no-such-match", lambda live: None)


async def test_a_raise_inside_the_change_stores_nothing(store: MatchStore) -> None:
    """É assim que uma recusa de mulligan deixa o estado exatamente como
    estava: a exceção sobe antes de o script de escrita rodar."""
    match = await saved_new_match(store)

    def refuse(live: Match) -> None:
        live.consecutive_passes = 2
        raise ValueError("mudei de ideia")

    with pytest.raises(ValueError):
        await store.mutate(match.match_id, refuse)

    assert (await stored_match(store, match)).consecutive_passes == 0


async def test_the_write_version_advances_on_every_write(
    store: MatchStore, redis: Redis
) -> None:
    """A versão é o que o compare-and-swap compara. Ela é versão de escrita, e
    não de esquema -- esquema continua sem número."""
    match = await saved_new_match(store)
    key = f"test:match:{match.match_id}"

    await store.mutate(match.match_id, lambda live: None)

    version = await redis.hget(key, "version")
    assert version is not None

    assert int(version) == 2


async def test_a_stale_version_is_refused_by_the_swap(
    store: MatchStore, redis: Redis
) -> None:
    """O caso que o compare-and-swap existe para pegar, no nível do script:
    a versão lida não é mais a que está lá, e a gravação não acontece."""
    match = await saved_new_match(store)
    key = f"test:match:{match.match_id}"
    stale = await redis.hget(key, "version")
    assert stale is not None

    await store.save(match)

    assert not await store._swap_state(match.match_id, stale, match)


async def test_endless_interference_gives_up_instead_of_looping(
    redis: Redis,
) -> None:
    """Com dois escritores a retentativa sempre fecha. Este é o caso que não
    fecha nunca, e o que se prova é que ele para em vez de girar."""
    store = AlwaysStaleMatchStore(redis, key_prefix="test:match")
    match = await saved_new_match(store)

    with pytest.raises(ConcurrentMatchWriteError, match=match.match_id):
        await store.mutate(match.match_id, _bump_passes)


async def test_two_concurrent_mulligans_both_land(store: MatchStore) -> None:
    """O mulligan é a única coisa simultânea da partida, e as duas respostas
    chegam por conexões diferentes -- possivelmente em workers diferentes.

    Sem o compare-and-swap uma das duas gravações sobrescreve a outra, e a
    partida fica esperando para sempre um jogador que já respondeu.
    """
    match = await saved_new_match(store)
    source = ScriptedRandomSource()

    await asyncio.gather(
        store.mutate(
            match.match_id,
            lambda live: record_mulligan(live, PLAYER_ONE, [], randomness=source),
        ),
        store.mutate(
            match.match_id,
            lambda live: record_mulligan(live, PLAYER_TWO, [], randomness=source),
        ),
    )

    final = await stored_match(store, match)

    assert final.awaiting_mulligan_user_ids == ()
    assert final.phase is MatchPhase.UPKEEP


async def test_two_workers_closing_the_setup_at_once_reach_round_one(
    redis: Redis,
) -> None:
    """Dois workers, cada um com o seu `MatchStore`, aplicando os dois
    mulligans do protocolo ao mesmo tempo (feature 009, SC-007).

    O comando do segundo mulligan executa o Upkeep da Rodada 1 dentro da
    mesma mutação: quem perder a disputa é reaplicado sobre o estado que o
    outro deixou, e a partida chega à Rodada 1 com os dois mulligans.
    """
    first_worker = MatchStore(redis, key_prefix="test:match")
    second_worker = MatchStore(redis, key_prefix="test:match")
    match = await saved_new_match(first_worker)
    catalog = mvp_catalog()

    def mulligan_of(user_id: int) -> MatchChange:
        return lambda live: apply_command(
            live,
            MulliganCommand(user_id, ()),
            catalog=catalog,
            randomness=ScriptedRandomSource(),
        )

    await asyncio.gather(
        first_worker.mutate(match.match_id, mulligan_of(PLAYER_ONE)),
        second_worker.mutate(match.match_id, mulligan_of(PLAYER_TWO)),
    )

    final = await stored_match(first_worker, match)
    assert (final.phase, final.round_number) == (MatchPhase.ACTION, 1)
    assert final.awaiting_mulligan_user_ids == ()


def _bump_passes(live: Match) -> None:
    live.consecutive_passes += 1


def _numeric_keys(node: object) -> list[str]:
    """Toda chave de objeto que pareça um identificador, em qualquer nível."""
    if isinstance(node, dict):
        here = [key for key in node if key.isdigit()]

        return here + [k for value in node.values() for k in _numeric_keys(value)]

    if isinstance(node, list):
        return [key for item in node for key in _numeric_keys(item)]

    return []
