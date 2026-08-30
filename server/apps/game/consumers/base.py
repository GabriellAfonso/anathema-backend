from collections.abc import Mapping
from typing import NotRequired, TypedDict

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.cache import cache
from django.utils import timezone


class ClientEventMessage(TypedDict):
    """Mensagem de channel layer que vira frame do cliente.

    `type` é o que o Channels usa para achar o handler (`client_event`);
    `event` é o nome que o cliente lê.
    """

    type: str
    event: str
    payload: NotRequired[dict[str, object]]


class BaseConsumer(AsyncJsonWebsocketConsumer):
    """Shared websocket plumbing: auth, per-user addressing, event envelope.

    `connect`/`disconnect` are final. Subclasses extend them through
    `on_connect`/`on_disconnect`, which only run on an accepted socket.
    """

    # Namespaces this consumer's per-user group, so a message meant for the
    # matchmaking socket never lands on the connection socket. Subclasses set it.
    group_prefix: str = ""

    user: AbstractBaseUser | None = None
    heartbeat_key: str | None = None

    # Guards `disconnect`, which Channels also fires for a rejected socket --
    # one that never joined the groups the cleanup would undo.
    accepted: bool = False

    @classmethod
    def user_group(cls, user_id: int) -> str:
        """Group addressing every socket one user has open on this consumer.

        Lives in the channel layer, so it spans worker processes -- unlike the
        `user_channel` cache map it replaced.

        >>> MatchmakingConsumer.user_group(7)
        'matchmaking.user.7'
        """
        return f"{cls.group_prefix}.user.{user_id}"

    @property
    def user_id(self) -> int:
        """Id do usuário autenticado, o endereço usado por toda a camada.

        `AbstractBaseUser` só expõe `pk`, e ele é `Any`: converter aqui deixa
        o tipo honesto em um lugar só, em vez de espalhar `self.user.id`.
        """
        if self.user is None:
            raise RuntimeError(
                "user_id lido fora de um socket aceito: self.user is None"
            )

        return int(self.user.pk)

    async def connect(self) -> None:
        """Final: authenticate, accept, then hand over to `on_connect`.

        Override `on_connect` instead: a subclass that ran past a rejected
        `super().connect()` hit `RuntimeError: Unexpected ASGI message
        'websocket.send', after sending 'websocket.close'.`
        """
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        await self.accept()
        self.accepted = True

        await self.channel_layer.group_add(
            self.user_group(self.user_id),
            self.channel_name,
        )
        await self.on_connect()

    async def on_connect(self) -> None:
        """Subclass hook: accepted socket, `self.user` authenticated.

        >>> await self.channel_layer.group_add("online_players", self.channel_name)
        """

    async def disconnect(self, code: int) -> None:
        """Final: run the subclass cleanup, then release the per-user group."""
        if not self.accepted:
            return

        await self.on_disconnect(code)

        await self.channel_layer.group_discard(
            self.user_group(self.user_id),
            self.channel_name,
        )

        if self.heartbeat_key:
            await cache.adelete(self.heartbeat_key)

    async def on_disconnect(self, code: int) -> None:
        """Subclass hook: cleanup, before the base leaves the per-user group.

        >>> await self.channel_layer.group_discard("online_players", self.channel_name)
        """

    async def receive_json(
        self, content: dict[str, object], **kwargs: object
    ) -> None:
        """Routes `{"type": "play_card", ...}` to `handle_play_card(payload)`."""
        msg_type = content.get('type')
        payload = content.get('payload')

        if not msg_type:
            return

        handler = getattr(self, f'handle_{msg_type}', None)
        if handler:
            await handler(payload)

    async def send_event(
        self, *, type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        """Envelope every frame the client reads.

        The payload goes out as a nested object, not a JSON string: dumping it
        here made the client parse twice.
        """
        await self.send_json({
            'type': type,
            'payload': payload or {},
        })

    async def send_error(self, type: str, message: str, **extra: object) -> None:
        await self.send_event(
            type=type,
            payload={
                'error': message,
                **extra,
            }
        )

    async def client_event(self, event: ClientEventMessage) -> None:
        """Channel-layer handler: forwards a group message to this socket."""
        await self.send_event(type=event["event"], payload=event.get("payload"))

    async def set_heartbeat(self, ttl: int = 30) -> None:
        self.heartbeat_key = f'presence:user:{self.user_id}'
        await cache.aset(
            self.heartbeat_key,
            {'last_seen': timezone.now().isoformat()},
            timeout=ttl,
        )
