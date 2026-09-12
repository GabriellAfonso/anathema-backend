"""Relógio que o teste dita, no lugar do relógio do sistema.

Nenhum cenário do relógio da vez (§15) pode esperar 45 segundos de verdade: o
tempo chega por parâmetro, como a aleatoriedade já chega, e aqui o teste escolhe
o instante e o avanço. Todo cenário roda instantâneo e repetível.
"""

from apps.game.wall_clock import EpochMillis, WallClock

# Um instante longe de zero, para que prazo calculado a partir daqui nunca fique
# negativo e nenhum teste passe por acidente comparando com 0.
DEFAULT_START_MS = 1_700_000_000_000


class FakeWallClock:
    """Mesma superfície de `WallClock`, com o instante que o teste manda.

    >>> clock = FakeWallClock()
    >>> clock.advance(1.5) - clock.now_ms()
    0
    """

    def __init__(self, start_ms: int = DEFAULT_START_MS) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> EpochMillis:
        return EpochMillis(self._now_ms)

    def advance(self, seconds: float) -> EpochMillis:
        """Adianta o relógio e devolve o instante novo.

        Devolve em vez de só mudar porque quase todo teste do relógio precisa do
        instante logo depois, para passá-lo ao ticker.

        >>> FakeWallClock(1000).advance(1.5)
        2500
        """
        self._now_ms += round(seconds * 1000)

        return self.now_ms()

    def set_ms(self, ms: int) -> EpochMillis:
        """Põe o relógio num instante exato, para prazo lido de um estado.

        >>> FakeWallClock().set_ms(42)
        42
        """
        self._now_ms = ms

        return self.now_ms()


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição, e esta é a única do arquivo. Sem ela, o
# dia em que `WallClock` ganhar um método o fake fica para trás em silêncio e só
# quebra na cara de quem for injetá-lo. Não apague por parecer sobra.
FAKE_WALL_CLOCK_MATCHES_THE_PROTOCOL: WallClock = FakeWallClock()
