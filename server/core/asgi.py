import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.asgi import get_asgi_application

# Uvicorn imports this module directly, so nothing has called django.setup()
# yet. get_asgi_application() does it, and must run before any import that
# touches models -- JWTAuthMiddleware pulls in django.contrib.auth.models.
django_asgi_app = get_asgi_application()

from channels.layers import get_channel_layer  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.game.cards import mvp_catalog  # noqa: E402
from apps.game.history import DatabaseFinishedMatchRecorder  # noqa: E402
from apps.game.match.client import (  # noqa: E402
    get_match_store,
    get_match_wake_queue,
)
from apps.game.match_timers import (  # noqa: E402
    MatchClockTicker,
    MatchTimersLifespan,
)
from apps.game.randomness import SeededRandomSource  # noqa: E402
from apps.game.wall_clock import SystemWallClock  # noqa: E402
from core.middlewares.jwt_auth import JWTAuthMiddleware  # noqa: E402
import apps.game.routing  # noqa: E402


def build_match_clock_ticker() -> MatchClockTicker:
    """O ponto de composição do relógio da vez (§15).

    Roda no startup do worker, e não no import: o cliente Redis e o channel
    layer nascem no processo que vai usá-los.
    """
    return MatchClockTicker(
        matches=get_match_store(),
        wake_queue=get_match_wake_queue(),
        channel_layer=get_channel_layer(),
        catalog=mvp_catalog(),
        randomness=SeededRandomSource(),
        clock=SystemWallClock(),
        recorder=DatabaseFinishedMatchRecorder(),
    )


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            URLRouter(apps.game.routing.websocket_urlpatterns)
        ),
        # O escopo que liga o relógio da vez em cada worker do uvicorn. Era por
        # não existir nada aqui que o projeto rodava com `--lifespan off`.
        "lifespan": MatchTimersLifespan(build_match_clock_ticker),
    }
)
