"""O que uma partida terminada produz, derivado do estado e de mais nada.

Puro: não conhece banco, não conhece Redis, não decide regra. Recebe a partida
de antes e a de depois de **uma** gravação de estado e responde uma pergunta só
-- esta gravação terminou a partida?

É aí que mora o "exatamente uma vez". A pergunta é sobre uma **transição**, e
uma transição acontece uma vez: a partida que já estava terminada em `before`
devolve `None`, quantas vezes for lida. Nenhuma observação -- a entrega do
estado final aos dois jogadores, a reconexão, a consulta de estado -- tem como
produzir registro, porque nenhuma delas tem uma transição para mostrar.

A mesma condição já existe em `protocol/match_events.py`, que a usa para montar
o evento `match_finished` do frame do cliente. É uma linha, e é copiada de
propósito: reusar aquele tipo amarraria o formato do banco ao contrato do
cliente, e os dois mudariam juntos sem precisar.
"""

from dataclasses import dataclass

from apps.game.cards import CardId
from apps.game.match import Match, MatchEndReason, PlayerState
from apps.game.wall_clock import EpochMillis

MILLIS_PER_SECOND = 1000


@dataclass(frozen=True, slots=True)
class FinishedSide:
    """Um dos dois lados da partida terminada, como ele ficou.

    >>> side.deck_name
    'Agro'
    """

    user_id: int
    final_nexus: int
    deck_name: str
    deck_card_ids: tuple[CardId, ...]


@dataclass(frozen=True, slots=True)
class FinishedMatch:
    """Uma partida terminada, pronta para virar linha no banco.

    **Não existe campo de empate** e não existe abandono: os dois lados são
    nomeados vencedor e derrotado, porque a §10 nomeia um derrotado só.

    >>> finished.reason
    <MatchEndReason.FORFEIT: 'forfeit'>
    """

    match_id: str
    reason: MatchEndReason
    winner: FinishedSide
    loser: FinishedSide
    started_at: EpochMillis
    ended_at: EpochMillis
    final_round: int

    @property
    def duration_seconds(self) -> int:
        """Quanto a partida durou, em segundos inteiros.

        Derivada, nunca gravada em campo próprio: dois campos com o mesmo fato
        podem divergir, e o que soma em `PlayerStats.play_time` tem de ser o
        mesmo que a linha guarda.

        `max(0, ...)` porque um relógio de parede pode andar para trás entre
        dois workers; duração negativa não é fato do jogo, é ruído de relógio.

        >>> finished.duration_seconds
        742
        """
        elapsed = self.ended_at - self.started_at

        return max(0, elapsed // MILLIS_PER_SECOND)


def finished_match(
    before: Match, after: Match, ended_at: EpochMillis
) -> FinishedMatch | None:
    """O que gravar, ou `None` se esta gravação não terminou a partida.

    `None` em três casos, todos o mesmo fato -- não houve transição: a partida
    continua em andamento, ela já estava terminada antes, ou a gravação não
    mexeu no desfecho.

    >>> finished_match(before, after, EpochMillis(1700000000000)).final_round
    8
    """
    outcome = after.outcome

    if outcome is None or before.outcome is not None:
        return None

    loser = after.player(outcome.defeated_user_id)

    return FinishedMatch(
        match_id=after.match_id,
        reason=outcome.reason,
        # O vencedor é o outro jogador, derivado -- `MatchOutcome` não tem campo
        # de vencedor de propósito, e acrescentar um aqui seria a segunda fonte
        # que ele recusa.
        winner=_side_of(after.opponent_of(outcome.defeated_user_id)),
        loser=_side_of(loser),
        started_at=after.started_at or ended_at,
        ended_at=ended_at,
        final_round=after.round_number,
    )


def _side_of(player: PlayerState) -> FinishedSide:
    """Um lado, com o deck da entrada na fila.

    Deck ausente é a partida gravada antes da feature 012 e ainda dentro do TTL
    de 6 horas: registra com lista vazia e sem nome, em vez de recusar e
    derrubar uma partida em curso numa implantação.
    """
    chosen = player.chosen_deck

    return FinishedSide(
        user_id=player.user_id,
        final_nexus=player.nexus,
        deck_name="" if chosen is None else chosen.name,
        deck_card_ids=() if chosen is None else chosen.card_ids,
    )
