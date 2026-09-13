import json
from collections.abc import Mapping
from typing import NotRequired, TypedDict

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.cache import cache
from django.utils import timezone

from apps.game.protocol import (
    MALFORMED_MESSAGE,
    PONG,
    UNKNOWN_MESSAGE_TYPE,
    is_ping,
    pong_payload,
)

# Close code do gate de autenticação, no range privado 4000-4999. Os gates de
# domínio continuam a série a partir dele (MatchConsumer usa 44xx).
UNAUTHENTICATED = 4001


def describe_scope_user(user: object) -> str:
    """Motivo da recusa em texto estável -- o cliente Unity casa com ele.

    Fica fora do repr do usuário de propósito: `repr` carrega o endereço de
    memória, e o cliente não teria como comparar duas recusas iguais.

    >>> describe_scope_user(None)
    'no user on the scope'
    """
    if not user:
        return "no user on the scope"

    return f"{type(user).__name__} is not authenticated"


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
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.deny_unauthenticated(describe_scope_user(user))
            return

        self.user = user
        await self.accept()
        self.accepted = True

        await self.channel_layer.group_add(
            self.user_group(self.user_id),
            self.channel_name,
        )
        await self.on_connect()

    async def deny_unauthenticated(self, reason: str) -> None:
        """Aceita o socket só para contar o motivo, e fecha em seguida.

        Mesmo padrão de `MatchConsumer.reject`: um close antes do handshake
        chega ao cliente como 1006 (Abnormal), sem código nem texto, então o
        Unity não distingue token expirado de queda de rede e reconecta com o
        mesmo access token morto. O access token do SimpleJWT dura 5 minutos,
        então essa recusa é rotina, não exceção.

        `self.accepted` continua False e `self.user` continua None de
        propósito: o socket não entrou em grupo nenhum, e é `self.accepted`
        que impede o `disconnect` de tentar desfazer o que não houve.

        >>> await self.deny_unauthenticated("no user on the scope")
        """
        await self.accept()
        await self.send_error("auth_denied", f"authentication required: {reason}")
        await self.close(code=UNAUTHENTICATED)

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

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        **kwargs: object,
    ) -> None:
        """Decodifica o frame, responde o ping, e entrega o resto ao `receive_json`.

        As recusas de forma moram em `decode_client_frame`.
        """
        content = await self.decode_client_frame(text_data)

        if content is None:
            return

        # O ping é tratado aqui, e não num `handle_ping`: o `MatchConsumer`
        # substitui o `receive_json` inteiro e não passa pelo roteamento, então
        # este é o último ponto por onde os dois sockets passam juntos (feature
        # 013, research D1).
        if is_ping(content):
            await self.answer_ping(content)
            return

        await self.receive_json(content)

    def passed_socket_gates(self) -> bool:
        """Se o socket passou pelos gates e pode receber resposta a mensagem.

        Os gates aceitam o socket antes de recusar, para o motivo chegar ao
        cliente, e fecham logo depois; `accepted` continua False no socket que o
        gate de autenticação recusou. Frame mandado depois do close é o
        `RuntimeError: Unexpected ASGI message 'websocket.send', after sending
        'websocket.close'` que `test_base_consumer_lifecycle.py` registra.

        >>> self.passed_socket_gates()
        True
        """
        return self.accepted

    async def answer_ping(self, content: Mapping[str, object]) -> None:
        """Responde o ping só a este socket, com o eco do payload.

        `send_event`, e não `group_send`: o pong não pode chegar a outro socket
        do mesmo usuário nem ao oponente, e o channel layer fica fora do caminho
        (research D4). Não renova presença: ela é por usuário, o ping é por
        socket, e o item continua adiado no `Backend/TODO.md` (research D5).

        O contrato está em
        `specs/013-socket-heartbeat/contracts/heartbeat_messages.md`.

        >>> await self.answer_ping({"type": "ping", "payload": {"n": 1}})
        """
        if not self.passed_socket_gates():
            return

        await self.send_event(type=PONG, payload=pong_payload(content))

    async def decode_client_frame(
        self, text_data: str | None
    ) -> dict[str, object] | None:
        """Decodifica o frame, e recusa em vez de derrubar o socket.

        O `receive` do Channels levanta com frame binário e com JSON inválido, e
        a exceção fecha a conexão. Um cliente com bug recebe a recusa e segue
        conectado (feature 009, FR-023). Devolve o objeto, ou `None` depois de
        recusar.

        >>> await self.decode_client_frame('{"type": "pass"}')
        {'type': 'pass'}
        """
        if text_data is None:
            await self.send_refusal(
                MALFORMED_MESSAGE, "expected a text frame, got binary"
            )
            return None

        try:
            content = json.loads(text_data)
        except json.JSONDecodeError as error:
            await self.send_refusal(MALFORMED_MESSAGE, f"frame is not JSON: {error}")
            return None

        if not isinstance(content, dict):
            await self.send_refusal(
                MALFORMED_MESSAGE, f"frame is {content!r}: expected a JSON object"
            )
            return None

        return content

    async def receive_json(self, content: dict[str, object], **kwargs: object) -> None:
        """Routes `{"type": "play_card", ...}` to `handle_play_card(payload)`.

        Mensagem sem `type`, ou com `type` sem handler, era ignorada em
        silêncio, e o cliente ficava esperando resposta a uma mensagem que o
        servidor jogou fora. Desde a feature 009 as duas recebem recusa.
        """
        msg_type = content.get("type")

        if not isinstance(msg_type, str) or not msg_type:
            await self.send_refusal(
                MALFORMED_MESSAGE, f"type is {msg_type!r}: expected a non-empty string"
            )
            return

        handler = getattr(self, f"handle_{msg_type}", None)

        if handler is None:
            await self.send_refusal(
                UNKNOWN_MESSAGE_TYPE, f"type {msg_type!r} has no handler on this socket"
            )
            return

        await handler(content.get("payload"))

    async def send_event(
        self, *, type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        """Envelope every frame the client reads.

        The payload goes out as a nested object, not a JSON string: dumping it
        here made the client parse twice.
        """
        await self.send_json(
            {
                "type": type,
                "payload": payload or {},
            }
        )

    async def send_refusal(self, code: str, message: str, **details: object) -> None:
        """Recusa uma mensagem, só para este socket, sem fechá-lo.

        `code` é o texto estável que o cliente compara; `message` é para gente.
        O catálogo está em `apps/game/protocol/refusal_codes.py`, e o do socket
        de matchmaking em `apps/game/protocol/matchmaking_refusals.py`.

        `details` é opcional e serve à recusa que tem estrutura além do texto:
        `invalid_deck` manda os problemas do deck por ele. O socket de partida
        não passa nada, então os frames da feature 009 não mudam.

        >>> await self.send_refusal("unknown_message_type", "type 'x' ...")
        >>> await self.send_refusal("invalid_deck", "...", deck_problems=[...])
        """
        await self.send_error("message_refused", message, code=code, **details)

    async def send_error(self, type: str, message: str, **extra: object) -> None:
        await self.send_event(
            type=type,
            payload={
                "error": message,
                **extra,
            },
        )

    async def client_event(self, event: ClientEventMessage) -> None:
        """Channel-layer handler: forwards a group message to this socket."""
        await self.send_event(type=event["event"], payload=event.get("payload"))

    async def set_heartbeat(self, ttl: int = 30) -> None:
        self.heartbeat_key = f"presence:user:{self.user_id}"
        await cache.aset(
            self.heartbeat_key,
            {"last_seen": timezone.now().isoformat()},
            timeout=ttl,
        )
