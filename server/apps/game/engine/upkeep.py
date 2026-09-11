"""O Upkeep da §4: a fase automática que reabastece a partida a cada volta.

Roda no início de toda rodada, inclusive a primeira, e não aceita input de
jogador nenhum. Para os dois jogadores: a energia soma o ganho da rodada -- a
rodada N dá N -- ao que sobrou, até o teto de 10, e cada um compra 1 carta pela
regra da §9.

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

# Fluxo de Partida §12. Mora aqui, e não em `player_state.py`, porque aplicá-lo
# é regra -- e aquele arquivo diz isso de si mesmo. A energia começa em 0, e é o
# primeiro Upkeep que faz a rodada 1 ter 1.
MAX_ENERGY = 10


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
        _gain_energy(player, match.round_number)
        draw_card(match, player.user_id, randomness=randomness)

    _open_action_phase(match)


def _gain_energy(player: PlayerState, round_number: int) -> None:
    """Soma o ganho da rodada ao que sobrou, com teto (§4).

    Fluxo de Partida, corrigido em 2026-09-11: energia acumula. Até então a
    rodada recarregava até uma máxima que subia 1 por rodada, e o que sobrava se
    perdia -- por isso existia um campo de máxima, que deixou de ter o que
    guardar. Quem gasta tudo começa cada rodada com 1, 2, 3...; quem guarda
    tudo, com 1, 3, 6 e 10.

    >>> _gain_energy(player, 2)  # sobrou 1 da rodada 1
    >>> player.energy_current
    3
    """
    player.energy_current = min(player.energy_current + round_number, MAX_ENERGY)


def _open_action_phase(match: Match) -> None:
    """Os quatro passos que a §4 manda depois dos dois jogadores.

    O token volta a estar disponível mesmo nesta feature, em que nada o consome:
    a §4 manda, e a feature de combate encontra o campo já correto.
    """
    match.token_consumed = False
    match.consecutive_passes = 0
    match.priority_user_id = match.token_holder_user_id
    match.phase = MatchPhase.ACTION
