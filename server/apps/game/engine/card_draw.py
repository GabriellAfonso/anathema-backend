"""Tirar a carta do topo do deck e pôr na mão. O movimento, e só ele.

Toda compra do jogo passa por aqui: as 4 do setup, a reposição do mulligan, a
carta de compensação de quem não recebeu o token, e o 1 do Upkeep quando a §9
entrar.

As duas condições da §9 -- teto de mão em 10 e reset de deck pelo cemitério --
ficam **em volta** desta função, não dentro. Nenhuma das duas pode ocorrer no
setup (a mão parte de zero, o deck tem 40), e a regra geral que a §9 pede vai
ser uma função que checa as duas e delega aqui, em vez de uma segunda cópia do
movimento.
"""

from apps.game.match import MatchCard, PlayerState


class EmptyDeckError(Exception):
    """Compra de um deck vazio, citando o dono.

    Não acontece no setup -- 40 cartas, 5 compras -- e não acontece na §9, que
    faz o reset de deck antes de comprar. Chegar aqui é bug de chamador, não
    fluxo de jogo, e por isso levanta em vez de devolver `None`.
    """

    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"user {user_id} cannot draw: the deck is empty, "
            f"expected at least 1 card on top"
        )
        self.user_id = user_id


def draw_from_deck_top(player: PlayerState) -> MatchCard:
    """Move a carta do topo do deck para o fim da mão, e devolve a carta.

    O topo é `deck[0]`, como `player_state.py` fixou. A carta mantém o
    identificador que já tinha -- trocar de zona não cunha identidade nova.

    >>> draw_from_deck_top(player).card_instance_id
    3
    """
    if not player.deck:
        raise EmptyDeckError(player.user_id)

    drawn = player.deck.pop(0)
    player.hand.append(drawn)

    return drawn
