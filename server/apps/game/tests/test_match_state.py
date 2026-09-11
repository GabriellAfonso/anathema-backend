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


def test_new_match_starts_waiting_for_the_mulligan(match: Match) -> None:
    """A partida nasce na espera da §3, não no Upkeep: o Upkeep da Rodada 1 só
    chega depois de os dois jogadores responderem o mulligan."""
    assert match.phase is MatchPhase.MULLIGAN


def test_the_phase_set_is_closed(match: Match) -> None:
    """As cinco fases da §2, mais a espera do setup e o fim da partida.

    `MULLIGAN` não é uma sexta fase do ciclo da rodada: é o momento anterior à
    Rodada 1, e é por isso que a §2 não a lista.

    `FINISHED` também não é do ciclo: é a §10, o outro lado da partida. Entrou
    na feature 006, e é terminal -- nenhuma transição sai dela.

    Esta lista é um inventário deliberado: quem acrescenta uma fase precisa
    passar por aqui e decidir o que ela significa. Foi o que aconteceu.
    """
    assert [phase.value for phase in MatchPhase] == [
        "mulligan",
        "upkeep",
        "action",
        "combat",
        "round_end",
        "finished",
    ]


def test_the_setup_waits_for_both_players(match: Match) -> None:
    assert match.awaiting_mulligan_user_ids == (PLAYER_ONE, PLAYER_TWO)


def test_a_player_who_answered_leaves_the_waiting_list(match: Match) -> None:
    """Derivado de `mulligan_taken`, e não de uma segunda lista que pudesse
    divergir dele."""
    match.players[0].mulligan_taken = True

    assert match.awaiting_mulligan_user_ids == (PLAYER_TWO,)


def test_rolls_never_share_an_ordinal(match: Match) -> None:
    """Dois sorteios com o mesmo ordinal consumiriam o mesmo fluxo."""
    minted = [match.mint_roll() for _ in range(5)]

    assert len({roll.ordinal for roll in minted}) == 5


def test_every_roll_carries_the_match_seed(match: Match) -> None:
    assert match.mint_roll().seed == match.random_seed


def test_token_starts_unconsumed(match: Match) -> None:
    assert not match.token_consumed


def test_nobody_holds_the_token_before_the_draw(match: Match) -> None:
    """`None` nos dois, e não um valor de espera: quem sorteia o dono do token
    é a §3, e antes dela a partida não tem um."""
    assert match.token_holder_user_id is None
    assert match.priority_user_id is None


def test_new_match_has_no_passes(match: Match) -> None:
    assert match.consecutive_passes == 0


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
