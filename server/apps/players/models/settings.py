# type: ignore
from django.db import models


class PlayerSettings(models.Model):
    profile = models.OneToOneField(
        'PlayerProfile', on_delete=models.CASCADE, related_name='settings')
    master_volume = models.IntegerField(default=100)
    music_volume = models.IntegerField(default=80)
    sfx_volume = models.IntegerField(default=80)
    resolution_width = models.IntegerField(default=1920)
    resolution_height = models.IntegerField(default=1080)
    notifications_enabled = models.BooleanField(default=True)
    language_preference = models.CharField(max_length=10, default='en')
