"""O relógio da vez acontecendo: aviso aos 30s, ação automática aos 45s (§15).

Cada cenário roda `ticker.tick(now)` com o relógio falso, e olha o que chegou
nos sockets dos dois jogadores. Nenhum teste espera tempo real.

O arranjo é o da partida de verdade: o mesmo `FakeMatchStore` que os testes de
consumer usam, o índice de despertar sobre ele, e o channel layer em memória do
`conftest.py` -- o mesmo por onde o consumer entrega.

O que o relógio **aguenta** -- desconexão, workers, corridas, abandono -- está em
`test_match_clock_resilience.py`.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.match import MatchEndReason, MatchPhase
from apps.game.match_timers import MatchClockTicker
from apps.game.protocol import advance_match_clock
from apps.game.tests.clock_boards import (
    EXPIRY_SECONDS,
    WARNING_SECONDS,
    both_sockets,
    close,
    stored,
    ticker_over,
    with_a_turn,
)
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    bank_card,
    declare_combat,
    fake_combat_board,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_spell_board import open_declaration
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.match_sockets import (
    event_kinds,
    next_turn_warning,
    next_update,
    saved,
    view_of,
)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def clock() -> FakeWallClock:
    return FakeWallClock()


@pytest.fixture
def matches(clock: FakeWallClock) -> FakeMatchStore:
    return FakeMatchStore(clock)


@pytest.fixture
def ticker(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> MatchClockTicker:
    return ticker_over(matches, clock, catalog)


# --- O aviso dos 30s ---------------------------------------------------------


async def test_the_warning_reaches_only_the_player_who_owes_the_play(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(WARNING_SECONDS))

    warning = await next_turn_warning(one)
    assert warning == {
        "turn_number": 1,
        "holder_user_id": PLAYER_ONE,
        "remaining_ms": 15_000,
    }
    assert await two.nothing_received()
    await close(one, two)


async def test_nothing_happens_before_the_warning(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(WARNING_SECONDS - 1))

    assert await one.nothing_received()
    assert await two.nothing_received()
    await close(one, two)


async def test_the_warning_goes_out_once(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """A marca é gravada, então a volta seguinte não avisa de novo."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await ticker.tick(clock.advance(WARNING_SECONDS))
    await next_turn_warning(one)

    await ticker.tick(clock.advance(5))

    assert await one.nothing_received()
    await close(one, two)


async def test_the_warning_follows_the_turn_to_its_new_holder(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """A vez do primeiro terminou aos 0s, e quem tem prazo agora é o segundo."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await one.send_json_to({"type": "pass"})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(WARNING_SECONDS))

    assert await next_turn_warning(two) == {
        "turn_number": 2,
        "holder_user_id": PLAYER_TWO,
        "remaining_ms": 15_000,
    }
    assert await one.nothing_received()
    await close(one, two)


# --- O estouro aos 45s -------------------------------------------------------


async def test_the_action_phase_passes_and_both_players_see_it(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    for payload in (await next_update(one), await next_update(two)):
        assert event_kinds(payload)[:2] == ["turn_timed_out", "passed"]
        assert view_of(payload)["priority_user_id"] == PLAYER_TWO
    await close(one, two)


async def test_the_expiry_opens_a_fresh_turn_for_the_other_player(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    payload = await next_update(two)
    assert payload["clock"] == {
        "turn": {
            "turn_number": 2,
            "holder_user_id": PLAYER_TWO,
            "remaining_ms": 45_000,
            "warning": False,
        },
        "mulligan_remaining_ms": None,
    }
    await next_update(one)
    await close(one, two)


async def test_the_declaration_attacks_with_everything_in_the_zone(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = fake_combat_board(
        catalog=catalog, bank_one=(DARK_AGE, MORTEM), bank_two=(SKILLET,)
    )
    attackers = open_declaration(match, 0, 1).attacker_card_instance_ids[:]
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    live = await stored(matches, match)
    assert live.phase is MatchPhase.COMBAT
    assert live.ongoing_combat().attacker_card_instance_ids == attackers
    assert live.priority_user_id == PLAYER_TWO
    assert event_kinds(await next_update(one))[:2] == [
        "turn_timed_out",
        "attack_confirmed",
    ]
    await next_update(two)
    await close(one, two)


async def test_the_defense_resolves_with_nothing_blocking(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = fake_combat_board(
        catalog=catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,)
    )
    declare_combat(match, 0)
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)
    one, two = await both_sockets(matches, clock, match)
    nexus_before = match.player(PLAYER_TWO).nexus

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    live = await stored(matches, match)
    assert live.phase is MatchPhase.ACTION
    assert live.player(PLAYER_TWO).nexus < nexus_before
    assert event_kinds(await next_update(two))[:2] == [
        "turn_timed_out",
        "defense_ended",
    ]
    await next_update(one)
    await close(one, two)


async def test_the_defense_resolves_with_the_blocker_already_assigned(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = fake_combat_board(
        catalog=catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,)
    )
    declare_combat(match, 0)
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)
    one, two = await both_sockets(matches, clock, match)
    blocker = bank_card(match.player(PLAYER_TWO))
    await two.send_json_to(
        {
            "type": "assign_blocker",
            "payload": {
                "blocker_card_instance_id": blocker,
                "attacker_card_instance_id": bank_card(match.player(PLAYER_ONE)),
            },
        }
    )
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    live = await stored(matches, match)
    assert live.player(PLAYER_TWO).nexus == match.player(PLAYER_TWO).nexus
    assert live.player(PLAYER_TWO).bank[0].damage_taken > 0
    await next_update(one), await next_update(two)
    await close(one, two)


async def test_a_timed_out_pass_can_close_the_round(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """A cascata chega como uma atualização só, já na rodada seguinte."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await one.send_json_to({"type": "pass"})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    payload = await next_update(two)
    assert view_of(payload)["round_number"] == 2
    assert "round_started" in event_kinds(payload)
    await next_update(one)
    await close(one, two)


async def test_a_timed_out_resolve_can_end_the_match(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = fake_combat_board(catalog=catalog, bank_one=(MORTEM,), bank_two=(SKILLET,))
    declare_combat(match, 0)
    match.player(PLAYER_TWO).nexus = 5
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    live = await stored(matches, match)
    assert live.phase is MatchPhase.FINISHED
    assert live.outcome is not None
    assert live.outcome.reason is MatchEndReason.NEXUS_DEPLETED
    for payload in (await next_update(one), await next_update(two)):
        assert "match_finished" in event_kinds(payload)
        assert payload["clock"] == {"turn": None, "mulligan_remaining_ms": None}
    await close(one, two)


async def test_a_finished_match_leaves_the_wake_up_index(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = fake_combat_board(catalog=catalog, bank_one=(MORTEM,), bank_two=(SKILLET,))
    declare_combat(match, 0)
    match.player(PLAYER_TWO).nexus = 5
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    assert matches.wake_at == {}


async def test_a_tick_with_nothing_due_sends_no_frame(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(1))

    assert await one.nothing_received()
    assert await two.nothing_received()
    await close(one, two)


async def test_the_clock_write_does_not_renew_the_expiry(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """§15: estouro grava sem adiar a expiração da partida."""
    await with_a_turn(matches, clock, catalog)

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    assert matches.expiry_renewals == [False]
