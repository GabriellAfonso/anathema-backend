"""Ler decks -- sempre pelos do dono, nunca por identificador solto.

O isolamento entre jogadores sai **da consulta**, e não de uma checagem depois
dela. Toda leitura parte de `filter(profile=<dono>, ...)`, de modo que deck de
outro jogador e deck inexistente percorrem o mesmo caminho e produzem a mesma
ausência. Não existe ramo que saiba a diferença, então não existe ramo que
possa vazá-la.

Uma checagem escrita como `if deck.profile_id != user_id: recusa` já teria
respondido "esse deck existe" antes de recusar -- e confirmar que o deck 5
existe já entrega informação a quem não deveria tê-la.
"""

from typing import Protocol, cast

from channels.db import database_sync_to_async
from django.db.models import QuerySet

from apps.game.cards import CardId
from apps.game.match import ChosenDeck
from apps.players.models.deck import PlayerDeck


def decks_of(user_id: int) -> QuerySet[PlayerDeck]:
    """Os decks daquele jogador, do mais antigo para o mais novo.

    `user_id` e não `profile_id`: são o mesmo inteiro (decisão 0001), e este é
    o nome do espaço de identidade do projeto.

    >>> decks_of(7).count()
    2
    """
    return PlayerDeck.objects.filter(profile_id=user_id).order_by("pk")


def deck_of(user_id: int, deck_id: int) -> PlayerDeck | None:
    """O deck daquele jogador com aquele identificador, ou `None`.

    `None` cobre os dois casos de propósito: o deck não existe, ou existe e é
    de outro jogador. Quem chama não consegue distinguir, porque não deve.

    >>> deck_of(7, 4) is None
    False
    """
    return decks_of(user_id).filter(pk=deck_id).first()


def deck_count_of(user_id: int) -> int:
    """Quantos decks o jogador tem. Para o teto, na criação.

    >>> deck_count_of(7)
    2
    """
    return decks_of(user_id).count()


class PlayerDeckSource(Protocol):
    """A porta por onde o socket de matchmaking lê o deck do jogador.

    `Protocol` e não classe base para que o substituto de teste só precise do
    método, sem herdar de nada -- mesma razão de `CardCatalog`.

    Existe para manter o transporte fora do ORM: o `conftest.py` de
    `apps/game/tests` registra que nenhum teste de websocket toca o banco, e é
    esta porta que deixa isso continuar valendo.
    """

    async def deck_for(self, *, user_id: int, deck_id: int) -> ChosenDeck | None:
        """O deck daquele jogador -- lista e nome --, ou `None` se não é dele.

        Nome junto da lista desde a feature 012: ele viaja até o registro do
        resultado, e uma segunda ida ao banco no momento do registro leria o
        nome de **depois**, que é o que a cópia congelada existe para evitar.
        """
        ...


class DatabasePlayerDeckSource:
    """A implementação de verdade: o deck vem do banco, pelo dono.

    >>> await DatabasePlayerDeckSource().deck_for(user_id=7, deck_id=4)
    ChosenDeck(name='Agro', card_ids=(1, 1, 1, 2, ...))
    """

    async def deck_for(self, *, user_id: int, deck_id: int) -> ChosenDeck | None:
        """O deck guardado, ou `None` -- inexistente e alheio, indistintos.

        O `cast` existe porque `database_sync_to_async` chega sem stubs e
        devolve `Any`; a função embrulhada é tipada logo abaixo.
        """
        return cast(ChosenDeck | None, await _read_deck(user_id, deck_id))


# channels não publica stubs, então o decorator chega como `Any` e levaria a
# função inteira junto.
@database_sync_to_async  # type: ignore[untyped-decorator]
def _read_deck(user_id: int, deck_id: int) -> ChosenDeck | None:
    """A leitura síncrona, do jeito que o Django sabe fazer.

    Lista e nome na mesma ida: são a mesma linha do banco.
    """
    deck = deck_of(user_id, deck_id)

    if deck is None:
        return None

    return ChosenDeck(
        name=deck.name,
        card_ids=tuple(CardId(card_id) for card_id in deck.card_ids),
    )


DATABASE_SOURCE_MATCHES_THE_PROTOCOL: PlayerDeckSource = DatabasePlayerDeckSource()
