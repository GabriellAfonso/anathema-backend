"""`/players/me/` answers for players, and only for players."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.players.services.player_creation import create_player_for_user


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_returns_the_profile_of_the_authenticated_player(client: APIClient) -> None:
    user = User.objects.create_user(username="gabriel", password="senha-forte-9134")
    create_player_for_user(user, nickname="gabriel")
    client.force_authenticate(user=user)

    response = client.get(reverse("player_me"))

    assert response.status_code == 200
    assert response.data["nickname"] == "gabriel"


@pytest.mark.django_db
def test_returns_404_for_a_user_without_a_profile(client: APIClient) -> None:
    """`createsuperuser` não cria profile; a rota responde 404, não 500."""
    admin = User.objects.create_superuser(username="root", password="senha-forte-9134")
    client.force_authenticate(user=admin)

    response = client.get(reverse("player_me"))

    assert response.status_code == 404
