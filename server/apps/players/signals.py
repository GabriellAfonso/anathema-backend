from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.players.models.player import PlayerProfile, PlayerStats
from apps.players.models.settings import PlayerSettings


@receiver(post_save, sender=User)
def create_player_related(sender: type[User], instance: User, created: bool, **kwargs: dict[str, object]) -> None:
    if created:
        profile = PlayerProfile.objects.create(
            user=instance, nickname=getattr(instance, "username"))

        PlayerStats.objects.create(
            profile=profile, )

        PlayerSettings.objects.create(profile=profile)
        print('criou a conta')
