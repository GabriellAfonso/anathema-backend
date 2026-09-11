"""O que aconteceu numa mudança aceita, pela diferença entre antes e depois.

Cada teste roda o comando de verdade pelo motor sobre uma cópia, e compara a
lista de eventos com o que a jogada causou. O recorte por destinatário é o que
mais importa: a compra do oponente revela só a contagem, e o mulligan de
qualquer um revela só quantas cartas foram trocadas.
"""

from copy import deepcopy

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
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
from apps.game.match import Match, MatchEndReason
from apps.game.protocol import (
    ClientCommand,
    ForfeitCommand,
    MatchEvent,
    MulliganCommand,
    apply_command,
    describe_change,
)
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    SKILLET,
    SUMMONED_AX,
    bank_card,
    declare_combat,
    fake_combat_board,
    hand_card,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_started_match


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


def play(
    match: Match, command: ClientCommand, catalog: CardCatalog, recipient: int
) -> list[MatchEvent]:
    """Aplica o comando e descreve a mudança para o destinatário."""
    before = deepcopy(match)
    apply_command(match, command, catalog=catalog, randomness=ScriptedRandomSource())

    return describe_change(before, match, command, recipient_user_id=recipient)


def kinds(events: list[MatchEvent]) -> list[str]:
    return [event["kind"] for event in events]


# --- A jogada ----------------------------------------------------------------


def test_a_unit_played_names_the_card(catalog: CardCatalog) -> None:
    match = fake_combat_board(catalog=catalog, hand_one=(KHRAS,))
    card = hand_card(match.player(PLAYER_ONE), KHRAS)

    events = play(match, PlayUnitAction(PLAYER_ONE, card), catalog, PLAYER_TWO)

    assert events[0] == {
        "kind": "unit_played",
        "user_id": PLAYER_ONE,
        "card": {"card_instance_id": card, "card_id": KHRAS},
    }


def test_a_spell_cast_names_the_card_and_the_target(catalog: CardCatalog) -> None:
    match = fake_combat_board(
        catalog=catalog, hand_one=(SUMMONED_AX,), bank_two=(SKILLET,)
    )
    ax = hand_card(match.player(PLAYER_ONE), SUMMONED_AX)
    target = bank_card(match.player(PLAYER_TWO))

    events = play(match, CastSpellAction(PLAYER_ONE, ax, target), catalog, PLAYER_TWO)

    assert events[0] == {
        "kind": "spell_cast",
        "user_id": PLAYER_ONE,
        "card": {"card_instance_id": ax, "card_id": SUMMONED_AX},
        "target_card_instance_id": target,
    }
    assert {"kind": "unit_damaged", "card_instance_id": target, "amount": 3} in events


def test_a_spell_that_kills_reports_the_death(catalog: CardCatalog) -> None:
    match = fake_combat_board(
        catalog=catalog, hand_one=(SUMMONED_AX,), bank_two=(MORTEM,)
    )
    ax = hand_card(match.player(PLAYER_ONE), SUMMONED_AX)
    target = bank_card(match.player(PLAYER_TWO))

    events = play(match, CastSpellAction(PLAYER_ONE, ax, target), catalog, PLAYER_ONE)

    assert {
        "kind": "unit_died",
        "user_id": PLAYER_TWO,
        "card": {"card_instance_id": target, "card_id": MORTEM},
    } in events


def test_the_attack_declaration_steps(catalog: CardCatalog) -> None:
    match = fake_combat_board(catalog=catalog, bank_one=(DARK_AGE, MORTEM))
    one = match.player(PLAYER_ONE)
    first, second = bank_card(one, 0), bank_card(one, 1)

    sent = play(
        match, DeclareAttackAction(PLAYER_ONE, (first, second)), catalog, PLAYER_TWO
    )
    withdrawn = play(
        match, WithdrawAttackerAction(PLAYER_ONE, second), catalog, PLAYER_TWO
    )
    confirmed = play(match, ConfirmAttackAction(PLAYER_ONE), catalog, PLAYER_TWO)

    assert sent == [
        {
            "kind": "attackers_sent",
            "user_id": PLAYER_ONE,
            "attacker_card_instance_ids": [first, second],
        }
    ]
    assert withdrawn == [
        {
            "kind": "attacker_withdrawn",
            "user_id": PLAYER_ONE,
            "attacker_card_instance_id": second,
        }
    ]
    assert confirmed == [{"kind": "attack_confirmed", "user_id": PLAYER_ONE}]


def test_the_defense_window_steps(catalog: CardCatalog) -> None:
    match = fake_combat_board(
        catalog=catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,)
    )
    declare_combat(match, 0)
    attacker = bank_card(match.player(PLAYER_ONE))
    blocker = bank_card(match.player(PLAYER_TWO))

    assigned = play(
        match, AssignBlockerAction(PLAYER_TWO, blocker, attacker), catalog, PLAYER_ONE
    )
    removed = play(match, RemoveBlockerAction(PLAYER_TWO, blocker), catalog, PLAYER_ONE)

    assert kinds(assigned) == ["blocker_assigned"]
    assert removed == [
        {
            "kind": "blocker_removed",
            "user_id": PLAYER_TWO,
            "blocker_card_instance_id": blocker,
        }
    ]


def test_ending_the_window_reports_the_combat_damage(catalog: CardCatalog) -> None:
    """DARK AGE sem bloqueio: 3 de dano no Nexus do defensor."""
    match = fake_combat_board(
        catalog=catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,)
    )
    declare_combat(match, 0)

    events = play(match, EndDefenseWindowAction(PLAYER_TWO), catalog, PLAYER_ONE)

    assert events == [
        {"kind": "defense_ended", "user_id": PLAYER_TWO},
        {"kind": "nexus_changed", "user_id": PLAYER_TWO, "amount": -3},
    ]


def test_a_forfeit_reports_the_end_of_the_match(catalog: CardCatalog) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)

    events = play(match, ForfeitCommand(PLAYER_ONE), catalog, PLAYER_TWO)

    assert events == [
        {"kind": "forfeited", "user_id": PLAYER_ONE},
        {
            "kind": "match_finished",
            "defeated_user_id": PLAYER_ONE,
            "reason": MatchEndReason.FORFEIT,
        },
    ]


# --- O recorte por destinatário ----------------------------------------------


def test_the_mulligan_reveals_only_the_count(catalog: CardCatalog) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    swapped = tuple(card.card_instance_id for card in match.player(PLAYER_ONE).hand[:2])

    for_opponent = play(
        deepcopy(match), MulliganCommand(PLAYER_ONE, swapped), catalog, PLAYER_TWO
    )

    assert for_opponent[0] == {
        "kind": "mulligan_taken",
        "user_id": PLAYER_ONE,
        "swapped_count": 2,
    }
    assert for_opponent[1] == {
        "kind": "cards_drawn",
        "user_id": PLAYER_ONE,
        "count": 2,
        "cards": [],
    }


def test_the_player_sees_the_cards_they_drew(catalog: CardCatalog) -> None:
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    swapped = (match.player(PLAYER_ONE).hand[0].card_instance_id,)

    for_author = play(match, MulliganCommand(PLAYER_ONE, swapped), catalog, PLAYER_ONE)

    drawn = for_author[1]
    assert drawn["kind"] == "cards_drawn"
    assert drawn["count"] == 1
    assert [card["card_instance_id"] for card in drawn["cards"]] == [
        match.player(PLAYER_ONE).hand[-1].card_instance_id
    ]


def test_closing_the_setup_reports_round_one_and_every_draw(
    catalog: CardCatalog,
) -> None:
    """Sorteio, compensação e Upkeep: uma lista só, e do oponente só a
    contagem."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    play(match, MulliganCommand(PLAYER_ONE, ()), catalog, PLAYER_ONE)

    events = play(match, MulliganCommand(PLAYER_TWO, ()), catalog, PLAYER_ONE)

    assert kinds(events) == [
        "mulligan_taken",
        "round_started",
        "cards_drawn",
        "cards_drawn",
    ]
    mine, theirs = events[2], events[3]
    assert mine["kind"] == "cards_drawn" and theirs["kind"] == "cards_drawn"
    assert (mine["user_id"], len(mine["cards"])) == (PLAYER_ONE, mine["count"])
    assert (theirs["user_id"], theirs["cards"]) == (PLAYER_TWO, [])


def test_a_cascade_is_one_ordered_list(catalog: CardCatalog) -> None:
    """Dois passes: o passe, a rodada nova e as compras do Upkeep."""
    match = fake_started_match(PLAYER_ONE, PLAYER_TWO)
    play(match, MulliganCommand(PLAYER_ONE, ()), catalog, PLAYER_ONE)
    play(match, MulliganCommand(PLAYER_TWO, ()), catalog, PLAYER_ONE)
    first = match.priority_user_id
    assert first is not None
    play(match, PassAction(first), catalog, PLAYER_ONE)
    second = match.opponent_of(first).user_id

    events = play(match, PassAction(second), catalog, PLAYER_ONE)

    assert kinds(events) == ["passed", "round_started", "cards_drawn", "cards_drawn"]
