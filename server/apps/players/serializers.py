from rest_framework import serializers
from .models.player import PlayerProfile


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProfile
        fields = (
            "nickname",
            "icon",
            "level",
            "experience_points",
            "coins",
            "credits",
        )
