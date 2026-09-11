"""A §7.2: o feitiço do defensor dentro da janela, e o que ele muda no combate.

É a mesma ação da Fase de Ação — `CastSpellAction` —, e o que ela faz em
qualquer fase está em `test_cast_spell.py`. Aqui fica o que só existe com o
combate aberto: a vez que continua com o defensor enquanto ele bloqueia e
conjura, o bloqueador que um feitiço salva, o atacante que um feitiço mata antes
do dano, e a partida que acaba dentro da janela.

Dois testes daqui usam SACRIFICIAL FIRE jogado pelo defensor, que a segunda
correção da nota (2026-09-11, §14) proíbe, e foram trazidos da feature 007
**sem mudança de afirmação**. A regra do FIRE os reescreve. O `return` que eles cobrem em `combat_cleanup._leave_combat` continua
existindo, e a desistência da §10 vai precisar dele.

Custos do MVP: SOMEONE'S SHIELD 2, MAGIC BARRIER 3, LIFE POTION 4,
SUMMONED AX 5.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, mvp_catalog
from apps.game.engine import (
    AssignBlockerAction,
    CastSpellAction,
    EndDefenseWindowAction,
    MatchIsOverError,
    submit_action,
)
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchPhase,
    STARTING_NEXUS,
    match_from_document,
    to_match_document,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_combat_board import (
    DARK_AGE,
    KHRAS,
    LIFE_POTION,
    MAGIC_BARRIER,
    MORTEM,
    PLAYER_ONE,
    PLAYER_TWO,
    POLAROID,
    SACRIFICIAL_FIRE,
    SKILLET,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    bank_card,
    declare_combat,
    fake_combat_board,
    hand_card,
    in_graveyard,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource

FIRE_NEXUS_COST = 8
AX_COST = 5


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def board(
    catalog: CardCatalog,
    *,
    hand_two: tuple[CardId, ...] = (SUMMONED_AX,),
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (SKILLET,),
) -> Match:
    """Combate já declarado com todo o banco do atacante."""
    match = fake_combat_board(
        catalog=catalog, hand_two=hand_two, bank_one=bank_one, bank_two=bank_two
    )

    declare_combat(match, *range(len(bank_one)))

    return match


def cast(
    match: Match,
    card_id: CardId,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    target: CardInstanceId | None = None,
) -> None:
    """O defensor joga a carta, pela mesma ação de qualquer outra fase."""
    submit_action(
        match,
        CastSpellAction(
            actor_user_id=PLAYER_TWO,
            card_instance_id=hand_card(match.player(PLAYER_TWO), card_id),
            target_card_instance_id=target,
        ),
        catalog=catalog,
        randomness=source,
    )


def resolve(match: Match, *, catalog: CardCatalog, source: RandomSource) -> None:
    submit_action(
        match,
        EndDefenseWindowAction(actor_user_id=PLAYER_TWO),
        catalog=catalog,
        randomness=source,
    )


# --- Resolve na hora, e a vez fica ------------------------------------------


def test_the_effect_happens_immediately(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(POLAROID,))
    attacker = bank_card(match.player(PLAYER_ONE))

    cast(match, SUMMONED_AX, catalog=catalog, source=source, target=attacker)

    assert match.player(PLAYER_ONE).bank[0].damage_taken == 3


def test_the_card_goes_straight_to_the_graveyard(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog)
    card = hand_card(match.player(PLAYER_TWO), SUMMONED_AX)

    cast(
        match,
        SUMMONED_AX,
        catalog=catalog,
        source=source,
        target=bank_card(match.player(PLAYER_ONE)),
    )

    assert in_graveyard(match.player(PLAYER_TWO), card)
    assert match.player(PLAYER_TWO).hand == []


def test_the_priority_stays_with_the_defender(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog)

    cast(
        match,
        SUMMONED_AX,
        catalog=catalog,
        source=source,
        target=bank_card(match.player(PLAYER_ONE)),
    )

    assert match.priority_user_id == PLAYER_TWO
    assert match.phase is MatchPhase.COMBAT


def test_two_spells_in_the_same_window(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Limitado só pela energia, sem limite de quantidade."""
    match = board(catalog, hand_two=(SUMMONED_AX, LIFE_POTION))
    attacker = bank_card(match.player(PLAYER_ONE))

    cast(match, SUMMONED_AX, catalog=catalog, source=source, target=attacker)
    cast(match, LIFE_POTION, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS + 5
    assert len(match.player(PLAYER_TWO).graveyard) == 2


def test_the_energy_is_spent(catalog: CardCatalog, source: RandomSource) -> None:
    match = board(catalog)
    before = match.player(PLAYER_TWO).energy_current

    cast(
        match,
        SUMMONED_AX,
        catalog=catalog,
        source=source,
        target=bank_card(match.player(PLAYER_ONE)),
    )

    assert match.player(PLAYER_TWO).energy_current == before - AX_COST


# --- O que o feitiço muda no dano --------------------------------------------


def test_a_buffed_blocker_survives_the_trade(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """MORTEM 7/2 atacando KHRAS 2/4: sem buff o bloqueador morre; com dois
    SOMEONE'S SHIELD ele fica com 8 de vida e sobrevive aos 7."""
    match = board(
        catalog,
        hand_two=(SOMEONES_SHIELD, SOMEONES_SHIELD),
        bank_one=(MORTEM,),
        bank_two=(KHRAS,),
    )
    blocker = bank_card(match.player(PLAYER_TWO))
    _block(match, catalog=catalog, source=source)

    cast(match, SOMEONES_SHIELD, catalog=catalog, source=source, target=blocker)
    cast(match, SOMEONES_SHIELD, catalog=catalog, source=source, target=blocker)
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).bank[0].damage_taken == 7
    assert not in_graveyard(match.player(PLAYER_TWO), blocker)


def test_an_immune_blocker_takes_nothing_and_the_attacker_takes_its_share(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A barreira absorve o golpe do atacante e some; o bloqueador ainda bate
    (§14)."""
    match = board(
        catalog,
        hand_two=(MAGIC_BARRIER,),
        bank_one=(SKILLET,),
        bank_two=(POLAROID,),
    )
    blocker = bank_card(match.player(PLAYER_TWO))
    _block(match, catalog=catalog, source=source)

    cast(match, MAGIC_BARRIER, catalog=catalog, source=source, target=blocker)
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).bank[0].damage_taken == 0
    assert match.player(PLAYER_TWO).bank[0].modifiers == []
    assert match.player(PLAYER_ONE).bank[0].damage_taken == 2


def test_killing_the_attacker_leaves_an_orphan_blocker(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """SUMMONED AX mata MORTEM 7/2 dentro da janela: o bloqueador dele não troca
    dano com ninguém e volta ao banco intacto."""
    match = board(
        catalog, hand_two=(SUMMONED_AX,), bank_one=(MORTEM,), bank_two=(SKILLET,)
    )
    attacker = bank_card(match.player(PLAYER_ONE))
    blocker = bank_card(match.player(PLAYER_TWO))
    _block(match, catalog=catalog, source=source)

    cast(match, SUMMONED_AX, catalog=catalog, source=source, target=attacker)
    resolve(match, catalog=catalog, source=source)

    assert in_graveyard(match.player(PLAYER_ONE), attacker)
    assert match.player(PLAYER_TWO).bank[0].card.card_instance_id == blocker
    assert match.player(PLAYER_TWO).bank[0].damage_taken == 0
    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS


def test_killing_every_attacker_resolves_with_no_damage(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(
        catalog, hand_two=(SUMMONED_AX,), bank_one=(MORTEM,), bank_two=(SKILLET,)
    )

    cast(
        match,
        SUMMONED_AX,
        catalog=catalog,
        source=source,
        target=bank_card(match.player(PLAYER_ONE)),
    )
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS
    assert match.player(PLAYER_TWO).bank[0].damage_taken == 0
    assert match.phase is MatchPhase.ACTION


# --- A partida que acaba dentro da janela ------------------------------------


def test_a_defender_who_kills_themselves_freezes_the_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """SACRIFICIAL FIRE cobra 8 de Nexus do lançador. Com 8 ou menos, o defensor
    se derrota **dentro** da janela: nenhuma ação seguinte é aceita, o dano do
    combate nunca resolve, e o estado de combate fica congelado onde parou.

    A §14 proíbe o FIRE ao defensor e o faz parar em Nexus 1. Quando ela
    entrar, este cenário é alcançado pela desistência da §10.
    """
    match = board(
        catalog, hand_two=(SACRIFICIAL_FIRE,), bank_one=(MORTEM,), bank_two=(KHRAS,)
    )
    match.player(PLAYER_TWO).nexus = FIRE_NEXUS_COST

    cast(match, SACRIFICIAL_FIRE, catalog=catalog, source=source)

    assert match.phase is MatchPhase.FINISHED
    assert match.outcome is not None
    assert match.outcome.defeated_user_id == PLAYER_TWO

    with pytest.raises(MatchIsOverError):
        resolve(match, catalog=catalog, source=source)

    assert match.combat is not None
    assert match.player(PLAYER_ONE).nexus == STARTING_NEXUS
    assert match.player(PLAYER_ONE).bank[0].damage_taken == 0


def test_the_frozen_combat_still_survives_the_round_trip(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O estado congelado precisa continuar íntegro e serializável. Mesma
    ressalva da §14 do teste acima."""
    match = board(
        catalog, hand_two=(SACRIFICIAL_FIRE,), bank_one=(MORTEM,), bank_two=(KHRAS,)
    )
    match.player(PLAYER_TWO).nexus = FIRE_NEXUS_COST

    cast(match, SACRIFICIAL_FIRE, catalog=catalog, source=source)

    document = to_match_document(match)

    assert to_match_document(match_from_document(document)) == document


def _block(match: Match, *, catalog: CardCatalog, source: RandomSource) -> None:
    """Bloqueia o primeiro atacante com a primeira unidade do defensor."""
    submit_action(
        match,
        AssignBlockerAction(
            actor_user_id=PLAYER_TWO,
            blocker_card_instance_id=bank_card(match.player(PLAYER_TWO)),
            attacker_card_instance_id=bank_card(match.player(PLAYER_ONE)),
        ),
        catalog=catalog,
        randomness=source,
    )
