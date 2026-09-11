"""Jogar pelo socket: mulligan, jogadas e recusas (US1, US2, US3).

Cada teste abre os sockets dos dois jogadores sobre o store em memória, manda
mensagens como o cliente mandaria, e confere o que chega a cada socket. A regra
de ouro é a da spec: **toda mudança aceita chega aos dois, cada um com a sua
visão**, e **toda recusa chega só a quem mandou**, sem fechar o socket.
"""

from typing import cast

import pytest

from apps.game.match import Match, to_match_document
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    SUMMONED_AX,
    bank_card,
    fake_combat_board,
    hand_card,
)
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_setup import fake_started_match
from apps.game.tests.match_sockets import (
    Frame,
    event_kinds,
    next_refusal_code,
    next_update,
    open_match_socket,
    saved,
    side_of,
    view_of,
)
from apps.game.cards import mvp_catalog
from apps.game.tests.websocket_test_client import WebsocketTestClient


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore()


async def board(matches: FakeMatchStore) -> Match:
    """Fase de Ação, vez do primeiro jogador, SUMMONED AX e KHRAS na mão dele,
    DARK AGE e MORTEM no banco dele, SKILLET no do outro."""
    return await saved(
        matches,
        fake_combat_board(
            catalog=mvp_catalog(),
            hand_one=(SUMMONED_AX, KHRAS),
            bank_one=(DARK_AGE, MORTEM),
            bank_two=(SKILLET,),
        ),
    )


# --- US1: mulligan pelo socket -------------------------------------------------


async def test_the_first_mulligan_reaches_both_players(matches: FakeMatchStore) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)

    await one.send_json_to({"type": "mulligan", "payload": {"card_instance_ids": []}})

    for_one, for_two = await next_update(one), await next_update(two)
    assert side_of(view_of(for_one), "you")["mulligan_taken"] is True
    assert side_of(view_of(for_two), "opponent")["mulligan_taken"] is True
    assert cast(list[Frame], for_two["events"])[0] == {
        "kind": "mulligan_taken",
        "user_id": PLAYER_ONE,
        "swapped_count": 0,
    }
    await one.disconnect()
    await two.disconnect()


async def test_the_second_mulligan_opens_round_one_with_no_other_message(
    matches: FakeMatchStore,
) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    empty: Frame = {"type": "mulligan", "payload": {"card_instance_ids": []}}

    await one.send_json_to(empty)
    await next_update(one), await next_update(two)
    await two.send_json_to(empty)

    for payload in (await next_update(one), await next_update(two)):
        view = view_of(payload)
        assert (view["phase"], view["round_number"]) == ("action", 1)
        assert "round_started" in event_kinds(payload)
    await one.disconnect()
    await two.disconnect()


async def test_a_repeated_mulligan_is_refused_only_to_the_sender(
    matches: FakeMatchStore,
) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    empty: Frame = {"type": "mulligan", "payload": {"card_instance_ids": []}}
    await one.send_json_to(empty)
    await next_update(one), await next_update(two)

    await one.send_json_to(empty)

    assert await next_refusal_code(one) == "mulligan_already_taken"
    assert await two.nothing_received()
    await one.disconnect()
    await two.disconnect()


async def test_a_play_during_the_mulligan_is_refused(matches: FakeMatchStore) -> None:
    match = await saved(matches, fake_started_match(PLAYER_ONE, PLAYER_TWO))
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)

    await one.send_json_to({"type": "pass"})

    assert await next_refusal_code(one) == "not_your_priority"
    await one.disconnect()


# --- US2: jogar a partida ------------------------------------------------------


async def test_an_accepted_play_reaches_both_each_with_their_own_view(
    matches: FakeMatchStore,
) -> None:
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    khras = hand_card(match.player(PLAYER_ONE), KHRAS)

    await one.send_json_to(
        {"type": "play_unit", "payload": {"card_instance_id": khras}}
    )

    for_one, for_two = await next_update(one), await next_update(two)
    own_hand = cast(list[Frame], side_of(view_of(for_one), "you")["hand"])
    assert khras not in [card["card_instance_id"] for card in own_hand]
    assert "hand" not in side_of(view_of(for_two), "opponent")
    assert event_kinds(for_two)[0] == "unit_played"
    assert view_of(for_two)["priority_user_id"] == PLAYER_TWO
    await one.disconnect()
    await two.disconnect()


async def test_an_author_field_in_the_message_does_not_change_who_acts(
    matches: FakeMatchStore,
) -> None:
    """O jogador sem a vez manda um passe dizendo que é o outro."""
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)

    await two.send_json_to(
        {
            "type": "pass",
            "payload": {"actor_user_id": PLAYER_ONE, "user_id": PLAYER_ONE},
        }
    )

    assert await next_refusal_code(two) == "not_your_priority"
    assert await one.nothing_received()
    await one.disconnect()
    await two.disconnect()


async def test_a_spell_resolves_and_the_turn_stays(matches: FakeMatchStore) -> None:
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    ax = hand_card(match.player(PLAYER_ONE), SUMMONED_AX)
    target = bank_card(match.player(PLAYER_TWO))

    await one.send_json_to(
        {
            "type": "cast_spell",
            "payload": {"card_instance_id": ax, "target_card_instance_id": target},
        }
    )

    for payload in (await next_update(one), await next_update(two)):
        assert view_of(payload)["priority_user_id"] == PLAYER_ONE
        assert event_kinds(payload) == ["spell_cast", "unit_damaged"]
    await one.disconnect()
    await two.disconnect()


async def test_two_passes_arrive_as_one_update_in_the_next_round(
    matches: FakeMatchStore,
) -> None:
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)

    await one.send_json_to({"type": "pass"})
    await next_update(one), await next_update(two)
    await two.send_json_to({"type": "pass"})

    for payload in (await next_update(one), await next_update(two)):
        assert view_of(payload)["round_number"] == 2
        assert event_kinds(payload)[:2] == ["passed", "round_started"]
    assert await one.nothing_received() and await two.nothing_received()
    await one.disconnect()
    await two.disconnect()


async def test_every_step_of_the_combat_is_one_update_for_each(
    matches: FakeMatchStore,
) -> None:
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    dark_age, mortem = (bank_card(match.player(PLAYER_ONE), i) for i in (0, 1))
    skillet = bank_card(match.player(PLAYER_TWO))
    steps: list[tuple[WebsocketTestClient, Frame]] = [
        (
            one,
            {
                "type": "declare_attack",
                "payload": {"attacker_card_instance_ids": [dark_age]},
            },
        ),
        (
            one,
            {
                "type": "declare_attack",
                "payload": {"attacker_card_instance_ids": [mortem]},
            },
        ),
        (
            one,
            {
                "type": "withdraw_attacker",
                "payload": {"attacker_card_instance_id": dark_age},
            },
        ),
        (one, {"type": "confirm_attack"}),
        (
            two,
            {
                "type": "assign_blocker",
                "payload": {
                    "blocker_card_instance_id": skillet,
                    "attacker_card_instance_id": mortem,
                },
            },
        ),
        (two, {"type": "end_defense_window"}),
    ]
    priorities = []

    for sender, message in steps:
        await sender.send_json_to(message)
        for_one, for_two = await next_update(one), await next_update(two)
        assert (
            view_of(for_one)["priority_user_id"] == view_of(for_two)["priority_user_id"]
        )
        priorities.append(view_of(for_one)["priority_user_id"])

    assert priorities == [
        PLAYER_ONE,
        PLAYER_ONE,
        PLAYER_ONE,
        PLAYER_TWO,
        PLAYER_TWO,
        PLAYER_ONE,
    ]
    await one.disconnect()
    await two.disconnect()


async def test_a_forfeit_out_of_turn_ends_the_match_for_both(
    matches: FakeMatchStore,
) -> None:
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)

    await two.send_json_to({"type": "forfeit"})

    for payload in (await next_update(one), await next_update(two)):
        assert view_of(payload)["outcome"] == {
            "defeated_user_id": PLAYER_TWO,
            "reason": "forfeit",
        }
    await one.send_json_to({"type": "pass"})
    assert await next_refusal_code(one) == "match_is_over"
    await one.disconnect()
    await two.disconnect()


# --- US3: recusa com código estável --------------------------------------------


async def test_malformed_messages_are_refused_only_to_the_sender(
    matches: FakeMatchStore,
) -> None:
    """Cada recusa com o código dela, o oponente sem frame nenhum, e o socket
    aceitando uma jogada legal logo depois."""
    match = await board(matches)
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)

    await one.send_json_to({"payload": {}})
    assert await next_refusal_code(one) == "malformed_message"
    await one.send_json_to({"type": "banana"})
    assert await next_refusal_code(one) == "unknown_message_type"
    await one.send_raw_text("{not json")
    assert await next_refusal_code(one) == "malformed_message"
    await one.send_json_to({"type": "play_unit", "payload": {"card_instance_id": "3"}})
    assert await next_refusal_code(one) == "malformed_message"
    assert await two.nothing_received()

    await one.send_json_to({"type": "pass"})
    await next_update(one), await next_update(two)
    await one.disconnect()
    await two.disconnect()


async def test_an_illegal_play_leaves_the_match_as_it_was(
    matches: FakeMatchStore,
) -> None:
    match = await board(matches)
    match.player(PLAYER_ONE).energy_current = 0
    await matches.save(match)
    before = await matches.get_stored(match.match_id)
    assert before is not None
    one, _ = await open_match_socket(matches, PLAYER_ONE, match.match_id)
    two, _ = await open_match_socket(matches, PLAYER_TWO, match.match_id)
    ax = hand_card(match.player(PLAYER_ONE), SUMMONED_AX)

    await one.send_json_to(
        {
            "type": "cast_spell",
            "payload": {
                "card_instance_id": ax,
                "target_card_instance_id": bank_card(match.player(PLAYER_TWO)),
            },
        }
    )

    assert await next_refusal_code(one) == "not_enough_energy"
    assert await two.nothing_received()
    after = await matches.get_stored(match.match_id)
    assert after is not None
    assert after.version == before.version
    assert to_match_document(after.match) == to_match_document(before.match)
    await one.disconnect()
    await two.disconnect()
