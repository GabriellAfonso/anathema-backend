"""Websocket test driver owned by this project.

Channels ships `WebsocketCommunicator`, but `channels.testing.__init__` imports
`ChannelsLiveServerTestCase`, which imports daphne -- dropped in 6cccd9d when
the ASGI server became uvicorn. Importing any submodule runs that `__init__`,
so reaching the communicator would mean reinstalling daphne just to collect
tests. This is the slice of it the websocket tests actually use, on top of
asgiref's ApplicationCommunicator.
"""

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import cast

from asgiref.testing import ApplicationCommunicator

# O que o consumer troca com o servidor ASGI: `{"type": "websocket.send", ...}`.
ASGIMessage = MutableMapping[str, object]
ASGIApp = Callable[..., Awaitable[None]]


class WebsocketTestClient(ApplicationCommunicator):
    """Drives a consumer over raw ASGI messages, no server involved.

    >>> client = WebsocketTestClient(MatchConsumer.as_asgi(), "/ws/match/")
    >>> client.scope["user"] = user
    >>> accepted, code = await client.connect()
    """

    def __init__(
        self, application: ASGIApp, path: str, query_string: str = ""
    ) -> None:
        self.scope = {
            "type": "websocket",
            "path": path,
            "query_string": query_string.encode(),
            "headers": [],
            "subprotocols": [],
        }
        super().__init__(application, self.scope)

    async def receive_output(self, timeout: float = 1) -> ASGIMessage:
        return cast(ASGIMessage, await super().receive_output(timeout))

    async def connect(self, timeout: float = 1) -> tuple[bool, int | str | None]:
        """Returns (True, subprotocol) when accepted, (False, close code) when not."""
        await self.send_input({"type": "websocket.connect"})
        response = await self.receive_output(timeout)

        if response["type"] == "websocket.close":
            return False, cast(int, response.get("code", 1000))

        assert response["type"] == "websocket.accept", (
            f"Expected 'websocket.accept' or 'websocket.close', "
            f"got {response['type']!r}"
        )
        return True, cast(str | None, response.get("subprotocol"))

    async def send_json_to(
        self, content: dict[str, object], timeout: float = 1
    ) -> None:
        await self.send_input(
            {"type": "websocket.receive", "text": json.dumps(content)}
        )

    async def receive_json_from(self, timeout: float = 1) -> dict[str, object]:
        response = await self.receive_output(timeout)

        assert response["type"] == "websocket.send", (
            f"Expected 'websocket.send', got {response['type']!r}"
        )
        return cast(dict[str, object], json.loads(cast(str, response["text"])))

    async def receive_close_code(self, timeout: float = 1) -> int:
        """Close code of a socket the consumer closed after accepting it."""
        response = await self.receive_output(timeout)

        assert response["type"] == "websocket.close", (
            f"Expected 'websocket.close', got {response['type']!r}"
        )
        return cast(int, response.get("code", 1000))

    async def disconnect(self, code: int = 1000, timeout: float = 1) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(timeout)
