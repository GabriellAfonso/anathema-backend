"""As recusas de jogar feitiço, iguais na Fase de Ação e na janela do defensor.

Jogar feitiço é uma ação só nas duas fases (Fluxo de Partida §5B e §7.2), e as
guardas são as mesmas, na mesma ordem. Por isso quase todo teste daqui roda
**duas vezes**, pela fixture `phase`: uma com a partida na Fase de Ação e quem
lança é o dono do token, outra com o combate aberto e quem lança é o defensor.
Uma recusa que só valesse numa das fases seria o primeiro sinal de dois caminhos
de lançamento, que é o que a feature 008 apagou.

Toda recusa nomeia o valor ofensor e prova, por `match_snapshot`, que a partida
ficou idêntica. A ordem das guardas é contrato: um autor que falha em duas
recebe a recusa da primeira, sempre.

Custos do MVP: SOMEONE'S SHIELD 2, LIFE POTION 4, SUMMONED AX 5.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, TargetKind, mvp_catalog
from apps.game.engine import (
    CardIsNotASpellError,
    CardNotInHandError,
    CastSpellAction,
    NotEnoughEnergyError,
    NotYourPriorityError,
    PhaseForbidsActionError,
    SpellNeedsTargetError,
    SpellTakesNoTargetError,
    SpellTargetNotOnBattlefieldError,
    WrongSpellTargetSideError,
    submit_action,
)
from apps.game.match import CardInstanceId, Match, MatchPhase, PlayerState
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    declare_combat,
    fake_combat_board,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    LIFE_POTION,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    TOUGH_UNIT,
    bank_card,
    fake_spell_board,
    hand_card,
)
from apps.game.tests.match_snapshot import match_snapshot

AX_COST = 5
MISSING = CardInstanceId(999)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


@pytest.fixture(params=[MatchPhase.ACTION, MatchPhase.COMBAT])
def phase(request: pytest.FixtureRequest) -> MatchPhase:
    """As duas fases em que jogar feitiço é legal."""
    selected: MatchPhase = request.param
    return selected


def board(catalog: CardCatalog, phase: MatchPhase, *hand: CardId) -> Match:
    """Quem tem a vez segura `hand`, e cada lado tem uma unidade no banco.

    Na Fase de Ação quem lança é o primeiro jogador; no Combate é o defensor,
    com o ataque declarado pelo atalho de estado de `fake_combat_board`.
    """
    if phase is MatchPhase.ACTION:
        return fake_spell_board(catalog=catalog, hand_one=hand)

    match = fake_combat_board(
        catalog=catalog, hand_two=hand, bank_one=(DARK_AGE,), bank_two=(KHRAS,)
    )
    declare_combat(match, 0)

    return match


def caster(match: Match) -> PlayerState:
    """Quem tem a vez, nas duas fases."""
    assert match.priority_user_id is not None
    return match.player(match.priority_user_id)


def opponent(match: Match) -> PlayerState:
    return match.opponent_of(caster(match).user_id)


def cast(
    match: Match,
    catalog: CardCatalog,
    source: RandomSource,
    action: CastSpellAction,
) -> None:
    """Toda jogada entra pela porta única do motor, nunca por `cast_spell`."""
    submit_action(match, action, catalog=catalog, randomness=source)


# --------------------------------------------------------------------------
# O alvo
# --------------------------------------------------------------------------


def test_an_untargeted_spell_refuses_a_target(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    match = board(catalog, phase, LIFE_POTION)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(SpellTakesNoTargetError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, LIFE_POTION), bank_card(me)),
        )

    assert "takes no target" in str(refusal.value)
    assert match_snapshot(match) == before


def test_a_targeted_spell_refuses_a_missing_target(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    match = board(catalog, phase, SOMEONES_SHIELD)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(SpellNeedsTargetError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, SOMEONES_SHIELD)),
        )

    assert refusal.value.expected is TargetKind.ALLIED_UNIT
    assert match_snapshot(match) == before


def test_an_allied_spell_refuses_an_enemy_unit(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    """ "Aliado" é relativo a quem lança, e quem lança muda de uma fase para a
    outra."""
    match = board(catalog, phase, SOMEONES_SHIELD)
    me, them = caster(match), opponent(match)
    before = match_snapshot(match)

    with pytest.raises(WrongSpellTargetSideError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                me.user_id, hand_card(me, SOMEONES_SHIELD), bank_card(them)
            ),
        )

    assert refusal.value.expected is TargetKind.ALLIED_UNIT
    assert refusal.value.owner_user_id == them.user_id
    assert match_snapshot(match) == before


def test_an_enemy_spell_refuses_an_allied_unit(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    match = board(catalog, phase, SUMMONED_AX)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(WrongSpellTargetSideError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, SUMMONED_AX), bank_card(me)),
        )

    assert refusal.value.expected is TargetKind.ENEMY_UNIT
    assert match_snapshot(match) == before


def test_a_target_that_is_not_on_the_battlefield_is_refused(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    """Sempre recusa: não existe intervalo entre validar o alvo e aplicar o
    efeito, então não existe alvo que some no meio."""
    match = board(catalog, phase, SOMEONES_SHIELD)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(SpellTargetNotOnBattlefieldError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, SOMEONES_SHIELD), MISSING),
        )

    assert refusal.value.target_card_instance_id == MISSING
    assert match_snapshot(match) == before


def test_a_card_in_hand_is_not_a_valid_target(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    """Só unidade em banco é alvo."""
    match = board(catalog, phase, SOMEONES_SHIELD, LIFE_POTION)
    me = caster(match)

    with pytest.raises(SpellTargetNotOnBattlefieldError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                me.user_id,
                hand_card(me, SOMEONES_SHIELD),
                hand_card(me, LIFE_POTION),
            ),
        )


# --------------------------------------------------------------------------
# A carta e a energia
# --------------------------------------------------------------------------


def test_not_enough_energy_is_refused(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    match = board(catalog, phase, SUMMONED_AX)
    me, them = caster(match), opponent(match)
    me.energy_current = AX_COST - 1
    before = match_snapshot(match)

    with pytest.raises(NotEnoughEnergyError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, SUMMONED_AX), bank_card(them)),
        )

    assert (refusal.value.cost, refusal.value.available) == (AX_COST, AX_COST - 1)
    assert match_snapshot(match) == before


def test_a_card_not_in_hand_is_refused(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    match = board(catalog, phase, SOMEONES_SHIELD)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(CardNotInHandError) as refusal:
        cast(
            match, catalog, source, CastSpellAction(me.user_id, MISSING, bank_card(me))
        )

    assert refusal.value.card_instance_id == MISSING
    assert match_snapshot(match) == before


def test_a_unit_card_in_the_spell_action_is_refused(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    """Simétrica da recusa que a §5A já dá a uma carta de feitiço."""
    match = board(catalog, phase, TOUGH_UNIT)
    me = caster(match)
    before = match_snapshot(match)

    with pytest.raises(CardIsNotASpellError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, TOUGH_UNIT), bank_card(me)),
        )

    assert "expected a spell" in str(refusal.value)
    assert match_snapshot(match) == before


def test_the_card_of_the_opponent_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A mão consultada é sempre a do autor da ação."""
    match = fake_spell_board(catalog=catalog)
    one, two = match.players

    with pytest.raises(CardNotInHandError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(two, SUMMONED_AX), bank_card(one)),
        )


# --------------------------------------------------------------------------
# As guardas comuns, antes das do feitiço
# --------------------------------------------------------------------------


def test_a_player_without_priority_is_refused_first(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem prioridade **e** com alvo errado **e** sem energia: vence a
    prioridade. As guardas comuns vêm antes da regra específica."""
    match = fake_spell_board(catalog=catalog)
    two = match.players[1]
    two.energy_current = 0
    before = match_snapshot(match)

    with pytest.raises(NotYourPriorityError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(two.user_id, hand_card(two, SUMMONED_AX), MISSING),
        )

    assert match_snapshot(match) == before


def test_the_attacker_cannot_cast_in_the_window(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O atacante é espectador da §7.2 pela guarda de prioridade que já existe,
    e não por uma guarda de feitiço."""
    match = fake_combat_board(catalog=catalog, hand_one=(SUMMONED_AX,))
    declare_combat(match, 0)
    one, two = match.players
    before = match_snapshot(match)

    with pytest.raises(NotYourPriorityError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
        )

    assert match_snapshot(match) == before


def test_a_phase_that_forbids_the_action_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_spell_board(catalog=catalog)
    one = match.players[0]
    match.phase = MatchPhase.MULLIGAN
    before = match_snapshot(match)

    with pytest.raises(PhaseForbidsActionError) as refusal:
        cast(
            match,
            catalog,
            source,
            CastSpellAction(
                one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)
            ),
        )

    assert refusal.value.phase is MatchPhase.MULLIGAN
    assert match_snapshot(match) == before


def test_a_refusal_never_advances_the_match_counters(
    catalog: CardCatalog, source: RandomSource, phase: MatchPhase
) -> None:
    """Nem identidade de carta nem sorteio: jogar feitiço não cunha nem sorteia
    nada."""
    match = board(catalog, phase, SOMEONES_SHIELD)
    me = caster(match)
    before = (match.next_card_instance_id, match.next_roll_ordinal)

    with pytest.raises(SpellNeedsTargetError):
        cast(
            match,
            catalog,
            source,
            CastSpellAction(me.user_id, hand_card(me, SOMEONES_SHIELD)),
        )

    assert (match.next_card_instance_id, match.next_roll_ordinal) == before
