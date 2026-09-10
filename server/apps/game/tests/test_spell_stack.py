"""A pilha guarda o alvo como identificador, e o estado responde se ele ainda
está em campo.

É o que torna o fizzle da §6 possível: com referência direta ao objeto, quem
resolve aplicaria efeito em unidade já removida do jogo.

Resolver a pilha não é deste pacote. O que se testa aqui é que a pergunta tem
resposta.
"""

import pytest

from apps.game.cards import CardId
from apps.game.match import BankUnit, CardInstanceId, Match, StackEntry
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_cards,
    fake_match_in_progress,
    fake_new_match,
)

DAMAGE_SPELL = CardId(1002)
NEXUS_SPELL = CardId(1004)
GHOST = CardInstanceId(9999)


@pytest.fixture
def match() -> Match:
    return fake_match_in_progress()


def targeted_unit(match: Match) -> BankUnit:
    """A unidade que o feitiço do fundo da pilha está mirando."""
    return match.player(PLAYER_ONE).bank[1]


def test_the_stack_resolves_last_in_first_out(match: Match) -> None:
    """Fim da lista é o topo: `append` empilha, `pop` tira o topo (§6)."""
    top = match.stack[-1]

    assert match.stack.pop() is top


def test_an_entry_says_which_spell_it_is(match: Match) -> None:
    assert match.stack[0].card.card_id == DAMAGE_SPELL


def test_an_entry_says_who_cast_it(match: Match) -> None:
    assert match.stack[0].caster_user_id == PLAYER_TWO


def test_an_entry_says_what_it_targets(match: Match) -> None:
    assert (
        match.stack[0].target_card_instance_id
        == targeted_unit(match).card.card_instance_id
    )


def test_a_spell_with_no_target_says_so_explicitly(match: Match) -> None:
    """`RestoreNexus` e `SacrificeNexusForAttack` não miram nada."""
    assert match.stack[1].target_card_instance_id is None


def test_the_target_is_an_identifier_not_a_reference(match: Match) -> None:
    """Se fosse referência, a unidade morta continuaria alcançável e o fizzle
    seria impossível."""
    assert isinstance(match.stack[0].target_card_instance_id, int)


def test_a_target_in_play_is_found(match: Match) -> None:
    unit = targeted_unit(match)

    assert match.bank_unit(unit.card.card_instance_id) is unit


def test_a_target_is_found_without_saying_which_player_owns_it(
    match: Match,
) -> None:
    """A busca varre os dois bancos: `BuffUnitHealth` mira aliado e
    `DamageUnit` mira inimigo, e decidir qual é legal é de outra feature."""
    enemy_unit = match.player(PLAYER_TWO).bank[0]

    assert match.bank_unit(enemy_unit.card.card_instance_id) is enemy_unit


def test_an_identifier_that_never_existed_is_not_in_play(match: Match) -> None:
    assert match.bank_unit(GHOST) is None


def test_a_dead_target_is_no_longer_in_play(match: Match) -> None:
    """O caso que autoriza o fizzle: o alvo morreu antes de o feitiço
    resolver."""
    player = match.player(PLAYER_ONE)
    dying = player.bank.pop(1)
    player.graveyard.append(dying.card)

    assert match.bank_unit(dying.card.card_instance_id) is None


def test_a_card_in_hand_is_not_in_play(match: Match) -> None:
    """A pergunta é "ainda está no banco?", não "ainda existe?"."""
    in_hand = match.player(PLAYER_ONE).hand[0]

    assert match.bank_unit(in_hand.card_instance_id) is None


def test_a_card_in_the_graveyard_is_not_in_play(match: Match) -> None:
    buried = match.player(PLAYER_ONE).graveyard[0]

    assert match.bank_unit(buried.card_instance_id) is None


def test_the_target_lookup_survives_the_stack_being_empty() -> None:
    new_match = fake_new_match()

    assert new_match.bank_unit(GHOST) is None


def test_two_copies_of_the_same_card_are_told_apart_by_the_lookup() -> None:
    """O ponto todo: um feitiço mirado numa cópia não pode acertar a outra."""
    match = fake_new_match()
    player = match.player(PLAYER_ONE)
    player.bank = [
        BankUnit(card=card) for card in fake_cards(match, [CardId(15), CardId(15)])
    ]

    found = match.bank_unit(player.bank[1].card.card_instance_id)

    assert found is player.bank[1]
    assert found is not player.bank[0]


def test_pushing_a_spell_is_appending_to_the_stack() -> None:
    match = fake_new_match()
    spell = fake_cards(match, [NEXUS_SPELL])[0]

    match.stack.append(StackEntry(card=spell, caster_user_id=PLAYER_ONE))

    assert match.stack[-1].card is spell
