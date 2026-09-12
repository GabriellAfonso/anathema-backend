"""O que venceu no relógio, e a ação que o estouro manda ao motor (§15).

A guarda é a peça que resolve as duas corridas da spec -- a jogada real no mesmo
instante e o estouro atrasado --, e por isso ela é testada com a vez certa, com
a vez trocada, com o prazo não vencido e com o aviso já mandado.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import (
    ConfirmAttackAction,
    EndDefenseWindowAction,
    PassAction,
    record_mulligan,
)
from apps.game.match import Match, MatchClock, TurnDeadline
from apps.game.protocol import MulliganCommand
from apps.game.protocol.clock_events import (
    ClockEventNotDueError,
    MulliganExpiry,
    TurnExpiry,
    TurnWarning,
    automatic_command,
    due_clock_event,
    ensure_clock_event_due,
)
from apps.game.protocol.turn_clock import opening_match_clock
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    PLAYER_ONE,
    PLAYER_TWO,
    bank_card,
    declare_combat,
    fake_combat_board,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_spell_board import open_declaration
from apps.game.wall_clock import EpochMillis

START_MS = EpochMillis(1_000_000)
WARNS_AT = EpochMillis(START_MS + 30_000)
EXPIRES_AT = EpochMillis(START_MS + 45_000)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def a_turn(
    *, turn_number: int = 1, warning_sent: bool = False, holder: int = PLAYER_ONE
) -> TurnDeadline:
    return TurnDeadline(
        turn_number=turn_number,
        holder_user_id=holder,
        round_number=1,
        warns_at_ms=WARNS_AT,
        expires_at_ms=EXPIRES_AT,
        warning_sent=warning_sent,
    )


def waiting_board(catalog: CardCatalog, turn: TurnDeadline) -> Match:
    """Fase de Ação com aquela vez gravada."""
    match = fake_combat_board(catalog=catalog, bank_one=(DARK_AGE,))
    match.clock = MatchClock(turn=turn)

    return match


def awaiting_mulligan() -> Match:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(EpochMillis(START_MS - 30_000))

    return match


# --- O que venceu ------------------------------------------------------------


def test_nothing_is_due_before_the_warning(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    assert due_clock_event(match, EpochMillis(WARNS_AT - 1)) is None


def test_the_warning_is_due_at_thirty_seconds(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    assert due_clock_event(match, WARNS_AT) == TurnWarning(1, PLAYER_ONE)


def test_a_sent_warning_is_not_due_again(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn(warning_sent=True))

    assert due_clock_event(match, EpochMillis(EXPIRES_AT - 1)) is None


def test_the_expiry_is_due_at_forty_five_seconds(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    assert due_clock_event(match, EXPIRES_AT) == TurnExpiry(1, PLAYER_ONE)


def test_the_expiry_wins_over_a_warning_that_never_went_out(
    catalog: CardCatalog,
) -> None:
    """Worker fora do ar durante a vez inteira: avisar não tem mais função."""
    match = waiting_board(catalog, a_turn())

    assert due_clock_event(match, EpochMillis(EXPIRES_AT + 60_000)) == TurnExpiry(
        1, PLAYER_ONE
    )


def test_the_mulligan_expiry_names_the_player_who_has_not_answered(
    source: RandomSource,
) -> None:
    match = awaiting_mulligan()
    record_mulligan(match, PLAYER_ONE, (), randomness=source)

    assert due_clock_event(match, START_MS) == MulliganExpiry(PLAYER_TWO)


def test_nothing_is_due_while_the_mulligan_deadline_has_not_passed() -> None:
    match = awaiting_mulligan()

    assert due_clock_event(match, EpochMillis(START_MS - 1)) is None


# --- A guarda da tentativa ---------------------------------------------------


def test_the_guard_accepts_the_event_that_is_due(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    ensure_clock_event_due(match, TurnExpiry(1, PLAYER_ONE), EXPIRES_AT)


def test_the_guard_refuses_an_expiry_armed_for_another_turn(
    catalog: CardCatalog,
) -> None:
    """O estouro atrasado que chega depois de a vez voltar ao mesmo jogador."""
    match = waiting_board(catalog, a_turn(turn_number=7))

    with pytest.raises(ClockEventNotDueError) as refusal:
        ensure_clock_event_due(match, TurnExpiry(6, PLAYER_ONE), EXPIRES_AT)

    assert refusal.value.event == TurnExpiry(6, PLAYER_ONE)


def test_the_guard_refuses_before_the_deadline(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    with pytest.raises(ClockEventNotDueError):
        ensure_clock_event_due(
            match, TurnExpiry(1, PLAYER_ONE), EpochMillis(EXPIRES_AT - 1)
        )


def test_the_guard_refuses_a_warning_already_sent(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn(warning_sent=True))

    with pytest.raises(ClockEventNotDueError):
        ensure_clock_event_due(match, TurnWarning(1, PLAYER_ONE), WARNS_AT)


def test_the_guard_refuses_a_mulligan_already_answered(
    source: RandomSource,
) -> None:
    match = awaiting_mulligan()
    record_mulligan(match, PLAYER_ONE, (), randomness=source)

    with pytest.raises(ClockEventNotDueError):
        ensure_clock_event_due(match, MulliganExpiry(PLAYER_ONE), START_MS)


# --- A ação automática -------------------------------------------------------


def test_the_action_phase_passes(catalog: CardCatalog) -> None:
    match = waiting_board(catalog, a_turn())

    assert automatic_command(match, TurnExpiry(1, PLAYER_ONE)) == PassAction(PLAYER_ONE)


def test_the_declaration_attacks_with_what_is_in_the_zone(
    catalog: CardCatalog,
) -> None:
    match = waiting_board(catalog, a_turn())
    open_declaration(match, 0)

    assert automatic_command(match, TurnExpiry(1, PLAYER_ONE)) == ConfirmAttackAction(
        PLAYER_ONE
    )


def test_the_defense_resolves_with_the_blockers_already_assigned(
    catalog: CardCatalog,
) -> None:
    match = waiting_board(catalog, a_turn(holder=PLAYER_TWO))
    declare_combat(match, 0)

    assert automatic_command(
        match, TurnExpiry(1, PLAYER_TWO)
    ) == EndDefenseWindowAction(PLAYER_TWO)


def test_the_mulligan_confirms_without_swapping_a_single_card() -> None:
    match = awaiting_mulligan()

    assert automatic_command(match, MulliganExpiry(PLAYER_TWO)) == MulliganCommand(
        user_id=PLAYER_TWO, card_instance_ids=()
    )


def test_the_command_follows_the_phase_of_now_not_of_the_arming(
    catalog: CardCatalog,
) -> None:
    """O atacante que puxa a última unidade no instante do estouro é passado, e
    não atacado."""
    match = waiting_board(catalog, a_turn())
    open_declaration(match, 0)
    match.combat = None
    match.phase = fake_combat_board(catalog=catalog).phase

    assert automatic_command(match, TurnExpiry(1, PLAYER_ONE)) == PassAction(PLAYER_ONE)


def test_the_attack_zone_is_read_by_the_engine_not_by_the_command(
    catalog: CardCatalog,
) -> None:
    """`ConfirmAttackAction` não cita atacante: a zona já está no estado."""
    match = waiting_board(catalog, a_turn())
    combat = open_declaration(match, 0)

    command = automatic_command(match, TurnExpiry(1, PLAYER_ONE))

    assert combat.attacker_card_instance_ids == [bank_card(match.player(PLAYER_ONE))]
    assert command == ConfirmAttackAction(PLAYER_ONE)
