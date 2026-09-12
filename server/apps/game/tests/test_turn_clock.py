"""Quando começa vez nova, transição a transição do motor de verdade (§15).

A regra da spec: a vez muda quando muda o **dono** ou a **rodada**, e nada mais.
Cada teste aqui faz uma jogada pela porta do motor e pergunta o que o relógio
fez -- é a diferença entre "feitiço não reinicia" escrito num comentário e
verificado.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, mvp_catalog
from apps.game.engine import (
    AssignBlockerAction,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    PassAction,
    PlayerAction,
    PlayUnitAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
    forfeit,
    submit_action,
)
from apps.game.match import IDLE_MATCH_CLOCK, Match, MatchPhase, TurnDeadline
from apps.game.protocol.turn_clock import (
    MULLIGAN_EXPIRY_MS,
    TURN_EXPIRY_MS,
    TURN_WARNING_MS,
    advance_match_clock,
    opening_match_clock,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    SOMEONES_SHIELD,
    bank_card,
    fake_combat_board,
    hand_card,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.wall_clock import EpochMillis

START_MS = EpochMillis(1_000_000)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def clock() -> FakeWallClock:
    return FakeWallClock(START_MS)


def board_with_a_turn(
    clock: FakeWallClock,
    *,
    catalog: CardCatalog,
    hand_one: tuple[CardId, ...] = (),
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (KHRAS,),
) -> Match:
    """Fase de Ação com a vez 1 já aberta, como o fim do mulligan a deixaria."""
    match = fake_combat_board(
        catalog=catalog,
        hand_one=hand_one,
        bank_one=bank_one,
        bank_two=bank_two,
    )
    advance_match_clock(match, clock.now_ms())

    return match


def play(
    match: Match,
    action: PlayerAction,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    clock: FakeWallClock,
) -> None:
    """Uma jogada pelo motor, e o relógio adiantado como a mutação faria."""
    submit_action(match, action, catalog=catalog, randomness=source)
    advance_match_clock(match, clock.now_ms())


def the_turn(match: Match) -> TurnDeadline:
    turn = match.clock.turn
    assert turn is not None, match.clock

    return turn


# --- A primeira vez ----------------------------------------------------------


def test_the_first_turn_opens_with_the_deadlines_of_section_twelve(
    catalog: CardCatalog, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog)

    assert the_turn(match) == TurnDeadline(
        turn_number=1,
        holder_user_id=PLAYER_ONE,
        round_number=1,
        warns_at_ms=EpochMillis(START_MS + TURN_WARNING_MS),
        expires_at_ms=EpochMillis(START_MS + TURN_EXPIRY_MS),
    )


def test_the_mulligan_deadline_counts_from_the_creation(
    clock: FakeWallClock,
) -> None:
    assert opening_match_clock(clock.now_ms()).mulligan_expires_at_ms == (
        START_MS + MULLIGAN_EXPIRY_MS
    )


def test_the_mulligan_phase_keeps_its_own_deadline(clock: FakeWallClock) -> None:
    """Mulligan tem prazo por jogador, e não vez: nada a abrir aqui."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(clock.now_ms())

    advance_match_clock(match, clock.advance(10))

    assert match.clock == opening_match_clock(START_MS)


# --- Trocou de mão: vez nova -------------------------------------------------


def test_playing_a_unit_opens_the_opponents_turn(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog, hand_one=(DARK_AGE,))
    one = match.player(PLAYER_ONE)

    play(
        match,
        PlayUnitAction(PLAYER_ONE, hand_card(one, DARK_AGE)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert (the_turn(match).turn_number, the_turn(match).holder_user_id) == (
        2,
        PLAYER_TWO,
    )


def test_passing_opens_the_opponents_turn_with_a_fresh_deadline(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog)
    clock.advance(20)

    play(match, PassAction(PLAYER_ONE), catalog=catalog, source=source, clock=clock)

    assert the_turn(match).expires_at_ms == START_MS + 20_000 + TURN_EXPIRY_MS


def test_confirming_the_attack_opens_the_defenders_turn(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog)
    one = match.player(PLAYER_ONE)
    play(
        match,
        DeclareAttackAction(PLAYER_ONE, (bank_card(one),)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    play(
        match,
        ConfirmAttackAction(PLAYER_ONE),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert (match.phase, the_turn(match).holder_user_id) == (
        MatchPhase.COMBAT,
        PLAYER_TWO,
    )
    assert the_turn(match).turn_number == 2


def test_resolving_the_combat_opens_the_token_holders_turn(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog, bank_two=(SKILLET,))
    one = match.player(PLAYER_ONE)
    for action in (
        DeclareAttackAction(PLAYER_ONE, (bank_card(one),)),
        ConfirmAttackAction(PLAYER_ONE),
    ):
        play(match, action, catalog=catalog, source=source, clock=clock)

    play(
        match,
        EndDefenseWindowAction(PLAYER_TWO),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert (match.phase, the_turn(match).holder_user_id) == (
        MatchPhase.ACTION,
        PLAYER_ONE,
    )
    assert the_turn(match).turn_number == 3


def test_the_round_turning_opens_a_new_turn_for_the_same_player(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    """A cascata dos dois passes devolve a vez a quem passou por último.

    Sem a rodada na identidade da vez, o passe por estouro abriria a rodada
    seguinte já vencida, e o mesmo jogador estouraria de novo na hora.
    """
    match = board_with_a_turn(clock, catalog=catalog)
    play(match, PassAction(PLAYER_ONE), catalog=catalog, source=source, clock=clock)
    second_turn = the_turn(match)
    clock.advance(40)

    play(match, PassAction(PLAYER_TWO), catalog=catalog, source=source, clock=clock)

    assert match.round_number == 2
    assert the_turn(match).holder_user_id == second_turn.holder_user_id
    assert the_turn(match).turn_number == second_turn.turn_number + 1
    assert the_turn(match).expires_at_ms == START_MS + 40_000 + TURN_EXPIRY_MS


# --- Mesma mão: o relógio não reinicia ---------------------------------------


def test_casting_a_spell_does_not_restart_the_clock(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog, hand_one=(SOMEONES_SHIELD,))
    one = match.player(PLAYER_ONE)
    before = the_turn(match)
    clock.advance(40)

    play(
        match,
        CastSpellAction(PLAYER_ONE, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert the_turn(match) == before


def test_declaring_and_sending_more_attackers_does_not_restart_the_clock(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog, bank_one=(DARK_AGE, MORTEM))
    one = match.player(PLAYER_ONE)
    before = the_turn(match)

    clock.advance(10)
    play(
        match,
        DeclareAttackAction(PLAYER_ONE, (bank_card(one),)),
        catalog=catalog,
        source=source,
        clock=clock,
    )
    clock.advance(10)
    play(
        match,
        DeclareAttackAction(PLAYER_ONE, (bank_card(one, 1),)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert (match.phase, the_turn(match)) == (MatchPhase.DECLARATION, before)


def test_withdrawing_the_last_attacker_does_not_restart_the_clock(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    """Voltar à Fase de Ação sem consumir nada é a mesma vez."""
    match = board_with_a_turn(clock, catalog=catalog)
    one = match.player(PLAYER_ONE)
    before = the_turn(match)
    play(
        match,
        DeclareAttackAction(PLAYER_ONE, (bank_card(one),)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    clock.advance(30)
    play(
        match,
        WithdrawAttackerAction(PLAYER_ONE, bank_card(one)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert (match.phase, the_turn(match)) == (MatchPhase.ACTION, before)


def test_blocking_and_unblocking_does_not_restart_the_clock(
    catalog: CardCatalog, source: RandomSource, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog, bank_two=(SKILLET,))
    one, two = match.players
    for action in (
        DeclareAttackAction(PLAYER_ONE, (bank_card(one),)),
        ConfirmAttackAction(PLAYER_ONE),
    ):
        play(match, action, catalog=catalog, source=source, clock=clock)
    before = the_turn(match)

    clock.advance(25)
    play(
        match,
        AssignBlockerAction(PLAYER_TWO, bank_card(two), bank_card(one)),
        catalog=catalog,
        source=source,
        clock=clock,
    )
    clock.advance(10)
    play(
        match,
        RemoveBlockerAction(PLAYER_TWO, bank_card(two)),
        catalog=catalog,
        source=source,
        clock=clock,
    )

    assert the_turn(match) == before


# --- Fim da partida ----------------------------------------------------------


def test_a_forfeit_stops_every_deadline(
    catalog: CardCatalog, clock: FakeWallClock
) -> None:
    match = board_with_a_turn(clock, catalog=catalog)

    forfeit(match, PLAYER_TWO)
    advance_match_clock(match, clock.advance(5))

    assert match.clock == IDLE_MATCH_CLOCK
