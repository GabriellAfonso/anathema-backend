"""JWTAuthMiddleware decides who every websocket consumer thinks it is talking
to, so the token paths are worth pinning down: a valid token must produce the
real user, and anything else must stay anonymous.
"""

from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import RefreshToken

from core.middlewares.jwt_auth import JWTAuthMiddleware, Scope

User = get_user_model()


class SpyInnerApp:
    """Innermost ASGI app: records the scope the middleware handed down."""

    def __init__(self) -> None:
        self.scope: Scope | None = None

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        self.scope = scope


async def connect_with(query_string: str) -> Scope:
    """Roda o middleware sobre um scope de websocket e devolve o que ele passou."""
    inner = SpyInnerApp()
    scope: Scope = {"type": "websocket", "query_string": query_string.encode()}

    async def receive() -> dict[str, object]:
        return {}

    async def send(message: Any) -> None:
        return None

    await JWTAuthMiddleware(inner)(scope, receive, send)
    assert inner.scope is not None

    return inner.scope


@pytest.fixture
def player() -> AbstractBaseUser:
    return User.objects.create_user(username="gabriel", password="x")


def access_token_for(user: AbstractBaseUser) -> str:
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db(transaction=True)
async def test_valid_token_authenticates_the_user(player: AbstractBaseUser) -> None:
    scope = await connect_with(f"token={access_token_for(player)}")

    assert scope["user"] == player


@pytest.mark.django_db(transaction=True)
async def test_missing_token_stays_anonymous() -> None:
    scope = await connect_with("")

    assert isinstance(scope["user"], AnonymousUser)


@pytest.mark.django_db(transaction=True)
async def test_garbage_token_stays_anonymous() -> None:
    """Token quebrado não pode derrubar o handshake: vira anônimo e o consumer
    fecha com 4001."""
    scope = await connect_with("token=not-a-jwt")

    assert isinstance(scope["user"], AnonymousUser)


@pytest.mark.django_db(transaction=True)
async def test_token_for_deleted_user_stays_anonymous(
    player: AbstractBaseUser,
) -> None:
    token = access_token_for(player)
    await sync_to_async(player.delete)()

    scope = await connect_with(f"token={token}")

    assert isinstance(scope["user"], AnonymousUser)
