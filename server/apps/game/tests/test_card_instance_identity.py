"""Cada carta em partida é endereçável sozinha.

Duas cópias de KRONOS no banco são coisas diferentes, e um feitiço mirado numa
delas não pode acertar a outra. É o que torna a revalidação de alvo da §6
possível.
"""

import pytest

from apps.game.cards import CardId
from apps.game.match import BankUnit, CardInstanceId, Match, MatchCard
from apps.game.tests.fake_match_state import (
    fake_cards,
    fake_match_in_progress,
    fake_new_match,
)

KRONOS = CardId(15)


@pytest.fixture
def match() -> Match:
    return fake_new_match()


def test_two_copies_of_the_same_card_get_different_identifiers(match: Match) -> None:
    first, second = fake_cards(match, [KRONOS, KRONOS])

    assert first.card_instance_id != second.card_instance_id


def test_two_copies_of_the_same_card_keep_the_same_card_id(match: Match) -> None:
    """A identidade é da cópia; o molde continua compartilhado."""
    first, second = fake_cards(match, [KRONOS, KRONOS])

    assert first.card_id == second.card_id == KRONOS


def test_the_instance_identifier_lives_in_its_own_space(match: Match) -> None:
    """Os dois são inteiros e viajam nos mesmos payloads, mas são espaços
    diferentes.

    A proteção de verdade é estática: `mypy` recusa comparar `CardInstanceId`
    com `CardId` diretamente (`comparison-overlap`), então trocar um pelo
    outro numa assinatura não compila. Aqui a comparação é entre os inteiros
    crus só para deixar o caso registrado em teste.
    """
    card = fake_cards(match, [KRONOS])[0]

    assert int(card.card_instance_id) != int(card.card_id)


def test_minting_advances_the_counter(match: Match) -> None:
    match.mint_card_instance_id()
    match.mint_card_instance_id()

    assert match.next_card_instance_id == 3


def test_minted_identifiers_are_never_reused(match: Match) -> None:
    minted = [match.mint_card_instance_id() for _ in range(10)]

    assert len(set(minted)) == 10


def test_no_identifier_repeats_across_the_two_players() -> None:
    """O espaço é único na partida, não um por jogador: a ação e o combate
    guardam o alvo como um número solto, e ele não pode ser ambíguo."""
    match = fake_match_in_progress()

    assert len(_all_identifiers(match)) == len(set(_all_identifiers(match)))


def test_the_identifier_survives_every_zone_change(match: Match) -> None:
    """Deck, mão, banco e cemitério: o mesmo número nas quatro."""
    player = match.players[0]
    player.deck = fake_cards(match, [KRONOS])
    born = player.deck[0].card_instance_id

    player.hand.append(player.deck.pop())
    player.bank.append(BankUnit(card=player.hand.pop()))
    player.graveyard.append(player.bank.pop().card)

    assert player.graveyard[0].card_instance_id == born


def test_moving_to_the_bank_keeps_the_same_card_object(match: Match) -> None:
    """A identidade sobrevive por construção: `BankUnit` contém a carta, não
    copia os campos dela."""
    player = match.players[0]
    player.hand = fake_cards(match, [KRONOS])
    card = player.hand[0]

    player.bank.append(BankUnit(card=player.hand.pop()))

    assert player.bank[0].card is card


def test_a_deck_reset_returns_the_same_identifiers(match: Match) -> None:
    """O reset da §9 devolve as mesmas cartas, sem passar pelo contador."""
    player = match.players[0]
    player.graveyard = fake_cards(match, [KRONOS, 22, 1004])
    buried = [card.card_instance_id for card in player.graveyard]
    counter_before = match.next_card_instance_id

    player.deck, player.graveyard = player.graveyard, []

    assert [card.card_instance_id for card in player.deck] == buried
    assert match.next_card_instance_id == counter_before


def test_a_card_in_hand_has_nowhere_to_carry_damage(match: Match) -> None:
    """Vida e modificador só existem para unidade no banco."""
    card = MatchCard(CardInstanceId(1), KRONOS)

    assert not hasattr(card, "damage_taken")
    assert not hasattr(card, "modifiers")


def _all_identifiers(match: Match) -> list[CardInstanceId]:
    """Todo identificador vivo na partida, nas quatro zonas dos dois lados."""
    identifiers: list[CardInstanceId] = []

    for player in match.players:
        loose = player.deck + player.hand + player.graveyard
        identifiers += [card.card_instance_id for card in loose]
        identifiers += [unit.card.card_instance_id for unit in player.bank]

    return identifiers
