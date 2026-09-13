"""O timeout de leitura do channel layer não pode empatar com a espera do BZPOPMIN.

Regressão: com o padrão do redis-py 8.1 (5s) e o `brpop_timeout` do
channels_redis 4.3 (5s), todo socket parado por 5 segundos caía sem close frame.

Provado pela configuração, e não esperando de verdade: a conexão é montada pelo
mesmo caminho que o channels_redis usa, sem abrir socket nenhum.
"""

from typing import cast

from django.conf import settings
from channels_redis.core import RedisChannelLayer
from redis.asyncio import Connection


def _channel_layer_connection() -> Connection:
    """A conexão que o channel layer abriria, com os kwargs que ele passaria."""
    # O stub do Django infere o dict de settings como `Collection[str]`.
    config = cast(dict[str, object], settings.CHANNEL_LAYERS["default"]["CONFIG"])
    layer = RedisChannelLayer(**config)
    connection: Connection = layer.create_pool(0).make_connection()

    return connection


def test_the_read_timeout_outlasts_the_bzpopmin_wait() -> None:
    timeout = _channel_layer_connection().socket_timeout
    wait = RedisChannelLayer.brpop_timeout

    # Estritamente maior: o empate é justamente o bug.
    assert timeout is None or timeout > wait, (
        f"channel layer socket_timeout={timeout!r}; expected None or a number "
        f"greater than channels_redis brpop_timeout={wait!r}"
    )


def test_connecting_to_redis_still_gives_up() -> None:
    timeout = _channel_layer_connection().socket_connect_timeout

    assert timeout is not None, (
        f"channel layer socket_connect_timeout={timeout!r}; expected a number "
        "of seconds, so an unreachable Redis fails instead of hanging"
    )
