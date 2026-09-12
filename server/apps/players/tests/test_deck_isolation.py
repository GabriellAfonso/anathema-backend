"""O deck de outro jogador não existe para mim.

A propriedade sob teste não é "recusa": é **indistinguível**. Cada operação
sobre um deck alheio é comparada, corpo a corpo, com a mesma operação sobre um
identificador que não existe para ninguém. Se as duas divergirem em qualquer
campo, a listagem alheia vira algo enumerável -- confirmar que o deck 5 existe
já entrega informação a quem não deveria tê-la.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.game.cards import get_card_catalog, starter_deck
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.player_creation import create_player_for_user

pytestmark = pytest.mark.django_db

# Identificador que não existe para ninguém: a referência com que toda recusa
# sobre deck alheio é comparada.
NOBODYS_DECK = 999_999


@pytest.fixture
def valid_card_ids() -> list[int]:
    return [int(card_id) for card_id in starter_deck(get_card_catalog())]


def player_named(username: str) -> PlayerProfile:
    user = User.objects.create_user(username=username, password="senha-forte-9134")
    return create_player_for_user(user, nickname=username)


@pytest.fixture
def owner(valid_card_ids: list[int]) -> PlayerDeck:
    """O jogador A, com um deck guardado."""
    return PlayerDeck.objects.create(
        profile=player_named("alice"), name="Agro", card_ids=valid_card_ids
    )


@pytest.fixture
def intruder() -> APIClient:
    """O jogador B, autenticado, sem nada a ver com o deck de A."""
    client = APIClient()
    client.force_authenticate(user=player_named("bruno").user)

    return client


def item(deck_id: int) -> str:
    return reverse("player_deck", kwargs={"deck_id": deck_id})


def test_reading_someone_elses_deck_is_the_same_as_reading_nothing(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    someone_elses = intruder.get(item(owner.pk))
    nobodys = intruder.get(item(NOBODYS_DECK))

    assert someone_elses.status_code == nobodys.status_code == 404
    assert someone_elses.data == nobodys.data


def test_renaming_someone_elses_deck_is_the_same_as_renaming_nothing(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    body = {"name": "meu agora"}

    someone_elses = intruder.patch(item(owner.pk), body, format="json")
    nobodys = intruder.patch(item(NOBODYS_DECK), body, format="json")

    assert someone_elses.status_code == nobodys.status_code == 404
    assert someone_elses.data == nobodys.data


def test_replacing_someone_elses_list_is_the_same_as_replacing_nothing(
    intruder: APIClient, owner: PlayerDeck, valid_card_ids: list[int]
) -> None:
    body = {"card_ids": valid_card_ids}

    someone_elses = intruder.patch(item(owner.pk), body, format="json")
    nobodys = intruder.patch(item(NOBODYS_DECK), body, format="json")

    assert someone_elses.status_code == nobodys.status_code == 404
    assert someone_elses.data == nobodys.data


def test_deleting_someone_elses_deck_is_the_same_as_deleting_nothing(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    someone_elses = intruder.delete(item(owner.pk))
    nobodys = intruder.delete(item(NOBODYS_DECK))

    assert someone_elses.status_code == nobodys.status_code == 404
    assert someone_elses.data == nobodys.data


def test_the_deck_of_the_owner_survives_every_attempt(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    """Não basta recusar: o deck de A não pode ter mudado nem sumido."""
    intruder.patch(item(owner.pk), {"name": "meu agora"}, format="json")
    intruder.delete(item(owner.pk))

    survivor = PlayerDeck.objects.get(pk=owner.pk)

    assert survivor.name == "Agro"
    assert survivor.card_ids == owner.card_ids


def test_the_listing_of_one_player_never_shows_the_other(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    """B vê os decks dele -- o inicial, que toda conta ganha -- e nenhum de A."""
    response = intruder.get(reverse("player_decks"))

    listed = [deck["deck_id"] for deck in response.data["decks"]]

    assert response.status_code == 200
    assert owner.pk not in listed


def test_the_refusal_carries_no_hint_of_the_other_player(
    intruder: APIClient, owner: PlayerDeck
) -> None:
    """Nem o dono, nem o nome, nem a contagem de cartas."""
    body = str(intruder.get(item(owner.pk)).data)

    assert "Agro" not in body
    assert "alice" not in body


def test_without_authentication_nothing_is_read_at_all(owner: PlayerDeck) -> None:
    """A recusa vem antes de qualquer leitura: 401, e não 404."""
    anonymous = APIClient()

    assert anonymous.get(item(owner.pk)).status_code == 401
    assert anonymous.delete(item(owner.pk)).status_code == 401
    assert PlayerDeck.objects.filter(pk=owner.pk).exists()
