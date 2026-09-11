"""O estado de combate sobrevive à ida e à volta pela forma gravada.

As duas conexões de uma partida podem estar em workers diferentes do uvicorn: o
pareamento nasce numa ação e é lido em outra, possivelmente em outro processo.
Sem round-trip o combate só funciona com um worker, que não é como o servidor
roda.

Passa por `json.dumps` e `json.loads` no meio, e não só pelas duas funções de
serialização: é o JSON que impõe chave string, e é ele que quebraria um
pareamento guardado num dicionário indexado por identificador de carta.

O teste que carrega o arquivo é
`test_ending_the_window_from_a_rebuilt_match_gives_the_same_result`: a garantia
que importa não é a igualdade dos campos, é que a partida reconstruída **joga
igual**.
"""

import json

import pytest

from apps.game.cards import CardCatalog, CardId, mvp_catalog
from apps.game.engine import (
    AssignBlockerAction,
    EndDefenseWindowAction,
    submit_action,
)
from apps.game.match import (
    BlockAssignment,
    Match,
    MatchDocument,
    match_from_document,
    to_match_document,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    POLAROID,
    SKILLET,
    bank_card,
    declare_combat,
    fake_combat_board,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.match_snapshot import match_snapshot


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    """Três atacantes declarados, dois bloqueadores disponíveis."""
    board = fake_combat_board(
        catalog=catalog,
        bank_one=(DARK_AGE, MORTEM, POLAROID),
        bank_two=(SKILLET, POLAROID),
    )

    declare_combat(board, 0, 1, 2)

    return board


def through_json(match: Match) -> Match:
    """Ida e volta de verdade: o JSON é quem impõe chave string."""
    document: MatchDocument = json.loads(json.dumps(to_match_document(match)))

    return match_from_document(document)


def pair_up(match: Match, attacker_index: int, blocker_index: int) -> None:
    match.ongoing_combat().blocks.append(
        BlockAssignment(
            blocker_card_instance_id=bank_card(match.player(PLAYER_TWO), blocker_index),
            attacker_card_instance_id=bank_card(
                match.player(PLAYER_ONE), attacker_index
            ),
        )
    )


# --- Os atacantes ------------------------------------------------------------


def test_the_attackers_come_back_in_the_same_order(match: Match) -> None:
    before = list(match.ongoing_combat().attacker_card_instance_ids)

    rebuilt = through_json(match)

    assert rebuilt.ongoing_combat().attacker_card_instance_ids == before


def test_the_attacker_identifiers_come_back_as_identifiers(match: Match) -> None:
    """A volta reembrulha os inteiros, como `card_from_document` já faz."""
    rebuilt = through_json(match)

    assert all(
        isinstance(one, int)
        for one in rebuilt.ongoing_combat().attacker_card_instance_ids
    )


# --- O pareamento ------------------------------------------------------------


def test_each_blocker_stays_paired_with_the_same_attacker(match: Match) -> None:
    pair_up(match, 0, 0)
    pair_up(match, 1, 1)
    before = match.ongoing_combat()
    pairs = [
        (block.blocker_card_instance_id, block.attacker_card_instance_id)
        for block in before.blocks
    ]

    rebuilt = through_json(match)

    assert [
        (block.blocker_card_instance_id, block.attacker_card_instance_id)
        for block in rebuilt.ongoing_combat().blocks
    ] == pairs


def test_the_whole_match_is_equal_field_by_field(match: Match) -> None:
    pair_up(match, 0, 0)
    before = match_snapshot(match)

    assert match_snapshot(through_json(match)) == before


def test_no_json_object_is_keyed_by_a_card_identifier(match: Match) -> None:
    """O pareamento é lista de pares, e não `{"4": 3}`. Chave de JSON é sempre
    string, e um objeto indexado por identificador precisaria da conversão de
    volta que `documents.py` existe para não ter."""
    pair_up(match, 0, 0)
    combat = to_match_document(match)["combat"]

    assert combat is not None
    assert isinstance(combat["blocks"], list)
    assert set(combat["blocks"][0]) == {
        "blocker_card_instance_id",
        "attacker_card_instance_id",
    }


# --- A ausência --------------------------------------------------------------


def test_a_match_outside_the_combat_comes_back_without_one(
    catalog: CardCatalog,
) -> None:
    board = fake_combat_board(catalog=catalog)

    assert through_json(board).combat is None


def test_the_absence_is_distinguishable_from_an_empty_pairing(
    match: Match, catalog: CardCatalog
) -> None:
    """Dois estados legais e diferentes: combate sem bloqueador, e sem
    combate."""
    without = fake_combat_board(catalog=catalog)

    assert to_match_document(without)["combat"] is None

    combat = to_match_document(match)["combat"]

    assert combat is not None
    assert combat["blocks"] == []


# --- Joga igual --------------------------------------------------------------


def test_ending_the_window_from_a_rebuilt_match_gives_the_same_result(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A garantia que importa: a partida reconstruída joga igual."""
    pair_up(match, 0, 0)

    rebuilt = through_json(match)

    for one in (match, rebuilt):
        submit_action(
            one,
            EndDefenseWindowAction(actor_user_id=PLAYER_TWO),
            catalog=catalog,
            randomness=source,
        )

    assert match_snapshot(rebuilt) == match_snapshot(match)


def test_blocking_from_a_rebuilt_match_still_works(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    rebuilt = through_json(match)
    blocker = bank_card(rebuilt.player(PLAYER_TWO))
    attacker = bank_card(rebuilt.player(PLAYER_ONE))

    submit_action(
        rebuilt,
        AssignBlockerAction(
            actor_user_id=PLAYER_TWO,
            blocker_card_instance_id=blocker,
            attacker_card_instance_id=attacker,
        ),
        catalog=catalog,
        randomness=source,
    )

    assert rebuilt.ongoing_combat().blocker_of(attacker) == blocker
