from django.urls import path

from .card_catalog_view import CardCatalogView
from .match_history_view import MatchHistoryView

urlpatterns = [
    path("cards/", CardCatalogView.as_view(), name="card_catalog"),
    path("matches/", MatchHistoryView.as_view(), name="match_history"),
]
