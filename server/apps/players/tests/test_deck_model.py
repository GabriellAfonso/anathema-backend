"""O deck guarda a lista como ela foi enviada, e pertence a um jogador só."""

import pytest
from django.contrib.auth.models import User

from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.player_creation import create_player_for_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile() -> PlayerProfile:
    user = User.objects.create_user(username="gabriel", password="segredo123")
    return create_player_for_user(user, nickname="gabriel")


def test_the_list_keeps_its_repetition(profile: PlayerProfile) -> None:
    """Deck é lista, não conjunto: três cópias entram e três cópias saem."""
    deck = PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[7, 7, 7])

    assert PlayerDeck.objects.get(pk=deck.pk).card_ids == [7, 7, 7]


def test_the_list_keeps_its_order(profile: PlayerProfile) -> None:
    sent = [9, 1, 5, 1, 9]

    deck = PlayerDeck.objects.create(profile=profile, name="Ordem", card_ids=sent)

    assert PlayerDeck.objects.get(pk=deck.pk).card_ids == sent


def test_the_owner_is_the_user_id(profile: PlayerProfile) -> None:
    """`PlayerProfile.user` é a chave primária (decisão 0001), então o dono do
    deck é nomeado pelo mesmo inteiro que identifica o usuário."""
    deck = PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[1])

    assert deck.profile_id == profile.user_id
    assert deck.profile_id == profile.pk


def test_two_decks_of_the_same_player_may_share_a_name(
    profile: PlayerProfile,
) -> None:
    """A identidade é o `deck_id`; o nome é rótulo de quem montou."""
    first = PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[1])
    second = PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[2])

    assert first.pk != second.pk


def test_deleting_the_profile_takes_the_decks_with_it(
    profile: PlayerProfile,
) -> None:
    PlayerDeck.objects.create(profile=profile, name="Agro", card_ids=[1])

    profile.delete()

    assert PlayerDeck.objects.count() == 0
