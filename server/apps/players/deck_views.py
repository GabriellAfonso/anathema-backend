"""Os decks do jogador pelo HTTP: listar, criar, ler, editar e apagar.

Toda rota opera **só** sobre os decks do autenticado, e o isolamento vem do
queryset (`deck_queries`), não de uma checagem depois da busca. Deck de outro
jogador e deck inexistente recebem o mesmo `404`, com o mesmo corpo: confirmar
que o deck 5 existe já entrega informação a quem não deveria tê-la.

O contrato está em `specs/011-deck-catalog-api/contracts/http_decks.md`.
"""

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.game.cards import CardCatalog, InvalidDeckError, get_card_catalog
from apps.players.deck_serializers import DeckSerializer, deck_write_fields
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile
from apps.players.services.deck_problem_payload import deck_problems_payload
from apps.players.services.deck_queries import deck_of, decks_of
from apps.players.services.deck_validation import (
    InvalidDeckNameError,
    TooManyDecksError,
)
from apps.players.services.deck_writes import (
    EmptyDeckUpdateError,
    create_deck,
    delete_deck,
    update_deck,
)


class DeckCollectionView(APIView):
    """`/players/decks/`: a coleção do jogador autenticado."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Os decks do autenticado, e só eles.

        Lista vazia é resposta válida: um jogador sem deck nenhum recebe `200`
        com `{"decks": []}`, não um erro.

        >>> client.get("/players/decks/").data["decks"]
        []
        """
        decks = decks_of(player_profile(request).pk)

        return Response({"decks": DeckSerializer(decks, many=True).data})

    def post(self, request: Request) -> Response:
        """Cria um deck. Deck recusado não é salvo nem parcialmente.

        >>> client.post("/players/decks/", deck).status_code
        201
        """
        profile = player_profile(request)
        name, card_ids = _required_fields(request)

        try:
            deck = create_deck(
                profile, name=name, card_ids=card_ids, catalog=deck_catalog()
            )
        except (TooManyDecksError, InvalidDeckNameError, InvalidDeckError) as refused:
            return _refusal_response(refused)

        return Response(DeckSerializer(deck).data, status=status.HTTP_201_CREATED)


class DeckItemView(APIView):
    """`/players/decks/<deck_id>/`: um deck do jogador autenticado."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, deck_id: int) -> Response:
        """O deck, ou `404` -- inclusive quando ele é de outro jogador.

        >>> client.get("/players/decks/4/").data["deck_id"]
        4
        """
        return Response(DeckSerializer(_owned_deck(request, deck_id)).data)

    def patch(self, request: Request, deck_id: int) -> Response:
        """Renomeia, troca a lista, ou as duas coisas.

        Uma recusa deixa o deck guardado exatamente como estava.

        >>> client.patch("/players/decks/4/", {"name": "Agro v2"}).status_code
        200
        """
        deck = _owned_deck(request, deck_id)
        fields = deck_write_fields(request.data)

        try:
            update_deck(
                deck,
                name=fields.name,
                card_ids=fields.card_ids,
                catalog=deck_catalog(),
            )
        except (
            EmptyDeckUpdateError,
            InvalidDeckNameError,
            InvalidDeckError,
        ) as refused:
            return _refusal_response(refused)

        return Response(DeckSerializer(deck).data)

    def delete(self, request: Request, deck_id: int) -> Response:
        """Apaga o deck. Partida em andamento e entrada na fila não mudam.

        >>> client.delete("/players/decks/4/").status_code
        204
        """
        delete_deck(_owned_deck(request, deck_id))

        return Response(status=status.HTTP_204_NO_CONTENT)


def deck_catalog() -> CardCatalog:
    """O catálogo contra o qual um deck salvo é validado.

    Função e não constante de módulo para que a fábrica em cache seja
    consultada na requisição, e não na importação do módulo.

    >>> len(deck_catalog().all_cards())
    29
    """
    return get_card_catalog()


def player_profile(request: Request) -> PlayerProfile:
    """O perfil do autenticado, ou `404` se ele não é jogador.

    Mesma razão de `PlayerMeView`: contas criadas fora do registro
    (`createsuperuser`, fixtures) não têm perfil, e deck pertence a jogador.
    Não é vazamento -- elas não possuem deck nenhum a distinguir.
    """
    profile = PlayerProfile.objects.filter(user=request.user).first()

    if profile is None:
        raise NotFound(
            f"user_id={request.user.pk} não tem PlayerProfile. "
            "Só contas criadas pelo registro são jogadores."
        )

    return profile


def _owned_deck(request: Request, deck_id: int) -> PlayerDeck:
    """O deck do autenticado, ou a **mesma** ausência dos dois casos.

    Deck inexistente e deck de outro jogador chegam aqui pelo mesmo caminho --
    `deck_of` filtra por dono -- e saem com o `404` padrão, sem detalhe
    próprio. Nada na resposta distingue um do outro.
    """
    deck = deck_of(player_profile(request).pk, deck_id)

    if deck is None:
        raise NotFound()

    return deck


def _required_fields(request: Request) -> tuple[str, list[int]]:
    """`name` e `card_ids`, os dois obrigatórios na criação.

    O `PATCH` aceita um só; criar exige os dois, porque um deck sem lista não
    existe -- não há rascunho a guardar.
    """
    fields = deck_write_fields(request.data)

    if fields.name is None or fields.card_ids is None:
        raise ValidationError(
            {"detail": "creating a deck needs both 'name' and 'card_ids'"}
        )

    return fields.name, fields.card_ids


def _refusal_response(error: Exception) -> Response:
    """Traduz a recusa do serviço para o corpo do contrato.

    Um `match` sobre os quatro tipos, e não um `except` por caminho: os dois
    verbos de escrita recusam pelas mesmas razões, e escrever a tradução duas
    vezes deixaria as duas saírem diferentes.

    `Response` e não `ValidationError`: o DRF converte todo valor de uma
    `ValidationError` em `ErrorDetail`, e `card_id`, `count` e `limit`
    chegariam ao cliente como texto. Os problemas de deck precisam dos números.
    """
    match error:
        case InvalidDeckError():
            body: dict[str, object] = {
                "deck_problems": deck_problems_payload(error.problems)
            }
        case InvalidDeckNameError():
            body = {"name": [str(error)]}
        case TooManyDecksError():
            body = {"deck_limit": [str(error)]}
        case _:
            body = {"detail": str(error)}

    return Response(body, status=status.HTTP_400_BAD_REQUEST)
