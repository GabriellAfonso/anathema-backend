"""A forma das mensagens do cliente, antes de qualquer regra.

O cliente não é confiável: mensagem malformada nunca chega ao motor, e o autor
de toda jogada é o usuário do socket -- nunca um campo do payload.
"""

import pytest

from apps.game.engine import (
    AssignBlockerAction,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    PassAction,
    PlayUnitAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
)
from apps.game.match import CardInstanceId
from apps.game.protocol import (
    MALFORMED_MESSAGE,
    UNKNOWN_MESSAGE_TYPE,
    ClientCommand,
    ForfeitCommand,
    MalformedMessageError,
    MulliganCommand,
    parse_client_message,
)

AUTHOR = 7
OPPONENT = 9


def parse(content: object) -> ClientCommand:
    return parse_client_message(content, author_user_id=AUTHOR)


def refusal_code(content: object) -> str:
    with pytest.raises(MalformedMessageError) as refusal:
        parse(content)

    return refusal.value.code


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            {"type": "mulligan", "payload": {"card_instance_ids": [3, 4]}},
            MulliganCommand(AUTHOR, (CardInstanceId(3), CardInstanceId(4))),
        ),
        (
            {"type": "mulligan", "payload": {"card_instance_ids": []}},
            MulliganCommand(AUTHOR, ()),
        ),
        ({"type": "forfeit"}, ForfeitCommand(AUTHOR)),
        (
            {"type": "play_unit", "payload": {"card_instance_id": 3}},
            PlayUnitAction(AUTHOR, CardInstanceId(3)),
        ),
        (
            {
                "type": "cast_spell",
                "payload": {"card_instance_id": 3, "target_card_instance_id": 11},
            },
            CastSpellAction(AUTHOR, CardInstanceId(3), CardInstanceId(11)),
        ),
        (
            {"type": "cast_spell", "payload": {"card_instance_id": 3}},
            CastSpellAction(AUTHOR, CardInstanceId(3), None),
        ),
        (
            {
                "type": "cast_spell",
                "payload": {"card_instance_id": 3, "target_card_instance_id": None},
            },
            CastSpellAction(AUTHOR, CardInstanceId(3), None),
        ),
        ({"type": "pass"}, PassAction(AUTHOR)),
        ({"type": "pass", "payload": {}}, PassAction(AUTHOR)),
        (
            {"type": "declare_attack", "payload": {"attacker_card_instance_ids": [5]}},
            DeclareAttackAction(AUTHOR, (CardInstanceId(5),)),
        ),
        (
            {"type": "withdraw_attacker", "payload": {"attacker_card_instance_id": 5}},
            WithdrawAttackerAction(AUTHOR, CardInstanceId(5)),
        ),
        ({"type": "confirm_attack"}, ConfirmAttackAction(AUTHOR)),
        (
            {
                "type": "assign_blocker",
                "payload": {
                    "blocker_card_instance_id": 8,
                    "attacker_card_instance_id": 5,
                },
            },
            AssignBlockerAction(AUTHOR, CardInstanceId(8), CardInstanceId(5)),
        ),
        (
            {"type": "remove_blocker", "payload": {"blocker_card_instance_id": 8}},
            RemoveBlockerAction(AUTHOR, CardInstanceId(8)),
        ),
        ({"type": "end_defense_window"}, EndDefenseWindowAction(AUTHOR)),
    ],
)
def test_every_well_formed_message_becomes_its_command(
    content: object, expected: ClientCommand
) -> None:
    assert parse(content) == expected


def test_an_author_field_in_the_payload_does_not_change_who_acts() -> None:
    """Quem age é o dono do socket, nunca um campo da mensagem."""
    command = parse(
        {
            "type": "pass",
            "payload": {"actor_user_id": OPPONENT, "user_id": OPPONENT},
        }
    )

    assert command == PassAction(AUTHOR)


def test_extra_fields_are_ignored() -> None:
    command = parse(
        {"type": "play_unit", "payload": {"card_instance_id": 3, "banana": True}}
    )

    assert command == PlayUnitAction(AUTHOR, CardInstanceId(3))


@pytest.mark.parametrize(
    "content",
    [
        "pass",
        [],
        None,
        {"payload": {}},
        {"type": ""},
        {"type": 3},
        {"type": "pass", "payload": 3},
        {"type": "play_unit"},
        {"type": "play_unit", "payload": {"card_instance_id": "3"}},
        {"type": "play_unit", "payload": {"card_instance_id": 3.5}},
        {"type": "play_unit", "payload": {"card_instance_id": True}},
        {"type": "play_unit", "payload": {"card_instance_id": None}},
        {"type": "play_unit", "payload": {"card_instance_id": 0}},
        {"type": "play_unit", "payload": {"card_instance_id": [3]}},
        {"type": "mulligan", "payload": {"card_instance_ids": 3}},
        {"type": "mulligan", "payload": {"card_instance_ids": ["3"]}},
        {
            "type": "cast_spell",
            "payload": {"card_instance_id": 3, "target_card_instance_id": "x"},
        },
        {"type": "assign_blocker", "payload": {"blocker_card_instance_id": 8}},
    ],
)
def test_a_malformed_message_is_refused_by_its_shape(content: object) -> None:
    assert refusal_code(content) == MALFORMED_MESSAGE


def test_an_unknown_type_has_its_own_code() -> None:
    assert refusal_code({"type": "banana"}) == UNKNOWN_MESSAGE_TYPE


def test_the_shape_refusal_names_the_offending_value() -> None:
    with pytest.raises(MalformedMessageError) as refusal:
        parse({"type": "play_unit", "payload": {"card_instance_id": "3"}})

    assert "card_instance_id is '3'" in str(refusal.value)
