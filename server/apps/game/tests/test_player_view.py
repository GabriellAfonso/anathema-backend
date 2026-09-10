"""A visão de um jogador mostra o que ele pode ver, e só isso.

O servidor é a autoridade. A ordem do deck nunca sai dele, e a mão do oponente
também não.

As provas mais importantes aqui são negativas: o que **não** aparece. A
ocultação é imposta pelo tipo — `OpponentSideView` não tem campo de mão — mas
um teste que confira a estrutura produzida pega também o dia em que alguém
trocar o tipo.
"""

import json
from typing import Any

import pytest

from apps.game.match import (
    Match,
    MatchPhase,
    NotAParticipantError,
    PlayerView,
    build_player_view,
)
from apps.game.tests.fake_match_state import (
    OUTSIDER,
    PLAYER_ONE,
    PLAYER_TWO,
    fake_match_in_progress,
)


@pytest.fixture
def match() -> Match:
    return fake_match_in_progress()


@pytest.fixture
def view(match: Match) -> PlayerView:
    return build_player_view(match, PLAYER_ONE)


def test_you_see_your_own_hand(match: Match, view: PlayerView) -> None:
    assert [card["card_instance_id"] for card in view["you"]["hand"]] == [
        card.card_instance_id for card in match.player(PLAYER_ONE).hand
    ]


def test_your_hand_carries_the_instance_identifier(view: PlayerView) -> None:
    """É com ele que o cliente mira uma cópia específica."""
    assert "card_instance_id" in view["you"]["hand"][0]


def test_your_hand_does_not_carry_the_template_values(view: PlayerView) -> None:
    """O cliente já tem o catálogo: nome, custo, ataque e vida não viajam."""
    assert set(view["you"]["hand"][0]) == {"card_instance_id", "card_id"}


def test_you_only_see_how_many_cards_the_opponent_holds(
    match: Match, view: PlayerView
) -> None:
    assert view["opponent"]["hand_size"] == len(match.player(PLAYER_TWO).hand)


def test_the_opponent_side_has_no_hand_field_at_all(view: PlayerView) -> None:
    """Contagem sim, identidade não. Não é uma checagem: o tipo não tem onde
    escrever a mão do oponente."""
    assert "hand" not in view["opponent"]


def test_neither_deck_appears_in_the_view(view: PlayerView) -> None:
    """A §2 protege conteúdo e ordem dos **dois** decks, o próprio inclusive."""
    assert "deck" not in view["you"]
    assert "deck" not in view["opponent"]


def test_both_deck_sizes_appear(match: Match, view: PlayerView) -> None:
    """Contagem não revela carta nenhuma, e o cliente precisa dela para
    desenhar a pilha de compra."""
    assert (view["you"]["deck_size"], view["opponent"]["deck_size"]) == (
        len(match.player(PLAYER_ONE).deck),
        len(match.player(PLAYER_TWO).deck),
    )


def test_no_hidden_card_identifier_leaks_into_the_view(
    match: Match, view: PlayerView
) -> None:
    """A prova mais forte: recolher tudo que deveria estar escondido e
    conferir que nada disso aparece na estrutura serializada."""
    visible = _identifiers_in(view)

    assert not visible & _hidden_identifiers(match)


def test_both_banks_appear(match: Match, view: PlayerView) -> None:
    assert (len(view["you"]["bank"]), len(view["opponent"]["bank"])) == (
        len(match.player(PLAYER_ONE).bank),
        len(match.player(PLAYER_TWO).bank),
    )


def test_a_bank_unit_shows_its_damage_and_modifiers(view: PlayerView) -> None:
    """O oponente precisa ver o dano para decidir o combate."""
    wounded = view["opponent"]["bank"][0]

    assert wounded["damage_taken"] == 1
    assert wounded["modifiers"] == []


def test_both_nexus_appear(view: PlayerView) -> None:
    assert (view["you"]["nexus"], view["opponent"]["nexus"]) == (18, 20)


def test_both_energies_appear(view: PlayerView) -> None:
    assert (view["you"]["energy_current"], view["opponent"]["energy_current"]) == (1, 3)


def test_both_graveyards_appear(match: Match, view: PlayerView) -> None:
    """Informação já revelada: aparece inteira, com conteúdo e ordem."""
    assert (len(view["you"]["graveyard"]), len(view["opponent"]["graveyard"])) == (
        len(match.player(PLAYER_ONE).graveyard),
        len(match.player(PLAYER_TWO).graveyard),
    )


def test_the_shared_round_fields_appear(view: PlayerView) -> None:
    assert (
        view["round_number"],
        view["phase"],
        view["priority_user_id"],
        view["token_holder_user_id"],
        view["token_consumed"],
        view["consecutive_passes"],
    ) == (3, MatchPhase.ACTION, PLAYER_ONE, PLAYER_TWO, False, 1)


def test_the_stack_appears_in_order(match: Match, view: PlayerView) -> None:
    assert [entry["card"]["card_instance_id"] for entry in view["stack"]] == [
        entry.card.card_instance_id for entry in match.stack
    ]


def test_the_view_is_the_same_from_the_other_side(match: Match) -> None:
    """Os lados trocam: a mão de quem pede aparece, a do outro não."""
    other = build_player_view(match, PLAYER_TWO)

    assert other["you"]["profile"]["user_id"] == PLAYER_TWO
    assert other["opponent"]["profile"]["user_id"] == PLAYER_ONE
    assert other["opponent"]["hand_size"] == len(match.player(PLAYER_ONE).hand)


def test_an_outsider_gets_no_view_at_all(match: Match) -> None:
    """Recusa citando o `user_id`, em vez de uma visão parcial."""
    with pytest.raises(NotAParticipantError, match=str(OUTSIDER)):
        build_player_view(match, OUTSIDER)


def test_the_view_survives_json(view: PlayerView) -> None:
    """Ela vai para o cliente por websocket: se não serializa, não serve."""
    assert json.loads(json.dumps(view))["you"]["deck_size"] == 3


def _identifiers_in(view: PlayerView) -> set[int]:
    """Todo `card_instance_id` que a visão carrega, em qualquer profundidade."""
    return set(_walk_identifiers(json.loads(json.dumps(view))))


def _walk_identifiers(node: Any) -> list[int]:
    if isinstance(node, dict):
        here = [node["card_instance_id"]] if "card_instance_id" in node else []

        return here + [i for value in node.values() for i in _walk_identifiers(value)]

    if isinstance(node, list):
        return [i for item in node for i in _walk_identifiers(item)]

    return []


def _hidden_identifiers(match: Match) -> set[int]:
    """Os dois decks inteiros e a mão do oponente: nada disso pode vazar."""
    hidden = [card.card_instance_id for player in match.players for card in player.deck]
    hidden += [card.card_instance_id for card in match.player(PLAYER_TWO).hand]

    return set(hidden)
