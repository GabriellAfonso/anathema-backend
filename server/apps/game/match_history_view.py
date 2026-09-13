"""`/game/matches/`: o histórico do jogador autenticado, paginado.

Só as próprias partidas, e não existe rota para as de outro jogador -- o
isolamento vem do queryset (`history/match_history_queries.py`), não de uma
checagem depois da busca.

A paginação é declarada aqui, e não em `REST_FRAMEWORK`: as rotas de deck
respondem a lista inteira hoje, e ligar paginação global mudaria o corpo delas
sem ninguém ter pedido.

O contrato está em
`specs/012-match-result-history/contracts/http_match_history.md`.
"""

from typing import Any

from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from apps.game.history.match_history_queries import matches_of
from apps.game.match_history_serializers import MatchHistorySerializer
from apps.game.models import MatchRecord
from apps.players.models.player import PlayerProfile


class MatchHistoryPagination(PageNumberPagination):
    """20 por página, teto de 100.

    20 cabe numa tela sem rolagem infinita; o teto existe para que um
    `page_size` grande não vire uma consulta que devolve o histórico inteiro.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class MatchHistoryView(ListAPIView[MatchRecord]):
    """As partidas do autenticado, da mais recente para a mais antiga.

    >>> client.get("/game/matches/").data["results"][0]["won"]
    True
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = MatchHistorySerializer
    pagination_class = MatchHistoryPagination

    def get_queryset(self) -> Any:
        return matches_of(self._player_user_id())

    def get_serializer_context(self) -> dict[str, Any]:
        """O serializer decide `won` e `opponent` pelo lado de quem pergunta."""
        return {**super().get_serializer_context(), "user_id": self._player_user_id()}

    def _player_user_id(self) -> int:
        """O `user_id` do autenticado, ou `404` se ele não é jogador.

        Mesma recusa e mesma razão de `PlayerMeView`: contas criadas fora do
        registro (`createsuperuser`, fixtures) não têm perfil, e histórico de
        partida pertence a jogador. Não é vazamento -- elas não jogaram nenhuma
        partida a distinguir.
        """
        user_id = self.request.user.pk

        if not PlayerProfile.objects.filter(pk=user_id).exists():
            raise NotFound(
                f"user_id={user_id} não tem PlayerProfile. "
                "Só contas criadas pelo registro são jogadores."
            )

        return int(user_id)
