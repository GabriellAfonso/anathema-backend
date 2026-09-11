"""A janela do defensor da §7.2: bloquear, desbloquear, e a prioridade que não
sai dele.

O teste central deste arquivo é
`test_the_priority_never_leaves_the_defender_across_four_actions`: é ele que
pega uma troca de prioridade que sobreviveu ao combate. Com a troca, a segunda
ação do defensor já seria recusada, e a janela livre da §7.2 viraria uma ação
só — o oposto da regra.

O segundo mais importante é `test_the_action_phase_still_alternates`: a exceção
da janela não pode vazar. Ela é propriedade da ação, e as três ações da §5 que
gastam a vez declaram que a devolvem — o feitiço, que não gasta, declara que
fica, e isso é afirmado em `test_cast_spell.py`.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import (
    AssignBlockerAction,
    AttackerAlreadyBlockedError,
    BlockerAlreadyBlockingError,
    BlockerNotAssignedError,
    BlockerNotInBankError,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    PassAction,
    PhaseForbidsActionError,
    PlayUnitAction,
    NotYourPriorityError,
    RemoveBlockerAction,
    UnitIsNotAttackingError,
    WithdrawAttackerAction,
    submit_action,
)
from apps.game.match import CardInstanceId, Match, MatchPhase
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    POLAROID,
    SKILLET,
    bank_card,
    declare_combat,
    fake_combat_board,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.match_snapshot import match_snapshot


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture
def match(catalog: CardCatalog) -> Match:
    """Combate já declarado: dois atacantes, dois defensores disponíveis."""
    board = fake_combat_board(
        catalog=catalog,
        bank_one=(DARK_AGE, MORTEM),
        bank_two=(KHRAS, SKILLET),
    )

    declare_combat(board, 0, 1)

    return board


def block(
    match: Match,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    blocker: CardInstanceId,
    attacker: CardInstanceId,
    actor_user_id: int = PLAYER_TWO,
) -> None:
    submit_action(
        match,
        AssignBlockerAction(
            actor_user_id=actor_user_id,
            blocker_card_instance_id=blocker,
            attacker_card_instance_id=attacker,
        ),
        catalog=catalog,
        randomness=source,
    )


def unblock(
    match: Match,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    blocker: CardInstanceId,
    actor_user_id: int = PLAYER_TWO,
) -> None:
    submit_action(
        match,
        RemoveBlockerAction(
            actor_user_id=actor_user_id, blocker_card_instance_id=blocker
        ),
        catalog=catalog,
        randomness=source,
    )


def attackers(match: Match) -> tuple[CardInstanceId, CardInstanceId]:
    one = match.player(PLAYER_ONE)

    return bank_card(one, 0), bank_card(one, 1)


def blockers(match: Match) -> tuple[CardInstanceId, CardInstanceId]:
    two = match.player(PLAYER_TWO)

    return bank_card(two, 0), bank_card(two, 1)


# --- Atribuir e remover ------------------------------------------------------


def test_a_blocker_covers_the_attacker(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )

    assert match.ongoing_combat().blocker_of(first_attacker) == first_blocker


def test_a_second_blocker_covers_a_second_attacker(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Não existe limite de ações na janela."""
    first_attacker, second_attacker = attackers(match)
    first_blocker, second_blocker = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    block(
        match,
        catalog=catalog,
        source=source,
        blocker=second_blocker,
        attacker=second_attacker,
    )

    assert len(match.ongoing_combat().blocks) == 2


def test_removing_frees_both_units(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    unblock(match, catalog=catalog, source=source, blocker=first_blocker)

    combat = match.ongoing_combat()

    assert combat.blocks == []
    assert combat.blocker_of(first_attacker) is None
    assert combat.attacker_blocked_by(first_blocker) is None


def test_a_removed_blocker_can_cover_another_attacker(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, second_attacker = attackers(match)
    first_blocker, _ = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    unblock(match, catalog=catalog, source=source, blocker=first_blocker)
    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=second_attacker,
    )

    assert match.ongoing_combat().blocker_of(second_attacker) == first_blocker


def test_blocking_spends_no_energy_and_moves_no_card(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)
    before = match_snapshot(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )

    after = match_snapshot(match)

    assert after["players"] == before["players"]
    assert after["combat"] != before["combat"]


# --- A prioridade que não sai -------------------------------------------------


def test_the_priority_never_leaves_the_defender_across_four_actions(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Bloquear, bloquear, remover e reatribuir — quatro ações seguidas, e a
    vez continua sendo do defensor nas quatro (SC-003)."""
    first_attacker, second_attacker = attackers(match)
    first_blocker, second_blocker = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    _still_the_defenders_turn(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=second_blocker,
        attacker=second_attacker,
    )
    _still_the_defenders_turn(match)

    unblock(match, catalog=catalog, source=source, blocker=first_blocker)
    _still_the_defenders_turn(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    _still_the_defenders_turn(match)

    assert match.ongoing_combat().blocker_of(first_attacker) == first_blocker
    assert match.ongoing_combat().blocker_of(second_attacker) == second_blocker


def _still_the_defenders_turn(match: Match) -> None:
    """A janela não devolve a vez e não sai do Combate."""
    assert match.priority_user_id == PLAYER_TWO
    assert match.phase is MatchPhase.COMBAT


def test_every_action_phase_arm_gives_the_turn_back() -> None:
    """Ficar com a vez é propriedade da ação, e as ações que gastam a vez
    declaram que a devolvem: jogar unidade, passar e **Atacar**. É o que impede
    a exceção de vazar."""
    assert not PlayUnitAction.keeps_priority
    assert not PassAction.keeps_priority
    assert not ConfirmAttackAction.keeps_priority


def test_every_declaration_arm_keeps_the_turn() -> None:
    """A declaração é janela do atacante (§7.1): mandar e puxar não entregam a
    vez."""
    assert DeclareAttackAction.keeps_priority
    assert WithdrawAttackerAction.keeps_priority


def test_every_defense_window_arm_keeps_the_turn() -> None:
    assert AssignBlockerAction.keeps_priority
    assert RemoveBlockerAction.keeps_priority


# --- As cinco recusas --------------------------------------------------------


def test_a_blocker_already_blocking_is_refused_naming_the_unit(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, second_attacker = attackers(match)
    first_blocker, _ = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    before = match_snapshot(match)

    with pytest.raises(BlockerAlreadyBlockingError) as refusal:
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=first_blocker,
            attacker=second_attacker,
        )

    assert refusal.value.blocker_card_instance_id == first_blocker
    assert match_snapshot(match) == before


def test_an_attacker_already_blocked_is_refused_naming_the_attacker(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_attacker, _ = attackers(match)
    first_blocker, second_blocker = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )
    before = match_snapshot(match)

    with pytest.raises(AttackerAlreadyBlockedError) as refusal:
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=second_blocker,
            attacker=first_attacker,
        )

    assert refusal.value.attacker_card_instance_id == first_attacker
    assert match_snapshot(match) == before


def test_blocking_with_a_unit_outside_the_bank_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A unidade do atacante não está no banco de quem bloqueia."""
    first_attacker, second_attacker = attackers(match)
    before = match_snapshot(match)

    with pytest.raises(BlockerNotInBankError) as refusal:
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=second_attacker,
            attacker=first_attacker,
        )

    assert refusal.value.card_instance_id == second_attacker
    assert match_snapshot(match) == before


def test_pointing_at_a_unit_that_is_not_attacking_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_blocker, second_blocker = blockers(match)
    before = match_snapshot(match)

    with pytest.raises(UnitIsNotAttackingError) as refusal:
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=first_blocker,
            attacker=second_blocker,
        )

    assert refusal.value.card_instance_id == second_blocker
    assert match_snapshot(match) == before


def test_pointing_at_an_attacker_that_already_died_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Declarado mas fora de campo: a guarda pergunta as duas coisas."""
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)
    one = match.player(PLAYER_ONE)
    one.bank = [
        unit for unit in one.bank if unit.card.card_instance_id != first_attacker
    ]

    with pytest.raises(UnitIsNotAttackingError):
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=first_blocker,
            attacker=first_attacker,
        )


def test_removing_an_unassigned_blocker_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    first_blocker, _ = blockers(match)
    before = match_snapshot(match)

    with pytest.raises(BlockerNotAssignedError) as refusal:
        unblock(match, catalog=catalog, source=source, blocker=first_blocker)

    assert refusal.value.card_instance_id == first_blocker
    assert match_snapshot(match) == before


# --- O atacante é espectador -------------------------------------------------


def test_the_attacker_cannot_block(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Recusa de **prioridade**, citando de quem é a vez. É assim que a §7.1
    diz "é espectador", e nenhuma guarda nova foi escrita para isso."""
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)

    with pytest.raises(NotYourPriorityError) as refusal:
        block(
            match,
            catalog=catalog,
            source=source,
            blocker=first_blocker,
            attacker=first_attacker,
            actor_user_id=PLAYER_ONE,
        )

    assert refusal.value.priority_user_id == PLAYER_TWO


def test_the_attacker_cannot_pass_play_or_cast_during_the_combat(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    forbidden = (
        PassAction(actor_user_id=PLAYER_ONE),
        PlayUnitAction(actor_user_id=PLAYER_ONE, card_instance_id=CardInstanceId(1)),
        CastSpellAction(actor_user_id=PLAYER_ONE, card_instance_id=CardInstanceId(1)),
        DeclareAttackAction(
            actor_user_id=PLAYER_ONE,
            attacker_card_instance_ids=(CardInstanceId(1),),
        ),
    )

    for action in forbidden:
        with pytest.raises(NotYourPriorityError):
            submit_action(match, action, catalog=catalog, randomness=source)


def test_the_defender_cannot_use_the_action_phase_actions(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Recusa de **fase**: `{ACTION}` não contém `COMBAT`.

    Jogar feitiço não está aqui: desde a feature 008 ele é legal nas duas
    fases, e as recusas dele no combate estão em `test_cast_spell_refusals.py`.
    """
    forbidden = (
        PassAction(actor_user_id=PLAYER_TWO),
        PlayUnitAction(actor_user_id=PLAYER_TWO, card_instance_id=CardInstanceId(1)),
    )

    for action in forbidden:
        with pytest.raises(PhaseForbidsActionError):
            submit_action(match, action, catalog=catalog, randomness=source)


def test_blocking_outside_the_combat_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O outro lado: as ações da janela não são legais na Fase de Ação."""
    board = fake_combat_board(catalog=catalog)

    with pytest.raises(PhaseForbidsActionError):
        block(
            match=board,
            catalog=catalog,
            source=source,
            blocker=CardInstanceId(1),
            attacker=CardInstanceId(2),
            actor_user_id=PLAYER_ONE,
        )


# --- A cascata ---------------------------------------------------------------


def test_the_combat_does_not_end_by_itself(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Nenhuma ação da janela devolve a partida à Fase de Ação: encerrar é
    explícito."""
    first_attacker, _ = attackers(match)
    first_blocker, _ = blockers(match)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=first_blocker,
        attacker=first_attacker,
    )

    assert match.phase is MatchPhase.COMBAT
    assert match.combat is not None
    assert match.round_number == 1
