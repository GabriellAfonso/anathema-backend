"""O resultado da partida nomeia um derrotado e o motivo.

A §10, corrigida em 2026-09-11, tem duas saídas -- Nexus a zero e desistência
-- e nenhum empate. Estes testes cobrem a forma do resultado; quando ele é
escrito está em `test_victory.py` e `test_forfeit.py`.
"""

from dataclasses import fields

from apps.game.match import MatchEndReason, MatchOutcome
from apps.game.tests.fake_match_state import PLAYER_ONE


def test_the_outcome_names_one_defeated_player_and_the_reason() -> None:
    outcome = MatchOutcome(
        defeated_user_id=PLAYER_ONE, reason=MatchEndReason.NEXUS_DEPLETED
    )

    assert (outcome.defeated_user_id, outcome.reason) == (
        PLAYER_ONE,
        MatchEndReason.NEXUS_DEPLETED,
    )


def test_the_reasons_are_the_two_exits_of_the_rule() -> None:
    """Inventário deliberado: uma saída nova passa por aqui e pela §10."""
    assert [reason.value for reason in MatchEndReason] == [
        "nexus_depleted",
        "forfeit",
    ]


def test_there_is_no_winner_field() -> None:
    """O vencedor é o outro jogador; gravá-lo seria uma segunda fonte."""
    assert [field.name for field in fields(MatchOutcome)] == [
        "defeated_user_id",
        "reason",
    ]
