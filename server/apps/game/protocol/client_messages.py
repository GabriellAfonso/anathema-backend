"""O JSON que o cliente manda vira um comando, ou é recusado pela forma.

O cliente não é confiável. Esta camada responde só "a mensagem tem a forma de
um pedido?" -- tipo conhecido, campos presentes, tipos certos. Se a jogada é
legal é pergunta do motor, e uma mensagem malformada nunca chega a ele.

**O autor sai do socket, nunca do payload.** `author_user_id` é o usuário
autenticado da conexão; um `actor_user_id` ou `user_id` dentro do payload é
ignorado como qualquer campo a mais. Sem isso um jogador jogaria o turno do
outro mandando o `user_id` dele.

Os `type` aceitos são os valores de `ActionKind` -- o discriminante que o motor
já declara como "o que o envelope de websocket carrega" -- mais `mulligan`. O
contrato está em `specs/009-match-protocol/contracts/client_messages.md`.
"""

from collections.abc import Callable, Mapping

from apps.game.engine import (
    ActionKind,
    AssignBlockerAction,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    PassAction,
    PlayUnitAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
)
from apps.game.match import CardInstanceId

from .commands import ClientCommand, ForfeitCommand, MulliganCommand
from .refusal_codes import MALFORMED_MESSAGE, UNKNOWN_MESSAGE_TYPE

MULLIGAN = "mulligan"

Payload = Mapping[str, object]
CommandReader = Callable[[Payload, int], ClientCommand]


class MalformedMessageError(Exception):
    """A mensagem não tem a forma de nenhum pedido. Carrega o código da recusa.

    >>> raise MalformedMessageError(MALFORMED_MESSAGE, "payload is 3: expected an object")
    MalformedMessageError: payload is 3: expected an object
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_client_message(content: object, *, author_user_id: int) -> ClientCommand:
    """O comando que a mensagem pede, com o autor do socket.

    >>> parse_client_message({"type": "pass"}, author_user_id=7)
    PassAction(actor_user_id=7)
    """
    message = _as_object(content, "message")
    message_type = message.get("type")

    if not isinstance(message_type, str) or not message_type:
        raise MalformedMessageError(
            MALFORMED_MESSAGE, f"type is {message_type!r}: expected a non-empty string"
        )

    reader = _READERS.get(message_type)

    if reader is None:
        raise MalformedMessageError(
            UNKNOWN_MESSAGE_TYPE,
            f"type {message_type!r} is unknown: expected one of {sorted(_READERS)}",
        )

    return reader(_payload_of(message), author_user_id)


def _as_object(value: object, name: str) -> Payload:
    """Um objeto JSON, com chaves texto. JSON sempre dá chave texto, e é isso
    que torna o `isinstance` de `dict` a pergunta inteira."""
    if not isinstance(value, dict):
        raise MalformedMessageError(
            MALFORMED_MESSAGE, f"{name} is {value!r}: expected an object"
        )

    return value


def _payload_of(message: Payload) -> Payload:
    """O payload, ou um objeto vazio quando ausente: pedidos sem campo --
    passar, Atacar -- podem vir sem ele."""
    if "payload" not in message or message["payload"] is None:
        return {}

    return _as_object(message["payload"], "payload")


def _card_id(payload: Payload, field: str) -> CardInstanceId:
    """Um identificador de instância obrigatório: inteiro ≥ 1, e não booleano.

    `bool` é subclasse de `int` em Python, e `true` chegaria como 1.
    """
    value = payload.get(field)

    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MalformedMessageError(
            MALFORMED_MESSAGE, f"{field} is {value!r}: expected an integer >= 1"
        )

    return CardInstanceId(value)


def _optional_card_id(payload: Payload, field: str) -> CardInstanceId | None:
    """Ausente ou `null` é "não mira nada"; qualquer outra coisa segue a regra
    do identificador obrigatório."""
    if payload.get(field) is None:
        return None

    return _card_id(payload, field)


def _card_ids(payload: Payload, field: str) -> tuple[CardInstanceId, ...]:
    """Uma lista de identificadores, que pode ser vazia. Vazia não é forma
    errada: se ela é legal, o motor responde."""
    values = payload.get(field)

    if not isinstance(values, list):
        raise MalformedMessageError(
            MALFORMED_MESSAGE, f"{field} is {values!r}: expected a list of integers"
        )

    return tuple(_card_id({field: value}, field) for value in values)


def _mulligan(payload: Payload, author: int) -> ClientCommand:
    return MulliganCommand(author, _card_ids(payload, "card_instance_ids"))


def _forfeit(payload: Payload, author: int) -> ClientCommand:
    return ForfeitCommand(author)


def _play_unit(payload: Payload, author: int) -> ClientCommand:
    return PlayUnitAction(author, _card_id(payload, "card_instance_id"))


def _cast_spell(payload: Payload, author: int) -> ClientCommand:
    return CastSpellAction(
        author,
        _card_id(payload, "card_instance_id"),
        _optional_card_id(payload, "target_card_instance_id"),
    )


def _pass(payload: Payload, author: int) -> ClientCommand:
    return PassAction(author)


def _declare_attack(payload: Payload, author: int) -> ClientCommand:
    return DeclareAttackAction(author, _card_ids(payload, "attacker_card_instance_ids"))


def _withdraw_attacker(payload: Payload, author: int) -> ClientCommand:
    return WithdrawAttackerAction(
        author, _card_id(payload, "attacker_card_instance_id")
    )


def _confirm_attack(payload: Payload, author: int) -> ClientCommand:
    return ConfirmAttackAction(author)


def _assign_blocker(payload: Payload, author: int) -> ClientCommand:
    return AssignBlockerAction(
        author,
        _card_id(payload, "blocker_card_instance_id"),
        _card_id(payload, "attacker_card_instance_id"),
    )


def _remove_blocker(payload: Payload, author: int) -> ClientCommand:
    return RemoveBlockerAction(author, _card_id(payload, "blocker_card_instance_id"))


def _end_defense_window(payload: Payload, author: int) -> ClientCommand:
    return EndDefenseWindowAction(author)


_READERS: dict[str, CommandReader] = {
    MULLIGAN: _mulligan,
    ActionKind.FORFEIT: _forfeit,
    ActionKind.PLAY_UNIT: _play_unit,
    ActionKind.CAST_SPELL: _cast_spell,
    ActionKind.PASS: _pass,
    ActionKind.DECLARE_ATTACK: _declare_attack,
    ActionKind.WITHDRAW_ATTACKER: _withdraw_attacker,
    ActionKind.CONFIRM_ATTACK: _confirm_attack,
    ActionKind.ASSIGN_BLOCKER: _assign_blocker,
    ActionKind.REMOVE_BLOCKER: _remove_blocker,
    ActionKind.END_DEFENSE_WINDOW: _end_defense_window,
}
