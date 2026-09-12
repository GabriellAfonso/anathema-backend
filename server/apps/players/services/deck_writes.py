"""Criar, editar e apagar deck. Nada é salvo antes de passar pela validação.

A ordem é sempre a mesma: validar tudo, depois gravar uma vez. Um deck
recusado não fica salvo pela metade, e uma edição recusada deixa o deck
guardado exatamente como estava.
"""

from collections.abc import Sequence

from apps.game.cards import CardCatalog, CardId
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile

from .deck_queries import deck_count_of
from .deck_validation import (
    ensure_room_for_another_deck,
    validated_card_ids,
    validated_deck_name,
)


class EmptyDeckUpdateError(Exception):
    """Um `PATCH` que não pede mudança nenhuma.

    Recusa e não no-op: uma edição vazia é cliente quebrado, e responder `200`
    faria parecer que algo mudou.

    >>> raise EmptyDeckUpdateError()
    EmptyDeckUpdateError: update names neither 'name' nor 'card_ids': expected
    at least one
    """

    def __init__(self) -> None:
        super().__init__(
            "update names neither 'name' nor 'card_ids': expected at least one"
        )


def create_deck(
    profile: PlayerProfile,
    *,
    name: str,
    card_ids: Sequence[int],
    catalog: CardCatalog,
) -> PlayerDeck:
    """Cria um deck do jogador, ou recusa sem salvar nada.

    O teto é conferido antes da lista de propósito: um jogador no teto não
    precisa saber se as 40 cartas dele estavam certas.

    >>> create_deck(profile, name="Agro", card_ids=deck, catalog=catalog).pk
    4
    """
    ensure_room_for_another_deck(deck_count_of(profile.pk))

    return PlayerDeck.objects.create(
        profile=profile,
        name=validated_deck_name(name),
        card_ids=list(validated_card_ids(card_ids, catalog)),
    )


def update_deck(
    deck: PlayerDeck,
    *,
    name: str | None,
    card_ids: Sequence[int] | None,
    catalog: CardCatalog,
) -> PlayerDeck:
    """Renomeia, troca a lista, ou as duas coisas, numa gravação só.

    `card_ids` **substitui** a lista inteira: não há edição por carta.

    >>> update_deck(deck, name="Agro v2", card_ids=None, catalog=catalog).name
    'Agro v2'
    """
    if name is None and card_ids is None:
        raise EmptyDeckUpdateError()

    new_name = None if name is None else validated_deck_name(name)
    new_cards = (
        None if card_ids is None else list(validated_card_ids(card_ids, catalog))
    )

    return _saved_with(deck, name=new_name, card_ids=new_cards)


def delete_deck(deck: PlayerDeck) -> None:
    """Apaga o deck.

    Permitido mesmo com o deck em uso: quem está na fila já carrega a lista
    validada, e quem está em partida já tem as cartas dela desde o setup.

    >>> delete_deck(deck)
    """
    deck.delete()


def _saved_with(
    deck: PlayerDeck, *, name: str | None, card_ids: list[CardId] | None
) -> PlayerDeck:
    """Grava só os campos que vieram, numa ida ao banco.

    Recebe valores **já validados**: quem chama valida os dois antes de
    atribuir qualquer um, para que uma recusa no segundo não deixe o primeiro
    aplicado.
    """
    fields: list[str] = []

    if name is not None:
        deck.name = name
        fields.append("name")

    if card_ids is not None:
        deck.card_ids = card_ids
        fields.append("card_ids")

    deck.save(update_fields=[*fields, "updated_at"])

    return deck
