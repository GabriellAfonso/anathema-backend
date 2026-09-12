"""O prazo da vez e o do mulligan, como a partida os guarda (§15).

Estado de transporte que viaja **dentro** do documento da partida. As duas
conexões podem estar em workers diferentes do uvicorn, e um prazo que morasse no
processo morreria com o worker que o armou -- justamente no caso que o relógio
existe para resolver, o do jogador que some. Aqui ele é gravado junto do estado,
na mesma escrita atômica, e qualquer worker o lê.

Nada aqui é regra, como em todo o pacote `match`: o motor não lê tempo (§15) e
não conhece este módulo. Quem abre e fecha vez é `protocol/turn_clock.py`; quem
decide o que venceu é `protocol/clock_events.py`.
"""

from dataclasses import dataclass

from apps.game.wall_clock import EpochMillis


@dataclass(frozen=True, slots=True)
class TurnDeadline:
    """A vez atual: de quem é, quando avisa e quando estoura.

    Congelada: mudar o prazo é trocar o objeto inteiro, e assim nenhuma parte do
    transporte altera meia vez enquanto outra a lê.

    `turn_number` é a **identidade** da vez, e é o que um estouro atrasado
    compara para não agir sobre uma vez que não é a dele. `round_number` mora
    aqui porque a vez muda de identidade quando a rodada vira, mesmo com o mesmo
    dono -- a cascata dos dois passes devolve a vez a quem passou por último.

    >>> deadline.turn_number
    3
    """

    turn_number: int
    holder_user_id: int
    round_number: int
    warns_at_ms: EpochMillis
    expires_at_ms: EpochMillis
    # Gravado, e não deduzido do instante: o índice de despertar é recalculado a
    # cada escrita, então sem esta marca uma jogada aos 40s traria o aviso de
    # volta e o jogador o receberia duas vezes.
    warning_sent: bool = False


@dataclass(frozen=True, slots=True)
class MatchClock:
    """Os prazos da partida: a vez, ou o mulligan, ou nenhum dos dois.

    Os dois nunca correm juntos: o mulligan da §3 acontece antes da Rodada 1, e
    a primeira vez começa na mesma mutação que o fecha.

    `None` nos dois não é valor de espera: partida terminada não tem prazo, e
    afirmar um seria mentir num campo que o cliente desenha.

    >>> IDLE_MATCH_CLOCK.turn is None
    True
    """

    turn: TurnDeadline | None = None
    mulligan_expires_at_ms: EpochMillis | None = None


# Partida sem prazo nenhum: antes de o mulligan ser armado, e depois do fim.
IDLE_MATCH_CLOCK = MatchClock()


def clock_wake_at(clock: MatchClock) -> EpochMillis | None:
    """O próximo instante em que esta partida precisa de alguém olhando.

    É o score do índice de despertar do `MatchStore`, derivado do estado e nunca
    gravado ao lado dele: duas fontes poderiam divergir, e divergência aqui é
    uma vez que nunca estoura.

    >>> clock_wake_at(IDLE_MATCH_CLOCK) is None
    True
    """
    if clock.turn is not None:
        return _turn_wake_at(clock.turn)

    return clock.mulligan_expires_at_ms


def _turn_wake_at(turn: TurnDeadline) -> EpochMillis:
    """O aviso primeiro; depois de avisada, o estouro.

    >>> _turn_wake_at(turn).__class__.__name__
    'int'
    """
    if turn.warning_sent:
        return turn.expires_at_ms

    return turn.warns_at_ms
