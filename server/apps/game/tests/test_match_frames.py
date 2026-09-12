"""Os frames do socket de partida, montados para quem vai recebê-los.

O teste que carrega o arquivo é
`test_no_frame_carries_a_hidden_card_of_the_opponent`: ele serializa o frame
como sairia pelo socket e procura, no texto, cada identificador que estava na
mão ou no deck do oponente. Não é checagem de campo -- é a pergunta que um
cliente curioso faria ao tráfego.

O relógio (§15) entra pela mesma porta: o frame leva **quanto falta**, medido
pelo servidor na montagem, e nunca um horário absoluto -- o relógio do
dispositivo do cliente pode estar errado sem que o prazo fique.
"""

import json
from copy import deepcopy

from apps.game.cards import mvp_catalog
from apps.game.engine import PassAction
from apps.game.match import Match
from apps.game.protocol import (
    ClockOrigin,
    MulliganCommand,
    PlayerOrigin,
    TurnExpiry,
    advance_match_clock,
    apply_command,
    match_start_payload,
    match_update_payload,
    opening_match_clock,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase, fake_started_match
from apps.game.wall_clock import EpochMillis

PLAYER_ONE = 7
PLAYER_TWO = 9

NOW = EpochMillis(1_000_000)
TWENTY_SECONDS_IN = EpochMillis(NOW + 20_000)
FORTY_SECONDS_IN = EpochMillis(NOW + 40_000)


def hidden_ids(match: Match, user_id: int) -> set[int]:
    """Identificadores que o dono de `user_id` tem na mão ou no deck."""
    player = match.player(user_id)

    return {card.card_instance_id for card in [*player.hand, *player.deck]}


def ids_in_frame(frame: object) -> set[int]:
    """Todo inteiro sob uma chave `card_instance_id`/`..._card_instance_id(s)`."""
    found: set[int] = set()

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            for child in node:
                walk(child, key)
        elif isinstance(node, int) and "card_instance_id" in key:
            found.add(node)

    walk(json.loads(json.dumps(frame)))

    return found


def keys_in_frame(frame: object) -> set[str]:
    """Toda chave de objeto do frame, em qualquer profundidade."""
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                found.add(str(key))
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(json.loads(json.dumps(frame)))

    return found


def match_with_a_turn() -> Match:
    """Fase de Ação com a vez aberta em `NOW`."""
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    advance_match_clock(match, NOW)

    return match


def test_the_start_frame_carries_the_version_and_the_view() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    payload = match_start_payload(match, 4, PLAYER_ONE, NOW)

    assert payload["version"] == 4
    assert payload["view"]["you"]["profile"]["user_id"] == PLAYER_ONE


def test_the_view_says_whose_mulligan_is_in() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.player(PLAYER_TWO).mulligan_taken = True

    view = match_start_payload(match, 1, PLAYER_ONE, NOW)["view"]

    assert (view["you"]["mulligan_taken"], view["opponent"]["mulligan_taken"]) == (
        False,
        True,
    )


def test_the_update_frame_is_built_for_its_recipient() -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    holder = match.priority_user_id
    assert holder is not None
    before = deepcopy(match)
    apply_command(
        match,
        PassAction(holder),
        catalog=mvp_catalog(),
        randomness=ScriptedRandomSource(),
    )

    for_one = match_update_payload(
        before, match, 7, PassAction(holder), PLAYER_ONE, origin=PlayerOrigin(), now=NOW
    )
    for_two = match_update_payload(
        before, match, 7, PassAction(holder), PLAYER_TWO, origin=PlayerOrigin(), now=NOW
    )

    assert for_one["version"] == for_two["version"] == 7
    assert for_one["view"]["you"]["profile"]["user_id"] == PLAYER_ONE
    assert for_two["view"]["you"]["profile"]["user_id"] == PLAYER_TWO
    assert for_one["events"] == [{"kind": "passed", "user_id": holder}]


def test_no_frame_carries_a_hidden_card_of_the_opponent() -> None:
    """Mulligan com troca, de um lado e do outro: nenhum identificador da mão
    ou do deck de um aparece no frame do outro."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    source = ScriptedRandomSource()

    for author in (PLAYER_ONE, PLAYER_TWO):
        swapped = tuple(card.card_instance_id for card in match.player(author).hand[:2])
        command = MulliganCommand(author, swapped)
        before = deepcopy(match)
        apply_command(match, command, catalog=mvp_catalog(), randomness=source)

        for recipient, opponent in ((PLAYER_ONE, PLAYER_TWO), (PLAYER_TWO, PLAYER_ONE)):
            frame = match_update_payload(
                before, match, 2, command, recipient, origin=PlayerOrigin(), now=NOW
            )
            leaked = ids_in_frame(frame) & (
                hidden_ids(before, opponent) | hidden_ids(match, opponent)
            )

            assert leaked == set(), (author, recipient)


# --- O relógio no frame (§15) ------------------------------------------------


def test_the_clock_counts_down_measured_by_the_server() -> None:
    match = match_with_a_turn()

    clock = match_start_payload(match, 1, PLAYER_TWO, TWENTY_SECONDS_IN)["clock"]

    assert clock["turn"] == {
        "turn_number": 1,
        "holder_user_id": match.priority_user_id,
        "remaining_ms": 25_000,
        "warning": False,
    }


def test_the_warning_flag_follows_the_remaining_time() -> None:
    """Derivado do que falta, e não da marca gravada: quem reconecta aos 40s vê
    o aviso valendo mesmo que o frame dele tenha se perdido."""
    match = match_with_a_turn()

    clock = match_start_payload(match, 1, PLAYER_ONE, FORTY_SECONDS_IN)["clock"]
    turn = clock["turn"]

    assert turn is not None
    assert (turn["remaining_ms"], turn["warning"]) == (5_000, True)


def test_the_remaining_time_never_goes_negative() -> None:
    match = match_with_a_turn()

    clock = match_start_payload(match, 1, PLAYER_ONE, EpochMillis(NOW + 90_000))[
        "clock"
    ]
    turn = clock["turn"]

    assert turn is not None
    assert turn["remaining_ms"] == 0


def test_the_mulligan_deadline_is_only_the_recipients_own() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.clock = opening_match_clock(NOW)
    match.player(PLAYER_ONE).mulligan_taken = True

    for_one = match_start_payload(match, 1, PLAYER_ONE, TWENTY_SECONDS_IN)["clock"]
    for_two = match_start_payload(match, 1, PLAYER_TWO, TWENTY_SECONDS_IN)["clock"]

    assert (for_one["turn"], for_one["mulligan_remaining_ms"]) == (None, None)
    assert for_two["mulligan_remaining_ms"] == 10_000


def test_a_finished_match_has_no_deadline() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    clock = match_start_payload(match, 1, PLAYER_ONE, NOW)["clock"]

    assert (clock["turn"], clock["mulligan_remaining_ms"]) == (None, None)


def test_the_clock_origin_marks_the_play_as_a_timeout() -> None:
    match = match_with_a_turn()
    holder = match.priority_user_id
    assert holder is not None
    before = deepcopy(match)
    apply_command(
        match,
        PassAction(holder),
        catalog=mvp_catalog(),
        randomness=ScriptedRandomSource(),
    )

    events = match_update_payload(
        before,
        match,
        8,
        PassAction(holder),
        PLAYER_TWO,
        origin=ClockOrigin(TurnExpiry(1, holder)),
        now=NOW,
    )["events"]

    assert events[:2] == [
        {"kind": "turn_timed_out", "user_id": holder, "turn_number": 1},
        {"kind": "passed", "user_id": holder},
    ]


def test_no_frame_carries_an_absolute_instant() -> None:
    """O cliente recebe quanto falta, nunca um horário para comparar com o
    relógio do dispositivo dele."""
    match = match_with_a_turn()

    frame = match_start_payload(match, 1, PLAYER_ONE, TWENTY_SECONDS_IN)

    assert [key for key in keys_in_frame(frame) if key.endswith("_at_ms")] == []
