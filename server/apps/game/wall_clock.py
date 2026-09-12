"""Que horas são, atrás de uma interface do projeto.

Único módulo do projeto que importa `time`. O instante chega por parâmetro a
quem precisa dele, atrás do `Protocol` daqui, para que um teste possa ditar o
relógio sem esperar 45 segundos de verdade -- é a mesma escolha de
`randomness.py`, e pela mesma razão: o que o servidor faz precisa ser repetível.

Milissegundos inteiros desde a época, e não `datetime`: o instante atravessa o
JSON do documento da partida e o score de um sorted set do Redis sem conversão
nenhuma, e prazos somam sem fuso horário no caminho.

O motor não conhece este módulo. Ele não lê tempo (Fluxo de Partida §15), e
`test_engine_reads_no_time.py` reprova quem tentar.

>>> SystemWallClock().now_ms() > 0
True
"""

import time
from typing import NewType, Protocol

# Um instante, em milissegundos desde a época. `NewType` pelo mesmo motivo de
# `CardInstanceId` e `RandomSeed`: passar uma duração onde se espera um instante
# vira erro de mypy, e os dois são `int`.
EpochMillis = NewType("EpochMillis", int)

NANOS_PER_MILLI = 1_000_000


class WallClock(Protocol):
    """O instante atual, atrás de uma interface do projeto.

    É `Protocol` e não classe base para que um substituto de teste só precise do
    método, sem herdar de nada -- a mesma escolha de `RandomSource` e de
    `CardCatalog`.
    """

    def now_ms(self) -> EpochMillis:
        """O instante agora.

        >>> clock.now_ms()
        1700000000000
        """
        ...


class SystemWallClock:
    """`WallClock` sobre o relógio do sistema.

    Sem estado próprio: a mesma instância serve qualquer partida e qualquer
    worker, e o ponto de composição pode ter uma só.

    `time.time_ns()` e não `time.time()`: o `float` de segundos já perde
    precisão de milissegundo em datas atuais, e o que este projeto compara são
    prazos de 30 e 45 segundos.

    >>> SystemWallClock().now_ms() % 1 == 0
    True
    """

    def now_ms(self) -> EpochMillis:
        return EpochMillis(time.time_ns() // NANOS_PER_MILLI)
