"""A forma servida prevê o veredito do motor, feitiço por feitiço.

É o ponto da US2: o cliente monta a jogada pelos campos estruturados do
catálogo e o servidor aceita. Se este arquivo falhar, o cliente estará
desenhando uma mira que a carta não tem -- ou deixando de desenhar uma que ela
exige -- e o jogador levaria a recusa na cara.

As guardas são chamadas direto (`validated_spell_cast`), sem passar pela ação:
o que está sob teste é a concordância entre o payload e a guarda, e ir pelo
ciclo de rodada faria uma falha dele reprovar um arquivo que não é sobre ele.
"""

import pytest

from apps.game.card_payload import card_payload
from apps.game.cards import CardCatalog, Spell, mvp_catalog
from apps.game.engine import (
    CastSpellAction,
    SpellNeedsTargetError,
    SpellOnlyInDeclarationError,
    SpellTakesNoTargetError,
    WrongSpellTargetSideError,
)
from apps.game.engine.spell_cast_guards import validated_spell_cast
from apps.game.match import CardInstanceId, Match
from apps.game.tests.fake_spell_board import (
    TOUGH_UNIT,
    bank_card,
    fake_spell_board,
    hand_card,
    open_declaration,
)


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture(params=[spell.card_id for spell in mvp_catalog().spells()])
def spell(request: pytest.FixtureRequest, catalog: CardCatalog) -> Spell:
    """Um teste por feitiço do MVP: são 5, e os 5 precisam concordar."""
    card = catalog.card(request.param)
    assert isinstance(card, Spell)

    return card


def served_effect(spell: Spell) -> dict[str, object]:
    """A forma do efeito exatamente como o cliente a recebe."""
    effect = card_payload(spell)["effect"]
    assert isinstance(effect, dict)

    return effect


def board_for(spell: Spell, catalog: CardCatalog) -> Match:
    """Tabuleiro com o feitiço na mão do primeiro e uma unidade em cada banco.

    Um feitiço com restrição de momento é posto na Declaração, porque é o único
    lugar em que a forma servida diz que ele pode ser jogado.
    """
    match = fake_spell_board(
        catalog=catalog,
        hand_one=(spell.card_id,),
        bank_one=(TOUGH_UNIT,),
        bank_two=(TOUGH_UNIT,),
    )

    if served_effect(spell)["declaration_only"]:
        open_declaration(match, 0)

    return match


def prescribed_target(match: Match, spell: Spell) -> CardInstanceId | None:
    """O alvo que o cliente escolheria lendo só a forma servida."""
    target_kind = served_effect(spell)["target_kind"]

    if target_kind == "none":
        return None

    if target_kind == "allied_unit":
        return bank_card(match.players[0])

    return bank_card(match.players[1])


def cast(
    match: Match, spell: Spell, target: CardInstanceId | None, catalog: CardCatalog
) -> None:
    actor = match.players[0]

    validated_spell_cast(
        match,
        actor,
        CastSpellAction(actor.user_id, hand_card(actor, spell.card_id), target),
        catalog=catalog,
    )


def test_the_play_the_served_shape_prescribes_is_accepted(
    spell: Spell, catalog: CardCatalog
) -> None:
    """O caso que importa: o cliente obedece ao payload e o servidor aceita."""
    match = board_for(spell, catalog)

    cast(match, spell, prescribed_target(match, spell), catalog)


def test_requires_target_false_means_a_target_is_refused(
    spell: Spell, catalog: CardCatalog
) -> None:
    if served_effect(spell)["requires_target"]:
        pytest.skip("este feitiço exige alvo")

    match = board_for(spell, catalog)

    with pytest.raises(SpellTakesNoTargetError):
        cast(match, spell, bank_card(match.players[0]), catalog)


def test_requires_target_true_means_the_absence_is_refused(
    spell: Spell, catalog: CardCatalog
) -> None:
    if not served_effect(spell)["requires_target"]:
        pytest.skip("este feitiço não aceita alvo")

    match = board_for(spell, catalog)

    with pytest.raises(SpellNeedsTargetError):
        cast(match, spell, None, catalog)


def test_target_kind_names_the_side_the_engine_demands(
    spell: Spell, catalog: CardCatalog
) -> None:
    """De qual lado do tabuleiro: errar o banco é recusa, e é o payload que
    diz qual banco é o certo."""
    if not served_effect(spell)["requires_target"]:
        pytest.skip("este feitiço não aceita alvo")

    match = board_for(spell, catalog)
    wrong_side = (
        bank_card(match.players[1])
        if served_effect(spell)["target_kind"] == "allied_unit"
        else bank_card(match.players[0])
    )

    with pytest.raises(WrongSpellTargetSideError):
        cast(match, spell, wrong_side, catalog)


def test_declaration_only_names_the_moment_the_engine_demands(
    spell: Spell, catalog: CardCatalog
) -> None:
    """O feitiço com restrição de momento é recusado fora da Declaração, que é
    o que o cliente evita mantendo a carta indisponível."""
    if not served_effect(spell)["declaration_only"]:
        pytest.skip("este feitiço não tem restrição de momento")

    match = fake_spell_board(
        catalog=catalog,
        hand_one=(spell.card_id,),
        bank_one=(TOUGH_UNIT,),
        bank_two=(TOUGH_UNIT,),
    )

    with pytest.raises(SpellOnlyInDeclarationError):
        cast(match, spell, prescribed_target(match, spell), catalog)


def test_a_spell_without_the_restriction_is_fine_in_the_action_phase(
    spell: Spell, catalog: CardCatalog
) -> None:
    if served_effect(spell)["declaration_only"]:
        pytest.skip("este feitiço só vale na declaração")

    match = fake_spell_board(
        catalog=catalog,
        hand_one=(spell.card_id,),
        bank_one=(TOUGH_UNIT,),
        bank_two=(TOUGH_UNIT,),
    )

    cast(match, spell, prescribed_target(match, spell), catalog)
