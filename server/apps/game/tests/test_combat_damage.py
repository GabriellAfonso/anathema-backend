"""A §7.3: todo o dano de uma vez, e a §10 apurada uma vez só.

`resolve_combat_damage` é exercitada **direto**, sobre um combate montado, antes
de existir a ação que a dispara — um corte que a feature 006 já tinha feito
com a resolução de feitiço, e que existe para que um erro no cálculo apareça sem
a cascata no meio.

Ninguém morre nestes testes: este módulo acumula dano e altera Nexus, e a
varredura da §7.4 é de `combat_cleanup.py`. O que se afirma aqui é
`damage_taken`, não cemitério.

O teste que carrega o arquivo é `test_two_nexus_at_zero_in_one_calculation_tie`:
é ele que pega a escolha errada entre `change_nexus` e
`change_nexus_simultaneously`. Com a errada, o empate da §10 vira vitória do
segundo — e como `check_victory` é idempotente, a segunda apuração não corrige
nada.

Os números vêm das cartas reais: DARK AGE 3/2, KHRAS 2/4, SKILLET 4/5,
POLAROID 2/6, MORTEM 7/2.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, EffectDuration, mvp_catalog
from apps.game.engine import (
    change_nexus_simultaneously,
    unit_effective_attack,
)
from apps.game.engine.combat_damage import resolve_combat_damage
from apps.game.match import (
    AttackModifier,
    BankUnit,
    BlockAssignment,
    DamageImmunity,
    Match,
    MatchPhase,
    PlayerState,
    STARTING_NEXUS,
)
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
    unit_damage,
)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


def board(
    catalog: CardCatalog,
    *,
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (KHRAS,),
) -> Match:
    return fake_combat_board(catalog=catalog, bank_one=bank_one, bank_two=bank_two)


def pair_up(match: Match, attacker_index: int, blocker_index: int) -> None:
    """Atribui um bloqueador direto no estado, sem passar pela ação da §7.2."""
    combat = match.ongoing_combat()
    combat.blocks.append(
        BlockAssignment(
            blocker_card_instance_id=bank_card(match.player(PLAYER_TWO), blocker_index),
            attacker_card_instance_id=bank_card(
                match.player(PLAYER_ONE), attacker_index
            ),
        )
    )


def unit_at(player: PlayerState, index: int) -> BankUnit:
    return player.bank[index]


# --- O ataque efetivo --------------------------------------------------------


def test_the_template_attack_is_the_default(catalog: CardCatalog) -> None:
    match = board(catalog)

    assert unit_effective_attack(unit_at(match.players[0], 0), catalog=catalog) == 3


def test_an_attack_bonus_is_added(catalog: CardCatalog) -> None:
    """SACRIFICIAL FIRE soma 3, e é a §7.3 que finalmente lê o modificador."""
    match = board(catalog)
    unit = unit_at(match.players[0], 0)
    unit.modifiers.append(AttackModifier(amount=3, duration=EffectDuration.PERMANENT))

    assert unit_effective_attack(unit, catalog=catalog) == 6


def test_a_negative_bonus_floors_at_zero(catalog: CardCatalog) -> None:
    """Sem o piso, o dano negativo curaria a unidade e somaria Nexus. Nenhuma
    das duas é regra da §7."""
    match = board(catalog)
    unit = unit_at(match.players[0], 0)
    unit.modifiers.append(AttackModifier(amount=-10, duration=EffectDuration.PERMANENT))

    assert unit_effective_attack(unit, catalog=catalog) == 0


def test_accumulated_damage_does_not_reduce_the_attack(
    catalog: CardCatalog,
) -> None:
    """Uma unidade machucada bate igual."""
    match = board(catalog)
    unit = unit_at(match.players[0], 0)
    unit.damage_taken = 1

    assert unit_effective_attack(unit, catalog=catalog) == 3


# --- A apuração única --------------------------------------------------------


def test_simultaneous_change_settles_after_every_nexus(
    catalog: CardCatalog,
) -> None:
    match = board(catalog)
    one, two = match.players

    change_nexus_simultaneously(match, ((one, -5), (two, -5)))

    assert (one.nexus, two.nexus) == (15, 15)
    assert match.is_over is False


def test_simultaneous_change_settles_only_once(catalog: CardCatalog) -> None:
    """Os dois a zero no mesmo cálculo é empate (§10), e não vitória do
    segundo."""
    match = board(catalog)
    one, two = match.players

    change_nexus_simultaneously(match, ((one, -STARTING_NEXUS), (two, -STARTING_NEXUS)))

    assert match.outcome is not None
    assert set(match.outcome.defeated_user_ids) == {PLAYER_ONE, PLAYER_TWO}


def test_a_single_defeat_still_names_one_player(catalog: CardCatalog) -> None:
    match = board(catalog)
    one, two = match.players

    change_nexus_simultaneously(match, ((one, 0), (two, -STARTING_NEXUS)))

    assert match.outcome is not None
    assert match.outcome.defeated_user_ids == (PLAYER_TWO,)


# --- Os pares ----------------------------------------------------------------


def test_a_blocked_pair_trades_damage(catalog: CardCatalog) -> None:
    """DARK AGE 3/2 contra KHRAS 2/4: cada um leva o ataque do outro."""
    match = board(catalog)
    declare_combat(match, 0)
    pair_up(match, 0, 0)

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[0], 0).damage_taken == 2
    assert unit_at(match.players[1], 0).damage_taken == 3


def test_a_blocked_pair_sends_nothing_to_the_nexus(catalog: CardCatalog) -> None:
    match = board(catalog)
    declare_combat(match, 0)
    pair_up(match, 0, 0)

    resolve_combat_damage(match, catalog=catalog)

    assert [player.nexus for player in match.players] == [
        STARTING_NEXUS,
        STARTING_NEXUS,
    ]


def test_an_unblocked_attacker_hits_the_defender_nexus(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(MORTEM,))
    declare_combat(match, 0)

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[1].nexus == STARTING_NEXUS - 7


def test_the_attacker_nexus_never_takes_combat_damage(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(MORTEM,))
    declare_combat(match, 0)

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[0].nexus == STARTING_NEXUS


def test_both_sides_of_a_mutual_kill_take_their_damage(
    catalog: CardCatalog,
) -> None:
    """DARK AGE 3/2 contra MORTEM 7/2: os dois alcançam a vida do outro. A
    remoção é da §7.4, e acontece em `combat_cleanup`."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(MORTEM,))
    declare_combat(match, 0)
    pair_up(match, 0, 0)

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[0], 0).damage_taken == 7
    assert unit_at(match.players[1], 0).damage_taken == 3


def test_three_unblocked_attackers_sum_on_the_nexus(catalog: CardCatalog) -> None:
    """3 + 7 + 2, e a §10 apurada uma vez só."""
    match = board(catalog, bank_one=(DARK_AGE, MORTEM, POLAROID))
    declare_combat(match, 0, 1, 2)

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[1].nexus == STARTING_NEXUS - 12


def test_the_declaration_order_does_not_change_the_result(
    catalog: CardCatalog,
) -> None:
    """A ordem é preservada e não é usada: o dano é simultâneo."""
    forward = board(catalog, bank_one=(DARK_AGE, MORTEM))
    backward = board(catalog, bank_one=(DARK_AGE, MORTEM))

    declare_combat(forward, 0, 1)
    declare_combat(backward, 1, 0)

    resolve_combat_damage(forward, catalog=catalog)
    resolve_combat_damage(backward, catalog=catalog)

    assert forward.players[1].nexus == backward.players[1].nexus


# --- Revalidação por identificador -------------------------------------------


def test_an_attacker_off_the_battlefield_deals_no_damage(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(MORTEM,))
    declare_combat(match, 0)
    match.players[0].bank = []

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[1].nexus == STARTING_NEXUS


def test_an_orphan_blocker_comes_back_untouched(catalog: CardCatalog) -> None:
    """O atacante morreu por feitiço antes da resolução: o bloqueador não troca
    dano com ninguém e volta ao banco intacto (§7.3)."""
    match = board(catalog, bank_one=(MORTEM,), bank_two=(SKILLET,))
    declare_combat(match, 0)
    pair_up(match, 0, 0)
    match.players[0].bank = []

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[1], 0).damage_taken == 0
    assert match.players[1].nexus == STARTING_NEXUS


def test_a_blocker_off_the_battlefield_leaves_the_attacker_blocked(
    catalog: CardCatalog,
) -> None:
    """Inalcançável com as cinco cartas do MVP, e o código precisa de um braço:
    estar bloqueado é propriedade da declaração, então nada chega ao Nexus."""
    match = board(catalog, bank_one=(MORTEM,), bank_two=(SKILLET,))
    declare_combat(match, 0)
    pair_up(match, 0, 0)
    match.players[1].bank = []

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[0], 0).damage_taken == 0
    assert match.players[1].nexus == STARTING_NEXUS


# --- Imunidade e bônus -------------------------------------------------------


def test_an_immune_attacker_attacks_and_takes_nothing(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(KHRAS,))
    declare_combat(match, 0)
    pair_up(match, 0, 0)
    unit_at(match.players[0], 0).modifiers.append(
        DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND)
    )

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[0], 0).damage_taken == 0
    assert unit_at(match.players[1], 0).damage_taken == 3


def test_an_immune_blocker_takes_nothing_and_still_hits_back(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(KHRAS,))
    declare_combat(match, 0)
    pair_up(match, 0, 0)
    unit_at(match.players[1], 0).modifiers.append(
        DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND)
    )

    resolve_combat_damage(match, catalog=catalog)

    assert unit_at(match.players[1], 0).damage_taken == 0
    assert unit_at(match.players[0], 0).damage_taken == 2


def test_an_attack_bonus_reaches_the_nexus(catalog: CardCatalog) -> None:
    match = board(catalog, bank_one=(DARK_AGE,))
    declare_combat(match, 0)
    unit_at(match.players[0], 0).modifiers.append(
        AttackModifier(amount=3, duration=EffectDuration.PERMANENT)
    )

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[1].nexus == STARTING_NEXUS - 6


# --- O empate ----------------------------------------------------------------


def test_two_nexus_at_zero_in_one_calculation_tie(catalog: CardCatalog) -> None:
    """Não é alcançável jogando: nenhuma das cinco cartas do MVP subtrai Nexus
    do oponente, e o dano de combate só chega ao Nexus do defensor. O estado é
    montado, e a garantia é estrutural -- uma apuração, depois das duas
    alterações.

    Com `change_nexus` no lugar de `change_nexus_simultaneously`, este teste
    devolve um derrotado só.
    """
    match = board(catalog, bank_one=(MORTEM,))
    declare_combat(match, 0)
    match.players[0].nexus = 0
    match.players[1].nexus = 7

    resolve_combat_damage(match, catalog=catalog)

    assert match.outcome is not None
    assert set(match.outcome.defeated_user_ids) == {PLAYER_ONE, PLAYER_TWO}
    assert match.phase is MatchPhase.FINISHED


def test_the_defender_alone_loses_when_only_their_nexus_reaches_zero(
    catalog: CardCatalog,
) -> None:
    match = board(catalog, bank_one=(MORTEM,))
    declare_combat(match, 0)
    match.players[1].nexus = 7

    resolve_combat_damage(match, catalog=catalog)

    assert match.outcome is not None
    assert match.outcome.defeated_user_ids == (PLAYER_TWO,)


def test_a_nexus_at_exactly_zero_is_a_defeat(catalog: CardCatalog) -> None:
    match = board(catalog, bank_one=(POLAROID,))
    declare_combat(match, 0)
    match.players[1].nexus = 2

    resolve_combat_damage(match, catalog=catalog)

    assert match.players[1].nexus == 0
    assert match.is_over
