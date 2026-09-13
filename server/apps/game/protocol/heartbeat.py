"""O ping dos dois sockets: a mensagem que o servidor sempre responde.

O cliente Unity manda `ping` a cada 10s e declara a conexão morta depois de 30s
sem receber nada; o detector só arma no primeiro `pong`. O ping/pong do
protocolo WebSocket não serve a ele: o `ClientWebSocket` do .NET o responde
sozinho e não o mostra para a aplicação.

Não é jogada nem entrada de fila, e por isso **não** passa por
`client_messages` -- lá viraria comando, entraria no `mutate` e geraria versão.
Quem o reconhece é o `receive` do `BaseConsumer`, antes de os dois sockets se
separarem.

O contrato está em `specs/013-socket-heartbeat/contracts/heartbeat_messages.md`.
"""

from collections.abc import Mapping

PING = "ping"
PONG = "pong"


def is_ping(content: Mapping[str, object]) -> bool:
    """Se a mensagem é um ping.

    O `type` decide sozinho, exato e sensível a maiúsculas. Payload e campos a
    mais nunca desqualificam um ping.

    >>> is_ping({"type": "ping", "payload": 42})
    True
    """
    return content.get("type") == PING


def pong_payload(content: Mapping[str, object]) -> dict[str, object]:
    """O payload do pong: o eco do ping quando ele é objeto, `{}` no resto.

    O ping nunca é recusado pelo payload: uma recusa deixaria o detector do
    cliente desligado. O servidor não acrescenta nada ao eco -- quem quer medir
    latência põe o próprio marcador.

    >>> pong_payload({"type": "ping", "payload": {"sent_at_ms": 1726000000000}})
    {'sent_at_ms': 1726000000000}
    """
    payload = content.get("payload")

    if not isinstance(payload, dict):
        return {}

    return payload
