from django.contrib.auth.models import User
from django.db import transaction

from apps.game.cards import CardCatalog, get_card_catalog
from apps.players.models.player import PlayerProfile, PlayerStats
from apps.players.models.settings import PlayerSettings

from .starter_deck_creation import create_starter_deck


@transaction.atomic
def create_player_for_user(
    user: User, nickname: str, *, catalog: CardCatalog | None = None
) -> PlayerProfile:
    """Cria perfil, stats, settings e o deck inicial de um usuário novo.

    Tudo ou nada: uma falha em qualquer etapa desfaz as anteriores, para
    que nenhum User fique sem profile (decisão 0001, um perfil por usuário
    e para sempre) e nenhum jogador nasça com perfil e sem deck. Quem chama
    precisa envolver a criação do User na mesma transação, senão o User
    sobrevive ao rollback daqui.

    `catalog` entra por parâmetro para que o teste injete o dele; sem ele,
    o handle do processo é consultado aqui, que é o ponto de composição.

    >>> create_player_for_user(user, nickname="gabriel")
    <PlayerProfile: pk=7>
    """
    profile = PlayerProfile.objects.create(user=user, nickname=nickname)
    PlayerStats.objects.create(profile=profile)
    PlayerSettings.objects.create(profile=profile)
    create_starter_deck(profile, catalog=catalog or get_card_catalog())
    return profile
