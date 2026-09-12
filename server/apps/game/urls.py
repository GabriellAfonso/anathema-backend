from django.urls import path

from .card_catalog_view import CardCatalogView
from .views import websocket_test_view

urlpatterns = [
    path("game/", websocket_test_view, name="game"),
    path("cards/", CardCatalogView.as_view(), name="card_catalog"),
]
