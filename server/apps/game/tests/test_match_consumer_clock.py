"""O relógio pelo socket: o prazo que o cliente vê, e o que não o reinicia.

Duas perguntas, as duas jogadas por sockets de verdade com o relógio falso:

- o relógio é **da vez, não da ação** (§15) -- feitiço, mandar e puxar atacante
  e bloquear não devolvem tempo, e trocar de mão ou virar a rodada devolvem;
- o cliente recebe **quanto falta**, medido pelo servidor, no `match_start` e em
  toda atualização.
"""

from typing import cast

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.match import Match
from apps.game.match_timers import MatchClockTicker
from apps.game.protocol import advance_match_clock, opening_match_clock
from apps.game.tests.fake_finished_match_recorder import (
    FakeFinishedMatchRecorder,
)
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
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_match_wake_queue import FakeMatchWakeQueue
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.match_sockets import (
    Frame,
    event_kinds,
    next_turn_warning,
    next_update,
    open_match_socket,
    saved,
    view_of,
)
from apps.game.tests.websocket_test_client import WebsocketTestClient

FULL_TURN_MS = 45_000


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
    from channels.layers import get_channel_layer

    return MatchClockTicker(
        matches=matches,
        wake_queue=FakeMatchWakeQueue(matches),
        channel_layer=get_channel_layer(),
        catalog=catalog,
        randomness=ScriptedRandomSource(),
        clock=clock,
        recorder=FakeFinishedMatchRecorder(),
    )


def clock_of(payload: Frame) -> Frame:
    return cast(Frame, payload["clock"])


def turn_of(payload: Frame) -> Frame:
    turn = clock_of(payload)["turn"]
    assert turn is not None, payload

    return cast(Frame, turn)


async def board(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> Match:
    """Fase de Ação, vez do primeiro jogador aberta agora, com o que jogar."""
    match = fake_combat_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD, KHRAS),
        bank_one=(DARK_AGE, MORTEM),
        bank_two=(SKILLET,),
    )
    advance_match_clock(match, clock.now_ms())

    return await saved(matches, match)


async def both_sockets(
    matches: FakeMatchStore, clock: FakeWallClock, match: Match
) -> tuple[WebsocketTestClient, WebsocketTestClient]:
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id, clock=clock)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id, clock=clock)

    return one, two


async def play(
    client: WebsocketTestClient,
    message: Frame,
    others: tuple[WebsocketTestClient, ...],
) -> Frame:
    """Manda a jogada e devolve a atualização que voltou para quem mandou."""
    await client.send_json_to(message)
    mine = await next_update(client)

    for other in others:
        await next_update(other)

    return mine


async def close(*clients: WebsocketTestClient) -> None:
    for client in clients:
        await client.disconnect()


# --- O relógio é da vez, não da ação (US3) -----------------------------------


async def test_a_spell_does_not_give_time_back(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    shield = hand_card(match.player(PLAYER_ONE), SOMEONES_SHIELD)
    clock.advance(40)

    payload = await play(
        one,
        {
            "type": "cast_spell",
            "payload": {
                "card_instance_id": shield,
                "target_card_instance_id": bank_card(match.player(PLAYER_ONE)),
            },
        },
        (two,),
    )

    assert turn_of(payload) == {
        "turn_number": 1,
        "holder_user_id": PLAYER_ONE,
        "remaining_ms": 5_000,
        "warning": True,
    }
    await close(one, two)


async def test_sending_and_withdrawing_attackers_does_not_restart_the_clock(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    attacker = bank_card(match.player(PLAYER_ONE))

    send: Frame = {
        "type": "declare_attack",
        "payload": {"attacker_card_instance_ids": [attacker]},
    }
    withdraw: Frame = {
        "type": "withdraw_attacker",
        "payload": {"attacker_card_instance_id": attacker},
    }

    for seconds, message in ((10, send), (10, withdraw), (10, send), (10, withdraw)):
        clock.advance(seconds)
        payload = await play(one, message, (two,))
        assert turn_of(payload)["turn_number"] == 1

    await ticker.tick(clock.advance(5))

    assert event_kinds(await next_update(one))[:2] == ["turn_timed_out", "passed"]
    await next_update(two)
    await close(one, two)


async def test_confirming_the_attack_gives_the_defender_a_fresh_clock(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    attacker = bank_card(match.player(PLAYER_ONE))
    await play(
        one,
        {
            "type": "declare_attack",
            "payload": {"attacker_card_instance_ids": [attacker]},
        },
        (two,),
    )
    clock.advance(20)

    payload = await play(one, {"type": "confirm_attack"}, (two,))

    assert turn_of(payload) == {
        "turn_number": 2,
        "holder_user_id": PLAYER_TWO,
        "remaining_ms": FULL_TURN_MS,
        "warning": False,
    }
    await close(one, two)


async def test_blocking_does_not_restart_the_defenders_clock(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    attacker = bank_card(match.player(PLAYER_ONE))
    blocker = bank_card(match.player(PLAYER_TWO))
    await play(
        one,
        {
            "type": "declare_attack",
            "payload": {"attacker_card_instance_ids": [attacker]},
        },
        (two,),
    )
    await play(one, {"type": "confirm_attack"}, (two,))

    clock.advance(25)
    payload = await play(
        two,
        {
            "type": "assign_blocker",
            "payload": {
                "blocker_card_instance_id": blocker,
                "attacker_card_instance_id": attacker,
            },
        },
        (one,),
    )
    assert turn_of(payload)["remaining_ms"] == 20_000

    clock.advance(15)
    payload = await play(
        two,
        {"type": "remove_blocker", "payload": {"blocker_card_instance_id": blocker}},
        (one,),
    )

    assert turn_of(payload)["remaining_ms"] == 5_000
    await ticker.tick(clock.advance(5))
    assert event_kinds(await next_update(two))[:2] == [
        "turn_timed_out",
        "defense_ended",
    ]
    await next_update(one)
    await close(one, two)


async def test_resolving_the_combat_opens_the_token_holders_clock(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    attacker = bank_card(match.player(PLAYER_ONE))
    await play(
        one,
        {
            "type": "declare_attack",
            "payload": {"attacker_card_instance_ids": [attacker]},
        },
        (two,),
    )
    await play(one, {"type": "confirm_attack"}, (two,))
    clock.advance(15)

    payload = await play(two, {"type": "end_defense_window"}, (one,))

    assert turn_of(payload) == {
        "turn_number": 3,
        "holder_user_id": PLAYER_ONE,
        "remaining_ms": FULL_TURN_MS,
        "warning": False,
    }
    await close(one, two)


async def test_the_round_turning_gives_the_same_player_a_new_clock(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    """Quem dá o segundo passe recebe a vez de volta -- com prazo novo."""
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await play(one, {"type": "pass"}, (two,))
    clock.advance(44)

    payload = await play(two, {"type": "pass"}, (one,))

    assert view_of(payload)["round_number"] == 2
    assert turn_of(payload) == {
        "turn_number": 3,
        "holder_user_id": PLAYER_TWO,
        "remaining_ms": FULL_TURN_MS,
        "warning": False,
    }
    await close(one, two)


async def test_a_timed_out_pass_does_not_expire_again_at_once(
    matches: FakeMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
    ticker: MatchClockTicker,
) -> None:
    """Sem a rodada na identidade da vez, este cenário giraria para sempre."""
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    await play(one, {"type": "pass"}, (two,))

    await ticker.tick(clock.advance(45))
    await next_update(one), await next_update(two)
    await ticker.tick(clock.now_ms())

    assert await one.nothing_received()
    assert await two.nothing_received()
    await close(one, two)


async def test_playing_a_unit_gives_the_opponent_a_full_clock(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)
    clock.advance(5)

    payload = await play(
        one,
        {
            "type": "play_unit",
            "payload": {"card_instance_id": hand_card(match.player(PLAYER_ONE), KHRAS)},
        },
        (two,),
    )

    assert turn_of(payload) == {
        "turn_number": 2,
        "holder_user_id": PLAYER_TWO,
        "remaining_ms": FULL_TURN_MS,
        "warning": False,
    }
    await close(one, two)


# --- O que o cliente vê (US6) ------------------------------------------------


async def test_connecting_mid_turn_sees_the_real_remaining_time(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    clock.advance(20)

    _, start = await open_match_socket(matches, PLAYER_TWO, match.match_id, clock=clock)

    assert turn_of(start) == {
        "turn_number": 1,
        "holder_user_id": PLAYER_ONE,
        "remaining_ms": 25_000,
        "warning": False,
    }


async def test_reconnecting_at_forty_seconds_sees_the_warning(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    """Reconexão mostra o tempo restante de verdade, não um relógio novo."""
    match = await board(matches, clock, catalog)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id, clock=clock)
    await one.disconnect()
    clock.advance(40)

    again, start = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, clock=clock
    )

    assert turn_of(start)["remaining_ms"] == 5_000
    assert turn_of(start)["warning"] is True
    await close(again)


async def test_the_mulligan_shows_each_player_their_own_deadline(
    matches: FakeMatchStore, clock: FakeWallClock
) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(clock.now_ms())
    await saved(matches, match)
    one, two = await both_sockets(matches, clock, match)
    clock.advance(12)

    payload = await play(
        one, {"type": "mulligan", "payload": {"card_instance_ids": []}}, (two,)
    )
    _, start = await open_match_socket(matches, PLAYER_TWO, match.match_id, clock=clock)

    assert clock_of(payload) == {"turn": None, "mulligan_remaining_ms": None}
    assert clock_of(start)["mulligan_remaining_ms"] == 18_000
    await close(one, two)


async def test_a_finished_match_shows_no_deadline(
    matches: FakeMatchStore, clock: FakeWallClock, catalog: CardCatalog
) -> None:
    match = await board(matches, clock, catalog)
    one, two = await both_sockets(matches, clock, match)

    payload = await play(one, {"type": "forfeit"}, (two,))

    assert clock_of(payload) == {"turn": None, "mulligan_remaining_ms": None}
    await close(one, two)
