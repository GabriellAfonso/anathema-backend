"""A forma da ação e as três guardas comuns da §5.

O teste central deste arquivo é
`test_the_common_guards_are_checked_in_order`: é ele que pega a inversão entre
prioridade e fase, que muda qual recusa o cliente recebe e que nenhum teste de
guarda isolada percebe.

Os testes de atomicidade comparam a partida inteira por `match_snapshot`, e não
uma lista de campos escolhida a dedo -- os dois contadores da partida são
exatamente os que uma lista escrita à mão esqueceria.
"""

from dataclasses import FrozenInstanceError

import pytest

from apps.game.engine import (
    ActionKind,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    PlayUnitAction,
)
from apps.game.engine.player_action import ensure_action_allowed
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchPhase,
    NotAParticipantError,
)
from apps.game.tests.fake_match_state import (
    OUTSIDER,
    PLAYER_ONE,
    PLAYER_TWO,
    fake_new_match,
)
from apps.game.tests.match_snapshot import match_snapshot

SOME_CARD = CardInstanceId(3)


def match_in_action_phase(priority_user_id: int = PLAYER_ONE) -> Match:
    """Partida parada na Fase de Ação, com a prioridade onde o teste pedir."""
    match = fake_new_match()

    match.token_holder_user_id = PLAYER_ONE
    match.priority_user_id = priority_user_id
    match.phase = MatchPhase.ACTION

    return match


# --- A forma da ação ---------------------------------------------------------


def test_each_action_declares_its_own_kind() -> None:
    assert PlayUnitAction.action_kind is ActionKind.PLAY_UNIT
    assert PassAction.action_kind is ActionKind.PASS


def test_both_actions_of_this_feature_belong_to_the_action_phase() -> None:
    assert PlayUnitAction.allowed_phases == frozenset({MatchPhase.ACTION})
    assert PassAction.allowed_phases == frozenset({MatchPhase.ACTION})


def test_an_action_carries_its_author() -> None:
    assert PassAction(actor_user_id=PLAYER_ONE).actor_user_id == PLAYER_ONE
    assert (
        PlayUnitAction(
            actor_user_id=PLAYER_TWO, card_instance_id=SOME_CARD
        ).actor_user_id
        == PLAYER_TWO
    )


def test_a_pass_has_nowhere_to_put_a_card() -> None:
    """A união é o que impede `PassAction(card_instance_id=...)` de existir."""
    assert not hasattr(PassAction(actor_user_id=PLAYER_ONE), "card_instance_id")


def test_an_action_cannot_be_altered_after_it_is_built() -> None:
    action = PlayUnitAction(actor_user_id=PLAYER_ONE, card_instance_id=SOME_CARD)

    with pytest.raises(FrozenInstanceError):
        action.actor_user_id = PLAYER_TWO  # type: ignore[misc]


def test_the_kind_belongs_to_the_mechanic_and_not_to_the_instance() -> None:
    """`ClassVar`, não campo: não existe um passe que se diga `play_unit`."""
    with pytest.raises(TypeError):
        PassAction(actor_user_id=PLAYER_ONE, action_kind=ActionKind.PLAY_UNIT)  # type: ignore[call-arg]


# --- As três guardas ---------------------------------------------------------


def test_the_guards_return_the_state_of_the_author() -> None:
    match = match_in_action_phase()

    actor = ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_ONE))

    assert actor.user_id == PLAYER_ONE
    assert actor is match.player(PLAYER_ONE)


def test_an_outsider_is_refused_naming_the_user_id() -> None:
    match = match_in_action_phase()

    with pytest.raises(NotAParticipantError, match=str(OUTSIDER)) as refused:
        ensure_action_allowed(match, PassAction(actor_user_id=OUTSIDER))

    assert refused.value.user_id == OUTSIDER


def test_acting_without_priority_is_refused_naming_who_has_it() -> None:
    match = match_in_action_phase(priority_user_id=PLAYER_ONE)

    with pytest.raises(NotYourPriorityError, match=str(PLAYER_ONE)) as refused:
        ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_TWO))

    assert refused.value.priority_user_id == PLAYER_ONE
    assert refused.value.actor_user_id == PLAYER_TWO


@pytest.mark.parametrize(
    "phase",
    [
        MatchPhase.MULLIGAN,
        MatchPhase.UPKEEP,
        MatchPhase.DECLARATION,
        MatchPhase.COMBAT,
        MatchPhase.ROUND_END,
    ],
)
def test_acting_outside_the_action_phase_is_refused_naming_the_phase(
    phase: MatchPhase,
) -> None:
    match = match_in_action_phase()
    match.phase = phase

    with pytest.raises(PhaseForbidsActionError, match=str(phase)) as refused:
        ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_ONE))

    assert refused.value.phase is phase


def test_the_refusal_names_the_phases_the_action_would_accept() -> None:
    match = match_in_action_phase()
    match.phase = MatchPhase.UPKEEP

    with pytest.raises(PhaseForbidsActionError, match="action") as refused:
        ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_ONE))

    assert refused.value.allowed_phases == PassAction.allowed_phases


# --- A ordem entre as guardas ------------------------------------------------


def test_the_common_guards_are_checked_in_order() -> None:
    """Participante, prioridade, fase. Quem falha em duas recebe a primeira.

    É o teste que pega a inversão: com as guardas trocadas, um jogador sem
    prioridade numa fase errada receberia a recusa de fase, e o cliente
    mostraria a mensagem errada.
    """
    match = match_in_action_phase(priority_user_id=PLAYER_ONE)
    match.phase = MatchPhase.UPKEEP

    with pytest.raises(NotYourPriorityError):
        ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_TWO))


def test_an_outsider_is_refused_before_the_priority_is_looked_at() -> None:
    match = match_in_action_phase(priority_user_id=PLAYER_ONE)
    match.phase = MatchPhase.UPKEEP

    with pytest.raises(NotAParticipantError):
        ensure_action_allowed(match, PassAction(actor_user_id=OUTSIDER))


# --- A atomicidade da recusa -------------------------------------------------


@pytest.mark.parametrize(
    "actor_user_id, phase",
    [
        (OUTSIDER, MatchPhase.ACTION),
        (PLAYER_TWO, MatchPhase.ACTION),
        (PLAYER_ONE, MatchPhase.UPKEEP),
    ],
    ids=["outsider", "no-priority", "wrong-phase"],
)
def test_a_refused_action_leaves_the_match_untouched(
    actor_user_id: int, phase: MatchPhase
) -> None:
    match = match_in_action_phase(priority_user_id=PLAYER_ONE)
    match.phase = phase
    before = match_snapshot(match)

    with pytest.raises(Exception):
        ensure_action_allowed(match, PassAction(actor_user_id=actor_user_id))

    assert match_snapshot(match) == before


def test_a_refusal_does_not_advance_the_match_counters() -> None:
    match = match_in_action_phase(priority_user_id=PLAYER_ONE)
    cards_before = match.next_card_instance_id
    rolls_before = match.next_roll_ordinal

    with pytest.raises(NotYourPriorityError):
        ensure_action_allowed(match, PassAction(actor_user_id=PLAYER_TWO))

    assert match.next_card_instance_id == cards_before
    assert match.next_roll_ordinal == rolls_before
