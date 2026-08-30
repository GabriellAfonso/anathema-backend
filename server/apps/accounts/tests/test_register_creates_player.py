"""Signing up creates the whole player, or none of it."""

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.fake_player_settings import FailingPlayerSettings
from apps.players.models.player import PlayerProfile, PlayerStats
from apps.players.models.settings import PlayerSettings

SIGNUP = {
    "username": "gabriel",
    "email": "gabriel@example.com",
    "password": "senha-forte-9134",
    "password_confirmation": "senha-forte-9134",
}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_register_creates_profile_stats_and_settings(client: APIClient) -> None:
    response = client.post(reverse("register"), SIGNUP, format="json")

    assert response.status_code == 201
    profile = PlayerProfile.objects.get(nickname="gabriel")
    assert profile.pk == User.objects.get(username="gabriel").pk
    assert PlayerStats.objects.filter(profile=profile).exists()
    assert PlayerSettings.objects.filter(profile=profile).exists()


@pytest.mark.django_db
def test_register_leaves_no_user_when_player_creation_fails(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressão: o `post_save` antigo commitava o User antes do profile.

    Um User órfão fazia `/players/me/` estourar 500 no `user.profile`.
    A criação inteira é uma transação só, então nada pode sobrar.
    """
    monkeypatch.setattr(
        "apps.players.services.player_creation.PlayerSettings",
        FailingPlayerSettings,
    )

    with pytest.raises(DatabaseError):
        client.post(reverse("register"), SIGNUP, format="json")

    assert not User.objects.exists()
    assert not PlayerProfile.objects.exists()
    assert not PlayerStats.objects.exists()
