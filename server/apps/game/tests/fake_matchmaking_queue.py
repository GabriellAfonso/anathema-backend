"""A fila em memória, para os testes de socket que não podem tocar o Redis.

A fila de verdade é um par de chaves com scripts Lua, e provar que o pareamento
é indivisível só o Redis de verdade prova -- é o que `test_matchmaking_queue.py`
faz. O que os testes do consumer precisam é outra coisa: quem entrou, com que
deck, e em que ordem.

Guarda `QueueEntry` inteira, com a lista validada, porque é justamente isso que
a feature 011 garante: o que foi validado na entrada é o que sai no par.
"""

from apps.game.matchmaking.queue import QueueEntry


class FakeMatchmakingQueue:
    """Fila FIFO em memória, com a mesma superfície de `MatchmakingQueue`.

    >>> queue = FakeMatchmakingQueue()
    >>> await queue.join(QueueEntry(7, deck)) is None
    True
    >>> (await queue.join(QueueEntry(9, other)))[0].user_id
    7
    """

    def __init__(self) -> None:
        self.waiting: list[QueueEntry] = []

    async def join(self, entry: QueueEntry) -> tuple[QueueEntry, QueueEntry] | None:
        """Entra na fila, trocando a entrada anterior do mesmo jogador."""
        self.waiting = [
            waiter for waiter in self.waiting if waiter.user_id != entry.user_id
        ]
        self.waiting.append(entry)

        if len(self.waiting) < 2:
            return None

        first, second = self.waiting[0], self.waiting[1]
        self.waiting = self.waiting[2:]

        return (first, second)

    async def leave(self, user_id: int) -> None:
        self.waiting = [waiter for waiter in self.waiting if waiter.user_id != user_id]

    async def size(self) -> int:
        return len(self.waiting)
