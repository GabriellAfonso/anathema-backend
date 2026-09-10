"""O estado da partida carrega os campos da §2 e sabe quem joga.

Substitui test_match_model.py, que cobria o `Match` de brinquedo.
"""

import pytest

from apps.game.match import Match, MatchPhase, NotAParticipantError, STARTING_NEXUS
from apps.game.tests.fake_match_state import (
    OUTSIDER,
    PLAYER_ONE,
    PLAYER_TWO,
    fake_new_match,
)


@pytest.fixture
def match() -> Match:
    return fake_new_match()


def test_new_match_starts_on_round_one(match: Match) -> None:
    assert match.round_number == 1


def test_new_match_starts_in_upkeep(match: Match) -> None:
    assert match.phase is MatchPhase.UPKEEP


def test_the_five_phases_of_the_flow_note_exist() -> None:
    """§2 lista cinco fases. Um sexto valor não pode ser representável."""
    assert [phase.value for phase in MatchPhase] == [
        "upkeep",
        "action",
        "stack_resolution",
        "combat",
        "round_end",
    ]


def test_token_starts_unconsumed(match: Match) -> None:
    assert not match.token_consumed


def test_priority_starts_with_the_token_holder(match: Match) -> None:
    assert match.priority_user_id == match.token_holder_user_id


def test_token_holder_is_a_user_id_not_a_list_index(match: Match) -> None:
    """A §2 nomeia o dono do token por jogador, e a identidade é `user_id`."""
    assert match.token_holder_user_id == PLAYER_ONE


def test_new_match_has_no_passes(match: Match) -> None:
    assert match.consecutive_passes == 0


def test_new_match_has_an_empty_stack(match: Match) -> None:
    assert match.stack == []


def test_instance_counter_starts_at_one(match: Match) -> None:
    assert match.next_card_instance_id == 1


def test_both_players_start_at_full_nexus(match: Match) -> None:
    assert [player.nexus for player in match.players] == [
        STARTING_NEXUS,
        STARTING_NEXUS,
    ]


def test_both_players_start_without_energy(match: Match) -> None:
    """Energia sobe no primeiro Upkeep, então a rodada 1 tem 1 (§4)."""
    player = match.player(PLAYER_ONE)

    assert (player.energy_max, player.energy_current) == (0, 0)


def test_every_card_zone_starts_empty(match: Match) -> None:
    """Embaralhar e comprar é o setup da §3, de outra feature."""
    player = match.player(PLAYER_ONE)

    assert (player.deck, player.hand, player.bank, player.graveyard) == ([], [], [], [])


def test_player_state_knows_its_user_id(match: Match) -> None:
    """Derivado do perfil, não campo duplicado que possa divergir."""
    assert match.player(PLAYER_TWO).user_id == PLAYER_TWO


def test_public_profile_survives_in_the_state(match: Match) -> None:
    """Quem reconecta precisa do apelido sem uma nova consulta ao banco."""
    assert match.player(PLAYER_ONE).profile["nickname"] == "one"


def test_first_player_is_a_participant(match: Match) -> None:
    assert match.has_player(PLAYER_ONE)


def test_second_player_is_a_participant(match: Match) -> None:
    assert match.has_player(PLAYER_TWO)


def test_outsider_is_not_a_participant(match: Match) -> None:
    assert not match.has_player(OUTSIDER)


def test_missing_user_id_is_not_a_participant(match: Match) -> None:
    """A socket with no authenticated user must never pass the gate."""
    assert not match.has_player(None)


def test_player_lookup_returns_that_players_state(match: Match) -> None:
    assert match.player(PLAYER_TWO).profile["nickname"] == "two"


def test_opponent_lookup_returns_the_other_player(match: Match) -> None:
    assert match.opponent_of(PLAYER_ONE).user_id == PLAYER_TWO


def test_opponent_lookup_works_from_either_side(match: Match) -> None:
    assert match.opponent_of(PLAYER_TWO).user_id == PLAYER_ONE


def test_player_lookup_refuses_an_outsider_by_naming_them(match: Match) -> None:
    """A constituição exige o valor ofensor na mensagem."""
    with pytest.raises(NotAParticipantError, match=str(OUTSIDER)):
        match.player(OUTSIDER)


def test_opponent_lookup_refuses_an_outsider_by_naming_them(match: Match) -> None:
    with pytest.raises(NotAParticipantError, match=str(OUTSIDER)):
        match.opponent_of(OUTSIDER)


def test_refusal_names_the_match_too(match: Match) -> None:
    with pytest.raises(NotAParticipantError, match=match.match_id):
        match.player(OUTSIDER)


def test_two_matches_do_not_share_an_id() -> None:
    assert fake_new_match().match_id != fake_new_match().match_id
