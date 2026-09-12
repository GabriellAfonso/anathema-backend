"""Todo estado que o feitiço produz sobrevive à ida e à volta.

A feature 002 garante o round-trip do estado que ela modelou; a feature 006 foi
a primeira a **preencher** os modificadores, o dano e os cemitérios, e a primeira
a acrescentar um campo desde então -- o desfecho da §10.

Passa por `to_match_document` -> `json` -> `match_from_document`, como
`test_match_serialization.py` faz, e não toca no Redis: o formato é o que está
sob teste, não o transporte.

O fim do arquivo cobre a outra metade de US9: a varredura do Fim de Rodada da
feature 005 continua a mesma, e agora tem o que varrer.
"""

import json
from dataclasses import replace

from apps.game.cards import (
    CardCatalog,
    FrozenCardCatalog,
    Spell,
    mvp_catalog,
)
from apps.game.engine import (
    CastSpellAction,
    DeclareAttackAction,
    WithdrawAttackerAction,
    PassAction,
    submit_action,
    unit_has_damage_immunity,
)
from apps.game.match import (
    AttackModifier,
    DamageImmunity,
    HealthModifier,
    Match,
    MatchDocument,
    MatchEndReason,
    MatchOutcome,
    MatchPhase,
    match_from_document,
    to_match_document,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_match_in_progress,
)
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    MAGIC_BARRIER,
    SACRIFICIAL_FIRE,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    bank_card,
    fake_spell_board,
    hand_card,
)


def round_trip(match: Match) -> Match:
    """A partida depois de uma volta completa pelo formato gravado."""
    document: MatchDocument = json.loads(json.dumps(to_match_document(match)))

    return match_from_document(document)


def pass_until_priority_returns(
    match: Match, catalog: CardCatalog, source: RandomSource, times: int = 2
) -> None:
    """Passes consecutivos, sempre por quem tem a prioridade no momento."""
    for _ in range(times):
        holder = match.priority_user_id
        assert holder is not None
        submit_action(match, PassAction(holder), catalog=catalog, randomness=source)


# --------------------------------------------------------------------------
# O desfecho da partida (§10)
# --------------------------------------------------------------------------


def test_a_running_match_comes_back_without_an_outcome() -> None:
    """`None` é partida em andamento, e atravessa como `None`."""
    match = fake_match_in_progress()

    assert round_trip(match).outcome is None


def test_a_running_match_is_not_over() -> None:
    assert fake_match_in_progress().is_over is False


def test_a_defeat_survives_the_round_trip() -> None:
    match = fake_match_in_progress()
    match.outcome = MatchOutcome(
        defeated_user_id=PLAYER_ONE, reason=MatchEndReason.NEXUS_DEPLETED
    )
    match.phase = MatchPhase.FINISHED

    assert round_trip(match).outcome == MatchOutcome(
        defeated_user_id=PLAYER_ONE, reason=MatchEndReason.NEXUS_DEPLETED
    )


def test_a_forfeit_survives_the_round_trip() -> None:
    """O motivo volta, e volta como o enum."""
    match = fake_match_in_progress()
    match.outcome = MatchOutcome(
        defeated_user_id=PLAYER_TWO, reason=MatchEndReason.FORFEIT
    )
    match.phase = MatchPhase.FINISHED

    rebuilt = round_trip(match).outcome

    assert rebuilt is not None
    assert rebuilt.reason is MatchEndReason.FORFEIT


def test_the_terminal_phase_comes_back_as_the_enum() -> None:
    match = fake_match_in_progress()
    match.outcome = MatchOutcome(
        defeated_user_id=PLAYER_TWO, reason=MatchEndReason.NEXUS_DEPLETED
    )
    match.phase = MatchPhase.FINISHED

    assert round_trip(match).phase is MatchPhase.FINISHED


def test_a_finished_match_is_over_after_the_round_trip() -> None:
    match = fake_match_in_progress()
    match.outcome = MatchOutcome(
        defeated_user_id=PLAYER_ONE, reason=MatchEndReason.NEXUS_DEPLETED
    )
    match.phase = MatchPhase.FINISHED

    assert round_trip(match).is_over is True


def test_a_finished_document_is_stable_across_the_round_trip() -> None:
    match = fake_match_in_progress()
    match.outcome = MatchOutcome(
        defeated_user_id=PLAYER_ONE, reason=MatchEndReason.NEXUS_DEPLETED
    )
    match.phase = MatchPhase.FINISHED

    assert to_match_document(round_trip(match)) == to_match_document(match)


# --------------------------------------------------------------------------
# O estado que esta feature produz, indo e voltando
# --------------------------------------------------------------------------


def fire_on_an_attacker(
    match: Match, catalog: CardCatalog, source: RandomSource
) -> None:
    """O primeiro jogador declara com a primeira unidade, joga SACRIFICIAL FIRE
    sem alvo -- e ele buffa toda a zona de ataque (§14) -- e a puxa de volta: a
    partida volta à Fase de Ação com o bônus na unidade, que a §13 registra como
    pergunta em aberto."""
    one = match.players[0]
    attacker = bank_card(one)

    for action in (
        DeclareAttackAction(one.user_id, (attacker,)),
        CastSpellAction(one.user_id, hand_card(one, SACRIFICIAL_FIRE)),
        WithdrawAttackerAction(one.user_id, attacker),
    ):
        submit_action(match, action, catalog=catalog, randomness=source)


def played_out_match() -> Match:
    """Uma partida que passou pela §5B dos dois lados, com os feitiços já
    resolvidos.

    Sai do motor de verdade, e não montada à mão: o que precisa sobreviver é o
    estado que o lançamento **produz**, não um que se pareça com ele. O
    SACRIFICIAL FIRE é o único feitiço do MVP que cria `AttackModifier`, e é
    jogado na declaração, como a §14 manda.
    """
    catalog = mvp_catalog()
    source = ScriptedRandomSource()
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(SOMEONES_SHIELD, SACRIFICIAL_FIRE),
        hand_two=(SUMMONED_AX, MAGIC_BARRIER),
    )
    one, two = match.players

    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
        catalog=catalog,
        randomness=source,
    )
    fire_on_an_attacker(match, catalog, source)

    for action in (
        PassAction(one.user_id),
        CastSpellAction(two.user_id, hand_card(two, MAGIC_BARRIER), bank_card(two)),
    ):
        submit_action(match, action, catalog=catalog, randomness=source)

    return match


def test_a_match_after_spells_is_stable_across_the_round_trip() -> None:
    """A prova mais forte: o documento inteiro, campo a campo."""
    match = played_out_match()

    assert to_match_document(round_trip(match)) == to_match_document(match)


def test_the_three_modifier_kinds_survive_the_round_trip() -> None:
    """A feature 006 foi a primeira a criar os três, e os três voltam."""
    match = played_out_match()
    kinds = {
        type(modifier)
        for player in match.players
        for unit in player.bank
        for modifier in unit.modifiers
    }

    rebuilt = round_trip(match)

    assert kinds == {HealthModifier, AttackModifier, DamageImmunity}
    assert to_match_document(rebuilt) == to_match_document(match)


def test_accumulated_damage_and_graveyards_survive_the_round_trip() -> None:
    catalog = mvp_catalog()
    source = ScriptedRandomSource()
    match = fake_spell_board(catalog=catalog, hand_one=(SUMMONED_AX,))
    one, two = match.players
    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
        catalog=catalog,
        randomness=source,
    )

    rebuilt = round_trip(match)

    assert rebuilt.players[1].bank[0].damage_taken == 3
    assert len(rebuilt.players[0].graveyard) == 1


# --------------------------------------------------------------------------
# A §8 continua a mesma, e agora tem o que varrer
# --------------------------------------------------------------------------


def test_the_round_end_keeps_the_barrier() -> None:
    """§14, corrigida em 2026-09-11: a barreira não expira no fim da rodada.
    Até a correção este era o primeiro caso real da varredura da feature 005;
    hoje nenhum feitiço do MVP cria modificador temporário."""
    catalog = mvp_catalog()
    source = ScriptedRandomSource()
    match = fake_spell_board(catalog=catalog, hand_one=(MAGIC_BARRIER,))
    one = match.players[0]
    unit = one.bank[0]
    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, MAGIC_BARRIER), bank_card(one)),
        catalog=catalog,
        randomness=source,
    )
    assert unit_has_damage_immunity(unit) is True

    pass_until_priority_returns(match, catalog, source)

    assert unit_has_damage_immunity(unit) is True
    assert match.round_number == 2


def test_the_round_end_keeps_the_permanent_modifiers() -> None:
    """O buff de vida e o bônus de ataque sobrevivem à mesma varredura."""
    catalog = mvp_catalog()
    source = ScriptedRandomSource()
    match = fake_spell_board(
        catalog=catalog, hand_one=(SOMEONES_SHIELD, SACRIFICIAL_FIRE)
    )
    one = match.players[0]
    unit = one.bank[0]
    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
        catalog=catalog,
        randomness=source,
    )
    fire_on_an_attacker(match, catalog, source)
    pass_until_priority_returns(match, catalog, source)

    assert match.round_number == 2
    assert {type(modifier) for modifier in unit.modifiers} == {
        HealthModifier,
        AttackModifier,
    }


def test_accumulated_damage_is_not_swept_by_the_round_end() -> None:
    """Dano não é modificador: não expira e a §8 não o toca."""
    catalog = mvp_catalog()
    source = ScriptedRandomSource()
    match = fake_spell_board(catalog=catalog, hand_one=(SUMMONED_AX,))
    one, two = match.players
    unit = two.bank[0]
    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, SUMMONED_AX), bank_card(two)),
        catalog=catalog,
        randomness=source,
    )
    pass_until_priority_returns(match, catalog, source)

    assert unit.damage_taken == 3
    assert match.round_number == 2


# --------------------------------------------------------------------------
# Os efeitos vêm do campo estruturado, nunca da descrição (FR-015)
# --------------------------------------------------------------------------


def resolved_shield(catalog: CardCatalog) -> Match:
    """Joga SOMEONE'S SHIELD com o catálogo dado; resolve na hora."""
    source = ScriptedRandomSource()
    match = fake_spell_board(catalog=catalog, hand_one=(SOMEONES_SHIELD,))
    one = match.players[0]

    submit_action(
        match,
        CastSpellAction(one.user_id, hand_card(one, SOMEONES_SHIELD), bank_card(one)),
        catalog=catalog,
        randomness=source,
    )

    return match


def test_no_rule_of_this_feature_reads_the_card_description() -> None:
    """Um catálogo com todas as descrições apagadas produz a mesma partida.

    Se alguma decisão de regra lesse `Spell.description`, este teste falharia --
    é a forma mais direta de afirmar FR-015 sem inspecionar o código.
    """
    stripped = FrozenCardCatalog(
        [
            replace(card, description="") if isinstance(card, Spell) else card
            for card in mvp_catalog().all_cards()
        ]
    )

    with_description = resolved_shield(mvp_catalog())
    without_description = resolved_shield(stripped)

    assert to_match_document(with_description) == to_match_document(without_description)
