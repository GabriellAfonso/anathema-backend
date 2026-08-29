import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.asgi import get_asgi_application

# Uvicorn imports this module directly, so nothing has called django.setup()
# yet. get_asgi_application() does it, and must run before any import that
# touches models -- JWTAuthMiddleware pulls in django.contrib.auth.models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from core.middlewares.jwt_auth import JWTAuthMiddleware  # noqa: E402
import apps.game.routing  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            apps.game.routing.websocket_urlpatterns
        )
    ),
})
