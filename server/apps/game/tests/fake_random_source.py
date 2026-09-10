"""Fonte de aleatoriedade que o teste dita, no lugar de um gerador de verdade.

Um teste que precisa saber qual carta caiu no topo não pode depender de uma
semente: ele passaria a afirmar o algoritmo do CPython em vez da regra do jogo.
Aqui as duas operações têm resultado previsível e visível.

Quem quer provar determinismo de verdade usa `SeededRandomSource` com uma
semente fixa -- é o que `test_setup_randomness.py` faz.
"""

from collections.abc import Sequence
from typing import TypeVar

from apps.game.randomness import RandomSource, Roll

T = TypeVar("T")


class ScriptedRandomSource:
    """Mesma superfície de `RandomSource`, com resultado que o teste prevê.

    `shuffled` inverte a lista e `choose` devolve um índice fixo: duas
    transformações estáveis, que dão para conferir de cabeça.

    Guarda os sorteios recebidos em `rolls`, para que um teste possa afirmar
    que os ordinais avançaram e não se repetiram.

    >>> source = ScriptedRandomSource()
    >>> source.shuffled([1, 2, 3], Roll(RandomSeed("s"), 1))
    [3, 2, 1]
    >>> source.choose(["a", "b"], Roll(RandomSeed("s"), 2))
    'a'
    """

    def __init__(self, *, choice_index: int = 0) -> None:
        self.choice_index = choice_index
        self.rolls: list[Roll] = []

    def shuffled(self, items: Sequence[T], roll: Roll) -> list[T]:
        self.rolls.append(roll)

        return list(reversed(items))

    def choose(self, options: Sequence[T], roll: Roll) -> T:
        self.rolls.append(roll)

        return options[self.choice_index]


# Asserção estática, não código de teste: conformidade de Protocol em Python só
# é conferida em ponto de atribuição, e esta é a única do arquivo. Sem ela, o
# dia em que `RandomSource` ganhar um método o fake fica para trás em silêncio e
# só quebra na cara de quem for injetá-lo. Não apague por parecer sobra.
FAKE_RANDOM_SOURCE_MATCHES_THE_PROTOCOL: RandomSource = ScriptedRandomSource()
