"""`GET /game/cards/`: o catálogo servido ao cliente.

Somente leitura, igual para todo mundo, e sem nada que dependa de partida em
curso. O catálogo vem de `get_card_catalog()`, o handle do processo; nada aqui
constrói um catálogo próprio.
"""

from functools import cache

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.game.card_payload import CardPayload, catalog_payload
from apps.game.cards import get_card_catalog


@cache
def served_catalog() -> tuple[CardPayload, ...]:
    """O catálogo em payload, montado uma vez por processo.

    O catálogo é congelado na carga e a resposta não depende de quem pergunta,
    então remontar 29 dicionários a cada requisição é trabalho que nunca muda
    de resultado. Mesma razão do `@cache` de `get_matchmaking_queue`.

    Tupla e não lista: o chamador não tem como alterar o que está em cache.

    >>> len(served_catalog())
    29
    """
    return tuple(catalog_payload(get_card_catalog()))


class CardCatalogView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Todas as cartas, ordenadas por `card_id`.

        Não há filtro nem paginação: são 29 cartas, e o cliente precisa das 29
        para desenhar qualquer mensagem de partida que receber.

        >>> client.get("/game/cards/").data["cards"][0]["card_id"]
        1
        """
        return Response({"cards": served_catalog()})
