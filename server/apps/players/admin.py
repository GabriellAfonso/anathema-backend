from django.contrib import admin

# Register your models here.
from django.contrib import admin
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile, PlayerStats, LoginHistory
from apps.players.models.settings import PlayerSettings

# Register your models here.


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    ...
    list_display = (
        "nickname",
        "user",
        "level",
        "experience_points",
        "coins",
        "credits",
    )


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin): ...


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin): ...


@admin.register(PlayerSettings)
class PlayerSettingsAdmin(admin.ModelAdmin): ...


@admin.register(PlayerDeck)
class PlayerDeckAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "updated_at")
