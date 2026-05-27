from django.urls import path
from .views import PlayerMeView

urlpatterns = [
    path("me/", PlayerMeView.as_view(), name="player_me"),
]
