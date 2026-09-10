"""O Upkeep da §4: a fase automática que reabastece a partida a cada volta.

Roda no início de toda rodada, inclusive a primeira, e não aceita input de
jogador nenhum. Para os dois jogadores: a energia máxima sobe 1 até o teto de
10, a atual passa a ser a máxima -- recarga total, o que sobrou da rodada
anterior é perdido --, e cada um compra 1 carta pela regra da §9.

A ordem em que os dois são resolvidos é a do par, e é garantia, não acaso. O que
a §4 promete é **independência**: nenhum passo do Upkeep de um jogador lê o
estado do outro. A ordem existe, é sempre a mesma, e é o que torna reproduzível
um Upkeep em que os dois resetam o deck -- os dois resets consomem o contador de
sorteios da partida, e sem ordem fixa qual pega qual ponto da sequência
dependeria de quem fosse resolvido primeiro.

Ordenar por `user_id`, por prioridade ou por dono do token amarraria a sequência
de sorteios a um campo que muda de rodada para rodada. Por isso é `match.players`
e nada mais.

Este módulo não valida a fase de entrada. Quem chama é `round_cycle`: ou o
primeiro empurrão, que valida, ou a cascata, que só chega aqui vinda do Fim de
Rodada.
"""

from apps.game.match import Match, MatchPhase, PlayerState
from apps.game.randomness import RandomSource

from .card_draw import draw_card

# Fluxo de Partida §12. Moram aqui, e não em `player_state.py`, porque aplicá-los
# é regra -- e aquele arquivo diz isso de si mesmo. `energy_max` começa em 0, e é
# o primeiro Upkeep que faz a rodada 1 ter 1 de energia.
MAX_ENERGY = 10
ENERGY_PER_ROUND = 1


def run_upkeep(match: Match, *, randomness: RandomSource) -> None:
    """A §4 inteira: recarga e compra dos dois, e a partida entra em Ação.

    A compra passa pela regra da §9 da feature 004, sem cópia e sem variante.
    Um jogador com a mão cheia não compra, e o Upkeep segue: `draw_card`
    devolve `None`, que não é erro.

    >>> run_upkeep(match, randomness=source)
    >>> match.players[0].energy_current
    1
    """
    for player in match.players:
        _refill_energy(player)
        draw_card(match, player.user_id, randomness=randomness)

    _open_action_phase(match)


def _refill_energy(player: PlayerState) -> None:
    """Sobe a máxima com teto, e recarrega a atual até ela.

    A atual é atribuída, nunca somada: energia não acumula (§4), e somar deixaria
    a rodada 11 de um jogador econômico com mais de 10.
    """
    player.energy_max = min(player.energy_max + ENERGY_PER_ROUND, MAX_ENERGY)
    player.energy_current = player.energy_max


def _open_action_phase(match: Match) -> None:
    """Os quatro passos que a §4 manda depois dos dois jogadores.

    O token volta a estar disponível mesmo nesta feature, em que nada o consome:
    a §4 manda, e a feature de combate encontra o campo já correto.
    """
    match.token_consumed = False
    match.consecutive_passes = 0
    match.priority_user_id = match.token_holder_user_id
    match.phase = MatchPhase.ACTION
