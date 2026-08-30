from collections.abc import Awaitable, Callable, MutableMapping
from typing import cast
from urllib.parse import parse_qs

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from asgiref.sync import sync_to_async
User = get_user_model()

# Forma ASGI mínima de que este middleware precisa. Os TypedDict de
# `asgiref.typing` descrevem o scope fechado, e nós escrevemos `user` nele.
Scope = MutableMapping[str, object]
Receive = Callable[[], Awaitable[MutableMapping[str, object]]]
Send = Callable[[MutableMapping[str, object]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class JWTAuthMiddleware:
    """
    Middleware de autenticação JWT para Django Channels.

    Responsabilidades:
    - Extrair token da query string
    - Validar JWT usando SimpleJWT
    - Popular scope["user"]
    """

    def __init__(self, inner: ASGIApp) -> None:
        self.inner = inner
        self.jwt_auth = JWTAuthentication()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["user"] = AnonymousUser()

        query_string = cast(bytes, scope.get("query_string", b"")).decode()
        params = parse_qs(query_string)

        token_list = params.get("token")

        if token_list:
            token = token_list[0]

            try:
                # simplejwt tipa o parâmetro como bytes e PyJWT aceita os
                # dois; a query string chega em str.
                validated_token = self.jwt_auth.get_validated_token(token.encode())
                get_user = cast(
                    Callable[[object], AbstractBaseUser], self.jwt_auth.get_user
                )
                scope["user"] = await sync_to_async(get_user)(validated_token)
            # AuthenticationFailed cobre InvalidToken (subclasse) e o caso
            # do usuário apagado ou inativo: `get_user` levanta
            # AuthenticationFailed('User not found'). Sem isso a excecao subia
            # e derrubava o handshake em vez de cair para anônimo.
            except (TokenError, AuthenticationFailed):
                pass

        return await self.inner(scope, receive, send)
