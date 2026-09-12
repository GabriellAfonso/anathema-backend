"""O deck entrando e saindo pelo HTTP.

Dois serializadores porque são duas formas: o que sai carrega o `deck_id` que o
banco cunhou; o que entra não o menciona, e no `PATCH` os dois campos são
opcionais.

As regras de deck **não** moram aqui. O serializador confere forma -- é uma
lista de inteiros? o nome é texto? --, e `deck_validation` confere regra. Pôr
as três regras num `validate_card_ids` faria a recusa sair como erro de campo,
sem os problemas estruturados que o cliente precisa para pintar a tela.
"""

from dataclasses import dataclass

from rest_framework import serializers


class DeckSerializer(serializers.Serializer[object]):
    """O deck como o cliente o lê.

    `deck_id` e nunca `id`: o espaço de identidade é nomeado (constituição, II).

    >>> DeckSerializer(deck).data["deck_id"]
    4
    """

    deck_id = serializers.IntegerField(source="pk", read_only=True)
    name = serializers.CharField(read_only=True)
    card_ids = serializers.ListField(child=serializers.IntegerField(), read_only=True)


class DeckWriteSerializer(serializers.Serializer[object]):
    """O que o cliente manda para criar ou editar.

    Os dois campos são opcionais aqui e obrigatórios na criação: quem exige os
    dois é a view do `POST`, porque o `PATCH` aceita um só.

    >>> DeckWriteSerializer(data={"name": "Agro"}).is_valid()
    True
    """

    # `allow_blank` e `trim_whitespace=False` de propósito: nome vazio precisa
    # chegar a `validated_deck_name`, que recusa citando o valor recebido. A
    # recusa genérica do DRF diria só "este campo não pode ser vazio".
    name = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    card_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


@dataclass(frozen=True, slots=True)
class DeckWriteFields:
    """O que o cliente mandou, com tipo -- `None` quando o campo não veio.

    Existe porque `serializer.validated_data` chega como `Any`: o DRF não
    publica stubs, e passar aquele dicionário adiante espalharia `Any` por toda
    a camada de escrita, que roda sob `mypy --strict`.

    >>> deck_write_fields({"name": "Agro"}).card_ids is None
    True
    """

    name: str | None
    card_ids: list[int] | None


def deck_write_fields(data: object) -> DeckWriteFields:
    """Confere a **forma** do corpo e devolve os campos tipados.

    Regra de deck não passa por aqui: ela é de `deck_validation`, e sai em
    `deck_problems`, estruturada, e não como erro de campo.

    >>> deck_write_fields({"name": "  Agro  "}).name
    '  Agro  '
    """
    serializer = DeckWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    name = serializer.validated_data.get("name")
    card_ids = serializer.validated_data.get("card_ids")

    return DeckWriteFields(
        name=None if name is None else str(name),
        card_ids=None if card_ids is None else [int(card_id) for card_id in card_ids],
    )
