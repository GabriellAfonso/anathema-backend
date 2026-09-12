"""Nenhuma conta nasce sem poder jogar.

Uma conta nova sem deck nenhum não entraria na fila, e não existiria partida
para ela. O deck inicial nasce na mesma transação do perfil: ou o jogador nasce
inteiro, ou não nasce.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.game.cards import deck_problems, get_card_catalog
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.player_creation import create_player_for_user
from apps.players.services.starter_deck_creation import STARTER_DECK_NAME

pytestmark = pytest.mark.django_db

REGISTRATION = {
    "username": "gabriel",
    "email": "gabriel@exemplo.com",
    "password": "senha-forte-9134",
    "password_confirmation": "senha-forte-9134",
}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_a_registered_account_is_born_with_exactly_one_deck(
    client: APIClient,
) -> None:
    response = client.post(reverse("register"), REGISTRATION, format="json")

    assert response.status_code == 201
    assert PlayerDeck.objects.count() == 1


def test_the_starter_deck_is_playable(client: APIClient) -> None:
    """Válido contra as três regras da feature 001, no momento em que nasce."""
    client.post(reverse("register"), REGISTRATION, format="json")

    deck = PlayerDeck.objects.get()

    assert deck_problems(deck.card_ids, get_card_catalog()) == ()
    assert len(deck.card_ids) == 40


def test_the_starter_deck_carries_a_name(client: APIClient) -> None:
    client.post(reverse("register"), REGISTRATION, format="json")

    assert PlayerDeck.objects.get().name == STARTER_DECK_NAME


def test_the_starter_deck_belongs_to_the_new_player(client: APIClient) -> None:
    client.post(reverse("register"), REGISTRATION, format="json")

    profile = PlayerProfile.objects.get()

    assert PlayerDeck.objects.get().profile_id == profile.pk


def test_the_new_player_sees_it_in_the_listing(client: APIClient) -> None:
    """O caminho inteiro: registrar, autenticar, listar."""
    client.post(reverse("register"), REGISTRATION, format="json")
    client.force_authenticate(user=User.objects.get(username="gabriel"))

    decks = client.get(reverse("player_decks")).data["decks"]

    assert len(decks) == 1
    assert decks[0]["name"] == STARTER_DECK_NAME


def test_the_starter_deck_is_an_ordinary_deck(client: APIClient) -> None:
    """Renomeável, editável e apagável como qualquer outro: sem proteção."""
    client.post(reverse("register"), REGISTRATION, format="json")
    client.force_authenticate(user=User.objects.get(username="gabriel"))
    deck_id = PlayerDeck.objects.get().pk
    item = reverse("player_deck", kwargs={"deck_id": deck_id})

    renamed = client.patch(item, {"name": "Meu agro"}, format="json")

    assert renamed.status_code == 200
    assert client.delete(item).status_code == 204
    assert PlayerDeck.objects.count() == 0


def test_a_failure_creating_the_deck_undoes_the_whole_registration(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tudo ou nada: nenhum jogador fica com perfil e sem deck."""

    def refuse_to_create(*args: object, **kwargs: object) -> PlayerDeck:
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(
        "apps.players.services.player_creation.create_starter_deck", refuse_to_create
    )

    with pytest.raises(RuntimeError):
        client.post(reverse("register"), REGISTRATION, format="json")

    assert User.objects.count() == 0
    assert PlayerProfile.objects.count() == 0
    assert PlayerDeck.objects.count() == 0


def test_an_account_without_a_profile_gets_no_deck() -> None:
    """`createsuperuser` não passa por aqui: deck pertence a jogador, e uma
    conta sem perfil não é jogador."""
    User.objects.create_superuser(username="root", password="senha-forte-9134")

    assert PlayerDeck.objects.count() == 0


def test_creating_a_player_directly_also_gets_the_deck() -> None:
    """O serviço é a porta única, e é ele que garante o deck -- não a rota."""
    user = User.objects.create_user(username="direto", password="senha-forte-9134")

    profile = create_player_for_user(user, nickname="direto")

    assert PlayerDeck.objects.filter(profile=profile).count() == 1
