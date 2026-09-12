"""O que um deck precisa ser para ser salvo.

Três perguntas, e duas delas já estavam respondidas em outro lugar:

1. **O nome** serve? É desta feature.
2. **A lista** passa nas três regras? É da feature 001 -- `deck_problems` --, e
   aqui ela é chamada, nunca reescrita.
3. **Cabe mais um deck?** É desta feature.

Não existe rascunho: um deck de 12 cartas é recusado no salvamento. A decisão
está em `specs/011-deck-catalog-api/spec.md`, seção *Clarifications*.

Isto **não** substitui a validação da entrada na fila. Um deck salvo ontem pode
citar uma carta que saiu do catálogo hoje: o salvamento valida contra o
catálogo daquele momento, e a fila contra o do momento da partida.
"""

from collections.abc import Sequence

from apps.game.cards import CardCatalog, CardId, Deck, ensure_valid_deck

# Pedido do maintainer na sessão de 2026-09-12: folga larga para quem gosta de
# variar, e teto baixo o bastante para a listagem caber numa resposta só.
DECK_LIMIT_PER_PLAYER = 20

# Casa com `PlayerDeck.name.max_length`. As duas precisam andar juntas: o banco
# truncaria em silêncio o que esta checagem deixasse passar.
MAX_DECK_NAME_LENGTH = 50


class InvalidDeckNameError(Exception):
    """Nome vazio, só espaços, ou acima do limite. A mensagem diz qual era.

    >>> raise InvalidDeckNameError("   ")
    InvalidDeckNameError: name is '   ': expected a non-empty name of up to 50
    characters
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            f"name is {name!r}: expected a non-empty name of up to "
            f"{MAX_DECK_NAME_LENGTH} characters"
        )
        self.name = name


class TooManyDecksError(Exception):
    """O jogador já está no teto. A mensagem diz o teto e a contagem atual.

    >>> raise TooManyDecksError(20)
    TooManyDecksError: player already has 20 decks: the limit is 20
    """

    def __init__(self, deck_count: int) -> None:
        super().__init__(
            f"player already has {deck_count} decks: "
            f"the limit is {DECK_LIMIT_PER_PLAYER}"
        )
        self.deck_count = deck_count
        self.limit = DECK_LIMIT_PER_PLAYER


def validated_deck_name(name: str) -> str:
    """O nome sem os espaços das pontas, ou recusa citando o que veio.

    Nome repetido **não** é recusado: a identidade do deck é o `deck_id`, e o
    nome é rótulo de quem montou.

    >>> validated_deck_name("  Agro  ")
    'Agro'
    """
    trimmed = name.strip()

    if not trimmed or len(trimmed) > MAX_DECK_NAME_LENGTH:
        raise InvalidDeckNameError(name)

    return trimmed


def validated_card_ids(card_ids: Sequence[int], catalog: CardCatalog) -> Deck:
    """A lista, se ela passa nas três regras da feature 001.

    Recusa com `InvalidDeckError`, que carrega **todos** os problemas de uma
    vez -- um construtor de deck quer a lista inteira para pintar a tela, não o
    primeiro erro.

    >>> len(validated_card_ids(list(starter_deck(catalog)), catalog))
    40
    """
    deck = tuple(CardId(card_id) for card_id in card_ids)

    ensure_valid_deck(deck, catalog)

    return deck


def ensure_room_for_another_deck(deck_count: int) -> None:
    """Aceita em silêncio, ou recusa citando o teto e a contagem atual.

    Só a criação pergunta isto: renomear, editar e apagar continuam
    funcionando com o jogador no teto.

    >>> ensure_room_for_another_deck(3)
    """
    if deck_count < DECK_LIMIT_PER_PLAYER:
        return

    raise TooManyDecksError(deck_count)
