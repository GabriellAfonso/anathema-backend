"""O deck de andaime do matchmaking precisa passar nas regras de deck.

Um andaime que produz deck inválido derruba o pareamento inteiro, e derruba
longe de onde o erro está. Este teste é curto de propósito: ele existe para
que a substituição pela feature de deck de verdade seja segura.
"""

import pytest

from apps.game.cards import (
    DECK_SIZE,
    MAX_COPIES_PER_CARD,
    deck_problems,
    mvp_catalog,
    starter_deck,
)
from apps.game.tests.fake_card_catalog import SAMPLE_SPELL, SAMPLE_UNIT, FakeCardCatalog


def test_the_starter_deck_has_the_required_size() -> None:
    assert len(starter_deck(mvp_catalog())) == DECK_SIZE


def test_the_starter_deck_passes_the_deck_rules() -> None:
    """Tamanho, limite de cópias e existência no catálogo, de uma vez."""
    catalog = mvp_catalog()

    assert deck_problems(starter_deck(catalog), catalog) == ()


def test_no_card_appears_more_than_the_copy_limit() -> None:
    deck = starter_deck(mvp_catalog())

    assert max(deck.count(card_id) for card_id in set(deck)) <= MAX_COPIES_PER_CARD


def test_the_starter_deck_is_the_same_every_time() -> None:
    """Andaime determinístico: o embaralhamento é do setup, não daqui."""
    catalog = mvp_catalog()

    assert starter_deck(catalog) == starter_deck(catalog)


def test_a_catalog_too_small_is_refused_naming_the_counts() -> None:
    """Duas cartas dão 6 entradas, não 40. Recusar aqui põe o erro ao lado de
    quem o causou, em vez de deixá-lo aparecer como deck inválido."""
    catalog = FakeCardCatalog([SAMPLE_UNIT, SAMPLE_SPELL])

    with pytest.raises(ValueError, match=str(DECK_SIZE)):
        starter_deck(catalog)
