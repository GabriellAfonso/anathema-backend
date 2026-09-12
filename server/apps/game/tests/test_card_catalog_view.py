"""`/game/cards/` serve o catálogo: igual para todos, e só para autenticado."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def player() -> User:
    return User.objects.create_user(username="gabriel", password="senha-forte-9134")


@pytest.mark.django_db
def test_the_whole_mvp_comes_back(client: APIClient, player: User) -> None:
    client.force_authenticate(user=player)

    response = client.get(reverse("card_catalog"))

    assert response.status_code == 200
    assert len(response.data["cards"]) == 29


@pytest.mark.django_db
def test_the_cards_come_back_ordered_by_card_id(
    client: APIClient, player: User
) -> None:
    client.force_authenticate(user=player)

    cards = client.get(reverse("card_catalog")).data["cards"]

    card_ids = [card["card_id"] for card in cards]

    assert card_ids == sorted(card_ids)


@pytest.mark.django_db
def test_twenty_four_units_and_five_spells(client: APIClient, player: User) -> None:
    client.force_authenticate(user=player)

    cards = client.get(reverse("card_catalog")).data["cards"]

    assert sum(card["card_type"] == "unit" for card in cards) == 24
    assert sum(card["card_type"] == "spell" for card in cards) == 5


@pytest.mark.django_db
def test_two_players_get_the_same_answer(client: APIClient, player: User) -> None:
    """O catálogo não depende de quem pergunta: é a mesma resposta, campo a
    campo, para qualquer autenticado."""
    other = User.objects.create_user(username="outro", password="senha-forte-9134")

    client.force_authenticate(user=player)
    first = client.get(reverse("card_catalog")).data

    client.force_authenticate(user=other)
    second = client.get(reverse("card_catalog")).data

    assert first == second


@pytest.mark.django_db
def test_a_player_without_a_profile_still_reads_the_catalog(
    client: APIClient, player: User
) -> None:
    """O catálogo é do jogo, não do jogador: não há perfil envolvido."""
    client.force_authenticate(user=player)

    assert client.get(reverse("card_catalog")).status_code == 200


@pytest.mark.django_db
def test_without_authentication_it_refuses(client: APIClient) -> None:
    assert client.get(reverse("card_catalog")).status_code == 401


@pytest.mark.django_db
def test_no_card_carries_a_bare_id(client: APIClient, player: User) -> None:
    client.force_authenticate(user=player)

    cards = client.get(reverse("card_catalog")).data["cards"]

    for card in cards:
        assert "id" not in card
        assert "card_id" in card


@pytest.mark.django_db
def test_every_spell_carries_the_effect_shape(client: APIClient, player: User) -> None:
    """Sem isto o cliente não sabe se deve pedir alvo antes de mandar a
    jogada, nem de qual lado do tabuleiro."""
    client.force_authenticate(user=player)

    cards = client.get(reverse("card_catalog")).data["cards"]
    spells = [card for card in cards if card["card_type"] == "spell"]

    for spell in spells:
        assert set(spell["effect"]) == {
            "requires_target",
            "target_kind",
            "duration",
            "declaration_only",
        }
