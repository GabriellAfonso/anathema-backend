from django.urls import path
from .views import websocket_test_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('game/', websocket_test_view, name='game'),
]
