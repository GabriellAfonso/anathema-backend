"""As consultas de deck: sempre pelos do dono, e a mesma ausência nos dois casos.

É aqui que o isolamento é provado na origem. A view apenas repassa o que estas
funções respondem -- se elas distinguissem "não é seu" de "não existe", não
haveria como a view não vazar a diferença.
"""

import pytest
from django.contrib.auth.models import User

from apps.game.cards import get_card_catalog, starter_deck
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.deck_queries import deck_count_of, deck_of, decks_of
from apps.players.services.player_creation import create_player_for_user

pytestmark = pytest.mark.django_db

NOBODYS_DECK = 999_999


def player_named(username: str) -> PlayerProfile:
    user = User.objects.create_user(username=username, password="senha-forte-9134")
    return create_player_for_user(user, nickname=username)


@pytest.fixture
def valid_card_ids() -> list[int]:
    return [int(card_id) for card_id in starter_deck(get_card_catalog())]


@pytest.fixture
def alice(valid_card_ids: list[int]) -> PlayerDeck:
    return PlayerDeck.objects.create(
        profile=player_named("alice"), name="Agro", card_ids=valid_card_ids
    )


@pytest.fixture
def bruno() -> PlayerProfile:
    return player_named("bruno")


def test_a_player_reads_their_own_deck(alice: PlayerDeck) -> None:
    assert deck_of(alice.profile_id, alice.pk) == alice


def test_someone_elses_deck_answers_none(
    alice: PlayerDeck, bruno: PlayerProfile
) -> None:
    assert deck_of(bruno.pk, alice.pk) is None


def test_a_deck_that_exists_for_nobody_answers_none(bruno: PlayerProfile) -> None:
    assert deck_of(bruno.pk, NOBODYS_DECK) is None


def test_the_two_absences_are_the_same_answer(
    alice: PlayerDeck, bruno: PlayerProfile
) -> None:
    """`None` nos dois casos, de propósito: quem chama não consegue
    distinguir, porque não deve."""
    assert deck_of(bruno.pk, alice.pk) == deck_of(bruno.pk, NOBODYS_DECK)


def test_the_queryset_of_one_player_never_includes_the_other(
    alice: PlayerDeck, bruno: PlayerProfile
) -> None:
    """Cada um tem o deck inicial dele; nenhum vê o deck do outro."""
    assert alice not in list(decks_of(bruno.pk))
    assert alice in list(decks_of(alice.profile_id))


def test_the_count_is_of_the_owner_only(
    alice: PlayerDeck, bruno: PlayerProfile
) -> None:
    """A tem o inicial mais o "Agro"; B tem só o inicial dele."""
    assert deck_count_of(alice.profile_id) == 2
    assert deck_count_of(bruno.pk) == 1


def test_the_listing_comes_back_oldest_first(
    alice: PlayerDeck, valid_card_ids: list[int]
) -> None:
    """Ordem estável, para que a listagem não dance entre duas requisições."""
    second = PlayerDeck.objects.create(
        profile_id=alice.profile_id, name="Controle", card_ids=valid_card_ids
    )

    assert list(decks_of(alice.profile_id))[-2:] == [alice, second]
