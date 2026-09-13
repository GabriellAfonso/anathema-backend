"""O disparo: uma linha nos dois caminhos que podem terminar uma partida.

Chamado **depois** da gravação de estado bem-sucedida, e depois da entrega do
estado final aos dois jogadores. As duas ordens são escolha:

- depois da gravação, porque dentro de `MatchStore.mutate` a mudança é reaplicada
  quando o compare-and-swap perde a disputa de versão -- uma escrita de banco lá
  dentro aconteceria duas vezes numa retentativa que é **rotina**, não exceção;
- depois da entrega, porque o jogador ver o fim da partida não pode depender de o
  banco estar de pé.

Nunca levanta. Uma falha aqui é uma linha a menos no histórico; uma falha que
subisse viraria recusa de uma jogada que já foi aplicada e já foi entregue.
"""

import json
import logging

from apps.game.match import Match
from apps.game.match.store import StoredMatch
from apps.game.wall_clock import EpochMillis

from .finished_match import finished_match
from .recorder import FinishedMatchRecorder

logger = logging.getLogger(__name__)


async def record_finished_match(
    recorder: FinishedMatchRecorder,
    before: Match,
    stored: StoredMatch,
    *,
    ended_at: EpochMillis,
) -> None:
    """Grava o resultado se **esta** gravação terminou a partida.

    Não fez nada quando não houve transição -- é o que impede a observação de
    uma partida já terminada de virar um segundo registro.

    >>> await record_finished_match(recorder, before, stored, ended_at=now)
    """
    finished = finished_match(before, stored.match, ended_at)

    if finished is None:
        return

    try:
        await recorder.record(finished)
    except Exception as failure:
        _log_failure(stored.match.match_id, failure)


def _log_failure(match_id: str, failure: Exception) -> None:
    """A partida acabou e ninguém vai saber depois. Isso merece log, não silêncio."""
    logger.error(
        json.dumps(
            {
                "event": "match_record_failed",
                "match_id": match_id,
                "error": type(failure).__name__,
                "detail": str(failure),
            }
        )
    )
