"""O estado inteiro vira JSON e volta sem perder nada.

O que o `MatchStore` grava no Redis precisa reconstruir a mesma partida em
outro worker do uvicorn. Zona vazia passa em qualquer serialização, então o
estado sob teste é o de `fake_match_in_progress`: todas as zonas ocupadas,
dano, modificadores das duas durações e pilha com dois feitiços.
"""

import json
from typing import Any

import pytest

from apps.game.cards import EffectDuration
from apps.game.match import (
    AttackModifier,
    DamageImmunity,
    HealthModifier,
    Match,
    MatchDocument,
    MatchPhase,
    match_from_document,
    to_match_document,
)
from apps.game.tests.fake_match_state import (
    PLAYER_ONE,
    PLAYER_TWO,
    fake_match_in_progress,
    fake_new_match,
)


@pytest.fixture
def match() -> Match:
    return fake_match_in_progress()


def round_trip(match: Match) -> Match:
    """A volta completa, passando de verdade pelo JSON.

    Serializar e desserializar sem `json.dumps` no meio esconde justamente os
    erros que o JSON introduz — tipo de chave, enum que não é string, tupla
    que vira lista.
    """
    return match_from_document(raw_json(match))


def raw_json(match: Match) -> MatchDocument:
    """O documento como ele sai do Redis: só tipos que o JSON conhece."""
    document: MatchDocument = json.loads(json.dumps(to_match_document(match)))

    return document


def test_a_rebuilt_match_equals_the_original(match: Match) -> None:
    assert round_trip(match) == match


def test_a_rebuilt_new_match_equals_the_original() -> None:
    """Zonas vazias voltam vazias, não ausentes."""
    new_match = fake_new_match()

    assert round_trip(new_match) == new_match


def test_the_document_is_stable_across_the_round_trip(match: Match) -> None:
    assert to_match_document(round_trip(match)) == to_match_document(match)


def test_deck_order_is_preserved(match: Match) -> None:
    """O deck é uma pilha de compra: a ordem é a regra, não decoração."""
    before = [card.card_instance_id for card in match.player(PLAYER_ONE).deck]

    after = [
        card.card_instance_id for card in round_trip(match).player(PLAYER_ONE).deck
    ]

    assert after == before


def test_stack_order_is_preserved(match: Match) -> None:
    """A pilha resolve em LIFO: inverter a ordem inverteria o jogo (§6)."""
    before = [entry.card.card_instance_id for entry in match.stack]

    assert [entry.card.card_instance_id for entry in round_trip(match).stack] == before


def test_accumulated_damage_survives(match: Match) -> None:
    assert round_trip(match).player(PLAYER_ONE).bank[1].damage_taken == 3


def test_modifiers_survive_with_their_types(match: Match) -> None:
    """A união volta pelo discriminante: sem ele, ataque e vida seriam o
    mesmo dicionário."""
    modifiers = round_trip(match).player(PLAYER_ONE).bank[1].modifiers

    assert [type(modifier) for modifier in modifiers] == [
        AttackModifier,
        HealthModifier,
        DamageImmunity,
    ]


def test_modifier_amounts_survive(match: Match) -> None:
    """Imunidade a dano não tem quantidade, e o documento dela também não."""
    modifiers = round_trip(match).player(PLAYER_ONE).bank[1].modifiers

    assert [getattr(modifier, "amount", None) for modifier in modifiers] == [2, 1, None]


def test_modifier_durations_survive(match: Match) -> None:
    """O Fim de Rodada (§8) varre pela duração; perdê-la deixaria buff
    temporário para sempre."""
    modifiers = round_trip(match).player(PLAYER_ONE).bank[1].modifiers

    assert [modifier.duration for modifier in modifiers] == [
        EffectDuration.PERMANENT,
        EffectDuration.PERMANENT,
        EffectDuration.UNTIL_END_OF_ROUND,
    ]


def test_the_instance_counter_survives(match: Match) -> None:
    """Sem isto, uma carta criada depois de uma recarga colidiria com uma
    existente."""
    assert round_trip(match).next_card_instance_id == match.next_card_instance_id


def test_the_phase_comes_back_as_the_enum(match: Match) -> None:
    assert round_trip(match).phase is MatchPhase.ACTION


def test_a_targeted_spell_keeps_its_target(match: Match) -> None:
    target = match.stack[0].target_card_instance_id

    assert round_trip(match).stack[0].target_card_instance_id == target


def test_an_untargeted_spell_stays_untargeted(match: Match) -> None:
    """`None` é ausência de alvo, e precisa ser distinguível de um alvo que
    sumiu."""
    assert round_trip(match).stack[1].target_card_instance_id is None


def test_the_two_players_keep_their_order(match: Match) -> None:
    assert [player.user_id for player in round_trip(match).players] == [
        PLAYER_ONE,
        PLAYER_TWO,
    ]


def test_public_profiles_survive(match: Match) -> None:
    """Quem reconecta precisa do apelido sem consultar o banco de novo."""
    assert round_trip(match).player(PLAYER_TWO).profile["nickname"] == "two"


def test_no_json_object_is_keyed_by_user_id(match: Match) -> None:
    """A armadilha que o modelo anterior tinha: chave de objeto JSON é sempre
    string, e uma busca por `User.id` inteiro erraria em silêncio.

    O formato novo remove a necessidade da conversão em vez de repeti-la —
    então a asserção é sobre a forma, não sobre o comportamento.
    """
    assert not _numeric_keys(raw_json(match))


def test_user_ids_survive_as_integer_values(match: Match) -> None:
    """Eles continuam existindo; o que mudou é que são valores, não chaves."""
    document = raw_json(match)

    assert document["players"][0]["profile"]["user_id"] == PLAYER_ONE
    assert isinstance(document["players"][0]["profile"]["user_id"], int)


def test_players_serialize_as_a_list_not_a_mapping(match: Match) -> None:
    assert isinstance(raw_json(match)["players"], list)


def _numeric_keys(node: Any) -> list[str]:
    """Toda chave de objeto que pareça um identificador, em qualquer nível."""
    if isinstance(node, dict):
        here = [key for key in node if key.isdigit()]

        return here + [k for value in node.values() for k in _numeric_keys(value)]

    if isinstance(node, list):
        return [key for item in node for key in _numeric_keys(item)]

    return []


def test_the_seed_survives_the_round_trip(match: Match) -> None:
    """Sem a semente, o worker que recebe o mulligan não continua a mesma
    sequência de sorteios -- ele começa outra."""
    assert round_trip(match).random_seed == match.random_seed


def test_the_roll_counter_survives_the_round_trip(match: Match) -> None:
    """E sem o ordinal, ele repetiria o fluxo que já foi gasto."""
    match.mint_roll()
    match.mint_roll()

    assert round_trip(match).next_roll_ordinal == match.next_roll_ordinal


def test_the_pending_mulligan_survives_the_round_trip() -> None:
    """A espera precisa atravessar o Redis: as duas respostas chegam por
    conexões diferentes, possivelmente em workers diferentes."""
    match = fake_new_match()
    match.players[0].mulligan_taken = True

    assert round_trip(match).awaiting_mulligan_user_ids == (PLAYER_TWO,)


def test_an_absent_token_holder_comes_back_absent(match: Match) -> None:
    """`None` não pode voltar como zero nem sumir do documento: é o que
    distingue o meio do setup de uma partida já sorteada."""
    match.token_holder_user_id = None
    match.priority_user_id = None

    reloaded = round_trip(match)

    assert reloaded.token_holder_user_id is None
    assert reloaded.priority_user_id is None
