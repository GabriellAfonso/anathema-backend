"""A desistência da §10: a qualquer momento, na vez do jogador ou não.

Fluxo de Partida, corrigido em 2026-09-11. Desistir não é ação da Fase de Ação:
não pede prioridade nem fase, e vale inclusive no mulligan e com o combate
aberto. O oponente vence na hora, e nada além do resultado e da fase muda.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import MatchIsOverError, PassAction, forfeit, submit_action
from apps.game.match import (
    Match,
    MatchEndReason,
    MatchOutcome,
    MatchPhase,
    NotAParticipantError,
)
from apps.game.tests.fake_combat_board import declare_combat, fake_combat_board
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase, fake_started_match
from apps.game.tests.match_snapshot import match_snapshot

OUTSIDER = 404


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


def without_outcome(match: Match) -> object:
    """O documento inteiro menos o par que a desistência escreve."""
    document = dict(match_snapshot(match))
    document.pop("outcome")
    document.pop("phase")

    return document


def test_the_player_with_priority_can_forfeit() -> None:
    match = fake_match_in_action_phase()
    holder = match.priority_user_id
    assert holder is not None

    forfeit(match, holder)

    assert match.outcome == MatchOutcome(
        defeated_user_id=holder, reason=MatchEndReason.FORFEIT
    )
    assert match.phase is MatchPhase.FINISHED


def test_the_player_without_priority_can_forfeit_too() -> None:
    """ "Na vez dele ou não."""
    match = fake_match_in_action_phase()
    assert match.priority_user_id is not None
    waiting = match.opponent_of(match.priority_user_id).user_id

    forfeit(match, waiting)

    assert match.outcome is not None
    assert match.outcome.defeated_user_id == waiting


def test_a_player_can_forfeit_during_the_mulligan() -> None:
    match = fake_started_match()
    one = match.players[0].user_id

    forfeit(match, one)

    assert match.outcome is not None
    assert match.outcome.defeated_user_id == one


def test_the_attacker_can_forfeit_inside_the_defense_window(
    catalog: CardCatalog,
) -> None:
    """A vez é do defensor, e o atacante desiste assim mesmo."""
    match = fake_combat_board(catalog=catalog)
    declare_combat(match, 0)
    attacker = match.players[0].user_id

    forfeit(match, attacker)

    assert match.phase is MatchPhase.FINISHED
    assert match.combat is not None


def test_forfeiting_changes_nothing_but_the_outcome_and_the_phase() -> None:
    """Mão, banco, Nexus, mulligan pendente -- tudo congelado onde estava."""
    match = fake_match_in_action_phase()
    before = without_outcome(match)

    forfeit(match, match.players[1].user_id)

    assert without_outcome(match) == before


def test_no_action_is_accepted_after_a_forfeit(catalog: CardCatalog) -> None:
    match = fake_match_in_action_phase()
    holder = match.priority_user_id
    assert holder is not None
    forfeit(match, match.opponent_of(holder).user_id)

    with pytest.raises(MatchIsOverError):
        submit_action(
            match,
            PassAction(actor_user_id=holder),
            catalog=catalog,
            randomness=ScriptedRandomSource(),
        )


def test_forfeiting_a_finished_match_is_refused() -> None:
    """O resultado já apurado não muda: o segundo a desistir não perde de novo."""
    match = fake_match_in_action_phase()
    one, two = (player.user_id for player in match.players)
    forfeit(match, one)
    before = match_snapshot(match)

    with pytest.raises(MatchIsOverError) as refusal:
        forfeit(match, two)

    assert "forfeit" in str(refusal.value)
    assert match_snapshot(match) == before


def test_an_outsider_cannot_forfeit() -> None:
    match = fake_match_in_action_phase()
    before = match_snapshot(match)

    with pytest.raises(NotAParticipantError) as refusal:
        forfeit(match, OUTSIDER)

    assert refusal.value.user_id == OUTSIDER
    assert match_snapshot(match) == before
