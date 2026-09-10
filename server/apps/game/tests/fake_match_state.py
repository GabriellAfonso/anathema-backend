"""Estados de partida prontos para teste, no formato de `fake_player_data.py`.

Montar um estado rico na mão em cada teste espalharia as mesmas trinta linhas
por todo lado, e um estado montado pela metade deixa a ida e volta passar sem
provar nada. Aqui ficam os dois que os testes precisam: a partida recém-criada
e uma com todas as zonas ocupadas.

Os `card_id` são valores das faixas do catálogo, mas nada aqui os resolve — o
estado guarda o identificador, e quem quer o molde consulta o catálogo.
"""

from collections.abc import Sequence

from apps.game.cards import CardId, EffectDuration
from apps.game.randomness import RandomSeed
from apps.game.match import (
    AttackModifier,
    BankUnit,
    DamageImmunity,
    HealthModifier,
    Match,
    MatchCard,
    MatchPhase,
    PlayerState,
    StackEntry,
)
from apps.game.tests.fake_player_data import fake_player_data

PLAYER_ONE = 7
PLAYER_TWO = 9
OUTSIDER = 99

# Fixos para que dois estados montados por este arquivo sejam comparáveis
# entre si -- um `uuid4()` e uma semente de entropia real fariam duas partidas
# "iguais" divergirem em dois campos que nenhum teste daqui exercita.
FAKE_MATCH_ID = "fake-match-0001"
FAKE_SEED = RandomSeed("fake-seed")


def fake_new_match(
    user_id_one: int = PLAYER_ONE, user_id_two: int = PLAYER_TWO
) -> Match:
    """Partida de zonas vazias, com os valores iniciais da §2.

    Monta o `Match` diretamente em vez de passar pelo setup da §3: este é um
    fake de **estado**, e os testes que o usam querem preencher as zonas na
    mão. Quem quer uma partida montada pelo setup usa `fake_setup.py`.

    >>> fake_new_match().round_number
    1
    """
    return Match(
        match_id=FAKE_MATCH_ID,
        players=(
            PlayerState(profile=fake_player_data(user_id_one, "one")),
            PlayerState(profile=fake_player_data(user_id_two, "two")),
        ),
        random_seed=FAKE_SEED,
    )


def fake_match_in_progress() -> Match:
    """Partida com todas as zonas ocupadas, dano, modificadores e pilha.

    É o estado que a ida e volta precisa para provar alguma coisa: zona vazia
    passa em qualquer serialização.

    >>> fake_match_in_progress().phase
    <MatchPhase.ACTION: 'action'>
    """
    match = fake_new_match()

    _fill_first_player(match)
    _fill_second_player(match)
    _fill_stack(match)
    _advance_to_mid_round(match)

    return match


def fake_cards(match: Match, card_ids: Sequence[int]) -> list[MatchCard]:
    """Cartas com identidade cunhada pela própria partida, na ordem pedida.

    >>> fake_cards(match, [15, 15])[0].card_instance_id
    1
    """
    return [
        MatchCard(match.mint_card_instance_id(), CardId(card_id))
        for card_id in card_ids
    ]


def _fill_first_player(match: Match) -> None:
    """Duas cópias da carta 15 no banco, uma intacta e uma machucada."""
    player = match.players[0]

    player.deck = fake_cards(match, [31, 32, 33])
    player.hand = fake_cards(match, [22, 15])
    player.bank = [BankUnit(card=card) for card in fake_cards(match, [15, 15])]
    player.graveyard = fake_cards(match, [1004])

    _wound_second_unit(player.bank[1])

    player.nexus = 18
    player.energy_max = 3
    player.energy_current = 1


def _wound_second_unit(unit: BankUnit) -> None:
    """Dano e os dois tipos de duração, para o Fim de Rodada ter o que varrer."""
    unit.damage_taken = 3
    unit.modifiers = [
        AttackModifier(amount=2, duration=EffectDuration.PERMANENT),
        HealthModifier(amount=1, duration=EffectDuration.PERMANENT),
        DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND),
    ]


def _fill_second_player(match: Match) -> None:
    """Valores distintos dos do primeiro, para um teste de visão não passar
    por engano ao trocar os lados."""
    player = match.players[1]

    player.deck = fake_cards(match, [41, 42])
    player.hand = fake_cards(match, [51, 52, 53])
    player.bank = [
        BankUnit(card=card, damage_taken=1) for card in fake_cards(match, [61])
    ]
    player.graveyard = fake_cards(match, [1001, 1002])

    player.nexus = 20
    player.energy_max = 3
    player.energy_current = 3


def _fill_stack(match: Match) -> None:
    """Dois feitiços: o de baixo mira uma unidade, o de cima não mira nada.

    Ordem importa — o fim da lista é o topo, e a resolução é LIFO (§6).
    """
    targeted, untargeted = fake_cards(match, [1002, 1003])
    target = match.players[0].bank[1].card.card_instance_id

    match.stack = [
        StackEntry(
            card=targeted, caster_user_id=PLAYER_TWO, target_card_instance_id=target
        ),
        StackEntry(card=untargeted, caster_user_id=PLAYER_ONE),
    ]


def _advance_to_mid_round(match: Match) -> None:
    """Rodada 3, token com o segundo jogador, um passe já dado."""
    match.round_number = 3
    match.phase = MatchPhase.ACTION
    match.token_holder_user_id = PLAYER_TWO
    match.priority_user_id = PLAYER_ONE
    match.consecutive_passes = 1
