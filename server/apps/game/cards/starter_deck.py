"""Deck de andaime: 40 identificadores válidos derivados do catálogo.

Andaime, não conteúdo. O matchmaking precisa entregar um deck para cada
jogador hoje, e a origem de verdade -- deck montado pelo jogador e guardado em
banco -- é outra feature. Quando ela entrar, esta função sai; nada aqui é
escolha de balanceamento e nada aqui é contrato.

Deriva do catálogo injetado em vez de listar 40 números à mão para que continue
válido quando o catálogo mudar, e para que o teste prove a validade em vez de
repetir a lista.
"""

from .card import CardId
from .catalog import CardCatalog
from .deck_rules import DECK_SIZE, MAX_COPIES_PER_CARD, Deck


def starter_deck(catalog: CardCatalog) -> Deck:
    """40 identificadores, no máximo 3 cópias de cada, todos do catálogo.

    Pega 3 cópias de cada carta, em ordem de `card_id`, até fechar 40 -- a
    última carta entra com o resto, que é 1 quando o catálogo tem 14 ou mais.

    >>> len(starter_deck(mvp_catalog()))
    40
    >>> deck_problems(starter_deck(mvp_catalog()), mvp_catalog())
    ()
    """
    deck: list[CardId] = []

    for card in catalog.all_cards():
        if len(deck) >= DECK_SIZE:
            break

        deck.extend([card.card_id] * _copies_to_take(len(deck)))

    _reject_catalog_too_small(deck, catalog)

    return tuple(deck)


def _copies_to_take(already_taken: int) -> int:
    """Três, ou o que faltar para 40 quando faltar menos que três."""
    return min(MAX_COPIES_PER_CARD, DECK_SIZE - already_taken)


def _reject_catalog_too_small(deck: list[CardId], catalog: CardCatalog) -> None:
    """Devolver um deck curto em silêncio jogaria o erro em `deck_problems`,
    longe de quem o causou. Aqui a mensagem diz qual catálogo não deu conta."""
    if len(deck) == DECK_SIZE:
        return

    raise ValueError(
        f"catalog with {len(catalog.all_cards())} cards yields only "
        f"{len(deck)} deck entries at {MAX_COPIES_PER_CARD} copies each: "
        f"expected at least {DECK_SIZE}"
    )
