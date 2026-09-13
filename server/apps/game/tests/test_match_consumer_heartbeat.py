"""O ping no socket de partida: pong só para quem mandou, e a partida intocada.

Feature 013, FR-007, SC-003, SC-004, SC-006 e research D8. É o socket onde a
queda silenciosa custa caro: o jogador perde a vez pelo relógio sem saber que
caiu. O ping existe para o cliente perceber a queda, e por isso ele não pode
custar nada à partida -- não lê, não grava, não gera versão nem `match_update`,
e não mexe no relógio.

"Não gravou" o `FakeMatchStore` já prova, pela versão e por `expiry_renewals`.
"Não leu" quem prova é o `AccessCountingMatchStore`, zerado depois de o gate ler
a partida ao conectar.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.match import Match, MatchDocument
from apps.game.tests.access_counting_match_store import AccessCountingMatchStore
from apps.game.tests.clock_boards import (
    EXPIRY_SECONDS,
    awaiting_mulligan,
    close,
    ticker_over,
    with_a_turn,
)
from apps.game.tests.fake_combat_board import (
    PLAYER_ONE,
    PLAYER_TWO,
    bank_card,
    declare_combat,
)
from apps.game.tests.fake_finished_match_recorder import (
    FakeFinishedMatchRecorder,
)
from apps.game.tests.fake_wall_clock import FakeWallClock
from apps.game.tests.heartbeat_sockets import expect_ping_burst_answered, expect_pong
from apps.game.tests.match_snapshot import match_snapshot
from apps.game.tests.match_sockets import (
    event_kinds,
    next_refusal_code,
    next_update,
    open_match_socket,
    saved,
    view_of,
)
from apps.game.tests.websocket_test_client import WebsocketTestClient

PING: dict[str, object] = {"type": "ping"}
BURST = 50
# Os pings do teste do relógio: quatro, de 10 em 10 segundos, ainda dentro da vez.
PINGS_BEFORE_EXPIRY = 4
SECONDS_BETWEEN_PINGS = 10


@pytest.fixture
def clock() -> FakeWallClock:
    return FakeWallClock()


@pytest.fixture
def matches(clock: FakeWallClock) -> AccessCountingMatchStore:
    return AccessCountingMatchStore(clock)


@pytest.fixture
def recorder() -> FakeFinishedMatchRecorder:
    return FakeFinishedMatchRecorder()


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


async def player_socket(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    match: Match,
    user_id: int,
) -> WebsocketTestClient:
    client, _ = await open_match_socket(
        matches, user_id, match.match_id, clock=clock, recorder=recorder
    )

    return client


def stored_state(
    matches: AccessCountingMatchStore, match_id: str
) -> tuple[MatchDocument, int]:
    """O estado inteiro gravado -- prazos do relógio inclusive -- e a versão."""
    stored = matches.matches[match_id]

    return match_snapshot(stored.match), stored.version


async def expect_pings_touch_nothing(
    matches: AccessCountingMatchStore, match_id: str, *clients: WebsocketTestClient
) -> None:
    """Ping por cada socket: um pong em cada, e a partida exatamente como estava."""
    before = stored_state(matches, match_id)
    renewals = len(matches.expiry_renewals)
    matches.forget_accesses()

    for client in clients:
        await client.send_json_to(PING)
        await expect_pong(client, {})

    assert not matches.accesses, matches.accesses
    assert stored_state(matches, match_id) == before
    assert len(matches.expiry_renewals) == renewals

    for client in clients:
        assert await client.nothing_received(), "nem match_update, nem recusa"


async def board_in(
    phase: str,
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    catalog: CardCatalog,
) -> Match:
    """A partida gravada naquela fase, montada direto no store."""
    if phase == "mulligan":
        return await awaiting_mulligan(matches, clock)

    match = await with_a_turn(matches, clock, catalog)

    if phase == "combat":
        declare_combat(match, 0)
        await saved(matches, match)

    return match


async def test_a_ping_is_answered_with_a_pong(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)

    await one.send_json_to(PING)

    await expect_pong(one, {})
    assert await one.nothing_received()
    await close(one)


@pytest.mark.parametrize("phase", ["mulligan", "action", "combat"])
async def test_a_ping_leaves_the_match_untouched(
    phase: str,
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """Pinga pelos dois lados: quem tem a vez e quem não tem.

    No mulligan, a igualdade do estado inclui o mulligan dos dois continuar
    pendente e o prazo dele continuar o mesmo.
    """
    match = await board_in(phase, matches, clock, catalog)
    one, start = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, clock=clock, recorder=recorder
    )
    two = await player_socket(matches, clock, recorder, match, PLAYER_TWO)
    assert view_of(start)["phase"] == phase

    await expect_pings_touch_nothing(matches, match.match_id, one, two)

    await close(one, two)


async def test_a_ping_during_the_declaration_leaves_the_match_untouched(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """A declaração passa pela jogada de verdade: não há atalho de estado para ela."""
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    two = await player_socket(matches, clock, recorder, match, PLAYER_TWO)
    attacker = bank_card(match.player(PLAYER_ONE))
    await one.send_json_to(
        {
            "type": "declare_attack",
            "payload": {"attacker_card_instance_ids": [attacker]},
        }
    )
    assert view_of(await next_update(one))["phase"] == "declaration"
    await next_update(two)

    await expect_pings_touch_nothing(matches, match.match_id, one, two)

    await close(one, two)


async def test_a_ping_after_the_end_is_answered_and_records_nothing(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """Pong, e não `match_is_over`; o registro continua um só (SC-004)."""
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    two = await player_socket(matches, clock, recorder, match, PLAYER_TWO)
    await one.send_json_to({"type": "forfeit", "payload": {}})
    assert view_of(await next_update(one))["phase"] == "finished"
    await next_update(two)

    await expect_pings_touch_nothing(matches, match.match_id, one, two)

    assert len(recorder.recorded) == 1
    await close(one, two)


async def test_pinging_does_not_hold_back_the_turn_clock(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """Quem tem a vez pinga a vez inteira, e ela estoura no mesmo instante.

    Se o ping contasse como ação ou estendesse o prazo, o tick dos 45s não
    acharia vez nenhuma vencida.
    """
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    two = await player_socket(matches, clock, recorder, match, PLAYER_TWO)
    ticker = ticker_over(matches, clock, catalog)

    for _ in range(PINGS_BEFORE_EXPIRY):
        clock.advance(SECONDS_BETWEEN_PINGS)
        await one.send_json_to(PING)
        await expect_pong(one, {})

    pinged_seconds = PINGS_BEFORE_EXPIRY * SECONDS_BETWEEN_PINGS
    await ticker.tick(clock.advance(EXPIRY_SECONDS - pinged_seconds))

    assert event_kinds(await next_update(one))[:2] == ["turn_timed_out", "passed"]
    await next_update(two)
    await close(one, two)


async def test_the_pong_reaches_only_the_socket_that_pinged(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """Nem o socket velho do mesmo usuário, nem o oponente (SC-006)."""
    match = await with_a_turn(matches, clock, catalog)
    pinging = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    same_user = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    opponent = await player_socket(matches, clock, recorder, match, PLAYER_TWO)

    await pinging.send_json_to(PING)

    await expect_pong(pinging, {})
    assert await same_user.nothing_received()
    assert await opponent.nothing_received()
    await close(pinging, same_user, opponent)


async def test_a_burst_of_pings_is_answered_in_order(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)

    await expect_ping_burst_answered(one, BURST)

    assert await one.nothing_received(), "nenhuma recusa no meio da rajada"
    await close(one)


async def test_a_ping_does_not_notice_an_expired_match(
    matches: AccessCountingMatchStore,
    clock: FakeWallClock,
    recorder: FakeFinishedMatchRecorder,
    catalog: CardCatalog,
) -> None:
    """O ping não consulta a partida; a próxima jogada é que descobre."""
    match = await with_a_turn(matches, clock, catalog)
    one = await player_socket(matches, clock, recorder, match, PLAYER_ONE)
    matches.forget(match.match_id)

    await one.send_json_to(PING)
    await expect_pong(one, {})

    await one.send_json_to({"type": "pass"})
    assert await next_refusal_code(one) == "match_not_found"
    await close(one)
