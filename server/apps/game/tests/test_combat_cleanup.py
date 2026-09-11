"""A §7.4 e a §7.5: encerrar a janela mata, devolve e reabre a Fase de Ação.

Aqui o combate roda inteiro por ações de jogador, de ponta a ponta, e é o
primeiro arquivo em que ele vale alguma coisa.

Dois testes carregam o arquivo. `test_ending_the_window_reopens_the_action_phase`
é o que pega uma partida que ficou parada em Combate — a §7.4 termina devolvendo
a vez, e sem isso o combate é um beco sem saída. E
`test_the_round_goes_on_after_the_combat` é o que pega um combate que fechou a
rodada: a §7.5 diz que ela **não** acaba com ele.

Os números vêm das cartas reais: DARK AGE 3/2, KHRAS 2/4, SKILLET 4/5,
POLAROID 2/6, MORTEM 7/2.
"""

import pytest

from apps.game.cards import CardCatalog, CardId, mvp_catalog
from apps.game.engine import (
    AssignBlockerAction,
    AttackTokenAlreadyConsumedError,
    CastSpellAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    NotTheTokenHolderError,
    PassAction,
    PlayUnitAction,
    submit_action,
)
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchCard,
    MatchPhase,
    PlayerState,
    STARTING_NEXUS,
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
    SUMMONED_AX,
    bank_card,
    fake_combat_board,
    hand_card,
    in_graveyard,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource

DECK_CARD_IDS = (CardId(31), CardId(32), CardId(33), CardId(34))


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def board(
    catalog: CardCatalog,
    *,
    bank_one: tuple[CardId, ...] = (DARK_AGE,),
    bank_two: tuple[CardId, ...] = (MORTEM,),
    hand_one: tuple[CardId, ...] = (),
    hand_two: tuple[CardId, ...] = (),
) -> Match:
    """Tabuleiro com deck dos dois lados, para o Upkeep da rodada seguinte ter
    o que comprar."""
    match = fake_combat_board(
        catalog=catalog,
        bank_one=bank_one,
        bank_two=bank_two,
        hand_one=hand_one,
        hand_two=hand_two,
    )

    for player in match.players:
        player.deck = [
            MatchCard(match.mint_card_instance_id(), card_id)
            for card_id in DECK_CARD_IDS
        ]

    return match


def declare(
    match: Match, *indexes: int, catalog: CardCatalog, source: RandomSource
) -> None:
    one = match.player(PLAYER_ONE)

    submit_action(
        match,
        DeclareAttackAction(
            actor_user_id=PLAYER_ONE,
            attacker_card_instance_ids=tuple(
                bank_card(one, index) for index in indexes
            ),
        ),
        catalog=catalog,
        randomness=source,
    )


def block(
    match: Match,
    *,
    catalog: CardCatalog,
    source: RandomSource,
    blocker: CardInstanceId,
    attacker: CardInstanceId,
) -> None:
    submit_action(
        match,
        AssignBlockerAction(
            actor_user_id=PLAYER_TWO,
            blocker_card_instance_id=blocker,
            attacker_card_instance_id=attacker,
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


def bank_ids(player: PlayerState) -> list[CardInstanceId]:
    return [unit.card.card_instance_id for unit in player.bank]


# --- Mortes e sobreviventes ---------------------------------------------------


def test_a_mutual_kill_sends_both_to_their_owners_graveyards(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """DARK AGE 3/2 contra MORTEM 7/2: os dois morrem no mesmo cálculo."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(MORTEM,))
    attacker = bank_card(match.player(PLAYER_ONE))
    blocker = bank_card(match.player(PLAYER_TWO))

    declare(match, 0, catalog=catalog, source=source)
    block(match, catalog=catalog, source=source, blocker=blocker, attacker=attacker)
    resolve(match, catalog=catalog, source=source)

    assert in_graveyard(match.player(PLAYER_ONE), attacker)
    assert in_graveyard(match.player(PLAYER_TWO), blocker)
    assert match.player(PLAYER_ONE).bank == []
    assert match.player(PLAYER_TWO).bank == []


def test_survivors_stay_in_their_own_bank(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """DARK AGE 3/2 contra SKILLET 4/5: o bloqueador aguenta, o atacante não."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,))
    attacker = bank_card(match.player(PLAYER_ONE))
    blocker = bank_card(match.player(PLAYER_TWO))

    declare(match, 0, catalog=catalog, source=source)
    block(match, catalog=catalog, source=source, blocker=blocker, attacker=attacker)
    resolve(match, catalog=catalog, source=source)

    assert bank_ids(match.player(PLAYER_TWO)) == [blocker]
    assert match.player(PLAYER_TWO).bank[0].damage_taken == 3
    assert in_graveyard(match.player(PLAYER_ONE), attacker)


def test_a_dead_unit_leaves_its_damage_and_modifiers_behind(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A carta no cemitério é um `MatchCard`, e ele não tem onde guardar
    dano nem modificador."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(MORTEM,))
    attacker = bank_card(match.player(PLAYER_ONE))

    declare(match, 0, catalog=catalog, source=source)
    block(
        match,
        catalog=catalog,
        source=source,
        blocker=bank_card(match.player(PLAYER_TWO)),
        attacker=attacker,
    )
    resolve(match, catalog=catalog, source=source)

    buried = match.player(PLAYER_ONE).graveyard[0]

    assert buried.card_instance_id == attacker
    assert not hasattr(buried, "damage_taken")


def test_unblocked_damage_reaches_the_nexus(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(MORTEM,), bank_two=())

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS - 7


def test_a_defender_with_an_empty_bank_just_ends_the_window(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=())

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS - 3
    assert match.phase is MatchPhase.ACTION


def test_ending_without_blocking_sends_everything_to_the_nexus(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(DARK_AGE, MORTEM), bank_two=(SKILLET,))

    declare(match, 0, 1, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.player(PLAYER_TWO).nexus == STARTING_NEXUS - 10
    assert match.player(PLAYER_TWO).bank[0].damage_taken == 0


# --- A volta -----------------------------------------------------------------


def test_ending_the_window_reopens_the_action_phase(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem isto o combate é um beco sem saída."""
    match = board(catalog)

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.phase is MatchPhase.ACTION
    assert match.priority_user_id == PLAYER_ONE
    assert match.consecutive_passes == 0


def test_the_combat_state_disappears(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog)

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.combat is None


def test_the_round_number_is_the_same_before_and_after(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog)

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.round_number == 1


def test_the_combat_spends_no_energy_and_draws_no_card(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog)
    energy_before = [player.energy_current for player in match.players]
    deck_before = [len(player.deck) for player in match.players]
    hand_before = [len(player.hand) for player in match.players]

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert [player.energy_current for player in match.players] == energy_before
    assert [len(player.deck) for player in match.players] == deck_before
    assert [len(player.hand) for player in match.players] == hand_before


def test_no_action_of_the_combat_stops_in_an_automatic_phase(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A promessa de `submit_action` desde a feature 005, agora com o combate
    dentro: nunca `UPKEEP`, `STACK_RESOLUTION` nem `ROUND_END`."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,))
    seen = []

    declare(match, 0, catalog=catalog, source=source)
    seen.append(match.phase)

    block(
        match,
        catalog=catalog,
        source=source,
        blocker=bank_card(match.player(PLAYER_TWO)),
        attacker=bank_card(match.player(PLAYER_ONE)),
    )
    seen.append(match.phase)

    resolve(match, catalog=catalog, source=source)
    seen.append(match.phase)

    assert seen == [MatchPhase.COMBAT, MatchPhase.COMBAT, MatchPhase.ACTION]


# --- O combate que encerra a partida -----------------------------------------


def test_lethal_combat_damage_finishes_the_match(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(MORTEM,), bank_two=())
    match.player(PLAYER_TWO).nexus = 7

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.phase is MatchPhase.FINISHED
    assert match.outcome is not None
    assert match.outcome.defeated_user_ids == (PLAYER_TWO,)


def test_a_finished_combat_does_not_go_back_to_the_action_phase(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(MORTEM,), bank_two=())
    match.player(PLAYER_TWO).nexus = 1

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.phase is MatchPhase.FINISHED


def test_a_combat_that_finishes_the_match_still_clears_its_state(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O combate terminou -- o que interrompe um combate é um feitiço dentro da
    janela, e esse caminho está em `test_cast_combat_spell.py`."""
    match = board(catalog, bank_one=(MORTEM,), bank_two=())
    match.player(PLAYER_TWO).nexus = 1

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    assert match.combat is None


# --- A rodada continua (US6) --------------------------------------------------


def test_the_round_goes_on_after_the_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A §7.5: os dois seguem alternando com a energia que sobrou."""
    match = board(catalog, hand_one=(SUMMONED_AX,))
    one = match.player(PLAYER_ONE)

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )

    assert match.priority_user_id == PLAYER_TWO
    assert match.phase is MatchPhase.ACTION


def test_the_stack_path_works_again_after_the_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A exceção da janela não vazou: a §5B volta a empilhar e a devolver a
    vez."""
    match = board(
        catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,), hand_two=(SUMMONED_AX,)
    )
    attacker = bank_card(match.player(PLAYER_ONE))

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )
    submit_action(
        match,
        CastSpellAction(
            actor_user_id=PLAYER_TWO,
            card_instance_id=hand_card(match.player(PLAYER_TWO), SUMMONED_AX),
            target_card_instance_id=bank_card(match.player(PLAYER_ONE)),
        ),
        catalog=catalog,
        randomness=source,
    )

    assert len(match.stack) == 1
    assert match.priority_user_id == PLAYER_ONE


def test_a_second_attack_in_the_same_round_is_refused(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(DARK_AGE, POLAROID))

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    with pytest.raises(AttackTokenAlreadyConsumedError):
        declare(match, 1, catalog=catalog, source=source)


def test_the_defender_of_the_combat_cannot_declare_in_the_same_round(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,))

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )

    with pytest.raises(NotTheTokenHolderError):
        submit_action(
            match,
            DeclareAttackAction(
                actor_user_id=PLAYER_TWO,
                attacker_card_instance_ids=(bank_card(match.player(PLAYER_TWO)),),
            ),
            catalog=catalog,
            randomness=source,
        )


def test_the_round_closes_normally_after_the_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Dois passes com a pilha vazia fecham a rodada, o token troca de dono, e
    o Upkeep da seguinte roda dentro da mesma chamada."""
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,))

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )
    submit_action(
        match, PassAction(actor_user_id=PLAYER_TWO), catalog=catalog, randomness=source
    )

    assert match.round_number == 2
    assert match.phase is MatchPhase.ACTION
    assert match.token_holder_user_id == PLAYER_TWO
    assert match.token_consumed is False


def test_the_new_token_holder_can_attack_in_the_next_round(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = board(catalog, bank_one=(DARK_AGE,), bank_two=(SKILLET,))

    declare(match, 0, catalog=catalog, source=source)
    resolve(match, catalog=catalog, source=source)

    submit_action(
        match, PassAction(actor_user_id=PLAYER_ONE), catalog=catalog, randomness=source
    )
    submit_action(
        match, PassAction(actor_user_id=PLAYER_TWO), catalog=catalog, randomness=source
    )

    submit_action(
        match,
        DeclareAttackAction(
            actor_user_id=PLAYER_TWO,
            attacker_card_instance_ids=(bank_card(match.player(PLAYER_TWO)),),
        ),
        catalog=catalog,
        randomness=source,
    )

    assert match.phase is MatchPhase.COMBAT
    assert match.priority_user_id == PLAYER_ONE
