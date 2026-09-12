from django.urls import path

from .deck_views import DeckCollectionView, DeckItemView
from .views import PlayerMeView

urlpatterns = [
    path("me/", PlayerMeView.as_view(), name="player_me"),
    path("decks/", DeckCollectionView.as_view(), name="player_decks"),
    path(
        "decks/<int:deck_id>/",
        DeckItemView.as_view(),
        name="player_deck",
    ),
]
