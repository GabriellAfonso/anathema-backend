from collections.abc import AsyncIterator

import pytest
from django.conf import settings
from pytest_django.fixtures import Settings
from redis.asyncio import Redis

# Throwaway database, so the Redis-backed tests never touch app data. Every
# fixture that hands out this connection flushes it on the way in and out.
TEST_REDIS_DB = 15


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings: Settings) -> None:
    """Keeps the websocket tests off Redis: groups live in the process."""
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }


@pytest.fixture(autouse=True)
def no_connection_churn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo consumer fecha conexões velhas do Django a cada mensagem.

    Nenhum teste de websocket toca o banco, e o pytest-django bloqueia esse
    acesso assim que a sessão tem qualquer teste com `django_db` -- o que
    quebraria estes testes por um efeito colateral que não é deles.
    """
    monkeypatch.setattr("channels.db.close_old_connections", lambda: None)


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(f"{settings.REDIS_URL}/{TEST_REDIS_DB}")
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
