"""O reset de deck da §9: o cemitério inteiro vira o novo deck, embaralhado.

É o que sustenta a garantia de que nenhuma partida acaba por deck acabado.
Errar aqui não trava a partida -- some com cartas, ou devolve ao deck uma carta
com identidade nova, e nenhum teste de contagem de mão perceberia.

Duas fontes de aleatoriedade, de propósito. `ScriptedRandomSource` para
afirmar a ordem concreta, que com uma fonte semeada seria afirmar o algoritmo
do CPython; `SeededRandomSource` para afirmar determinismo, que com a fonte
roteirizada não afirmaria nada -- ela é determinística por construção.
"""

import json

import pytest

from apps.game.engine import reset_deck_from_graveyard
from apps.game.match import (
    BankUnit,
    Match,
    PlayerState,
    match_from_document,
    to_match_document,
)
from apps.game.randomness import RandomSeed, SeededRandomSource
from apps.game.tests.fake_match_state import fake_cards, fake_new_match
from apps.game.tests.fake_random_source import ScriptedRandomSource

GRAVEYARD = [15, 22, 31, 32, 33]


@pytest.fixture
def match() -> Match:
    return fake_new_match()


@pytest.fixture
def player(match: Match) -> PlayerState:
    """Deck vazio e cemitério cheio: as duas pré-condições que a §9 verifica."""
    state = match.players[0]
    state.graveyard = fake_cards(match, GRAVEYARD)

    return state


def test_the_graveyard_becomes_the_deck(match: Match, player: PlayerState) -> None:
    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert len(player.deck) == len(GRAVEYARD)


def test_the_graveyard_is_left_empty(match: Match, player: PlayerState) -> None:
    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert player.graveyard == []


def test_the_new_deck_is_an_exact_permutation(
    match: Match, player: PlayerState
) -> None:
    """Nada duplicado, nada perdido -- é permutação, não amostra."""
    before = {card.card_instance_id for card in player.graveyard}

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert {card.card_instance_id for card in player.deck} == before


def test_the_identifiers_come_back_unchanged(match: Match, player: PlayerState) -> None:
    """A carta que morreu é a mesma carta que volta: identidade acompanha ela."""
    born = [(card.card_instance_id, card.card_id) for card in player.graveyard]

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert sorted((c.card_instance_id, c.card_id) for c in player.deck) == sorted(born)


def test_the_reset_does_not_mint_a_new_identifier(
    match: Match, player: PlayerState
) -> None:
    counter_before = match.next_card_instance_id

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert match.next_card_instance_id == counter_before


def test_the_hand_and_the_bank_are_not_touched(
    match: Match, player: PlayerState
) -> None:
    player.hand = fake_cards(match, [41, 42])
    player.bank = [BankUnit(card=card) for card in fake_cards(match, [51])]
    hand_before, bank_before = list(player.hand), list(player.bank)

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert player.hand == hand_before
    assert player.bank == bank_before


def test_the_nexus_and_the_energies_are_not_touched(
    match: Match, player: PlayerState
) -> None:
    player.nexus = 13
    player.energy_max = 5
    player.energy_current = 2

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert (player.nexus, player.energy_max, player.energy_current) == (13, 5, 2)


def test_the_order_is_the_one_the_source_dictated(
    match: Match, player: PlayerState
) -> None:
    """`ScriptedRandomSource` inverte a lista, e é isso que precisa sair."""
    reversed_ids = [card.card_id for card in reversed(player.graveyard)]

    reset_deck_from_graveyard(
        player, randomness=ScriptedRandomSource(), roll=match.mint_roll()
    )

    assert [card.card_id for card in player.deck] == reversed_ids


def test_the_roll_reaches_the_source_untouched(
    match: Match, player: PlayerState
) -> None:
    """Um sorteio, e é o que o chamador passou -- a função não cunha o seu."""
    source = ScriptedRandomSource()
    roll = match.mint_roll()

    reset_deck_from_graveyard(player, randomness=source, roll=roll)

    assert source.rolls == [roll]


def test_the_same_graveyard_and_roll_give_the_same_deck() -> None:
    """Sem isto, nenhum teste que atravesse um reset é repetível."""
    assert _deck_after_reset(FAKE_SEED_ONE) == _deck_after_reset(FAKE_SEED_ONE)


def test_different_seeds_give_different_decks() -> None:
    """A semente é o que decide, e não uma ordem fixa escondida."""
    assert _deck_after_reset(FAKE_SEED_ONE) != _deck_after_reset(FAKE_SEED_TWO)


def test_a_reload_continues_the_sequence_instead_of_restarting(
    match: Match, player: PlayerState
) -> None:
    """Dois resets seguidos, com a partida indo e voltando pela serialização.

    O segundo reset precisa abrir um fluxo novo, não repetir o primeiro. É o
    `next_roll_ordinal` gravado que sustenta isso -- se ele não sobrevivesse à
    volta, os dois decks sairiam iguais.
    """
    source = SeededRandomSource()

    reset_deck_from_graveyard(player, randomness=source, roll=match.mint_roll())
    first = [card.card_id for card in player.deck]

    reloaded = match_from_document(json.loads(json.dumps(to_match_document(match))))
    survivor = reloaded.players[0]
    survivor.graveyard, survivor.deck = survivor.deck, []

    reset_deck_from_graveyard(survivor, randomness=source, roll=reloaded.mint_roll())

    assert [card.card_id for card in survivor.deck] != first


def test_the_state_right_after_a_reset_survives_the_round_trip(
    match: Match, player: PlayerState
) -> None:
    """A garantia da feature 002 continua valendo depois de um reset.

    O reset não cria campo nenhum, então isto vale por construção -- mas o
    estado que ele produz tem uma forma que nenhum outro fake monta: cemitério
    vazio, deck reordenado por um sorteio de meio de partida, e
    `next_roll_ordinal` acima de 1. Sem Redis: a serialização é onde o
    round-trip pode quebrar, e o Redis é só o meio.
    """
    player.hand = fake_cards(match, [41, 42])
    reset_deck_from_graveyard(
        player, randomness=SeededRandomSource(), roll=match.mint_roll()
    )

    reloaded = match_from_document(json.loads(json.dumps(to_match_document(match))))

    assert reloaded == match
    assert reloaded.players[0].graveyard == []
    assert reloaded.next_roll_ordinal > 1


FAKE_SEED_ONE = RandomSeed("seed-one")
FAKE_SEED_TWO = RandomSeed("seed-two")


def _deck_after_reset(seed: RandomSeed) -> list[int]:
    """Um reset isolado, do zero, sob a semente pedida.

    Monta a partida por dentro em vez de usar a fixture porque as duas provas
    de determinismo precisam variar a semente, e `fake_new_match` a fixa.
    """
    match = fake_new_match()
    match.random_seed = seed
    player = match.players[0]
    player.graveyard = fake_cards(match, GRAVEYARD)

    reset_deck_from_graveyard(
        player, randomness=SeededRandomSource(), roll=match.mint_roll()
    )

    return [card.card_id for card in player.deck]
