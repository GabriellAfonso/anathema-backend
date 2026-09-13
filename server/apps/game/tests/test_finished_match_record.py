"""A gravação de verdade: uma linha no banco e os contadores dos dois jogadores.

Estes tocam o banco (`django_db`), ao contrário dos testes de socket -- é aqui
que a porta injetada é provada, e é por ela existir que a suíte de websocket
continua fora do banco.
"""

from copy import deepcopy

import pytest
from django.contrib.auth.models import User

from apps.game.cards import CardId
from apps.game.engine import change_nexus, forfeit
from apps.game.history import DatabaseFinishedMatchRecorder, finished_match
from apps.game.match import ChosenDeck, Match, MatchEndReason
from apps.game.models import MatchRecord
from apps.game.tests.fake_setup import fake_match_in_action_phase
from apps.game.wall_clock import EpochMillis
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile, PlayerStats

STARTED_AT = EpochMillis(1_700_000_000_000)
ENDED_AT = EpochMillis(1_700_000_742_000)
DURATION_SECONDS = 742

pytestmark = pytest.mark.django_db


@pytest.fixture
def players() -> tuple[int, int]:
    """Os dois jogadores, com estatísticas zeradas como o cadastro as cria.

    Devolve `user_id`, que é também o `profile_id` (decisão 0001). Os números
    vêm do banco, e não fixos no teste: o estado da partida usa a identidade de
    verdade, e a linha gravada aponta para perfis que existem.
    """
    return (_a_player("one").pk, _a_player("two").pk)


@pytest.fixture
def match(players: tuple[int, int]) -> Match:
    running = fake_match_in_action_phase(*players)
    running.started_at = STARTED_AT

    return running


def _a_player(nickname: str) -> PlayerProfile:
    user = User.objects.create_user(username=nickname, password="x")
    profile = PlayerProfile.objects.create(user=user, nickname=nickname)
    PlayerStats.objects.create(profile=profile)

    return profile


async def _record(match: Match, before: Match, ended_at: EpochMillis = ENDED_AT) -> bool:
    finished = finished_match(before, match, ended_at)
    assert finished is not None

    return await DatabaseFinishedMatchRecorder().record(finished)


def _stats_of(user_id: int) -> PlayerStats:
    return PlayerStats.objects.get(profile_id=user_id)


# --- A linha ----------------------------------------------------------------


async def test_a_nexus_defeat_becomes_one_row(
    players: tuple[int, int], match: Match
) -> None:
    before = deepcopy(match)
    change_nexus(match, match.player(players[1]), -20)

    assert await _record(match, before) is True

    record = await MatchRecord.objects.aget(match_id=match.match_id)
    assert record.end_reason == MatchEndReason.NEXUS_DEPLETED
    assert (record.winner_id, record.loser_id) == (players[0], players[1])


async def test_a_forfeit_becomes_one_row_too(
    players: tuple[int, int], match: Match
) -> None:
    before = deepcopy(match)
    forfeit(match, players[0])

    assert await _record(match, before) is True

    record = await MatchRecord.objects.aget(match_id=match.match_id)
    assert record.end_reason == MatchEndReason.FORFEIT
    assert (record.winner_id, record.loser_id) == (players[1], players[0])


async def test_the_row_carries_duration_round_and_final_nexus(
    players: tuple[int, int], match: Match
) -> None:
    match.round_number = 8
    change_nexus(match, match.player(players[0]), -5)
    before = deepcopy(match)

    change_nexus(match, match.player(players[1]), -20)
    await _record(match, before)

    record = await MatchRecord.objects.aget(match_id=match.match_id)
    assert record.duration_seconds == DURATION_SECONDS
    assert record.final_round == 8
    assert (record.winner_final_nexus, record.loser_final_nexus) == (15, 0)


async def test_the_row_carries_the_deck_each_player_entered_with(
    players: tuple[int, int], match: Match
) -> None:
    match.player(players[1]).chosen_deck = ChosenDeck(
        name="Controle", card_ids=(CardId(1), CardId(2), CardId(2))
    )
    before = deepcopy(match)

    forfeit(match, players[1])
    await _record(match, before)

    record = await MatchRecord.objects.aget(match_id=match.match_id)
    assert record.loser_deck_name == "Controle"
    assert record.loser_deck_card_ids == [1, 2, 2]
    assert record.winner_deck_name == "Fake Deck"
    assert len(record.winner_deck_card_ids) == 40


async def test_the_recorded_deck_outlives_the_deck_it_was_copied_from(
    players: tuple[int, int], match: Match
) -> None:
    """Cópia congelada: renomear ou apagar o deck não mexe na linha."""
    match.player(players[0]).chosen_deck = ChosenDeck(
        name="Agro", card_ids=(CardId(3), CardId(3))
    )
    before = deepcopy(match)
    forfeit(match, players[1])
    await _record(match, before)

    # O deck guardado do jogador some inteiro; a linha não é referência a ele.
    await PlayerDeck.objects.filter(profile_id=players[0]).adelete()

    record = await MatchRecord.objects.aget(match_id=match.match_id)
    assert (record.winner_deck_name, record.winner_deck_card_ids) == ("Agro", [3, 3])


# --- As estatísticas --------------------------------------------------------


async def test_both_players_get_a_match_played(
    players: tuple[int, int], match: Match
) -> None:
    before = deepcopy(match)
    forfeit(match, players[0])

    await _record(match, before)

    assert _stats_of(players[0]).matches_played == 1
    assert _stats_of(players[1]).matches_played == 1


async def test_the_win_and_the_loss_land_on_the_right_sides(
    players: tuple[int, int], match: Match
) -> None:
    before = deepcopy(match)
    forfeit(match, players[0])

    await _record(match, before)

    winner, loser = _stats_of(players[1]), _stats_of(players[0])
    assert (winner.wins, winner.losses) == (1, 0)
    assert (loser.wins, loser.losses) == (0, 1)


async def test_the_duration_is_added_to_both_play_times(
    players: tuple[int, int], match: Match
) -> None:
    before = deepcopy(match)
    forfeit(match, players[0])

    await _record(match, before)

    assert _stats_of(players[0]).play_time == DURATION_SECONDS
    assert _stats_of(players[1]).play_time == DURATION_SECONDS


async def test_a_sixth_match_adds_one_without_recounting(
    players: tuple[int, int], match: Match
) -> None:
    PlayerStats.objects.filter(profile_id=players[0]).update(
        matches_played=5, wins=3, losses=2, play_time=1000
    )
    before = deepcopy(match)
    forfeit(match, players[1])

    await _record(match, before)

    stats = _stats_of(players[0])
    assert (stats.matches_played, stats.wins, stats.losses) == (6, 4, 2)
    assert stats.play_time == 1000 + DURATION_SECONDS


async def test_a_player_without_stats_does_not_stop_the_record(
    players: tuple[int, int], match: Match
) -> None:
    """Conta criada fora do registro não tem `PlayerStats`, e a partida aconteceu."""
    PlayerStats.objects.filter(profile_id=players[1]).delete()
    before = deepcopy(match)

    forfeit(match, players[0])

    assert await _record(match, before) is True
    assert await MatchRecord.objects.filter(match_id=match.match_id).acount() == 1
