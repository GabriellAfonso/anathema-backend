"""O deck que todo jogador ganha ao nascer.

Sem ele, uma conta nova não teria deck nenhum, não conseguiria entrar na fila e
não existiria partida para ela -- o caminho do registro até a primeira partida
passaria obrigatoriamente por montar 40 cartas à mão.

É um deck comum: renomeável, editável e apagável como qualquer outro, e conta
para o teto de decks. Não há proteção especial, e a lista dele não é escolha de
balanceamento.
"""

from apps.game.cards import CardCatalog, starter_deck
from apps.players.models.deck import PlayerDeck
from apps.players.models.player import PlayerProfile

STARTER_DECK_NAME = "Deck inicial"


def create_starter_deck(profile: PlayerProfile, *, catalog: CardCatalog) -> PlayerDeck:
    """Cria o deck inicial do jogador, derivado do catálogo.

    Derivado e não listado à mão para que continue válido quando o catálogo
    mudar -- é a mesma razão que `cards/starter_deck.py` dá de si mesmo.

    Não confere o teto nem revalida a lista: `starter_deck` só devolve deck
    válido, e o jogador acabou de nascer com zero decks.

    >>> create_starter_deck(profile, catalog=catalog).name
    'Deck inicial'
    """
    return PlayerDeck.objects.create(
        profile=profile,
        name=STARTER_DECK_NAME,
        card_ids=[int(card_id) for card_id in starter_deck(catalog)],
    )
