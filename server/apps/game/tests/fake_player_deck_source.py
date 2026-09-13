"""Decks para o socket de matchmaking, sem passar pelo banco.

O `conftest.py` deste pacote registra que nenhum teste de websocket toca o
banco, e o `no_connection_churn` existe por causa disso. Com o deck chegando ao
consumer por porta injetada, isto é o que mantém a regra: quem prova a consulta
de verdade é `apps/players/tests/test_deck_queries.py`, com `django_db`.

Devolve `None` pelos dois motivos -- o deck não existe, ou é de outro jogador --
porque é isso que a implementação real faz, e um fake que os distinguisse
deixaria passar um consumer que também os distingue.
"""

from apps.game.match import ChosenDeck
from apps.players.services.deck_queries import PlayerDeckSource


class FakePlayerDeckSource:
    """Decks em memória, endereçados por `(user_id, deck_id)`.

    >>> source = FakePlayerDeckSource({(7, 1): deck})
    >>> await source.deck_for(user_id=7, deck_id=1) == deck
    True
    >>> await source.deck_for(user_id=9, deck_id=1) is None   # não é dele
    True
    """

    def __init__(self, decks: dict[tuple[int, int], ChosenDeck] | None = None) -> None:
        self.decks: dict[tuple[int, int], ChosenDeck] = dict(decks or {})
        # O que foi pedido, na ordem. Um teste confere que o consumer pergunta
        # pelo deck **do autor**, e não por um `deck_id` solto.
        self.asked: list[tuple[int, int]] = []

    def give(self, *, user_id: int, deck_id: int, deck: ChosenDeck) -> None:
        """Guarda um deck daquele jogador.

        >>> source.give(user_id=7, deck_id=1, deck=deck)
        """
        self.decks[(user_id, deck_id)] = deck

    def take(self, *, user_id: int, deck_id: int) -> None:
        """Apaga o deck, como o jogador faria pelo HTTP no meio da fila.

        >>> source.take(user_id=7, deck_id=1)
        """
        self.decks.pop((user_id, deck_id), None)

    async def deck_for(self, *, user_id: int, deck_id: int) -> ChosenDeck | None:
        self.asked.append((user_id, deck_id))

        return self.decks.get((user_id, deck_id))


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição, e esta é a única do arquivo. Sem ela, o
# dia em que `PlayerDeckSource` ganhar um método o fake fica para trás em
# silêncio e só quebra na cara de quem for injetá-lo. Não apague por parecer
# sobra.
FAKE_DECK_SOURCE_MATCHES_THE_PROTOCOL: PlayerDeckSource = FakePlayerDeckSource()
