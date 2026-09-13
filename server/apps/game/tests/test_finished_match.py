"""A derivação do resultado: transição registra, observação não.

Puro, sem banco e sem Redis. É aqui que o "exatamente uma vez" começa: a
pergunta é sobre uma **transição**, e uma transição acontece uma vez. Quem lê
uma partida já terminada não tem transição para mostrar, e não registra.
"""

from copy import deepcopy

import pytest

from apps.game.cards import CardId
from apps.game.engine import change_nexus, forfeit
from apps.game.history import finished_match
from apps.game.match import ChosenDeck, Match, MatchEndReason
from apps.game.tests.fake_chosen_deck import fake_chosen_deck
from apps.game.tests.fake_setup import (
    fake_match_in_action_phase,
    fake_started_match,
)
from apps.game.wall_clock import EpochMillis

PLAYER_ONE = 7
PLAYER_TWO = 9

STARTED_AT = EpochMillis(1_700_000_000_000)
ENDED_AT = EpochMillis(1_700_000_742_000)


@pytest.fixture
def match() -> Match:
    running = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    running.started_at = STARTED_AT

    return running


def test_a_running_match_produces_nothing(match: Match) -> None:
    """Sem desfecho não há o que registrar."""
    assert finished_match(deepcopy(match), match, ENDED_AT) is None


def test_a_nexus_defeat_names_the_loser_and_the_reason(match: Match) -> None:
    before = deepcopy(match)
    change_nexus(match, match.player(PLAYER_TWO), -20)

    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.match_id == match.match_id
    assert finished.reason is MatchEndReason.NEXUS_DEPLETED
    assert finished.loser.user_id == PLAYER_TWO
    assert finished.winner.user_id == PLAYER_ONE


def test_the_winner_is_derived_from_the_opponent(match: Match) -> None:
    """`MatchOutcome` não tem campo de vencedor, e este não inventa um."""
    before = deepcopy(match)
    forfeit(match, PLAYER_ONE)

    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert (finished.loser.user_id, finished.winner.user_id) == (PLAYER_ONE, PLAYER_TWO)


def test_a_forfeit_names_its_own_reason(match: Match) -> None:
    """Quem desiste com 20 de Nexus perdeu igual, e o motivo diz qual foi."""
    before = deepcopy(match)
    forfeit(match, PLAYER_TWO)

    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.reason is MatchEndReason.FORFEIT
    assert finished.loser.final_nexus == 20


def test_the_duration_is_the_span_between_the_two_instants(match: Match) -> None:
    before = deepcopy(match)
    forfeit(match, PLAYER_ONE)

    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert (finished.started_at, finished.ended_at) == (STARTED_AT, ENDED_AT)
    assert finished.duration_seconds == 742


def test_a_match_without_a_start_records_a_zero_duration() -> None:
    """Partida gravada antes da feature 012 e ainda dentro do TTL de 6 horas."""
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    assert match.started_at is None
    before = deepcopy(match)

    forfeit(match, PLAYER_ONE)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.started_at == ENDED_AT
    assert finished.duration_seconds == 0


def test_a_clock_that_walked_backwards_never_gives_a_negative_duration(
    match: Match,
) -> None:
    """Dois workers, dois relógios de parede. Duração negativa é ruído, não fato."""
    before = deepcopy(match)
    forfeit(match, PLAYER_ONE)

    finished = finished_match(before, match, EpochMillis(STARTED_AT - 5_000))

    assert finished is not None
    assert finished.duration_seconds == 0


def test_the_final_round_is_the_round_it_ended_in(match: Match) -> None:
    match.round_number = 8
    before = deepcopy(match)

    forfeit(match, PLAYER_ONE)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.final_round == 8


def test_a_forfeit_during_the_mulligan_records_the_first_round() -> None:
    """Desistir antes da Rodada 1 registra igual, na primeira rodada."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.started_at = STARTED_AT
    before = deepcopy(match)

    forfeit(match, PLAYER_ONE)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.final_round == 1
    assert finished.reason is MatchEndReason.FORFEIT


def test_the_final_nexus_of_both_sides_is_carried(match: Match) -> None:
    change_nexus(match, match.player(PLAYER_ONE), -5)
    before = deepcopy(match)

    change_nexus(match, match.player(PLAYER_TWO), -20)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.winner.final_nexus == 15
    assert finished.loser.final_nexus == 0


def test_each_side_carries_the_deck_it_entered_the_queue_with() -> None:
    one = fake_chosen_deck(name="Agro")
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, deck=one.card_ids)
    match.player(PLAYER_TWO).chosen_deck = ChosenDeck(
        name="Controle", card_ids=(CardId(1), CardId(2))
    )
    before = deepcopy(match)

    forfeit(match, PLAYER_TWO)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert finished.winner.deck_name == "Fake Deck"
    assert finished.winner.deck_card_ids == one.card_ids
    assert finished.loser.deck_name == "Controle"
    assert finished.loser.deck_card_ids == (CardId(1), CardId(2))


def test_a_side_without_a_chosen_deck_records_an_empty_one(match: Match) -> None:
    """Documento anterior à feature 012: registra vazio em vez de recusar."""
    match.player(PLAYER_ONE).chosen_deck = None
    before = deepcopy(match)

    forfeit(match, PLAYER_TWO)
    finished = finished_match(before, match, ENDED_AT)

    assert finished is not None
    assert (finished.winner.deck_name, finished.winner.deck_card_ids) == ("", ())


# --- Observação nunca registra ----------------------------------------------


def test_a_match_that_was_already_over_produces_nothing(match: Match) -> None:
    """A leitura de uma partida terminada. É o coração do exatamente-uma-vez."""
    forfeit(match, PLAYER_ONE)
    already_over = deepcopy(match)

    assert finished_match(already_over, match, ENDED_AT) is None


def test_reading_the_same_finished_match_again_and_again_produces_nothing(
    match: Match,
) -> None:
    forfeit(match, PLAYER_ONE)
    finished = deepcopy(match)

    for _ in range(20):
        assert finished_match(finished, deepcopy(match), ENDED_AT) is None
