"""O que é um deck aceitável para salvar: nome, as três regras, e o teto.

As três regras não são reescritas aqui nem lá: `deck_validation` chama
`deck_problems` da feature 001. O que estes testes provam é que ela chama, que
a recusa sai inteira, e que nome e teto -- que são desta feature -- recusam
nomeando o valor ofensor.

O catálogo é um fake pequeno com 14 unidades de valores redondos: 14 é o
mínimo para fechar 40 entradas a 3 cópias por carta, e usar as 29 do MVP faria
uma mudança de balanceamento reprovar um arquivo que não é sobre isso.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, InvalidDeckError, Unit, starter_deck
from apps.game.tests.fake_card_catalog import FakeCardCatalog
from apps.players.services.deck_validation import (
    DECK_LIMIT_PER_PLAYER,
    MAX_DECK_NAME_LENGTH,
    InvalidDeckNameError,
    TooManyDecksError,
    ensure_room_for_another_deck,
    validated_card_ids,
    validated_deck_name,
)

# 14 cartas: o mínimo para um deck de 40 caber em 3 cópias por identificador.
CARDS_IN_THE_FAKE_CATALOG = 14
MISSING = CardId(9999)


def sample_unit(card_id: int) -> Unit:
    return Unit(
        card_id=CardId(card_id),
        name=f"SAMPLE {card_id}",
        energy=2,
        attack=3,
        health=4,
        image=f"sample_{card_id}",
    )


@pytest.fixture
def catalog() -> CardCatalog:
    return FakeCardCatalog(
        sample_unit(card_id) for card_id in range(1, CARDS_IN_THE_FAKE_CATALOG + 1)
    )


@pytest.fixture
def valid_card_ids(catalog: CardCatalog) -> list[CardId]:
    """40 entradas válidas, derivadas do catálogo em vez de listadas à mão."""
    return list(starter_deck(catalog))


# --- Nome -------------------------------------------------------------------


def test_a_name_is_kept_without_the_surrounding_spaces() -> None:
    assert validated_deck_name("  Agro  ") == "Agro"


def test_an_empty_name_is_refused_naming_the_value() -> None:
    with pytest.raises(InvalidDeckNameError) as refused:
        validated_deck_name("")

    assert "''" in str(refused.value)


def test_a_name_of_only_spaces_is_refused() -> None:
    with pytest.raises(InvalidDeckNameError):
        validated_deck_name("   ")


def test_a_name_above_the_limit_is_refused_naming_the_limit() -> None:
    with pytest.raises(InvalidDeckNameError) as refused:
        validated_deck_name("a" * (MAX_DECK_NAME_LENGTH + 1))

    assert str(MAX_DECK_NAME_LENGTH) in str(refused.value)


def test_a_name_exactly_at_the_limit_is_accepted() -> None:
    name = "a" * MAX_DECK_NAME_LENGTH

    assert validated_deck_name(name) == name


# --- As três regras da feature 001 ------------------------------------------


def test_a_valid_list_comes_back_untouched(
    catalog: CardCatalog, valid_card_ids: list[CardId]
) -> None:
    assert list(validated_card_ids(valid_card_ids, catalog)) == valid_card_ids


def test_a_draft_of_twelve_cards_is_refused(
    catalog: CardCatalog, valid_card_ids: list[CardId]
) -> None:
    """Não existe rascunho: as três regras valem no salvamento."""
    with pytest.raises(InvalidDeckError) as refused:
        validated_card_ids(valid_card_ids[:12], catalog)

    assert "deck has 12 cards, expected exactly 40" in str(refused.value)


def test_an_empty_list_is_refused(catalog: CardCatalog) -> None:
    with pytest.raises(InvalidDeckError) as refused:
        validated_card_ids([], catalog)

    assert "deck has 0 cards" in str(refused.value)


def test_a_fourth_copy_is_refused_naming_the_card_and_the_count(
    catalog: CardCatalog, valid_card_ids: list[CardId]
) -> None:
    """O caso nominal da spec: 40 entradas, uma carta 4 vezes. A recusa nomeia
    a carta e a contagem, não um "deck inválido" genérico."""
    card_ids = valid_card_ids[:-1] + [CardId(1)]

    with pytest.raises(InvalidDeckError) as refused:
        validated_card_ids(card_ids, catalog)

    assert "card_id 1 appears 4 times, limit is 3" in str(refused.value)


def test_a_card_outside_the_catalog_is_refused_naming_it(
    catalog: CardCatalog, valid_card_ids: list[CardId]
) -> None:
    card_ids = valid_card_ids[:-1] + [MISSING]

    with pytest.raises(InvalidDeckError) as refused:
        validated_card_ids(card_ids, catalog)

    assert f"card_id {MISSING} is not in the catalog" in str(refused.value)


def test_every_problem_comes_out_at_once(
    catalog: CardCatalog, valid_card_ids: list[CardId]
) -> None:
    """39 entradas, uma carta 4 vezes e uma fora do catálogo: três problemas,
    uma recusa só."""
    card_ids = valid_card_ids[:37] + [CardId(1), MISSING]

    with pytest.raises(InvalidDeckError) as refused:
        validated_card_ids(card_ids, catalog)

    assert len(refused.value.problems) == 3


# --- O teto -----------------------------------------------------------------


def test_there_is_room_below_the_limit() -> None:
    ensure_room_for_another_deck(DECK_LIMIT_PER_PLAYER - 1)


def test_at_the_limit_there_is_no_room_and_the_refusal_says_both_numbers() -> None:
    with pytest.raises(TooManyDecksError) as refused:
        ensure_room_for_another_deck(DECK_LIMIT_PER_PLAYER)

    assert str(DECK_LIMIT_PER_PLAYER) in str(refused.value)


def test_the_limit_is_twenty() -> None:
    """O número que a spec fixou. Mudá-lo é mudar a decisão, não um detalhe."""
    assert DECK_LIMIT_PER_PLAYER == 20
