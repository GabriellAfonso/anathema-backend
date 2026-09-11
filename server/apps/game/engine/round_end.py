"""O Fim de Rodada da §8: a fase automática que fecha a rodada e devolve a
partida ao Upkeep.

Quatro passos, na ordem da nota:

    1. remove das unidades no banco dos dois jogadores todo modificador marcado
       como "até o fim da rodada"
    2. o token de ataque passa para o outro jogador
    3. a rodada sobe 1
    4. volta para o Upkeep

Executar o Upkeep **não** é daqui. A §8 termina pondo a partida em `UPKEEP`, e
quem atravessa é a cascata de `round_cycle`. Encadear as duas por dentro faria a
§8 dona da §4, e tornaria impossível testar o Fim de Rodada sem executar um
Upkeep junto.

Dano acumulado não é varrido: ele não é modificador, não expira, e mora em
`BankUnit.damage_taken` justamente para não ser confundido com um.

Não existe descarte por excesso de mão. O teto de 10 é aplicado na compra (§9),
e a própria §8 registra isso.

A varredura nasceu na feature 005, antes de existir feitiço que criasse um
modificador temporário, e foi testada com um modificador posto à mão -- senão a
feature de feitiço teria de voltar aqui.
"""

from apps.game.cards import EffectDuration
from apps.game.match import (
    Match,
    MatchPhase,
    NotAParticipantError,
    PlayerState,
    UnitModifier,
)


def end_round(match: Match) -> None:
    """A §8, na ordem dela.

    >>> end_round(match)
    >>> match.phase
    <MatchPhase.UPKEEP: 'upkeep'>
    """
    for player in match.players:
        _sweep_expired_modifiers(player)

    _swap_token(match)

    match.round_number += 1
    match.phase = MatchPhase.UPKEEP


def _sweep_expired_modifiers(player: PlayerState) -> None:
    """Passo 1 da §8, num banco só. `damage_taken` não é tocado."""
    for unit in player.bank:
        unit.modifiers = _lasting_modifiers(unit.modifiers)


def _lasting_modifiers(modifiers: list[UnitModifier]) -> list[UnitModifier]:
    """Os que sobrevivem à rodada. Lista nova, para não mutar durante a leitura."""
    return [
        modifier
        for modifier in modifiers
        if modifier.duration is not EffectDuration.UNTIL_END_OF_ROUND
    ]


def _swap_token(match: Match) -> None:
    """Passo 2 da §8: o token passa para o outro jogador.

    O `None` é estado corrompido, não fluxo: o Fim de Rodada só é alcançável a
    partir da Fase de Ação, que só existe depois do sorteio do token na §3.
    Recusa em vez de `assert` -- que some com `-O` -- e em vez de `cast`, que
    calaria o mypy sem responder a pergunta.
    """
    holder = match.token_holder_user_id

    if holder is None:
        raise NotAParticipantError(holder, match.match_id)

    match.token_holder_user_id = match.opponent_of(holder).user_id
