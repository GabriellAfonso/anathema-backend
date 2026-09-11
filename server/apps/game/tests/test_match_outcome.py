"""O resultado da partida nomeia os derrotados e recusa o que não é resultado.

A §10 tem um fato primitivo só -- quem chegou a Nexus <= 0 --, e vitória e
empate são leituras dele. Estes testes cobrem as duas leituras e as três formas
de construir um resultado impossível.
"""

import pytest

from apps.game.match import InvalidMatchOutcomeError, MatchOutcome
from apps.game.tests.fake_match_state import PLAYER_ONE, PLAYER_TWO


def test_one_defeated_player_is_not_a_draw() -> None:
    assert MatchOutcome(defeated_user_ids=(PLAYER_ONE,)).is_draw is False


def test_two_defeated_players_is_a_draw() -> None:
    """A §10: os dois Nexus <= 0 no mesmo cálculo."""
    assert MatchOutcome(defeated_user_ids=(PLAYER_ONE, PLAYER_TWO)).is_draw is True


def test_the_defeated_are_kept_in_the_order_they_were_given() -> None:
    """Tupla e não conjunto: o documento precisa comparar por `==` até o fundo,
    e é assim que `match_snapshot` prova atomicidade."""
    outcome = MatchOutcome(defeated_user_ids=(PLAYER_TWO, PLAYER_ONE))

    assert outcome.defeated_user_ids == (PLAYER_TWO, PLAYER_ONE)


def test_a_result_without_a_defeated_player_is_refused() -> None:
    """Partida sem derrotado não acabou."""
    with pytest.raises(InvalidMatchOutcomeError) as refusal:
        MatchOutcome(defeated_user_ids=())

    assert "()" in str(refusal.value)
    assert "one or two distinct user_ids" in str(refusal.value)


def test_a_result_with_three_defeated_players_is_refused() -> None:
    """A partida tem dois jogadores (§2)."""
    with pytest.raises(InvalidMatchOutcomeError) as refusal:
        MatchOutcome(defeated_user_ids=(PLAYER_ONE, PLAYER_TWO, 11))

    assert str(11) in str(refusal.value)


def test_a_repeated_defeated_player_is_refused() -> None:
    """O mesmo jogador não perde duas vezes."""
    with pytest.raises(InvalidMatchOutcomeError) as refusal:
        MatchOutcome(defeated_user_ids=(PLAYER_ONE, PLAYER_ONE))

    assert refusal.value.defeated_user_ids == (PLAYER_ONE, PLAYER_ONE)


def test_the_refusal_carries_the_offending_value() -> None:
    """Recusa genérica não serve para depurar."""
    with pytest.raises(InvalidMatchOutcomeError) as refusal:
        MatchOutcome(defeated_user_ids=())

    assert refusal.value.defeated_user_ids == ()
