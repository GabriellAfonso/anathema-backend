"""Partidas montadas pelo setup da §3, prontas para teste.

Diferente de `fake_match_state.py`, que monta zonas na mão para exercitar o
estado: aqui a partida sai do motor de verdade, com deck embaralhado e mão de
4. É o que os testes de store, de consumer e de determinismo precisam.

O deck é o de andaime do catálogo do MVP, e a semente é fixa: uma partida
montada duas vezes por estas funções é a mesma partida, exceto pelo `match_id`,
que é sorteado fora do controle da semente.
"""

from apps.game.cards import mvp_catalog, starter_deck
from apps.game.engine import MatchEntry, record_mulligan, start_match
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
) -> Match:
    """Partida na espera do mulligan: decks embaralhados, mãos de 4.

    >>> fake_started_match().phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    """
    catalog = mvp_catalog()
    deck = starter_deck(catalog)

    return start_match(
        MatchEntry(profile=fake_player_data(user_id_one, "one"), deck=deck),
        MatchEntry(profile=fake_player_data(user_id_two, "two"), deck=deck),
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
) -> Match:
    """Setup fechado: os dois trocaram 0 cartas, o token já foi sorteado.

    Trocar 0 é a escolha mais barata que ainda é resposta completa -- o que
    interessa a quem chama isto é a partida do outro lado da espera.

    >>> fake_match_ready_for_upkeep().phase
    <MatchPhase.UPKEEP: 'upkeep'>
    """
    source = randomness or ScriptedRandomSource()
    match = fake_started_match(user_id_one, user_id_two, randomness=source, seed=seed)

    record_mulligan(match, user_id_one, [], randomness=source)
    record_mulligan(match, user_id_two, [], randomness=source)

    return match
