"""Os frames do socket de partida, montados para quem vai recebê-los.

O teste que carrega o arquivo é
`test_no_frame_carries_a_hidden_card_of_the_opponent`: ele serializa o frame
como sairia pelo socket e procura, no texto, cada identificador que estava na
mão ou no deck do oponente. Não é checagem de campo -- é a pergunta que um
cliente curioso faria ao tráfego.
"""

import json
from copy import deepcopy

from apps.game.cards import mvp_catalog
from apps.game.engine import PassAction
from apps.game.match import Match
from apps.game.protocol import (
    MulliganCommand,
    apply_command,
    match_start_payload,
    match_update_payload,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase, fake_started_match

PLAYER_ONE = 7
PLAYER_TWO = 9


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


def test_the_start_frame_carries_the_version_and_the_view() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    payload = match_start_payload(match, 4, PLAYER_ONE)

    assert payload["version"] == 4
    assert payload["view"]["you"]["profile"]["user_id"] == PLAYER_ONE


def test_the_view_says_whose_mulligan_is_in() -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    match.player(PLAYER_TWO).mulligan_taken = True

    view = match_start_payload(match, 1, PLAYER_ONE)["view"]

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

    for_one = match_update_payload(before, match, 7, PassAction(holder), PLAYER_ONE)
    for_two = match_update_payload(before, match, 7, PassAction(holder), PLAYER_TWO)

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
            frame = match_update_payload(before, match, 2, command, recipient)
            leaked = ids_in_frame(frame) & (
                hidden_ids(before, opponent) | hidden_ids(match, opponent)
            )

            assert leaked == set(), (author, recipient)
