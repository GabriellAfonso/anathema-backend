"""O setup precisa ser repetível, senão nenhum teste do resto do motor é.

Combate, feitiço e compra partem todos de uma partida montada pelo setup. Se
duas execuções com as mesmas entradas divergirem, todo teste que dependa da
mão inicial vira sorteio.

A aleatoriedade é endereçada por `(semente, ordinal do sorteio)`, e os dois
vivem no estado -- é isso que faz o mulligan que chega depois de a partida ir
ao Redis e voltar continuar a mesma sequência.
"""

import json

import pytest

from apps.game.cards import mvp_catalog, starter_deck
from apps.game.engine import MatchEntry, record_mulligan, start_match
from apps.game.match import CardInstanceId, Match, MatchPhase
from apps.game.match.serialization import match_from_document, to_match_document
from apps.game.randomness import (
    EmptyOptionsError,
    RandomSeed,
    Roll,
    SeededRandomSource,
)
from apps.game.tests.fake_player_data import fake_player_data

PLAYER_ONE = 7
PLAYER_TWO = 9

SEED = RandomSeed("repeatable")
OTHER_SEED = RandomSeed("something-else")
MATCH_ID = "fixed-match-id"


# --- A fonte semeada ------------------------------------------------------


def test_the_same_roll_gives_the_same_result_in_a_fresh_instance() -> None:
    """Duas instâncias, dois processos: o resultado é do par, não do objeto."""
    roll = Roll(SEED, 1)

    assert SeededRandomSource().shuffled(
        range(20), roll
    ) == SeededRandomSource().shuffled(range(20), roll)


def test_different_rolls_of_the_same_seed_differ() -> None:
    """Sem isto, embaralhar o deck dos dois jogadores daria a mesma ordem."""
    source = SeededRandomSource()

    first = source.shuffled(range(20), Roll(SEED, 1))
    second = source.shuffled(range(20), Roll(SEED, 2))

    assert first != second


def test_shuffling_is_an_exact_permutation() -> None:
    source = SeededRandomSource()

    shuffled = source.shuffled(range(40), Roll(SEED, 1))

    assert sorted(shuffled) == list(range(40))


def test_the_original_sequence_is_not_touched() -> None:
    original = [1, 2, 3, 4, 5]

    SeededRandomSource().shuffled(original, Roll(SEED, 1))

    assert original == [1, 2, 3, 4, 5]


def test_choosing_from_nothing_is_refused_naming_the_roll() -> None:
    with pytest.raises(EmptyOptionsError, match="roll 1"):
        SeededRandomSource().choose([], Roll(SEED, 1))


# --- O setup inteiro ------------------------------------------------------


def run_setup(
    seed: RandomSeed = SEED, arrival: tuple[int, int] = (PLAYER_ONE, PLAYER_TWO)
) -> Match:
    """Setup completo, do zero ao Upkeep, com o `match_id` fixado.

    O `match_id` é um `uuid4` fora do alcance da semente, e compará-lo faria
    duas partidas idênticas parecerem diferentes por um campo que esta
    propriedade não promete.
    """
    catalog = mvp_catalog()
    deck = starter_deck(catalog)
    source = SeededRandomSource()

    match = start_match(
        MatchEntry(profile=fake_player_data(PLAYER_ONE, "one"), deck=deck),
        MatchEntry(profile=fake_player_data(PLAYER_TWO, "two"), deck=deck),
        catalog=catalog,
        randomness=source,
        seed=seed,
    )
    match.match_id = MATCH_ID

    for user_id in arrival:
        record_mulligan(match, user_id, _first_two(match, user_id), randomness=source)

    return match


def test_the_same_seed_produces_the_very_same_match() -> None:
    assert run_setup() == run_setup()


def test_a_different_seed_produces_a_different_match() -> None:
    """A semente é o que decide -- não uma ordem fixa escondida no código."""
    assert run_setup() != run_setup(seed=OTHER_SEED)


def test_the_arrival_order_is_part_of_the_input() -> None:
    """Cada mulligan roda na chegada, então os dois consomem a sequência na
    ordem em que responderam. É comportamento definido, não corrida."""
    assert run_setup() != run_setup(arrival=(PLAYER_TWO, PLAYER_ONE))


def test_the_setup_finishes_the_same_after_a_round_trip() -> None:
    """O caso que a semente no estado existe para resolver: o segundo mulligan
    chega em outro worker, sobre uma partida recarregada do Redis."""
    straight = run_setup()

    assert _setup_across_a_round_trip() == straight


def _setup_across_a_round_trip() -> Match:
    """Grava depois do primeiro mulligan e recarrega antes do segundo."""
    catalog = mvp_catalog()
    deck = starter_deck(catalog)
    source = SeededRandomSource()

    match = start_match(
        MatchEntry(profile=fake_player_data(PLAYER_ONE, "one"), deck=deck),
        MatchEntry(profile=fake_player_data(PLAYER_TWO, "two"), deck=deck),
        catalog=catalog,
        randomness=source,
        seed=SEED,
    )
    match.match_id = MATCH_ID

    record_mulligan(match, PLAYER_ONE, _first_two(match, PLAYER_ONE), randomness=source)

    reloaded = match_from_document(json.loads(json.dumps(to_match_document(match))))

    record_mulligan(
        reloaded, PLAYER_TWO, _first_two(reloaded, PLAYER_TWO), randomness=source
    )

    return reloaded


def test_the_repeatable_setup_is_actually_finished() -> None:
    """Uma propriedade sobre duas partidas iguais não vale nada se as duas
    pararam no mesmo ponto errado."""
    match = run_setup()

    assert match.phase is MatchPhase.UPKEEP
    assert match.token_holder_user_id is not None


def _first_two(match: Match, user_id: int) -> list[CardInstanceId]:
    """Uma escolha de mulligan qualquer, mas a mesma nas duas execuções."""
    return [card.card_instance_id for card in match.player(user_id).hand[:2]]
