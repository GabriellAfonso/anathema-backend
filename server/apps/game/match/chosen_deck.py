"""O deck com que um jogador entrou na partida, congelado no momento da fila.

Cópia, e **não** referência ao `PlayerDeck` guardado. O deck pode ser renomeado,
reescrito ou apagado a qualquer momento, e um `deck_id` dentro do registro de uma
partida terminada mudaria de significado junto -- o dado histórico ficaria falso
exatamente quando alguém fosse usá-lo.

A lista já viajava congelada: `matchmaking/queue.py` guarda o deck ao lado da
entrada na fila e o pareamento não o relê. O que a feature 012 acrescenta é o
**nome**, que até então se perdia no `deck_id` e é o que um humano reconhece
numa análise de balanceamento.

`frozen` porque isto é registro histórico dentro de um estado que muda: a partida
anda, e o que o jogador escolheu não.
"""

from dataclasses import dataclass

from apps.game.cards import CardId


@dataclass(frozen=True, slots=True)
class ChosenDeck:
    """A lista de cartas da entrada na fila, e o nome que o deck tinha lá.

    Não confundir com `PlayerState.deck`, que é a pilha de compra e **muda**
    durante a partida. Isto é a lista de 40 como ela entrou.

    >>> ChosenDeck(name="Agro", card_ids=(CardId(1), CardId(1), CardId(2))).name
    'Agro'
    """

    name: str
    card_ids: tuple[CardId, ...]
