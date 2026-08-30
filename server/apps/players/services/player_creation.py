from django.contrib.auth.models import User
from django.db import transaction

from apps.players.models.player import PlayerProfile, PlayerStats
from apps.players.models.settings import PlayerSettings


@transaction.atomic
def create_player_for_user(user: User, nickname: str) -> PlayerProfile:
    """Cria perfil, stats e settings de um usuário recém-registrado.

    Tudo ou nada: uma falha em qualquer etapa desfaz as anteriores, para
    que nenhum User fique sem profile (decisão 0001, um perfil por usuário
    e para sempre). Quem chama precisa envolver a criação do User na mesma
    transação, senão o User sobrevive ao rollback daqui.

    >>> create_player_for_user(user, nickname="gabriel")
    <PlayerProfile: pk=7>
    """
    profile = PlayerProfile.objects.create(user=user, nickname=nickname)
    PlayerStats.objects.create(profile=profile)
    PlayerSettings.objects.create(profile=profile)
    return profile
