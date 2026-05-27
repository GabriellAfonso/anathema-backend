# type: ignore
from django.contrib.auth.models import User
from django.db import models


class PlayerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=255, default='default_icon')
    level = models.IntegerField(default=1)
    experience_points = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)
    credits = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Player Profile"
        verbose_name_plural = "Player Profiles"


class PlayerStats(models.Model):
    profile = models.OneToOneField(
        'PlayerProfile', on_delete=models.CASCADE, related_name='stats')
    matches_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    play_time = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "Player Stat"
        verbose_name_plural = "Player Stats"

    def __str__(self):
        return f"{self.profile.nickname} Stats"


class LoginHistory(models.Model):
    # TODO criar sistema pra registrar isso (Provavelmente no websocket)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        verbose_name = "Login History"
        verbose_name_plural = "Login Histories"

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


# class Friend(models.Model):
#     profile = models.ForeignKey(
#         'PlayerProfile', on_delete=models.CASCADE, related_name='friends')
#     friend = models.ForeignKey(
#         'PlayerProfile', on_delete=models.CASCADE, related_name='friend_of')
#     status = models.CharField(max_length=20, choices=[
#         ('pending', 'Pending'),
#         ('accepted', 'Accepted'),
#         ('blocked', 'Blocked'),
#     ], default='pending')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ('profile', 'friend')  # evita duplicatas

#     def __str__(self):
#         return f"{self.profile.nickname} -> {self.friend.nickname} ({self.status})"
