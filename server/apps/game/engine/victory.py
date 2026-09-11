"""A §10: as duas saídas da partida, e a única porta que escreve Nexus.

As duas saídas passam por `_finish_match`, o único ponto do código que escreve
o par (resultado, fase terminal):

- um Nexus chega a zero -- `change_nexus` altera e apura em seguida, e
  `check_victory` só apura;
- um jogador desiste -- `forfeit`, a qualquer momento, na vez dele ou não.

**Não existe empate** (Fluxo de Partida, corrigido em 2026-09-11). É impossível
por construção: só o dano de combate leva um Nexus a zero, e ele só atinge o
defensor; o SACRIFICIAL FIRE para em 1 (§14). Por isso a apuração nomeia um
derrotado só, e dois Nexus a zero ao mesmo tempo é estado corrompido, que
levanta em vez de escolher um.

Até a correção existia uma terceira porta, que alterava vários Nexus antes de
apurar uma vez, para que o dano de combate pudesse empatar. Sem empate ela
deixou de ter o que proteger, e o combate usa `change_nexus` no Nexus do
defensor.

O Nexus não tem teto. O 20 da §12 é o valor **inicial**, não um limite, e a
sessão de esclarecimento da feature 006 fixou que a cura pode ultrapassá-lo.
"""

from apps.game.match import (
    Match,
    MatchEndReason,
    MatchOutcome,
    MatchPhase,
    PlayerState,
)

from .action_kind import ActionKind
from .player_action import MatchIsOverError


class SimultaneousDefeatError(Exception):
    """Os dois Nexus estão em zero ou menos ao mesmo tempo.

    Estado corrompido, não jogada: a §10 diz que não existe empate e que nenhuma
    regra do jogo leva os dois a zero. Recusa nomeada em vez de escolher um
    derrotado, porque escolher esconderia o bug que produziu o estado.

    >>> raise SimultaneousDefeatError((7, 9), "m-1")
    SimultaneousDefeatError: users (7, 9) of match 'm-1' are all at nexus 0 or
    below: expected at most one, there is no draw
    """

    def __init__(self, user_ids: tuple[int, ...], match_id: str) -> None:
        super().__init__(
            f"users {user_ids} of match {match_id!r} are all at nexus 0 or "
            f"below: expected at most one, there is no draw"
        )
        self.user_ids = user_ids
        self.match_id = match_id


def change_nexus(match: Match, player: PlayerState, amount: int) -> None:
    """Altera o Nexus de um jogador e apura a §10 em seguida.

    `amount` é assinado: LIFE POTION soma; SACRIFICIAL FIRE e o dano de combate
    subtraem. Sem teto -- ver o cabeçalho do módulo.

    >>> change_nexus(match, caster, -8)
    >>> caster.nexus
    12
    """
    _add_to_nexus(player, amount)
    check_victory(match)


def _add_to_nexus(player: PlayerState, amount: int) -> None:
    """Único ponto do código que escreve Nexus.

    Privado pela mesma razão de `_finish_match`: um ponto só de escrita é o que
    impede uma alteração de Nexus de acontecer sem passar pela §10.
    """
    player.nexus += amount


def check_victory(match: Match) -> None:
    """A §10 por Nexus: quem está em zero ou menos perde.

    Idempotente: uma partida já terminada não muda de resultado, e chamar de
    novo não faz nada. É o que impede um efeito posterior de reescrever um
    desfecho já apurado.

    >>> check_victory(match)
    >>> match.outcome.reason
    <MatchEndReason.NEXUS_DEPLETED: 'nexus_depleted'>
    """
    if match.is_over:
        return

    # A §10 escreve "Nexus <= 0", e o zero é a regra, não um valor calibrável
    # como os da §12. Por isso é literal, e não constante nomeada.
    defeated = tuple(player.user_id for player in match.players if player.nexus <= 0)

    if not defeated:
        return

    if len(defeated) > 1:
        raise SimultaneousDefeatError(defeated, match.match_id)

    _finish_match(match, defeated[0], MatchEndReason.NEXUS_DEPLETED)


def forfeit(match: Match, user_id: int) -> None:
    """A desistência da §10: o jogador perde, e o oponente vence na hora.

    Porta própria, e não um braço de `PlayerAction`: a §10 permite desistir "a
    qualquer momento da partida, na vez dele ou não, inclusive no mulligan", e
    toda ação da união passa pela guarda de prioridade e pela de fase. Das três
    guardas comuns, só a de participante e a de partida terminada valem aqui.

    Não mexe em mais nada: mão, banco, combate aberto e mulligan pendente ficam
    congelados onde estavam, como fica a partida que acaba por Nexus.

    >>> forfeit(match, 9)
    >>> match.outcome
    MatchOutcome(defeated_user_id=9, reason=<MatchEndReason.FORFEIT: 'forfeit'>)
    """
    match.player(user_id)

    if match.is_over:
        raise MatchIsOverError(ActionKind.FORFEIT, match.outcome, match.match_id)

    _finish_match(match, user_id, MatchEndReason.FORFEIT)


def _finish_match(match: Match, defeated_user_id: int, reason: MatchEndReason) -> None:
    """Único ponto que escreve o par (resultado, fase terminal).

    Privado de propósito: a invariante `outcome is not None` ⟺ `phase is
    FINISHED` vale porque existe um lugar só onde ela pode ser quebrada.
    """
    match.outcome = MatchOutcome(defeated_user_id=defeated_user_id, reason=reason)
    match.phase = MatchPhase.FINISHED
