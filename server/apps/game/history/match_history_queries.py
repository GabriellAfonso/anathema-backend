"""Ler o histórico -- sempre pelas partidas do próprio jogador.

O isolamento sai **da consulta**, e não de uma checagem depois dela. É o mesmo
argumento que `apps/players/services/deck_queries.py` escreve: sem rota que
receba o jogador por parâmetro, não existe caminho a recusar, e uma recusa que
dissesse "esse histórico existe, mas não é seu" já teria entregado informação a
quem não deveria tê-la.

Os dois `select_related` evitam uma consulta por linha para montar o oponente da
página -- 20 linhas dariam 40 idas ao banco.
"""

from django.db.models import Q, QuerySet

from apps.game.models import MatchRecord


def matches_of(user_id: int) -> QuerySet[MatchRecord]:
    """As partidas daquele jogador, da mais recente para a mais antiga.

    `user_id` e não `profile_id`: são o mesmo inteiro (decisão 0001), e este é o
    nome do espaço de identidade do projeto.

    >>> matches_of(7).count()
    37
    """
    return (
        MatchRecord.objects.filter(Q(winner_id=user_id) | Q(loser_id=user_id))
        .select_related("winner", "loser")
        .order_by("-ended_at")
    )
