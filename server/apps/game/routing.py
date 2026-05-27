from django.urls import path

from apps.game.consumers.connection import ConnectionConsumer
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.consumers.match import MatchConsumer

websocket_urlpatterns = [
    path("ws/connection/", ConnectionConsumer.as_asgi()),
    path("ws/matchmaking/", MatchmakingConsumer.as_asgi()),
    path("ws/match/", MatchConsumer.as_asgi()),
]
