"""A segunda vida do desfecho: a partida que acaba vira linha no banco.

Três responsabilidades, uma por módulo:

- `finished_match.py` -- **derivar**. Função pura sobre o par (antes, depois):
  esta gravação terminou a partida, ou não? Não conhece banco nem Redis.
- `recorder.py` -- **gravar**. A porta que o caminho de partida enxerga, e a
  implementação de ORM do outro lado dela.
- `record_finished_match.py` -- **disparar**. A linha que os dois caminhos de
  escrita chamam depois de gravar o estado.

Duas fronteiras que este pacote não cruza, e que são a feature inteira:

**O motor não sabe que isto existe.** Ele não conhece banco (Fluxo de Partida) e
continua sem conhecer: nada aqui é importado de `apps.game.engine`.

**Nada aqui roda dentro de `MatchStore.mutate`.** O compare-and-swap relê e
reaplica a mudança quando perde a disputa de versão, e uma escrita de banco lá
dentro aconteceria duas vezes numa retentativa que é rotina, não exceção. A
gravação acontece **depois** da gravação de estado bem-sucedida, e o `match_id`
único no banco é o que faz a corrida que sobra perder em vez de duplicar.
"""

from .finished_match import FinishedMatch, FinishedSide, finished_match
from .record_finished_match import record_finished_match
from .recorder import DatabaseFinishedMatchRecorder, FinishedMatchRecorder

__all__ = [
    "FinishedMatch",
    "FinishedSide",
    "finished_match",
    "FinishedMatchRecorder",
    "DatabaseFinishedMatchRecorder",
    "record_finished_match",
]
