"""A ação A da §5: jogar unidade, e as quatro recusas dela.

O teste central deste arquivo é
`test_a_refused_play_leaves_the_match_untouched`: é ele que pega uma
implementação que desconte a energia antes de conferir o banco, ou que tire a
carta da mão antes de conferir a energia. Meia ação aplicada deixa a partida em
estado que nenhuma regra produziria, e nenhum teste de contagem percebe.

O catálogo é montado aqui, com valores redondos, em vez de vir do MVP: um teste
de guarda de energia que dependa do balanceamento das 29 cartas reais quebra no
dia em que alguém mexer num custo.
"""

import pytest

from apps.game.cards import CardId, Spell, Unit
from apps.game.cards.effects import DamageUnit
from apps.game.engine import (
    BankIsFullError,
    CardIsNotAUnitError,
    CardNotInHandError,
    NotEnoughEnergyError,
    PlayUnitAction,
)
from apps.game.engine.play_unit import MAX_BANK_SIZE, play_unit
from apps.game.match import BankUnit, CardInstanceId, Match, MatchPhase
from apps.game.tests.fake_card_catalog import FakeCardCatalog
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.match_snapshot import match_snapshot

FREE_UNIT = Unit(
    card_id=CardId(1), name="FREE", energy=0, attack=1, health=1, image="free_card"
)
CHEAP_UNIT = Unit(
    card_id=CardId(2), name="CHEAP", energy=2, attack=3, health=4, image="cheap_card"
)
COSTLY_UNIT = Unit(
    card_id=CardId(3), name="COSTLY", energy=3, attack=5, health=5, image="costly_card"
)
A_SPELL = Spell(
    card_id=CardId(1001),
    name="A SPELL",
    energy=1,
    description="Causa 1 de dano à unidade inimiga alvo.",
    effect=DamageUnit(amount=1),
    image="spell_card",
)

CATALOG = FakeCardCatalog([FREE_UNIT, CHEAP_UNIT, COSTLY_UNIT, A_SPELL])


def match_with_hand(
    hand_card_ids: list[int], *, energy: int = 3, bank_size: int = 0
) -> Match:
    """Partida na Fase de Ação com a mão, a energia e o banco pedidos."""
    match = fake_new_match()

    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = PLAYER_ONE
    match.phase = MatchPhase.ACTION

    actor = match.players[0]
    actor.hand = fake_cards(match, hand_card_ids)
    actor.energy_max = energy
    actor.energy_current = energy
    actor.bank = [BankUnit(card=card) for card in fake_cards(match, [1] * bank_size)]

    return match


def play(match: Match, card_index: int = 0) -> None:
    actor = match.players[0]
    action = PlayUnitAction(
        actor_user_id=actor.user_id,
        card_instance_id=actor.hand[card_index].card_instance_id,
    )

    play_unit(match, actor, action, catalog=CATALOG)


# --- A jogada aceita ---------------------------------------------------------


def test_the_energy_is_deducted_and_the_card_leaves_the_hand() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id], energy=3)

    play(match)

    assert match.players[0].energy_current == 1
    assert match.players[0].hand == []


def test_the_unit_lands_in_the_bank_of_the_author() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])
    played = match.players[0].hand[0].card_instance_id

    play(match)

    assert len(match.players[0].bank) == 1
    assert match.players[0].bank[0].card.card_instance_id == played


def test_the_unit_keeps_the_identity_it_had_in_the_hand() -> None:
    """Trocar de zona não cunha identidade nova."""
    match = match_with_hand([CHEAP_UNIT.card_id])
    card = match.players[0].hand[0]
    minted_before = match.next_card_instance_id

    play(match)

    assert match.players[0].bank[0].card is card
    assert match.next_card_instance_id == minted_before


def test_the_unit_enters_ready_and_undamaged() -> None:
    """Não existe doença de invocação (§5A), e nada a marca como recém-jogada."""
    match = match_with_hand([CHEAP_UNIT.card_id])

    play(match)

    unit = match.players[0].bank[0]
    assert unit.damage_taken == 0
    assert unit.modifiers == []


def test_playing_a_unit_resets_the_consecutive_passes() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])
    match.consecutive_passes = 1

    play(match)

    assert match.consecutive_passes == 0


def test_the_opponent_is_not_touched() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])
    before = match_snapshot(match)["players"][1]

    play(match)

    assert match_snapshot(match)["players"][1] == before


def test_playing_a_unit_changes_no_nexus() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])
    nexus_before = [player.nexus for player in match.players]

    play(match)

    assert [player.nexus for player in match.players] == nexus_before


# --- As bordas das guardas ---------------------------------------------------


def test_energy_exactly_equal_to_the_cost_is_accepted() -> None:
    """A guarda é `energia >= custo`, não `>`."""
    match = match_with_hand([CHEAP_UNIT.card_id], energy=2)

    play(match)

    assert match.players[0].energy_current == 0
    assert len(match.players[0].bank) == 1


def test_a_free_unit_is_playable_with_no_energy_at_all() -> None:
    match = match_with_hand([FREE_UNIT.card_id], energy=0)

    play(match)

    assert len(match.players[0].bank) == 1


def test_a_bank_with_five_units_still_has_room() -> None:
    """A guarda é `banco < 6`: com 5 a jogada passa e o banco vai a 6."""
    match = match_with_hand([CHEAP_UNIT.card_id], bank_size=MAX_BANK_SIZE - 1)

    play(match)

    assert len(match.players[0].bank) == MAX_BANK_SIZE


# --- As quatro recusas -------------------------------------------------------


def test_not_enough_energy_is_refused_naming_cost_and_available() -> None:
    match = match_with_hand([COSTLY_UNIT.card_id], energy=1)

    with pytest.raises(NotEnoughEnergyError, match="costs 3 energy, has 1") as refused:
        play(match)

    assert refused.value.cost == 3
    assert refused.value.available == 1


def test_a_full_bank_is_refused_naming_the_limit() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id], bank_size=MAX_BANK_SIZE)

    with pytest.raises(BankIsFullError, match=str(MAX_BANK_SIZE)) as refused:
        play(match)

    assert refused.value.bank_size == MAX_BANK_SIZE


def test_a_card_that_is_not_in_the_hand_is_refused_naming_the_card() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])
    absent = CardInstanceId(999)
    action = PlayUnitAction(actor_user_id=PLAYER_ONE, card_instance_id=absent)

    with pytest.raises(CardNotInHandError, match=str(absent)) as refused:
        play_unit(match, match.players[0], action, catalog=CATALOG)

    assert refused.value.card_instance_id == absent


def test_the_hand_consulted_is_always_the_authors() -> None:
    """Citar a carta do oponente cai na mesma recusa de carta que não existe."""
    match = match_with_hand([CHEAP_UNIT.card_id])
    match.players[1].hand = fake_cards(match, [CHEAP_UNIT.card_id])
    theirs = match.players[1].hand[0].card_instance_id
    action = PlayUnitAction(actor_user_id=PLAYER_ONE, card_instance_id=theirs)

    with pytest.raises(CardNotInHandError, match=str(theirs)):
        play_unit(match, match.players[0], action, catalog=CATALOG)


def test_a_spell_played_as_a_unit_is_refused_naming_the_type() -> None:
    """Usar a ação errada não é atalho para jogar feitiço."""
    match = match_with_hand([A_SPELL.card_id])

    with pytest.raises(CardIsNotAUnitError, match="expected a unit") as refused:
        play(match)

    assert refused.value.card_type is A_SPELL.card_type


# --- A atomicidade da recusa -------------------------------------------------


@pytest.mark.parametrize(
    "hand, energy, bank_size",
    [
        ([COSTLY_UNIT.card_id], 1, 0),
        ([CHEAP_UNIT.card_id], 3, MAX_BANK_SIZE),
        ([A_SPELL.card_id], 3, 0),
    ],
    ids=["no-energy", "full-bank", "spell"],
)
def test_a_refused_play_leaves_the_match_untouched(
    hand: list[int], energy: int, bank_size: int
) -> None:
    match = match_with_hand(hand, energy=energy, bank_size=bank_size)
    match.consecutive_passes = 1
    before = match_snapshot(match)

    with pytest.raises(Exception):
        play(match)

    assert match_snapshot(match) == before


def test_a_refused_play_does_not_reset_the_passes() -> None:
    """Zerar os passes é efeito da jogada, e a jogada não aconteceu."""
    match = match_with_hand([COSTLY_UNIT.card_id], energy=1)
    match.consecutive_passes = 1

    with pytest.raises(NotEnoughEnergyError):
        play(match)

    assert match.consecutive_passes == 1


def test_a_refused_play_advances_no_match_counter() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id], bank_size=MAX_BANK_SIZE)
    cards_before = match.next_card_instance_id
    rolls_before = match.next_roll_ordinal

    with pytest.raises(BankIsFullError):
        play(match)

    assert match.next_card_instance_id == cards_before
    assert match.next_roll_ordinal == rolls_before


def test_the_guard_order_shows_in_which_refusal_arrives() -> None:
    """Sem energia **e** com o banco cheio: a recusa é a de energia.

    A ordem é carta na mão, carta é unidade, energia, banco -- e a energia vem
    antes justamente porque o custo é o número que o cliente precisa mostrar.
    """
    match = match_with_hand([COSTLY_UNIT.card_id], energy=1, bank_size=MAX_BANK_SIZE)

    with pytest.raises(NotEnoughEnergyError):
        play(match)


def test_a_spell_is_refused_before_the_energy_is_looked_at() -> None:
    match = match_with_hand([A_SPELL.card_id], energy=0)

    with pytest.raises(CardIsNotAUnitError):
        play(match)


def test_playing_a_unit_never_touches_the_graveyard() -> None:
    match = match_with_hand([CHEAP_UNIT.card_id])

    play(match)

    assert match.players[0].graveyard == []


def test_the_opponent_keeps_playing_from_their_own_bank_limit() -> None:
    """O teto de banco é por jogador, não por partida."""
    match = match_with_hand([CHEAP_UNIT.card_id], bank_size=MAX_BANK_SIZE)
    match.players[1].bank = []

    with pytest.raises(BankIsFullError, match=str(PLAYER_ONE)):
        play(match)

    assert match.players[1].user_id == PLAYER_TWO
    assert match.players[1].bank == []
