"""Cada comando chega à porta certa do motor, e o fim do setup acontece sozinho.

O teste que carrega o arquivo é `test_the_second_mulligan_opens_round_one`:
sem o empurrão dentro do comando, a partida pararia em `UPKEEP` esperando uma
terceira mensagem que nenhum cliente sabe que precisa mandar (FR-009).
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import MulliganAlreadyTakenError, NotYourPriorityError, PassAction
from apps.game.match import Match, MatchEndReason, MatchPhase
from apps.game.protocol import ForfeitCommand, MulliganCommand, apply_command
from apps.game.protocol.commands import command_author
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase, fake_started_match

PLAYER_ONE = 7
PLAYER_TWO = 9


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def apply(
    match: Match,
    command: MulliganCommand | ForfeitCommand | PassAction,
    catalog: CardCatalog,
    source: RandomSource,
) -> None:
    apply_command(match, command, catalog=catalog, randomness=source)


def test_the_first_mulligan_keeps_the_match_waiting(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    apply(match, MulliganCommand(PLAYER_ONE, ()), catalog, source)

    assert match.phase is MatchPhase.MULLIGAN
    assert match.awaiting_mulligan_user_ids == (PLAYER_TWO,)


def test_the_second_mulligan_opens_round_one(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sorteio, compensação e o Upkeep da Rodada 1 no mesmo comando."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    apply(match, MulliganCommand(PLAYER_ONE, ()), catalog, source)

    apply(match, MulliganCommand(PLAYER_TWO, ()), catalog, source)

    assert (match.phase, match.round_number) == (MatchPhase.ACTION, 1)
    assert [player.energy_current for player in match.players] == [1, 1]
    assert match.priority_user_id == match.token_holder_user_id


def test_the_mulligan_swaps_the_cards_it_names(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    one = match.player(PLAYER_ONE)
    returned = one.hand[0].card_instance_id

    apply(match, MulliganCommand(PLAYER_ONE, (returned,)), catalog, source)

    assert returned not in [card.card_instance_id for card in one.hand]
    assert len(one.hand) == 4


def test_a_repeated_mulligan_is_the_engine_refusal(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    apply(match, MulliganCommand(PLAYER_ONE, ()), catalog, source)

    with pytest.raises(MulliganAlreadyTakenError):
        apply(match, MulliganCommand(PLAYER_ONE, ()), catalog, source)


def test_forfeit_ends_the_match(catalog: CardCatalog, source: RandomSource) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    apply(match, ForfeitCommand(PLAYER_TWO), catalog, source)

    assert match.outcome is not None
    assert (match.outcome.defeated_user_id, match.outcome.reason) == (
        PLAYER_TWO,
        MatchEndReason.FORFEIT,
    )


def test_an_action_goes_through_the_engine_door(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    holder = match.priority_user_id
    assert holder is not None

    apply(match, PassAction(holder), catalog, source)

    assert match.consecutive_passes == 1


def test_an_engine_refusal_passes_through_untouched(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    holder = match.priority_user_id
    assert holder is not None

    with pytest.raises(NotYourPriorityError):
        apply(match, PassAction(match.opponent_of(holder).user_id), catalog, source)


def test_the_author_of_every_command_family() -> None:
    assert [
        command_author(MulliganCommand(PLAYER_ONE, ())),
        command_author(ForfeitCommand(PLAYER_TWO)),
        command_author(PassAction(PLAYER_ONE)),
    ] == [PLAYER_ONE, PLAYER_TWO, PLAYER_ONE]
