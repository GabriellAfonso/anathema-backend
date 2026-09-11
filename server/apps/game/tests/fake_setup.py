"""Partidas montadas pelo setup da §3, prontas para teste.

Diferente de `fake_match_state.py`, que monta zonas na mão para exercitar o
estado: aqui a partida sai do motor de verdade, com deck embaralhado e mão de
4. É o que os testes de store, de consumer e de determinismo precisam.

O deck é o de andaime do catálogo do MVP, a menos que o teste passe outro, e a
semente é fixa: uma partida
montada duas vezes por estas funções é a mesma partida, exceto pelo `match_id`,
que é sorteado fora do controle da semente.
"""

from apps.game.cards import Deck, mvp_catalog, starter_deck
from apps.game.engine import (
    MatchEntry,
    begin_round_cycle,
    record_mulligan,
    start_match,
)
from apps.game.match import Match
from apps.game.randomness import RandomSeed, RandomSource
from apps.game.tests.fake_player_data import fake_player_data
from apps.game.tests.fake_random_source import ScriptedRandomSource

FAKE_SETUP_SEED = RandomSeed("fake-setup-seed")


def fake_started_match(
    user_id_one: int = 7,
    user_id_two: int = 9,
    *,
    randomness: RandomSource | None = None,
    seed: RandomSeed = FAKE_SETUP_SEED,
    deck: Deck | None = None,
) -> Match:
    """Partida na espera do mulligan: decks embaralhados, mãos de 4.

    >>> fake_started_match().phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    """
    catalog = mvp_catalog()
    chosen = deck if deck is not None else starter_deck(catalog)

    return start_match(
        MatchEntry(profile=fake_player_data(user_id_one, "one"), deck=chosen),
        MatchEntry(profile=fake_player_data(user_id_two, "two"), deck=chosen),
        catalog=catalog,
        randomness=randomness or ScriptedRandomSource(),
        seed=seed,
    )


def fake_match_ready_for_upkeep(
    user_id_one: int = 7,
    user_id_two: int = 9,
    *,
    randomness: RandomSource | None = None,
    seed: RandomSeed = FAKE_SETUP_SEED,
    deck: Deck | None = None,
) -> Match:
    """Setup fechado: os dois trocaram 0 cartas, o token já foi sorteado.

    Trocar 0 é a escolha mais barata que ainda é resposta completa -- o que
    interessa a quem chama isto é a partida do outro lado da espera.

    >>> fake_match_ready_for_upkeep().phase
    <MatchPhase.UPKEEP: 'upkeep'>
    """
    source = randomness or ScriptedRandomSource()
    match = fake_started_match(
        user_id_one, user_id_two, randomness=source, seed=seed, deck=deck
    )

    record_mulligan(match, user_id_one, [], randomness=source)
    record_mulligan(match, user_id_two, [], randomness=source)

    return match


def fake_match_in_action_phase(
    user_id_one: int = 7,
    user_id_two: int = 9,
    *,
    randomness: RandomSource | None = None,
    seed: RandomSeed = FAKE_SETUP_SEED,
    deck: Deck | None = None,
) -> Match:
    """Rodada 1 já aberta: o primeiro empurrão dado, esperando ação.

    É o setup fechado mais `begin_round_cycle` -- a partida como o transporte a
    encontra quando o primeiro jogador vai agir.

    >>> fake_match_in_action_phase().phase
    <MatchPhase.ACTION: 'action'>
    """
    source = randomness or ScriptedRandomSource()
    match = fake_match_ready_for_upkeep(
        user_id_one, user_id_two, randomness=source, seed=seed, deck=deck
    )

    begin_round_cycle(match, randomness=source)

    return match
