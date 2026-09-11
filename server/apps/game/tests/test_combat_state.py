"""O estado de combate da §7: o que ele guarda e o que ele sabe responder.

Só perguntas. Atribuir e remover bloqueador é regra, e regra mora em
`engine/blocker_pairing.py` — aqui se prova o que o estado diz, não o que é
legal fazer com ele.

O teste que carrega este arquivo é
`test_a_combat_without_blockers_is_not_the_same_as_no_combat`: é ele que pega
um modelo em que a ausência de combate e o combate sem bloqueador nenhum
viraram o mesmo valor. Os dois são estados legais e diferentes, e confundi-los
deixaria a §7.2 sem como saber se a janela já abriu.
"""

import pytest

from apps.game.match import (
    BlockAssignment,
    CardInstanceId,
    CombatState,
    Match,
    MatchIsNotInCombatError,
    MatchPhase,
)
from apps.game.tests.fake_match_state import FAKE_MATCH_ID, fake_new_match

ATTACKER = CardInstanceId(3)
OTHER_ATTACKER = CardInstanceId(5)
BLOCKER = CardInstanceId(4)
STRANGER = CardInstanceId(99)


@pytest.fixture
def combat() -> CombatState:
    """Dois atacantes declarados, ninguém bloqueando ainda."""
    return CombatState(attacker_card_instance_ids=[ATTACKER, OTHER_ATTACKER])


@pytest.fixture
def blocked_combat(combat: CombatState) -> CombatState:
    """O mesmo, com o primeiro atacante coberto."""
    combat.blocks.append(
        BlockAssignment(
            blocker_card_instance_id=BLOCKER, attacker_card_instance_id=ATTACKER
        )
    )

    return combat


# --- A declaração ------------------------------------------------------------


def test_a_declared_unit_is_attacking(combat: CombatState) -> None:
    assert combat.is_attacking(ATTACKER)


def test_a_unit_outside_the_declaration_is_not_attacking(
    combat: CombatState,
) -> None:
    assert not combat.is_attacking(STRANGER)


def test_the_declaration_order_is_preserved(combat: CombatState) -> None:
    """A ordem é guardada (FR-018). Que ela não influencie o dano é afirmado
    em `test_combat_damage.py`, e não aqui."""
    assert combat.attacker_card_instance_ids == [ATTACKER, OTHER_ATTACKER]


def test_a_new_combat_has_no_blocks(combat: CombatState) -> None:
    assert combat.blocks == []


# --- O pareamento ------------------------------------------------------------


def test_blocker_of_an_unblocked_attacker_is_none(combat: CombatState) -> None:
    """`None` não é erro: atacante sem bloqueador passa direto (§7.3)."""
    assert combat.blocker_of(ATTACKER) is None


def test_blocker_of_finds_the_assigned_blocker(blocked_combat: CombatState) -> None:
    assert blocked_combat.blocker_of(ATTACKER) == BLOCKER


def test_blocker_of_does_not_answer_for_another_attacker(
    blocked_combat: CombatState,
) -> None:
    assert blocked_combat.blocker_of(OTHER_ATTACKER) is None


def test_attacker_blocked_by_an_unassigned_blocker_is_none(
    combat: CombatState,
) -> None:
    assert combat.attacker_blocked_by(BLOCKER) is None


def test_attacker_blocked_by_finds_the_covered_attacker(
    blocked_combat: CombatState,
) -> None:
    assert blocked_combat.attacker_blocked_by(BLOCKER) == ATTACKER


def test_the_two_questions_are_inverses(blocked_combat: CombatState) -> None:
    """O pareamento é 1 para 1, então ir e voltar dá o mesmo par."""
    attacker = blocked_combat.attacker_blocked_by(BLOCKER)

    assert attacker is not None
    assert blocked_combat.blocker_of(attacker) == BLOCKER


def test_a_block_names_both_sides_of_the_pair() -> None:
    block = BlockAssignment(
        blocker_card_instance_id=BLOCKER, attacker_card_instance_id=ATTACKER
    )

    assert (block.blocker_card_instance_id, block.attacker_card_instance_id) == (
        BLOCKER,
        ATTACKER,
    )


# --- A ausência --------------------------------------------------------------


def test_a_combat_without_blockers_is_not_the_same_as_no_combat(
    combat: CombatState,
) -> None:
    """Dois estados legais e diferentes: a janela aberta sem ninguém bloqueando,
    e nenhuma janela. Confundi-los deixaria a §7.2 sem como saber se o combate
    já começou."""
    match = fake_new_match()

    assert match.combat is None

    match.combat = combat

    assert match.combat is not None
    assert match.combat.blocks == []


def test_a_new_match_is_not_in_combat() -> None:
    assert fake_new_match().combat is None


# --- O estreitamento ---------------------------------------------------------


def test_ongoing_combat_returns_the_state(combat: CombatState) -> None:
    match = _match_in_combat(combat)

    assert match.ongoing_combat() is combat


def test_ongoing_combat_outside_combat_is_refused_naming_the_phase() -> None:
    match = fake_new_match()
    match.phase = MatchPhase.ACTION

    with pytest.raises(MatchIsNotInCombatError) as refusal:
        match.ongoing_combat()

    assert refusal.value.phase is MatchPhase.ACTION
    assert "'action'" in str(refusal.value)
    assert "'combat'" in str(refusal.value)


def test_the_refusal_names_the_match() -> None:
    match = fake_new_match()

    with pytest.raises(MatchIsNotInCombatError) as refusal:
        match.ongoing_combat()

    assert refusal.value.match_id == FAKE_MATCH_ID
    assert FAKE_MATCH_ID in str(refusal.value)


def _match_in_combat(combat: CombatState) -> Match:
    match = fake_new_match()

    match.combat = combat
    match.phase = MatchPhase.COMBAT

    return match
