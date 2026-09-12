"""O que o relógio da vez aguenta (§15).

O aviso e o estouro em si estão em `test_match_clock_ticker.py`. Aqui ficam os
casos que a spec chama de "o que o relógio precisa aguentar": o jogador que
fechou o jogo, o worker que morreu depois de reivindicar, a jogada real
chegando no mesmo instante, o mulligan sem resposta, e a partida que ninguém
joga mais.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import PassAction
from apps.game.match import MatchPhase
from apps.game.match.store import MATCH_TTL_SECONDS
from apps.game.match_timers import (
    WAKE_BATCH_SIZE,
    WAKE_LEASE_MS,
    MatchClockTicker,
)
from apps.game.protocol import (
    MulliganCommand,
    PlayerChange,
    advance_match_clock,
    opening_match_clock,
)
from apps.game.tests.clock_boards import (
    EXPIRY_SECONDS,
    MULLIGAN_SECONDS,
    awaiting_mulligan,
    both_sockets,
    close,
    stored,
    ticker_over,
    with_a_turn,
)
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    PLAYER_ONE,
    PLAYER_TWO,
    fake_combat_board,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_match_wake_queue import FakeMatchWakeQueue
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.interleaved_match_store import InterleavedMatchStore
from apps.game.tests.match_sockets import (
    event_kinds,
    next_refusal_code,
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


# --- Desconexão e workers ----------------------------------------------------


async def test_the_expiry_happens_with_the_holder_disconnected(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """É o caso que justifica o relógio: quem deve a jogada fechou o jogo."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await one.disconnect()

    await ticker.tick(clock.advance(EXPIRY_SECONDS))

    assert event_kinds(await next_update(two))[:2] == ["turn_timed_out", "passed"]
    assert (await stored(matches, match)).priority_user_id == PLAYER_TWO
    await close(two)


async def test_a_worker_that_dies_after_claiming_only_delays_the_expiry(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """O lease vence e o próximo worker pega o despertar."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    dead_worker = FakeMatchWakeQueue(matches)
    now = clock.advance(EXPIRY_SECONDS)
    await dead_worker.claim_due(now, lease_ms=WAKE_LEASE_MS, limit=WAKE_BATCH_SIZE)

    await ticker.tick(now)
    assert await one.nothing_received()

    await ticker.tick(clock.advance(WAKE_LEASE_MS / 1000))

    assert event_kinds(await next_update(one))[:2] == ["turn_timed_out", "passed"]
    await next_update(two)
    await close(one, two)


async def test_two_tickers_on_the_same_wake_up_write_once(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    other_worker = ticker_over(matches, clock, catalog)
    now = clock.advance(EXPIRY_SECONDS)

    await ticker.tick(now)
    await other_worker.tick(now)

    assert (await stored(matches, match)).consecutive_passes == 1
    await next_update(one), await next_update(two)
    assert await one.nothing_received()
    await close(one, two)


# --- A corrida com a jogada real ---------------------------------------------


async def test_a_real_pass_landing_in_the_middle_beats_the_expiry(
    clock: FakeWallClock, catalog: CardCatalog
) -> None:
    """A jogada do socket entra entre a leitura e a gravação do estouro.

    Exatamente um passe é gravado, e o estouro não age sobre a vez nova.
    """
    matches = InterleavedMatchStore(lambda: real_pass(), clock)
    match = fake_combat_board(catalog=catalog, bank_one=(DARK_AGE,))
    advance_match_clock(match, clock.now_ms())
    await saved(matches, match)

    async def real_pass() -> None:
        await matches.mutate(
            match.match_id,
            PlayerChange(
                PassAction(PLAYER_ONE),
                catalog=catalog,
                randomness=ScriptedRandomSource(),
                clock=clock,
            ),
        )

    await ticker_over(matches, clock, catalog).tick(clock.advance(EXPIRY_SECONDS))

    live = await stored(matches, match)
    turn = live.clock.turn
    assert live.consecutive_passes == 1
    assert turn is not None
    assert (turn.turn_number, turn.holder_user_id) == (2, PLAYER_TWO)


async def test_a_pass_after_the_expiry_is_refused_by_priority(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """Quando o estouro vence a corrida, a jogada é avaliada contra o que ele
    deixou -- e recebe a recusa de sempre."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await ticker.tick(clock.advance(EXPIRY_SECONDS))
    await next_update(one), await next_update(two)

    await one.send_json_to({"type": "pass"})

    assert await next_refusal_code(one) == "not_your_priority"
    assert await two.nothing_received()
    await close(one, two)


# --- O mulligan (US5) --------------------------------------------------------


async def test_the_mulligan_expiry_answers_for_who_is_missing(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    ticker: MatchClockTicker,
) -> None:
    match = await awaiting_mulligan(matches, clock)
    one, two = await both_sockets(matches, clock, match)
    await one.send_json_to({"type": "mulligan", "payload": {"card_instance_ids": []}})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(MULLIGAN_SECONDS))

    payload = await next_update(two)
    assert event_kinds(payload)[:2] == ["mulligan_timed_out", "mulligan_taken"]
    assert (view_of(payload)["phase"], view_of(payload)["round_number"]) == (
        "action",
        1,
    )
    await next_update(one)
    await close(one, two)


async def test_the_first_turn_opens_with_a_fresh_clock_after_a_timed_out_mulligan(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    ticker: MatchClockTicker,
) -> None:
    match = await awaiting_mulligan(matches, clock)
    one, two = await both_sockets(matches, clock, match)
    await one.send_json_to({"type": "mulligan", "payload": {"card_instance_ids": []}})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(MULLIGAN_SECONDS))

    payload = await next_update(one)
    assert payload["clock"] == {
        "turn": {
            "turn_number": 1,
            "holder_user_id": (await stored(matches, match)).token_holder_user_id,
            "remaining_ms": 45_000,
            "warning": False,
        },
        "mulligan_remaining_ms": None,
    }
    await next_update(two)
    await close(one, two)


async def test_both_mulligans_can_time_out(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    ticker: MatchClockTicker,
) -> None:
    """Um estouro por volta: a partida continua vencida no índice até fechar."""
    match = await awaiting_mulligan(matches, clock)
    now = clock.advance(MULLIGAN_SECONDS)

    await ticker.tick(now)
    await ticker.tick(now)

    live = await stored(matches, match)
    assert live.awaiting_mulligan_user_ids == ()
    assert (live.phase, live.round_number) == (MatchPhase.ACTION, 1)


async def test_the_mulligan_has_no_warning(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    ticker: MatchClockTicker,
) -> None:
    """§15: 30s, sem aviso."""
    match = await awaiting_mulligan(matches, clock)
    one, two = await both_sockets(matches, clock, match)

    await ticker.tick(clock.advance(MULLIGAN_SECONDS - 1))

    assert await one.nothing_received()
    assert await two.nothing_received()
    await close(one, two)


async def test_a_mulligan_that_lands_first_beats_its_expiry(
    clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(clock.now_ms())
    matches = InterleavedMatchStore(lambda: real_mulligan(), clock)
    await saved(matches, match)
    swapped = tuple(card.card_instance_id for card in match.player(PLAYER_ONE).hand[:2])

    async def real_mulligan() -> None:
        await matches.mutate(
            match.match_id,
            PlayerChange(
                MulliganCommand(PLAYER_ONE, swapped),
                catalog=catalog,
                randomness=ScriptedRandomSource(),
                clock=clock,
            ),
        )

    await ticker_over(matches, clock, catalog).tick(clock.advance(MULLIGAN_SECONDS))

    live = await stored(matches, match)
    assert live.player(PLAYER_ONE).mulligan_taken is True
    assert [card.card_instance_id for card in live.player(PLAYER_ONE).hand] != [
        card.card_instance_id for card in match.player(PLAYER_ONE).hand
    ]


# --- Fim de partida e partida abandonada (US7) -------------------------------


async def test_a_forfeit_in_the_mulligan_stops_the_deadline(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    ticker: MatchClockTicker,
) -> None:
    match = await awaiting_mulligan(matches, clock)
    one, two = await both_sockets(matches, clock, match)
    await one.send_json_to({"type": "forfeit"})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(MULLIGAN_SECONDS))

    assert await one.nothing_received()
    assert await two.nothing_received()
    assert matches.wake_at == {}
    await close(one, two)


async def test_a_forfeit_stops_the_turn_deadline(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    clock.advance(20)
    await two.send_json_to({"type": "forfeit"})
    await next_update(one), await next_update(two)

    await ticker.tick(clock.advance(25))

    assert await one.nothing_received()
    assert await two.nothing_received()
    assert matches.wake_at == {}
    await close(one, two)


async def test_an_expired_match_leaves_the_index_and_sends_nothing(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """A chave da partida expira sozinha; o membro do índice é limpo aqui."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    clock.advance(MATCH_TTL_SECONDS)

    await ticker.tick(clock.now_ms())

    assert await matches.get(match.match_id) is None
    assert matches.wake_at == {}
    assert await one.nothing_received()
    await close(one, two)


async def test_timeouts_alone_never_postpone_the_expiry(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """Partida sem ninguém gira, mas some 6h depois da última jogada real."""
    match = await with_a_turn(matches, clock, catalog)

    for _ in range(4):
        await ticker.tick(clock.advance(EXPIRY_SECONDS))

    assert matches.expiry_renewals == [False] * 4
    clock.advance(MATCH_TTL_SECONDS)
    assert await matches.get(match.match_id) is None


async def test_a_real_play_postpones_the_expiry_and_a_timeout_does_not(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """Um jogador presente segura a partida; os estouros do ausente não."""
    match = await with_a_turn(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await ticker.tick(clock.advance(EXPIRY_SECONDS))
    await next_update(one), await next_update(two)

    await two.send_json_to({"type": "pass"})
    await next_update(one), await next_update(two)

    assert matches.expiry_renewals == [False, True]
    await close(one, two)
