"""A §5C: o token é consumido, os atacantes ficam registrados e a partida entra
em Combate.

Três metades. O caminho aceito -- e o que ele **não** faz, que é tão contrato
quanto o que faz: nenhuma carta se move, nenhuma energia é gasta, nenhum Nexus
muda. As sete recusas, cada uma nomeando o valor ofensor e provando por
`match_snapshot` que o estado ficou idêntico. E a cascata, que é onde esta
feature podia dar errado sem ninguém notar: `submit_action` precisa devolver a
partida **parada em Combate**, e não em Fim de Rodada nem em Resolução de Pilha.

O teste central é `test_a_declaration_does_not_close_the_round`: com o oponente
tendo passado uma vez, uma declaração que esquecesse de zerar os passes deixaria
`_exit_action_phase` fechar a rodada por baixo do combate.
"""

import pytest

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.engine import (
    AttackerNotInBankError,
    AttackTokenAlreadyConsumedError,
    BankHasNoUnitsError,
    DeclareAttackAction,
    DuplicateAttackerError,
    NoAttackersSelectedError,
    NotTheTokenHolderError,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    StackIsNotEmptyError,
    submit_action,
)
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchPhase,
    PlayerState,
    STARTING_NEXUS,
    StackEntry,
)
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
    """Três unidades no banco do dono do token, uma no do defensor."""
    return fake_combat_board(
        catalog=catalog,
        bank_one=(DARK_AGE, MORTEM, POLAROID),
        bank_two=(KHRAS,),
    )


def declare(
    match: Match,
    *indexes: int,
    catalog: CardCatalog,
    source: RandomSource,
    actor_user_id: int = PLAYER_ONE,
) -> None:
    """Declara ataque com as unidades daquelas posições do banco do autor."""
    attacker = match.player(actor_user_id)

    submit_action(
        match,
        DeclareAttackAction(
            actor_user_id=actor_user_id,
            attacker_card_instance_ids=tuple(
                bank_card(attacker, index) for index in indexes
            ),
        ),
        catalog=catalog,
        randomness=source,
    )


# --- O caminho aceito --------------------------------------------------------


def test_part_of_the_bank_attacks(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.player(PLAYER_ONE)
    chosen = (bank_card(one, 0), bank_card(one, 1))

    declare(match, 0, 1, catalog=catalog, source=source)

    assert match.combat is not None
    assert match.combat.attacker_card_instance_ids == list(chosen)


def test_a_single_unit_can_attack(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 1, catalog=catalog, source=source)

    assert match.combat is not None
    assert len(match.combat.attacker_card_instance_ids) == 1


def test_the_whole_bank_can_attack(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 0, 1, 2, catalog=catalog, source=source)

    assert match.combat is not None
    assert len(match.combat.attacker_card_instance_ids) == 3


def test_the_declaration_order_is_the_one_asked_for(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.player(PLAYER_ONE)

    declare(match, 2, 0, catalog=catalog, source=source)

    assert match.combat is not None
    assert match.combat.attacker_card_instance_ids == [
        bank_card(one, 2),
        bank_card(one, 0),
    ]


def test_the_token_is_consumed(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 0, catalog=catalog, source=source)

    assert match.token_consumed is True


def test_a_declaration_starts_with_nobody_blocking(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 0, catalog=catalog, source=source)

    assert match.combat is not None
    assert match.combat.blocks == []


def test_a_declaration_moves_no_card_and_spends_no_energy(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """O que a ação **não** faz é tão contrato quanto o que ela faz."""
    before = [_zone_sizes(player) for player in match.players]
    energy_before = [player.energy_current for player in match.players]

    declare(match, 0, 1, catalog=catalog, source=source)

    assert [_zone_sizes(player) for player in match.players] == before
    assert [player.energy_current for player in match.players] == energy_before


def test_a_declaration_touches_no_nexus_and_no_damage(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 0, 1, catalog=catalog, source=source)

    assert [player.nexus for player in match.players] == [
        STARTING_NEXUS,
        STARTING_NEXUS,
    ]
    assert all(
        unit.damage_taken == 0 and unit.modifiers == []
        for player in match.players
        for unit in player.bank
    )


# --- A cascata ---------------------------------------------------------------


def test_the_match_stops_in_combat_waiting_for_the_defender(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """O único ponto do jogo em que `submit_action` devolve a partida fora da
    Fase de Ação sem ela ter acabado."""
    declare(match, 0, catalog=catalog, source=source)

    assert match.phase is MatchPhase.COMBAT


def test_the_priority_goes_to_the_defender(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    declare(match, 0, catalog=catalog, source=source)

    assert match.priority_user_id == PLAYER_TWO


def test_a_declaration_zeroes_the_pass_count(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    match.consecutive_passes = 1

    declare(match, 0, catalog=catalog, source=source)

    assert match.consecutive_passes == 0


def test_a_declaration_does_not_close_the_round(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Com o oponente tendo passado uma vez, uma declaração que esquecesse de
    zerar os passes deixaria a saída da §5 fechar a rodada por baixo do
    combate: dois passes consecutivos com a pilha vazia é Fim de Rodada."""
    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )
    match.priority_user_id = PLAYER_ONE

    declare(match, 0, catalog=catalog, source=source)

    assert match.consecutive_passes == 0
    assert match.phase is MatchPhase.COMBAT
    assert match.round_number == 1


# --- As sete recusas ---------------------------------------------------------


def test_a_player_without_the_token_is_refused_naming_the_holder(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    match.priority_user_id = PLAYER_TWO
    before = match_snapshot(match)

    with pytest.raises(NotTheTokenHolderError) as refusal:
        declare(match, 0, catalog=catalog, source=source, actor_user_id=PLAYER_TWO)

    assert refusal.value.token_holder_user_id == PLAYER_ONE
    assert match_snapshot(match) == before


def test_a_consumed_token_is_refused_naming_the_round(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    match.token_consumed = True
    before = match_snapshot(match)

    with pytest.raises(AttackTokenAlreadyConsumedError) as refusal:
        declare(match, 0, catalog=catalog, source=source)

    assert refusal.value.round_number == 1
    assert match_snapshot(match) == before


def test_a_full_stack_is_refused_naming_the_size(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.player(PLAYER_ONE)
    match.stack = [
        StackEntry(card=one.bank[0].card, caster_user_id=PLAYER_ONE),
    ]
    before = match_snapshot(match)

    with pytest.raises(StackIsNotEmptyError) as refusal:
        declare(match, 0, catalog=catalog, source=source)

    assert refusal.value.stack_size == 1
    assert match_snapshot(match) == before


def test_an_empty_bank_is_refused(catalog: CardCatalog, source: RandomSource) -> None:
    match = fake_combat_board(catalog=catalog, bank_one=(), bank_two=(KHRAS,))
    before = match_snapshot(match)

    with pytest.raises(BankHasNoUnitsError) as refusal:
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_ONE, attacker_card_instance_ids=()
            ),
            catalog=catalog,
            randomness=source,
        )

    assert refusal.value.user_id == PLAYER_ONE
    assert match_snapshot(match) == before


def test_an_empty_selection_is_refused_naming_the_bank_size(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Banco cheio e nada escolhido é jogada mal formada, não combate vazio."""
    before = match_snapshot(match)

    with pytest.raises(NoAttackersSelectedError) as refusal:
        declare(match, catalog=catalog, source=source)

    assert refusal.value.bank_size == 3
    assert match_snapshot(match) == before


def test_a_unit_of_the_opponent_is_refused_naming_the_unit(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    stranger = bank_card(match.player(PLAYER_TWO))
    before = match_snapshot(match)

    with pytest.raises(AttackerNotInBankError) as refusal:
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_ONE, attacker_card_instance_ids=(stranger,)
            ),
            catalog=catalog,
            randomness=source,
        )

    assert refusal.value.card_instance_id == stranger
    assert match_snapshot(match) == before


def test_a_unit_that_is_nowhere_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    before = match_snapshot(match)

    with pytest.raises(AttackerNotInBankError):
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_ONE,
                attacker_card_instance_ids=(CardInstanceId(9999),),
            ),
            catalog=catalog,
            randomness=source,
        )

    assert match_snapshot(match) == before


def test_the_same_unit_twice_is_refused_naming_the_unit(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    repeated = bank_card(match.player(PLAYER_ONE))
    before = match_snapshot(match)

    with pytest.raises(DuplicateAttackerError) as refusal:
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_ONE,
                attacker_card_instance_ids=(repeated, repeated),
            ),
            catalog=catalog,
            randomness=source,
        )

    assert refusal.value.card_instance_id == repeated
    assert match_snapshot(match) == before


# --- As guardas comuns -------------------------------------------------------


def test_declaring_without_priority_is_refused_before_the_token_is_looked_at(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """A ordem participante -> prioridade -> fase é contrato da feature 005, e
    vale para a ação nova como para as três antigas."""
    match.priority_user_id = PLAYER_TWO

    with pytest.raises(NotYourPriorityError):
        declare(match, 0, catalog=catalog, source=source)


def test_declaring_outside_the_action_phase_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    match.phase = MatchPhase.COMBAT

    with pytest.raises(PhaseForbidsActionError):
        declare(match, 0, catalog=catalog, source=source)


def test_declaring_twice_in_the_same_round_is_refused(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Um ataque por rodada (§12).

    A recusa é de **prioridade**, e não de fase: durante o combate a vez é do
    defensor, e a guarda 2 corre antes da 3. É a mesma recusa que faz do
    atacante um espectador (FR-022), e `test_blocker_pairing.py` a prova para
    as outras ações.

    Depois do combate o segundo ataque cai no token -- esse é
    `test_combat_cleanup.py`.
    """
    declare(match, 0, catalog=catalog, source=source)

    with pytest.raises(NotYourPriorityError):
        declare(match, 1, catalog=catalog, source=source, actor_user_id=PLAYER_ONE)


# --- A atomicidade -----------------------------------------------------------


def test_a_refusal_does_not_advance_the_match_counters(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """Os dois contadores são os que mais fácil se esquece, e `match_snapshot`
    os confere sem que nenhum teste precise lembrar deles."""
    before = match_snapshot(match)

    with pytest.raises(NoAttackersSelectedError):
        declare(match, catalog=catalog, source=source)

    assert match_snapshot(match)["next_card_instance_id"] == (
        before["next_card_instance_id"]
    )
    assert match_snapshot(match)["next_roll_ordinal"] == before["next_roll_ordinal"]


def test_a_refusal_leaves_no_combat_behind(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    with pytest.raises(AttackerNotInBankError):
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_ONE,
                attacker_card_instance_ids=(CardInstanceId(9999),),
            ),
            catalog=catalog,
            randomness=source,
        )

    assert match.combat is None
    assert match.phase is MatchPhase.ACTION
    assert match.token_consumed is False


def _zone_sizes(player: PlayerState) -> tuple[int, int, int, int]:
    return (
        len(player.deck),
        len(player.hand),
        len(player.bank),
        len(player.graveyard),
    )
