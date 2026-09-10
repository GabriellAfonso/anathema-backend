"""O Upkeep da §4: recarga de energia, uma compra por jogador, e a partida
entrando na Fase de Ação.

O teste central deste arquivo é
`test_two_upkeeps_from_the_same_state_produce_the_same_match`: é ele que pega
uma ordem de resolução que dependa de prioridade, de dono do token ou de
`user_id`. Com os dois jogadores resetando o deck na mesma rodada, os dois
resets consomem o contador de sorteios da partida, e uma ordem variável mudaria
qual deck sai de qual ponto da sequência.
"""

from apps.game.engine.upkeep import MAX_ENERGY, run_upkeep
from apps.game.match import Match, MatchPhase
from apps.game.randomness import RandomSource
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource

DECK_CARD_IDS = [31, 32, 33, 34, 35]


def match_before_upkeep(
    *, round_number: int = 1, energy_max: int = 0, energy_current: int = 0
) -> Match:
    """Partida parada em `UPKEEP`, com deck em cada lado e as energias dadas."""
    match = fake_new_match()

    match.round_number = round_number
    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = None
    match.phase = MatchPhase.UPKEEP

    for player in match.players:
        player.deck = fake_cards(match, DECK_CARD_IDS)
        player.energy_max = energy_max
        player.energy_current = energy_current

    return match


def upkeep_source() -> RandomSource:
    return ScriptedRandomSource()


# --- Energia -----------------------------------------------------------------


def test_the_first_upkeep_gives_one_energy_to_both_players() -> None:
    match = match_before_upkeep()

    run_upkeep(match, randomness=upkeep_source())

    assert [player.energy_max for player in match.players] == [1, 1]
    assert [player.energy_current for player in match.players] == [1, 1]


def test_the_maximum_energy_rises_by_one_each_round() -> None:
    match = match_before_upkeep(round_number=3, energy_max=2)

    run_upkeep(match, randomness=upkeep_source())

    assert [player.energy_max for player in match.players] == [3, 3]


def test_round_eleven_and_beyond_stay_at_ten() -> None:
    """O teto da §12 se mantém, não vira 11."""
    match = match_before_upkeep(round_number=11, energy_max=MAX_ENERGY)

    run_upkeep(match, randomness=upkeep_source())

    assert [player.energy_max for player in match.players] == [10, 10]
    assert [player.energy_current for player in match.players] == [10, 10]


def test_energy_left_over_from_the_previous_round_is_lost() -> None:
    """Recarga total: a atual vira a máxima, não a máxima mais o que sobrou."""
    match = match_before_upkeep(round_number=5, energy_max=4, energy_current=4)

    run_upkeep(match, randomness=upkeep_source())

    assert [player.energy_current for player in match.players] == [5, 5]


def test_a_player_who_spent_everything_is_refilled_all_the_same() -> None:
    match = match_before_upkeep(round_number=5, energy_max=4, energy_current=0)

    run_upkeep(match, randomness=upkeep_source())

    assert match.players[0].energy_current == 5


# --- Compra ------------------------------------------------------------------


def test_each_player_draws_exactly_one_card() -> None:
    match = match_before_upkeep()

    run_upkeep(match, randomness=upkeep_source())

    assert [len(player.hand) for player in match.players] == [1, 1]
    assert [len(player.deck) for player in match.players] == [4, 4]


def test_the_card_drawn_is_the_one_on_top_of_the_deck() -> None:
    match = match_before_upkeep()
    top_of_each = [player.deck[0].card_instance_id for player in match.players]

    run_upkeep(match, randomness=upkeep_source())

    assert [player.hand[0].card_instance_id for player in match.players] == top_of_each


def test_a_player_with_a_full_hand_does_not_draw_and_the_upkeep_goes_on() -> None:
    """Mão cheia é fluxo normal (§9). O Upkeep não pode explodir por causa dela."""
    match = match_before_upkeep()
    match.players[0].hand = fake_cards(match, list(range(21, 31)))
    deck_before = list(match.players[0].deck)

    run_upkeep(match, randomness=upkeep_source())

    assert len(match.players[0].hand) == 10
    assert match.players[0].deck == deck_before
    assert len(match.players[1].hand) == 1
    assert match.phase is MatchPhase.ACTION


def test_an_empty_deck_is_reset_from_the_graveyard_before_the_draw() -> None:
    """A §9 inteira é chamada, não uma variante dela."""
    match = match_before_upkeep()
    match.players[0].deck = []
    match.players[0].graveyard = fake_cards(match, [41, 42, 43])

    run_upkeep(match, randomness=upkeep_source())

    assert len(match.players[0].hand) == 1
    assert len(match.players[0].deck) == 2
    assert match.players[0].graveyard == []


def test_an_upkeep_without_a_reset_consumes_no_roll() -> None:
    match = match_before_upkeep()
    rolls_before = match.next_roll_ordinal

    run_upkeep(match, randomness=upkeep_source())

    assert match.next_roll_ordinal == rolls_before


# --- O fim da fase -----------------------------------------------------------


def test_the_upkeep_ends_in_the_action_phase() -> None:
    match = match_before_upkeep()

    run_upkeep(match, randomness=upkeep_source())

    assert match.phase is MatchPhase.ACTION


def test_priority_goes_to_the_token_holder() -> None:
    match = match_before_upkeep()
    match.token_holder_user_id = PLAYER_TWO

    run_upkeep(match, randomness=upkeep_source())

    assert match.priority_user_id == PLAYER_TWO


def test_the_token_becomes_available_again_and_the_passes_reset() -> None:
    match = match_before_upkeep()
    match.token_consumed = True
    match.consecutive_passes = 2

    run_upkeep(match, randomness=upkeep_source())

    assert match.token_consumed is False
    assert match.consecutive_passes == 0


def test_the_upkeep_touches_neither_nexus_nor_bank() -> None:
    match = match_before_upkeep()
    nexus_before = [player.nexus for player in match.players]
    banks_before = [list(player.bank) for player in match.players]

    run_upkeep(match, randomness=upkeep_source())

    assert [player.nexus for player in match.players] == nexus_before
    assert [list(player.bank) for player in match.players] == banks_before


def test_the_upkeep_does_not_change_the_round_number() -> None:
    """Subir a rodada é da §8, não da §4."""
    match = match_before_upkeep(round_number=4)

    run_upkeep(match, randomness=upkeep_source())

    assert match.round_number == 4


# --- Ordem fixa e independência ----------------------------------------------


def match_with_both_decks_empty() -> Match:
    """O caso que torna a ordem observável: os dois resetam no mesmo Upkeep."""
    match = match_before_upkeep()

    for index, player in enumerate(match.players):
        player.deck = []
        player.graveyard = fake_cards(match, [50 + index, 60 + index, 70 + index])

    return match


def test_two_upkeeps_from_the_same_state_produce_the_same_match() -> None:
    """A ordem de resolução é fixa, então o resultado é reproduzível.

    Sem ordem fixa, qual jogador pega qual ponto da sequência de sorteios
    dependeria de quem fosse resolvido primeiro, e este teste não seria estável.
    """
    first = match_with_both_decks_empty()
    second = match_with_both_decks_empty()

    run_upkeep(first, randomness=upkeep_source())
    run_upkeep(second, randomness=upkeep_source())

    for one, other in zip(first.players, second.players, strict=True):
        assert [card.card_instance_id for card in one.deck] == [
            card.card_instance_id for card in other.deck
        ]
        assert [card.card_instance_id for card in one.hand] == [
            card.card_instance_id for card in other.hand
        ]
    assert first.next_roll_ordinal == second.next_roll_ordinal


def test_each_reset_uses_only_its_own_graveyard() -> None:
    match = match_with_both_decks_empty()
    theirs = {card.card_instance_id for card in match.players[1].graveyard}

    run_upkeep(match, randomness=upkeep_source())

    mine = {card.card_instance_id for card in match.players[0].deck} | {
        card.card_instance_id for card in match.players[0].hand
    }
    assert mine.isdisjoint(theirs)


def test_one_side_of_the_upkeep_does_not_depend_on_the_other() -> None:
    """A garantia da §4 é independência: um lado não lê o estado do outro."""
    untouched = match_before_upkeep()
    opponent_changed = match_before_upkeep()
    opponent_changed.players[1].hand = fake_cards(opponent_changed, [81, 82, 83])
    opponent_changed.players[1].nexus = 4

    run_upkeep(untouched, randomness=upkeep_source())
    run_upkeep(opponent_changed, randomness=upkeep_source())

    assert (
        untouched.players[0].energy_current
        == opponent_changed.players[0].energy_current
    )
    assert len(untouched.players[0].hand) == len(opponent_changed.players[0].hand)
