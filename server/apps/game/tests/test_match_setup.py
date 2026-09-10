"""O setup da §3, das duas pontas: a criação e o fechamento.

A criação valida os decks, materializa as cartas, embaralha e compra 4, e para
na espera do mulligan. O fechamento sorteia o token, compensa quem não o
recebeu, e posiciona a partida para o Upkeep da Rodada 1.

O mulligan em si é de `test_mulligan.py`; aqui ele só aparece como o gatilho
que fecha o setup.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, Deck, mvp_catalog, starter_deck
from apps.game.engine import (
    InvalidPlayerDeckError,
    MatchEntry,
    record_mulligan,
    start_match,
)
from apps.game.match import Match, MatchCard, MatchPhase, PlayerState
from apps.game.randomness import RandomSeed
from apps.game.tests.fake_player_data import fake_player_data
from apps.game.tests.fake_random_source import ScriptedRandomSource

PLAYER_ONE = 7
PLAYER_TWO = 9

OPENING_HAND = 4
DECK_AFTER_OPENING_HAND = 36
SEED = RandomSeed("test-setup-seed")


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def deck(catalog: CardCatalog) -> Deck:
    return starter_deck(catalog)


@pytest.fixture
def match(catalog: CardCatalog, deck: Deck) -> Match:
    return started(catalog, deck, deck)


def started(catalog: CardCatalog, first: Deck, second: Deck) -> Match:
    return start_match(
        MatchEntry(profile=fake_player_data(PLAYER_ONE, "one"), deck=first),
        MatchEntry(profile=fake_player_data(PLAYER_TWO, "two"), deck=second),
        catalog=catalog,
        randomness=ScriptedRandomSource(),
        seed=SEED,
    )


def all_cards(player: PlayerState) -> list[MatchCard]:
    return [*player.deck, *player.hand]


def instance_ids(match: Match) -> list[int]:
    return [
        card.card_instance_id for player in match.players for card in all_cards(player)
    ]


# --- Criação --------------------------------------------------------------


def test_each_player_draws_the_opening_hand(match: Match) -> None:
    for player in match.players:
        assert len(player.hand) == OPENING_HAND
        assert len(player.deck) == DECK_AFTER_OPENING_HAND


def test_no_card_is_lost_between_deck_and_hand(match: Match) -> None:
    for player in match.players:
        assert len(all_cards(player)) == 40


def test_each_player_starts_with_the_opening_values(match: Match) -> None:
    """Nexus 20 e energia zerada: subir para 1 é do primeiro Upkeep (§4)."""
    for player in match.players:
        assert player.nexus == 20
        assert player.energy_max == 0
        assert player.energy_current == 0


def test_the_match_starts_waiting_for_both_mulligans(match: Match) -> None:
    assert match.phase is MatchPhase.MULLIGAN
    assert match.awaiting_mulligan_user_ids == (PLAYER_ONE, PLAYER_TWO)


def test_no_token_holder_before_the_draw(match: Match) -> None:
    """`None`, e não um valor de espera: no meio do setup ninguém tem o token."""
    assert match.token_holder_user_id is None
    assert match.priority_user_id is None


def test_two_matches_do_not_share_an_id(catalog: CardCatalog, deck: Deck) -> None:
    """Duas partidas criadas com a mesma semente ainda são partidas
    diferentes: o `match_id` é endereço, e não resultado do setup."""
    assert (
        started(catalog, deck, deck).match_id != started(catalog, deck, deck).match_id
    )


def test_the_other_zones_start_empty(match: Match) -> None:
    assert match.stack == []
    assert match.round_number == 1
    assert match.consecutive_passes == 0

    for player in match.players:
        assert player.bank == []
        assert player.graveyard == []


def test_the_deck_is_shuffled_by_the_injected_source(
    catalog: CardCatalog, deck: Deck
) -> None:
    """`ScriptedRandomSource` inverte: a mão sai do fim do deck de entrada.

    O que se prova é que a ordem veio da fonte, e não da ordem de entrada nem
    de um gerador global.
    """
    match = started(catalog, deck, deck)

    drawn = [card.card_id for card in match.players[0].hand]

    assert drawn == list(reversed(deck))[:OPENING_HAND]


# --- Identidade -----------------------------------------------------------


def test_three_copies_become_three_addressable_cards(
    catalog: CardCatalog, deck: Deck
) -> None:
    match = started(catalog, deck, deck)
    repeated = _most_repeated_card_id(deck)

    copies = [card for card in all_cards(match.players[0]) if card.card_id == repeated]

    assert len({card.card_instance_id for card in copies}) == len(copies)


def test_the_eighty_identifiers_never_repeat(match: Match) -> None:
    """O espaço é único na partida, não um por jogador."""
    minted = instance_ids(match)

    assert len(minted) == 80
    assert len(set(minted)) == 80


# --- Recusa de deck -------------------------------------------------------


def test_a_deck_of_the_wrong_size_is_refused(catalog: CardCatalog, deck: Deck) -> None:
    with pytest.raises(InvalidPlayerDeckError, match="39 cards"):
        started(catalog, tuple(deck[:39]), deck)


def test_too_many_copies_are_refused(catalog: CardCatalog, deck: Deck) -> None:
    flooded: Deck = (deck[0],) * 40

    with pytest.raises(InvalidPlayerDeckError, match="limit is 3"):
        started(catalog, flooded, deck)


def test_a_card_outside_the_catalog_is_refused(
    catalog: CardCatalog, deck: Deck
) -> None:
    unknown = CardId(99999)

    with pytest.raises(InvalidPlayerDeckError, match="99999"):
        started(catalog, (unknown, *deck[1:]), deck)


def test_the_refusal_names_the_owner(catalog: CardCatalog, deck: Deck) -> None:
    """Sem o dono, quem lê a recusa não sabe qual dos dois decks corrigir."""
    with pytest.raises(InvalidPlayerDeckError, match=f"user {PLAYER_ONE}"):
        started(catalog, tuple(deck[:39]), deck)


def test_the_refusal_names_every_problem_at_once(
    catalog: CardCatalog, deck: Deck
) -> None:
    broken: Deck = (deck[0],) * 39

    with pytest.raises(InvalidPlayerDeckError) as refused:
        started(catalog, broken, deck)

    assert len(refused.value.problems) == 2


def test_one_bad_deck_refuses_the_whole_match(catalog: CardCatalog, deck: Deck) -> None:
    """Não existe partida com um lado só, nem partida com um deck não
    validado."""
    with pytest.raises(InvalidPlayerDeckError, match=f"user {PLAYER_TWO}"):
        started(catalog, deck, tuple(deck[:39]))


# --- Sorteio do token e compensação ---------------------------------------


def take_both_mulligans(match: Match, choice_index: int = 0) -> None:
    source = ScriptedRandomSource(choice_index=choice_index)

    record_mulligan(match, PLAYER_ONE, [], randomness=source)
    record_mulligan(match, PLAYER_TWO, [], randomness=source)


def test_exactly_one_player_holds_the_token(match: Match) -> None:
    take_both_mulligans(match)

    assert match.token_holder_user_id in (PLAYER_ONE, PLAYER_TWO)


def test_the_token_holder_keeps_four_cards(match: Match) -> None:
    take_both_mulligans(match)
    assert match.token_holder_user_id is not None

    assert len(match.player(match.token_holder_user_id).hand) == OPENING_HAND


def test_the_other_player_draws_the_compensation_card(match: Match) -> None:
    """A desvantagem de iniciativa da §3: quem não tem o token começa com 5."""
    take_both_mulligans(match)
    assert match.token_holder_user_id is not None

    assert len(match.opponent_of(match.token_holder_user_id).hand) == 5


def test_priority_starts_with_the_token_holder(match: Match) -> None:
    take_both_mulligans(match)

    assert match.priority_user_id == match.token_holder_user_id


def test_the_match_is_positioned_for_the_first_upkeep(match: Match) -> None:
    take_both_mulligans(match)

    assert match.phase is MatchPhase.UPKEEP
    assert match.round_number == 1
    assert match.token_consumed is False
    assert match.consecutive_passes == 0


def test_the_energy_is_still_zero_after_the_setup(match: Match) -> None:
    """Entregar a partida com energia 1 seria entregá-la com o Upkeep já
    executado, e o Upkeep é da §4."""
    take_both_mulligans(match)

    for player in match.players:
        assert player.energy_max == 0
        assert player.energy_current == 0


def test_the_other_draw_result_swaps_both_sides_together(
    catalog: CardCatalog, deck: Deck
) -> None:
    """Dono do token e mão de 5 trocam de lado juntos, nunca separados."""
    holders = []

    for choice_index in (0, 1):
        match = started(catalog, deck, deck)
        take_both_mulligans(match, choice_index)
        assert match.token_holder_user_id is not None

        holders.append(match.token_holder_user_id)

        assert len(match.player(match.token_holder_user_id).hand) == OPENING_HAND
        assert len(match.opponent_of(match.token_holder_user_id).hand) == 5

    assert holders == [PLAYER_ONE, PLAYER_TWO]


def _most_repeated_card_id(deck: Deck) -> CardId:
    return max(set(deck), key=deck.count)
