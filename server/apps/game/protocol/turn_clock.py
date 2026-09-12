"""Quando começa vez nova, e quando o relógio do mulligan é armado (§15).

Puro: recebe a partida já mudada e o instante, e troca `match.clock`. Não lê
Redis, não manda frame, e o motor não o conhece -- é chamado no fim de toda
mutação, dentro da mesma gravação atômica.

A §15 diz que o relógio é **da vez, não da ação**: feitiço, mandar e puxar
atacante e atribuir ou remover bloqueador não reiniciam nada. Aqui isso não é
uma lista de ações que não contam; é a consequência de uma pergunta só -- **o
par (dono da vez, rodada) mudou?**

A rodada faz parte da identidade porque a cascata dos dois passes devolve a vez
a quem passou por último: ele não tinha o token, recebe o token na troca da §8,
e o Upkeep da §4 dá a prioridade ao dono do token. Sem a rodada na identidade, o
passe por estouro abriria a rodada seguinte já vencida, e o mesmo jogador
estouraria de novo na hora, em laço.
"""

from apps.game.match import (
    IDLE_MATCH_CLOCK,
    Match,
    MatchClock,
    MatchPhase,
    TurnDeadline,
)
from apps.game.wall_clock import EpochMillis

# Fluxo de Partida §12: 30s de aviso, mais 15s até o estouro, e 30s no mulligan.
# Fixas por decisão da spec: não se configuram por partida nem por modo.
TURN_WARNING_MS = 30_000
TURN_EXPIRY_MS = 45_000
MULLIGAN_EXPIRY_MS = 30_000

# As três fases em que alguém deve a jogada (§5, §7.1, §7.2). As automáticas não
# aparecem porque a cascata nunca devolve a partida numa delas, e `MULLIGAN` tem
# prazo próprio, por jogador.
_PHASES_WITH_A_TURN = frozenset(
    {MatchPhase.ACTION, MatchPhase.DECLARATION, MatchPhase.COMBAT}
)


class MatchHasNoPriorityError(Exception):
    """Fase que espera jogador, e ninguém na prioridade.

    Estado corrompido, não fluxo normal: `ACTION`, `DECLARATION` e `COMBAT` só
    são alcançáveis depois do sorteio da §3. Recusa nomeada em vez de `assert`,
    que some com `-O`, pela mesma razão de `round_end._swap_token`.
    """

    def __init__(self, phase: MatchPhase, match_id: str) -> None:
        super().__init__(
            f"match {match_id!r} is in phase '{phase}' with no priority: "
            f"expected a player to owe the play"
        )
        self.phase = phase
        self.match_id = match_id


def opening_match_clock(now: EpochMillis) -> MatchClock:
    """O relógio de uma partida recém-criada: só o prazo do mulligan (§3).

    Conta da criação, e não da conexão de cada jogador: o relógio não pode
    depender de socket aberto, e é na criação que o `match_found` sai para os
    dois.

    >>> opening_match_clock(EpochMillis(1000)).mulligan_expires_at_ms
    31000
    """
    return MatchClock(mulligan_expires_at_ms=EpochMillis(now + MULLIGAN_EXPIRY_MS))


def advance_match_clock(match: Match, now: EpochMillis) -> None:
    """Abre vez nova se a mudança trocou a vez de mão, e para o relógio no fim.

    Chamada no fim de **toda** mutação -- jogada do socket ou estouro do
    relógio.

    >>> advance_match_clock(match, EpochMillis(1000))
    >>> match.clock.turn.expires_at_ms
    46000
    """
    if match.phase is MatchPhase.FINISHED:
        match.clock = IDLE_MATCH_CLOCK
        return

    if match.phase not in _PHASES_WITH_A_TURN or _is_the_same_turn(match):
        return

    match.clock = MatchClock(turn=_next_turn(match, now))


def _is_the_same_turn(match: Match) -> bool:
    """A vez gravada ainda é a que a partida espera?

    Ir da Fase de Ação para a Declaração e voltar dela não muda o par, e é por
    isso que declarar e puxar o último atacante não reiniciam o relógio.
    """
    turn = match.clock.turn

    if turn is None:
        return False

    return (turn.holder_user_id, turn.round_number) == (
        match.priority_user_id,
        match.round_number,
    )


def _next_turn(match: Match, now: EpochMillis) -> TurnDeadline:
    """A vez seguinte, numerada a partir da que estava lá."""
    previous = match.clock.turn
    holder_user_id = match.priority_user_id

    if holder_user_id is None:
        raise MatchHasNoPriorityError(match.phase, match.match_id)

    return TurnDeadline(
        turn_number=previous.turn_number + 1 if previous is not None else 1,
        holder_user_id=holder_user_id,
        round_number=match.round_number,
        warns_at_ms=EpochMillis(now + TURN_WARNING_MS),
        expires_at_ms=EpochMillis(now + TURN_EXPIRY_MS),
    )
