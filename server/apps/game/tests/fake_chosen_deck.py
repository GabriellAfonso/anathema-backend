"""O deck da entrada na fila, para testes que só se importam com a lista.

Desde a feature 012 a fila, o `MatchEntry` e o `PlayerState` carregam um
`ChosenDeck` -- lista **e** nome --, porque o nome é o que o registro do
resultado guarda. A maioria dos testes de partida não tem opinião sobre o nome:
eles querem 40 cartas válidas.

Existe para que essa maioria continue passando só a lista, em vez de repetir um
nome inventado em cem chamadas.
"""

from apps.game.cards import Deck, mvp_catalog, starter_deck
from apps.game.match import ChosenDeck

FAKE_DECK_NAME = "Fake Deck"


def fake_chosen_deck(deck: Deck | None = None, name: str = FAKE_DECK_NAME) -> ChosenDeck:
    """Um deck escolhido, com o de andaime do MVP quando nada é passado.

    >>> len(fake_chosen_deck().card_ids)
    40
    >>> fake_chosen_deck(name="Agro").name
    'Agro'
    """
    return ChosenDeck(
        name=name,
        card_ids=tuple(deck if deck is not None else starter_deck(mvp_catalog())),
    )
