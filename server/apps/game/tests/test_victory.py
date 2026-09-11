"""A §10: um Nexus em zero encerra a partida, e nada é aceito depois.

Esta é a primeira feature em que uma partida pode acabar. O que se testa aqui é
a regra sozinha -- `change_nexus` e `check_victory` sobre um estado montado à
mão --, sem feitiço nenhum: quem chama é a feature de efeitos, e ela é testada
em `test_spell_effect.py`.
"""

import pytest

from apps.game.cards import mvp_catalog
from apps.game.engine import (
    MatchIsOverError,
    SimultaneousDefeatError,
    PassAction,
    change_nexus,
    check_victory,
    submit_action,
)
from apps.game.match import Match, MatchEndReason, MatchOutcome, MatchPhase
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase
from apps.game.tests.match_snapshot import match_snapshot


@pytest.fixture
def match() -> Match:
    return fake_match_in_action_phase()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def test_a_running_match_has_no_outcome(match: Match) -> None:
    assert match.outcome is None
    assert match.is_over is False


def test_nexus_at_exactly_zero_defeats_the_player(match: Match) -> None:
    """A §10 escreve `Nexus <= 0`: o zero derrota, não só o negativo."""
    one, _ = match.players
    change_nexus(match, one, -one.nexus)

    assert match.outcome == MatchOutcome(
        defeated_user_id=one.user_id, reason=MatchEndReason.NEXUS_DEPLETED
    )


def test_a_defeated_match_reaches_the_terminal_phase(match: Match) -> None:
    one, _ = match.players
    change_nexus(match, one, -one.nexus)

    assert match.phase is MatchPhase.FINISHED
    assert match.is_over is True


def test_a_negative_nexus_is_preserved_as_it_landed(match: Match) -> None:
    """Sem piso: fixar em 0 apagaria por quanto o jogador passou do ponto."""
    one, _ = match.players
    change_nexus(match, one, -(one.nexus + 3))

    assert one.nexus == -3


def test_nexus_above_zero_does_not_end_the_match(match: Match) -> None:
    one, _ = match.players
    change_nexus(match, one, -(one.nexus - 1))

    assert one.nexus == 1
    assert match.is_over is False


def test_the_nexus_has_no_upper_bound(match: Match) -> None:
    """O 20 da §12 é o valor inicial, não um teto (esclarecimento de 006)."""
    one, _ = match.players
    change_nexus(match, one, 5)

    assert one.nexus == 25


def test_both_players_at_zero_is_refused_as_corrupted_state(match: Match) -> None:
    """Não existe empate (§10, corrigida em 2026-09-11), e nenhuma regra leva os
    dois a zero: o estado é recusado, e nenhum derrotado é escolhido."""
    one, two = match.players
    one.nexus = 0
    two.nexus = -2

    with pytest.raises(SimultaneousDefeatError) as refusal:
        check_victory(match)

    assert set(refusal.value.user_ids) == {one.user_id, two.user_id}
    assert match.outcome is None


def test_check_victory_is_idempotent(match: Match) -> None:
    """Chamar de novo não troca o resultado -- nem com o outro Nexus zerado
    depois, que sem a idempotência seria o estado recusado acima."""
    one, two = match.players
    one.nexus = 0
    check_victory(match)

    two.nexus = 0
    check_victory(match)

    assert match.outcome == MatchOutcome(
        defeated_user_id=one.user_id, reason=MatchEndReason.NEXUS_DEPLETED
    )


def test_a_later_heal_does_not_revive_a_finished_match(match: Match) -> None:
    """A partida terminada não volta atrás: `change_nexus` ainda escreve o
    Nexus, mas o desfecho já apurado permanece."""
    one, _ = match.players
    change_nexus(match, one, -one.nexus)

    change_nexus(match, one, 5)

    assert one.nexus == 5
    assert match.is_over is True


def test_a_running_match_never_carries_an_outcome(match: Match) -> None:
    """A invariante, no sentido de ida: sem desfecho, sem fase terminal."""
    check_victory(match)

    assert match.outcome is None
    assert match.phase is not MatchPhase.FINISHED


def test_a_finished_match_always_carries_an_outcome(match: Match) -> None:
    """A invariante, no sentido de volta: um ponto só escreve o par."""
    one, _ = match.players
    change_nexus(match, one, -one.nexus)

    assert (match.phase is MatchPhase.FINISHED) is (match.outcome is not None)


def test_the_defeated_player_cannot_act(match: Match, source: RandomSource) -> None:
    holder = match.priority_user_id
    assert holder is not None
    change_nexus(match, match.player(holder), -match.player(holder).nexus)

    with pytest.raises(MatchIsOverError) as refusal:
        submit_action(
            match,
            PassAction(actor_user_id=holder),
            catalog=mvp_catalog(),
            randomness=source,
        )

    assert "the match is over" in str(refusal.value)


def test_the_surviving_player_cannot_act_either(
    match: Match, source: RandomSource
) -> None:
    """ "Nenhuma ação é aceita depois disso" vale para os dois lados."""
    holder = match.priority_user_id
    assert holder is not None
    change_nexus(match, match.player(holder), -match.player(holder).nexus)
    match.priority_user_id = match.opponent_of(holder).user_id

    with pytest.raises(MatchIsOverError):
        submit_action(
            match,
            PassAction(actor_user_id=match.opponent_of(holder).user_id),
            catalog=mvp_catalog(),
            randomness=source,
        )


def test_the_refusal_names_the_defeated(match: Match, source: RandomSource) -> None:
    holder = match.priority_user_id
    assert holder is not None
    change_nexus(match, match.player(holder), -match.player(holder).nexus)

    with pytest.raises(MatchIsOverError) as refusal:
        submit_action(
            match,
            PassAction(actor_user_id=holder),
            catalog=mvp_catalog(),
            randomness=source,
        )

    assert refusal.value.outcome == MatchOutcome(
        defeated_user_id=holder, reason=MatchEndReason.NEXUS_DEPLETED
    )


def test_an_action_on_a_finished_match_changes_nothing(
    match: Match, source: RandomSource
) -> None:
    holder = match.priority_user_id
    assert holder is not None
    change_nexus(match, match.player(holder), -match.player(holder).nexus)
    before = match_snapshot(match)

    with pytest.raises(MatchIsOverError):
        submit_action(
            match,
            PassAction(actor_user_id=holder),
            catalog=mvp_catalog(),
            randomness=source,
        )

    assert match_snapshot(match) == before
