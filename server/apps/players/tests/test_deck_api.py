"""`/players/decks/`: listar, criar, ler, editar e apagar os próprios decks.

O contrato está em
`specs/011-deck-catalog-api/contracts/http_decks.md`.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.game.cards import CardId, get_card_catalog, starter_deck
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.deck_validation import DECK_LIMIT_PER_PLAYER
from apps.players.services.player_creation import create_player_for_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def profile() -> PlayerProfile:
    user = User.objects.create_user(username="gabriel", password="senha-forte-9134")
    return create_player_for_user(user, nickname="gabriel")


@pytest.fixture
def player(client: APIClient, profile: PlayerProfile) -> PlayerProfile:
    """Autenticado, e **sem** o deck inicial.

    Toda conta nasce com um deck (US7), e quase todo teste daqui conta decks ou
    compara listagens. Apagá-lo aqui deixa cada teste contar só o que ele mesmo
    criou; quem prova que o deck inicial existe é
    `test_starter_deck_creation.py`.
    """
    client.force_authenticate(user=profile.user)
    PlayerDeck.objects.filter(profile=profile).delete()

    return profile


@pytest.fixture
def valid_card_ids() -> list[int]:
    """40 identificadores válidos, derivados do catálogo do processo."""
    return [int(card_id) for card_id in starter_deck(get_card_catalog())]


@pytest.fixture
def deck(player: PlayerProfile, valid_card_ids: list[int]) -> PlayerDeck:
    """Um deck já guardado.

    Criado aqui e não pelo deck inicial do registro: US3 tem de ser testável
    sozinha, sem depender da história que faz toda conta nascer com um deck.
    """
    return PlayerDeck.objects.create(
        profile=player, name="Agro", card_ids=valid_card_ids
    )


def collection() -> str:
    return reverse("player_decks")


def item(deck_id: int) -> str:
    return reverse("player_deck", kwargs={"deck_id": deck_id})


def decks_of_the_player(client: APIClient) -> list[dict[str, object]]:
    return list(client.get(collection()).data["decks"])


# --- Listar -----------------------------------------------------------------


def test_a_player_without_decks_gets_an_empty_list(
    client: APIClient, player: PlayerProfile
) -> None:
    """Lista vazia é resposta, não erro."""
    response = client.get(collection())

    assert response.status_code == 200
    assert response.data["decks"] == []


def test_the_listing_shows_what_was_created(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    client.post(
        collection(), {"name": "Agro", "card_ids": valid_card_ids}, format="json"
    )
    client.post(
        collection(), {"name": "Controle", "card_ids": valid_card_ids}, format="json"
    )

    names = [deck["name"] for deck in decks_of_the_player(client)]

    assert names == ["Agro", "Controle"]


def test_a_deck_carries_deck_id_and_never_a_bare_id(
    client: APIClient, deck: PlayerDeck
) -> None:
    listed = decks_of_the_player(client)[0]

    assert "id" not in listed
    assert set(listed) == {"deck_id", "name", "card_ids"}


# --- Criar ------------------------------------------------------------------


def test_creating_a_valid_deck_answers_201_with_its_identifier(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    response = client.post(
        collection(), {"name": "Agro", "card_ids": valid_card_ids}, format="json"
    )

    assert response.status_code == 201
    assert response.data["name"] == "Agro"
    assert isinstance(response.data["deck_id"], int)


def test_the_list_is_stored_with_its_repetition_and_order(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    response = client.post(
        collection(), {"name": "Agro", "card_ids": valid_card_ids}, format="json"
    )

    assert response.data["card_ids"] == valid_card_ids


def test_two_decks_of_the_same_player_may_share_a_name(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    body = {"name": "Agro", "card_ids": valid_card_ids}

    first = client.post(collection(), body, format="json")
    second = client.post(collection(), body, format="json")

    assert second.status_code == 201
    assert first.data["deck_id"] != second.data["deck_id"]


def test_creating_without_the_two_fields_is_refused(
    client: APIClient, player: PlayerProfile
) -> None:
    response = client.post(collection(), {"name": "Agro"}, format="json")

    assert response.status_code == 400


# --- Recusas do salvamento --------------------------------------------------


def test_an_empty_name_is_refused_naming_the_field(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    response = client.post(
        collection(), {"name": "   ", "card_ids": valid_card_ids}, format="json"
    )

    assert response.status_code == 400
    assert "name" in response.data


def test_a_draft_of_twelve_cards_is_refused(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    """Não existe rascunho: as três regras valem no salvamento."""
    response = client.post(
        collection(),
        {"name": "Rascunho", "card_ids": valid_card_ids[:12]},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["deck_problems"][0]["kind"] == "wrong_deck_size"
    assert response.data["deck_problems"][0]["found"] == 12


def test_a_fourth_copy_is_refused_naming_the_card_and_the_count(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    """O caso nominal da spec: 40 entradas, uma carta 4 vezes."""
    card_ids = valid_card_ids[:-1] + [valid_card_ids[0]]

    response = client.post(
        collection(), {"name": "Quatro", "card_ids": card_ids}, format="json"
    )

    problem = response.data["deck_problems"][0]

    assert response.status_code == 400
    assert problem["kind"] == "too_many_copies"
    assert problem["card_id"] == valid_card_ids[0]
    assert problem["count"] == 4
    assert problem["limit"] == 3


def test_a_card_outside_the_catalog_is_refused_naming_it(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    card_ids = valid_card_ids[:-1] + [9999]

    response = client.post(
        collection(), {"name": "Fantasma", "card_ids": card_ids}, format="json"
    )

    assert response.data["deck_problems"][0]["kind"] == "unknown_card"
    assert response.data["deck_problems"][0]["card_id"] == 9999


def test_every_problem_comes_back_at_once(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    card_ids = valid_card_ids[:37] + [valid_card_ids[0], 9999]

    response = client.post(
        collection(), {"name": "Três", "card_ids": card_ids}, format="json"
    )

    kinds = {problem["kind"] for problem in response.data["deck_problems"]}

    assert kinds == {"wrong_deck_size", "too_many_copies", "unknown_card"}


def test_the_twenty_first_deck_is_refused_with_the_limit(
    client: APIClient, player: PlayerProfile, valid_card_ids: list[int]
) -> None:
    for index in range(DECK_LIMIT_PER_PLAYER):
        PlayerDeck.objects.create(
            profile=player, name=f"Deck {index}", card_ids=valid_card_ids
        )

    response = client.post(
        collection(), {"name": "Mais um", "card_ids": valid_card_ids}, format="json"
    )

    assert response.status_code == 400
    assert str(DECK_LIMIT_PER_PLAYER) in response.data["deck_limit"][0]
    assert PlayerDeck.objects.count() == DECK_LIMIT_PER_PLAYER


# --- Ler, editar, apagar ----------------------------------------------------


def test_reading_a_deck_of_mine(client: APIClient, deck: PlayerDeck) -> None:
    response = client.get(item(deck.pk))

    assert response.status_code == 200
    assert response.data["deck_id"] == deck.pk
    assert response.data["name"] == "Agro"


def test_renaming_keeps_the_card_list(client: APIClient, deck: PlayerDeck) -> None:
    response = client.patch(item(deck.pk), {"name": "Agro v2"}, format="json")

    assert response.data["name"] == "Agro v2"
    assert response.data["card_ids"] == deck.card_ids


def test_replacing_the_list_keeps_the_name(
    client: APIClient, deck: PlayerDeck, valid_card_ids: list[int]
) -> None:
    replacement = list(reversed(valid_card_ids))

    response = client.patch(item(deck.pk), {"card_ids": replacement}, format="json")

    assert response.data["card_ids"] == replacement
    assert response.data["name"] == deck.name


def test_an_empty_patch_is_refused(client: APIClient, deck: PlayerDeck) -> None:
    assert client.patch(item(deck.pk), {}, format="json").status_code == 400


def test_a_refused_patch_leaves_the_stored_deck_untouched(
    client: APIClient, deck: PlayerDeck, valid_card_ids: list[int]
) -> None:
    """Deck recusado não fica salvo pela metade."""
    client.patch(
        item(deck.pk),
        {"name": "Novo nome", "card_ids": valid_card_ids[:12]},
        format="json",
    )

    stored = client.get(item(deck.pk)).data

    assert stored["name"] == deck.name
    assert stored["card_ids"] == deck.card_ids


def test_deleting_removes_it_from_the_listing(
    client: APIClient, deck: PlayerDeck
) -> None:
    assert client.delete(item(deck.pk)).status_code == 204
    assert client.get(item(deck.pk)).status_code == 404
    assert decks_of_the_player(client) == []


def test_deleting_the_last_deck_is_allowed(client: APIClient, deck: PlayerDeck) -> None:
    """O jogador fica sem deck e não entra na fila até criar um. A recusa da
    fila é que explica isso -- apagar não é bloqueado."""
    client.delete(item(deck.pk))

    assert decks_of_the_player(client) == []


def test_deleting_a_deck_does_not_touch_a_match_in_progress(
    client: APIClient, deck: PlayerDeck
) -> None:
    """A partida já tem as cartas dela desde o setup: apagar o deck com que se
    entrou não muda nada do que está em jogo."""
    from apps.game.engine import MatchEntry, start_match
    from apps.game.randomness import SeededRandomSource, new_random_seed
    from apps.game.tests.fake_player_data import fake_player_data
    from apps.game.tests.match_snapshot import match_snapshot

    card_ids = [CardId(card_id) for card_id in deck.card_ids]
    match = start_match(
        MatchEntry(profile=fake_player_data(7, "one"), deck=card_ids),
        MatchEntry(profile=fake_player_data(9, "two"), deck=card_ids),
        catalog=get_card_catalog(),
        randomness=SeededRandomSource(),
        seed=new_random_seed(),
    )
    before = match_snapshot(match)

    client.delete(item(deck.pk))

    assert match_snapshot(match) == before


# --- Autenticação -----------------------------------------------------------


def test_without_authentication_every_route_refuses(client: APIClient) -> None:
    assert client.get(collection()).status_code == 401
    assert client.post(collection(), {}, format="json").status_code == 401
    assert client.get(item(1)).status_code == 401
    assert client.patch(item(1), {}, format="json").status_code == 401
    assert client.delete(item(1)).status_code == 401


def test_an_account_without_a_profile_is_not_a_player(client: APIClient) -> None:
    """`createsuperuser` não cria perfil, e deck pertence a jogador."""
    admin = User.objects.create_superuser(username="root", password="senha-forte-9134")
    client.force_authenticate(user=admin)

    assert client.get(collection()).status_code == 404
