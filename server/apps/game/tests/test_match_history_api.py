"""`/game/matches/`: o histórico do jogador autenticado, e só o dele.

O contrato está em
`specs/012-match-result-history/contracts/http_match_history.md`.
"""

import datetime

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.game.match import MatchEndReason
from apps.game.models import MatchRecord
from apps.players.models.player import PlayerProfile
from apps.players.services.player_creation import create_player_for_user

pytestmark = pytest.mark.django_db

FIRST_END = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=datetime.UTC)
ONE_MINUTE = datetime.timedelta(minutes=1)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def me(client: APIClient) -> PlayerProfile:
    profile = _a_player("gabriel")
    client.force_authenticate(user=profile.user)

    return profile


@pytest.fixture
def rival() -> PlayerProfile:
    return _a_player("brenda")


def history() -> str:
    return reverse("match_history")


def _a_player(nickname: str) -> PlayerProfile:
    user = User.objects.create_user(username=nickname, password="senha-forte-9134")

    return create_player_for_user(user, nickname=nickname)


def _a_match(
    winner: PlayerProfile | None,
    loser: PlayerProfile | None,
    *,
    match_id: str = "m-1",
    ended_at: datetime.datetime = FIRST_END,
    reason: MatchEndReason = MatchEndReason.NEXUS_DEPLETED,
    final_round: int = 8,
    duration_seconds: int = 742,
) -> MatchRecord:
    return MatchRecord.objects.create(
        match_id=match_id,
        winner=winner,
        loser=loser,
        end_reason=reason,
        started_at=ended_at - datetime.timedelta(seconds=duration_seconds),
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        final_round=final_round,
        winner_final_nexus=12,
        loser_final_nexus=0,
        winner_deck_name="Agro",
        loser_deck_name="Controle",
        winner_deck_card_ids=[1, 1, 2],
        loser_deck_card_ids=[3, 3, 4],
    )


# --- A linha ----------------------------------------------------------------


def test_a_won_match_comes_back_with_the_opponent_and_the_outcome(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    _a_match(me, rival)

    row = client.get(history()).data["results"][0]

    assert row["match_id"] == "m-1"
    assert row["won"] is True
    assert row["end_reason"] == MatchEndReason.NEXUS_DEPLETED
    assert row["opponent"]["user_id"] == rival.pk
    assert row["opponent"]["nickname"] == "brenda"
    assert (row["duration_seconds"], row["final_round"]) == (742, 8)


def test_a_lost_match_says_so_from_the_asking_side(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    """A mesma linha é vitória para um e derrota para o outro."""
    _a_match(rival, me, reason=MatchEndReason.FORFEIT)

    row = client.get(history()).data["results"][0]

    assert row["won"] is False
    assert row["end_reason"] == MatchEndReason.FORFEIT
    assert row["opponent"]["user_id"] == rival.pk


def test_no_field_is_called_id(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    """O espaço de identidade é nomeado: `match_id`, `user_id`."""
    _a_match(me, rival)

    row = client.get(history()).data["results"][0]

    assert "id" not in row
    assert "id" not in row["opponent"]


def test_the_deck_and_the_final_nexus_are_not_exposed(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    """Guardados para análise depois; servi-los é decisão de outra feature."""
    _a_match(me, rival)

    row = client.get(history()).data["results"][0]

    assert set(row) == {
        "match_id",
        "won",
        "end_reason",
        "opponent",
        "duration_seconds",
        "final_round",
        "ended_at",
    }


# --- A ordem e a paginação --------------------------------------------------


def test_the_most_recent_match_comes_first(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    _a_match(me, rival, match_id="older", ended_at=FIRST_END)
    _a_match(rival, me, match_id="newer", ended_at=FIRST_END + ONE_MINUTE)

    listed = [row["match_id"] for row in client.get(history()).data["results"]]

    assert listed == ["newer", "older"]


def test_fifty_matches_come_back_once_each_across_the_pages(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    for number in range(50):
        _a_match(
            me,
            rival,
            match_id=f"m-{number}",
            ended_at=FIRST_END + number * ONE_MINUTE,
        )

    seen: list[str] = []
    page = 1

    while True:
        response = client.get(history(), {"page": page})
        seen.extend(row["match_id"] for row in response.data["results"])

        if response.data["next"] is None:
            break

        page += 1

    assert len(seen) == 50
    assert len(set(seen)) == 50


def test_the_first_page_holds_twenty(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    for number in range(25):
        _a_match(me, rival, match_id=f"m-{number}")

    response = client.get(history())

    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20


def test_a_page_size_above_the_ceiling_is_capped(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    for number in range(120):
        _a_match(me, rival, match_id=f"m-{number}")

    response = client.get(history(), {"page_size": 500})

    assert len(response.data["results"]) == 100


# --- O isolamento -----------------------------------------------------------


def test_a_match_of_other_players_never_shows_up(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    stranger = _a_player("outro")
    _a_match(rival, stranger, match_id="theirs")
    _a_match(me, rival, match_id="mine")

    listed = [row["match_id"] for row in client.get(history()).data["results"]]

    assert listed == ["mine"]


def test_a_player_with_no_matches_gets_an_empty_list(
    client: APIClient, me: PlayerProfile
) -> None:
    """Lista vazia é resposta válida, não recusa."""
    response = client.get(history())

    assert response.status_code == 200
    assert response.data["results"] == []


def test_without_authentication_the_route_refuses(client: APIClient) -> None:
    assert client.get(history()).status_code == 401


def test_an_account_that_is_not_a_player_gets_a_404(client: APIClient) -> None:
    """Conta criada fora do registro não tem perfil, e não jogou partida nenhuma."""
    user = User.objects.create_user(username="root", password="senha-forte-9134")
    client.force_authenticate(user=user)

    assert client.get(history()).status_code == 404


# --- O perfil apagado -------------------------------------------------------


def test_a_deleted_opponent_leaves_the_line_readable(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    """O histórico do outro jogador não pode quebrar por causa disso."""
    _a_match(me, rival)
    rival.user.delete()

    row = client.get(history()).data["results"][0]

    assert row["opponent"] is None
    assert row["won"] is True
    assert row["end_reason"] == MatchEndReason.NEXUS_DEPLETED


def test_a_deleted_opponent_does_not_take_the_row_with_them(
    client: APIClient, me: PlayerProfile, rival: PlayerProfile
) -> None:
    """`SET_NULL`, e não `CASCADE`: a linha é do histórico dos dois."""
    _a_match(me, rival)
    rival.user.delete()

    assert MatchRecord.objects.count() == 1
    assert client.get(history()).data["count"] == 1
