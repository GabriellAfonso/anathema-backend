"""O Fim de Rodada da §8: a varredura de modificadores, a troca de token e a
virada de rodada.

Nenhum feitiço existe ainda para criar um modificador "até o fim da rodada", e é
por isso que os modificadores destes testes são postos à mão. A varredura precisa
existir e ser testada agora -- senão a feature de pilha teria de voltar aqui, e o
primeiro buff temporário do jogo seria também o primeiro a nunca expirar.

O teste que mais paga é `test_damage_is_not_swept`: dano não é modificador, e uma
varredura escrita sobre "tudo que é temporário na unidade" o levaria junto.
"""

from apps.game.cards import EffectDuration
from apps.game.engine.round_end import end_round
from apps.game.match import (
    AttackModifier,
    BankUnit,
    DamageImmunity,
    HealthModifier,
    Match,
    MatchPhase,
    NotAParticipantError,
    UnitModifier,
)
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_new_match,
)
from apps.game.tests.match_snapshot import match_snapshot

import pytest

TEMPORARY = AttackModifier(amount=2, duration=EffectDuration.UNTIL_END_OF_ROUND)
PERMANENT = HealthModifier(amount=1, duration=EffectDuration.PERMANENT)
TEMPORARY_IMMUNITY = DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND)


def match_at_round_end(round_number: int = 3) -> Match:
    """Partida com uma unidade em cada banco, parada na Fase de Ação."""
    match = fake_new_match()

    match.round_number = round_number
    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = PLAYER_ONE
    match.phase = MatchPhase.ACTION
    match.consecutive_passes = 2

    for index, player in enumerate(match.players):
        player.bank = [BankUnit(card=card) for card in fake_cards(match, [15 + index])]

    return match


def modifiers_of(match: Match, side: int) -> list[UnitModifier]:
    return match.players[side].bank[0].modifiers


# --- A varredura -------------------------------------------------------------


def test_a_modifier_that_lasts_until_the_end_of_the_round_is_removed() -> None:
    match = match_at_round_end()
    modifiers_of(match, 0).append(TEMPORARY)

    end_round(match)

    assert modifiers_of(match, 0) == []


def test_a_permanent_modifier_stays() -> None:
    match = match_at_round_end()
    modifiers_of(match, 0).append(PERMANENT)

    end_round(match)

    assert modifiers_of(match, 0) == [PERMANENT]


def test_only_the_temporary_one_goes_when_a_unit_carries_both() -> None:
    match = match_at_round_end()
    modifiers_of(match, 0).extend([TEMPORARY, PERMANENT, TEMPORARY_IMMUNITY])

    end_round(match)

    assert modifiers_of(match, 0) == [PERMANENT]


def test_both_banks_are_swept() -> None:
    match = match_at_round_end()
    modifiers_of(match, 0).extend([TEMPORARY, PERMANENT])
    modifiers_of(match, 1).extend([PERMANENT, TEMPORARY_IMMUNITY])

    end_round(match)

    assert modifiers_of(match, 0) == [PERMANENT]
    assert modifiers_of(match, 1) == [PERMANENT]


def test_damage_is_not_swept() -> None:
    """Dano não é modificador: não expira e não some no Fim de Rodada."""
    match = match_at_round_end()
    match.players[0].bank[0].damage_taken = 3
    modifiers_of(match, 0).append(TEMPORARY)

    end_round(match)

    assert match.players[0].bank[0].damage_taken == 3


def test_an_empty_bank_on_both_sides_is_not_an_error() -> None:
    match = match_at_round_end()
    for player in match.players:
        player.bank = []

    end_round(match)

    assert match.round_number == 4


def test_a_unit_with_nothing_to_sweep_is_left_alone() -> None:
    match = match_at_round_end()
    modifiers_of(match, 0).append(PERMANENT)
    unit = match.players[0].bank[0]

    end_round(match)

    assert match.players[0].bank[0] is unit
    assert unit.modifiers == [PERMANENT]


# --- Token, rodada e fase ----------------------------------------------------


def test_the_token_goes_to_the_other_player() -> None:
    match = match_at_round_end()

    end_round(match)

    assert match.token_holder_user_id == PLAYER_TWO


def test_the_round_number_goes_up_by_one() -> None:
    match = match_at_round_end(round_number=7)

    end_round(match)

    assert match.round_number == 8


def test_the_round_end_returns_to_the_upkeep() -> None:
    match = match_at_round_end()

    end_round(match)

    assert match.phase is MatchPhase.UPKEEP


def test_a_match_without_a_token_holder_is_refused_naming_the_match() -> None:
    """Estado corrompido, não fluxo: o token é sorteado na §3, antes da Ação."""
    match = match_at_round_end()
    match.token_holder_user_id = None
    before = match_snapshot(match)

    with pytest.raises(NotAParticipantError, match=match.match_id):
        end_round(match)

    assert match_snapshot(match)["token_holder_user_id"] is None
    assert match_snapshot(match)["round_number"] == before["round_number"]


# --- O que o Fim de Rodada não faz -------------------------------------------


def test_there_is_no_discard_for_holding_too_many_cards() -> None:
    """O teto de 10 é aplicado na compra (§9), e a §8 registra que não é aqui."""
    match = match_at_round_end()
    match.players[0].hand = fake_cards(match, list(range(21, 31)))
    hand_before = list(match.players[0].hand)

    end_round(match)

    assert match.players[0].hand == hand_before


def test_the_round_end_touches_neither_nexus_nor_the_card_zones() -> None:
    match = match_at_round_end()
    for player in match.players:
        player.deck = fake_cards(match, [31, 32])
        player.hand = fake_cards(match, [41])
        player.graveyard = fake_cards(match, [1001])

    before = match_snapshot(match)

    end_round(match)

    after = match_snapshot(match)
    for one, other in zip(before["players"], after["players"], strict=True):
        assert one["nexus"] == other["nexus"]
        assert one["deck"] == other["deck"]
        assert one["hand"] == other["hand"]
        assert one["graveyard"] == other["graveyard"]
        assert len(one["bank"]) == len(other["bank"])


def test_the_round_end_does_not_refill_energy() -> None:
    """Recarregar é da §4. Encadear as duas por dentro faria a §8 dona da §4."""
    match = match_at_round_end()
    match.players[0].energy_max = 3
    match.players[0].energy_current = 1

    end_round(match)

    assert match.players[0].energy_max == 3
    assert match.players[0].energy_current == 1


def test_the_round_end_does_not_touch_the_passes_or_the_priority() -> None:
    """Zerar os passes e repor a prioridade são passos da §4."""
    match = match_at_round_end()

    end_round(match)

    assert match.consecutive_passes == 2
    assert match.priority_user_id == PLAYER_ONE
