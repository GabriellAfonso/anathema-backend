"""O protocolo ao longo da partida: ocultação, reconexão, concorrência e a
partida inteira pela rede (US4, US5, US6, US7).

O teste que carrega o arquivo é `test_a_whole_match_over_the_socket`: o jogador
automático de `test_full_match.py` joga pelos dois sockets do mulligan ao
resultado, e a cada atualização o frame de cada jogador é varrido atrás de
qualquer carta que estivesse na mão ou no deck do outro.
"""

from typing import cast

import pytest

from apps.game.cards import mvp_catalog
from apps.game.match import Match
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    SUMMONED_AX,
    bank_card,
    declare_combat,
    fake_combat_board,
    hand_card,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.match_sockets import (
    Frame,
    message_for,
    next_refusal_code,
    next_update,
    open_match_socket,
    saved,
    side_of,
    view_of,
)
from apps.game.tests.test_full_match import MAX_ACTIONS, next_action, spell_deck
from apps.game.tests.test_match_frames import hidden_ids, ids_in_frame
from apps.game.tests.websocket_test_client import WebsocketTestClient


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore()


async def stored_match(matches: FakeMatchStore, match_id: str) -> Match:
    stored = await matches.get(match_id)
    assert stored is not None

    return stored


async def reconnect(
    client: WebsocketTestClient, matches: FakeMatchStore, user_id: int, match_id: str
) -> tuple[WebsocketTestClient, Frame]:
    await client.disconnect()

    return await open_match_socket(matches, user_id, match_id)


# --- US4: nenhum frame entrega o que o jogador não pode ver -------------------


async def test_citing_a_card_of_the_opponent_hand_is_refused_like_a_missing_card(
    matches: FakeMatchStore,
) -> None:
    match = await saved(
        matches,
        fake_combat_board(catalog=mvp_catalog(), hand_two=(SUMMONED_AX,)),
    )
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    theirs = hand_card(match.player(PLAYER_TWO), SUMMONED_AX)

    codes = []
    for card in (theirs, 99999):
        await one.send_json_to(
            {"type": "play_unit", "payload": {"card_instance_id": card}}
        )
        codes.append(await next_refusal_code(one))

    assert codes == ["card_not_in_hand", "card_not_in_hand"]
    await one.disconnect()


# --- US5: reconexão ------------------------------------------------------------


async def test_reconnecting_during_the_mulligan_says_who_already_chose(
    matches: FakeMatchStore,
) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    await one.send_json_to({"type": "mulligan", "payload": {"card_instance_ids": []}})
    await next_update(one), await next_update(two)

    one, start_one = await reconnect(one, matches, PLAYER_ONE, match.match_id)
    two, start_two = await reconnect(two, matches, PLAYER_TWO, match.match_id)

    mine, theirs = view_of(start_one), view_of(start_two)
    assert (
        side_of(mine, "you")["mulligan_taken"],
        side_of(mine, "opponent")["mulligan_taken"],
    ) == (True, False)
    assert (
        side_of(theirs, "you")["mulligan_taken"],
        side_of(theirs, "opponent")["mulligan_taken"],
    ) == (False, True)
    stored = await matches.get_stored(match.match_id)
    assert stored is not None and start_one["version"] == stored.version
    await one.disconnect()
    await two.disconnect()


async def test_reconnecting_with_the_declaration_open(matches: FakeMatchStore) -> None:
    match = await saved(
        matches, fake_combat_board(catalog=mvp_catalog(), bank_one=(DARK_AGE,))
    )
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    attacker = bank_card(match.player(PLAYER_ONE))
    await one.send_json_to(
        {
            "type": "declare_attack",
            "payload": {"attacker_card_instance_ids": [attacker]},
        }
    )
    await next_update(one)

    one, start = await reconnect(one, matches, PLAYER_ONE, match.match_id)

    view = view_of(start)
    assert (view["phase"], view["priority_user_id"]) == ("declaration", PLAYER_ONE)
    assert cast(Frame, view["combat"])["attacker_card_instance_ids"] == [attacker]
    await one.disconnect()


async def test_reconnecting_with_the_defense_window_open(
    matches: FakeMatchStore,
) -> None:
    board = fake_combat_board(
        catalog=mvp_catalog(), bank_one=(DARK_AGE,), bank_two=(SKILLET,)
    )
    declare_combat(board, 0)
    match = await saved(matches, board)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    blocker, attacker = bank_card(match.player(PLAYER_TWO)), bank_card(
        match.player(PLAYER_ONE)
    )
    await two.send_json_to(
        {
            "type": "assign_blocker",
            "payload": {
                "blocker_card_instance_id": blocker,
                "attacker_card_instance_id": attacker,
            },
        }
    )
    await next_update(two)

    two, start = await reconnect(two, matches, PLAYER_TWO, match.match_id)

    combat = cast(Frame, view_of(start)["combat"])
    assert combat["blocks"] == [
        {"blocker_card_instance_id": blocker, "attacker_card_instance_id": attacker}
    ]
    await two.disconnect()


async def test_reconnecting_after_the_end_brings_the_result(
    matches: FakeMatchStore,
) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    await one.send_json_to({"type": "forfeit"})
    await next_update(one)

    one, start = await reconnect(one, matches, PLAYER_ONE, match.match_id)

    assert view_of(start)["outcome"] == {
        "defeated_user_id": PLAYER_ONE,
        "reason": "forfeit",
    }
    await one.disconnect()


# --- US6: concorrência e sockets repetidos -------------------------------------


async def test_two_sockets_of_one_player_both_get_the_update_but_not_the_refusal(
    matches: FakeMatchStore,
) -> None:
    match = await saved(
        matches, fake_combat_board(catalog=mvp_catalog(), hand_one=(KHRAS,))
    )
    first, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    second, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    khras = hand_card(match.player(PLAYER_ONE), KHRAS)

    await first.send_json_to({"type": "banana"})
    assert await next_refusal_code(first) == "unknown_message_type"
    assert await second.nothing_received()

    await second.send_json_to(
        {"type": "play_unit", "payload": {"card_instance_id": khras}}
    )
    await next_update(first), await next_update(second)

    await first.send_json_to(
        {"type": "play_unit", "payload": {"card_instance_id": khras}}
    )
    assert await next_refusal_code(first) == "not_your_priority"
    await first.disconnect()
    await second.disconnect()


async def test_a_play_is_judged_against_the_stored_state_not_the_one_at_connect(
    matches: FakeMatchStore,
) -> None:
    """O primeiro socket conectou com KHRAS na mão; o segundo socket do mesmo
    jogador o jogou. Jogar de novo pelo primeiro é avaliado contra o agora."""
    match = await saved(
        matches, fake_combat_board(catalog=mvp_catalog(), hand_one=(KHRAS, SUMMONED_AX))
    )
    first, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    second, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    ax = hand_card(match.player(PLAYER_ONE), SUMMONED_AX)
    target = bank_card(match.player(PLAYER_TWO))
    cast_ax: Frame = {
        "type": "cast_spell",
        "payload": {"card_instance_id": ax, "target_card_instance_id": target},
    }

    await second.send_json_to(cast_ax)
    await next_update(first), await next_update(second)
    await first.send_json_to(cast_ax)

    assert await next_refusal_code(first) == "card_not_in_hand"
    await first.disconnect()
    await second.disconnect()


async def test_the_version_grows_with_every_update(matches: FakeMatchStore) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, start = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    versions = [start["version"]]
    messages: tuple[Frame, ...] = (
        {"type": "mulligan", "payload": {"card_instance_ids": []}},
        {"type": "forfeit"},
    )

    for message in messages:
        await one.send_json_to(message)
        versions.append((await next_update(one))["version"])

    assert versions == sorted(set(cast(list[int], versions)))
    await one.disconnect()


async def test_a_play_on_an_expired_match_is_refused_and_the_socket_stays_open(
    matches: FakeMatchStore,
) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    matches.forget(match.match_id)

    for _ in range(2):
        await one.send_json_to({"type": "forfeit"})
        assert await next_refusal_code(one) == "match_not_found"
    await one.disconnect()


# --- US7: a partida inteira pela rede -----------------------------------------


async def test_a_whole_match_over_the_socket(matches: FakeMatchStore) -> None:
    catalog = mvp_catalog()
    match = await saved(
        matches, fake_started_match(PLAYER_ONE, PLAYER_TWO, deck=spell_deck(catalog))
    )
    sockets = {
        user_id: (await open_match_socket(matches, user_id, match.match_id))[0]
        for user_id in (PLAYER_ONE, PLAYER_TWO)
    }

    for user_id in (PLAYER_ONE, PLAYER_TWO):
        await play_and_check(
            matches,
            sockets,
            user_id,
            {"type": "mulligan", "payload": {"card_instance_ids": []}},
        )

    for _ in range(MAX_ACTIONS):
        current = await stored_match(matches, match.match_id)
        if current.is_over:
            break
        action = next_action(current, catalog)
        await play_and_check(
            matches, sockets, action.actor_user_id, message_for(action)
        )

    final = await stored_match(matches, match.match_id)
    assert final.is_over
    await sockets[PLAYER_ONE].send_json_to({"type": "pass"})
    assert await next_refusal_code(sockets[PLAYER_ONE]) == "match_is_over"
    for client in sockets.values():
        await client.disconnect()


async def play_and_check(
    matches: FakeMatchStore,
    sockets: dict[int, WebsocketTestClient],
    sender: int,
    message: Frame,
) -> None:
    """Manda a jogada, e confere que cada socket recebeu uma atualização sem
    nenhuma carta que, depois dela, esteja na mão ou no deck do outro jogador.

    Depois, e não antes: a carta que o outro acabou de jogar estava na mão dele
    e virou pública ao entrar no banco ou no cemitério -- o evento dela a cita
    por inteiro, e deve.
    """
    match_id = next(iter(matches.matches))
    await sockets[sender].send_json_to(message)
    payloads = {
        user_id: await next_update(client) for user_id, client in sockets.items()
    }
    # Lido só depois das duas atualizações: antes delas o consumer pode não ter
    # gravado ainda, e o estado lido seria o de antes da jogada.
    after = await stored_match(matches, match_id)

    for user_id, payload in payloads.items():
        opponent = after.opponent_of(user_id).user_id
        assert ids_in_frame(payload) & hidden_ids(after, opponent) == set(), (
            user_id,
            message,
        )
