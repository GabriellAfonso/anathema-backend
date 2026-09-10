"""Aleatoriedade de partida, endereçada por semente e número do sorteio.

Único módulo do projeto que importa `random`. Embaralhar e sortear chegam por
parâmetro a quem precisa deles, atrás do `Protocol` daqui, para que um teste
possa ditar a ordem sem simular gerador nenhum.

O que este módulo resolve: o setup da §3 consome aleatoriedade em momentos
separados por uma espera de websocket -- embaralhar na criação, reembaralhar no
mulligan, sortear o token quando o segundo jogador responde. Entre um e outro a
partida vai ao Redis e volta, possivelmente em outro worker do uvicorn, e um
gerador não sobrevive a essa viagem.

A saída é não guardar gerador nenhum: a partida guarda uma semente e um
contador de sorteios, e cada operação abre um fluxo próprio derivado do par.
Assim quantos números uma operação consome deixa de importar, porque a
seguinte não continua o mesmo fluxo -- ela abre outro.

>>> source = SeededRandomSource()
>>> source.shuffled([1, 2, 3], Roll(RandomSeed("s"), 1)) == source.shuffled(
...     [1, 2, 3], Roll(RandomSeed("s"), 1)
... )
True
"""

import random
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NewType, Protocol, TypeVar

# A semente de uma partida. Texto e não inteiro por dois motivos:
# `random.Random` semeia string por SHA-512 do conteúdo, sem depender de
# `PYTHONHASHSEED` nem do processo; e texto atravessa o JSON sem conversão.
#
# `NewType` pelo mesmo motivo de `CardId` e `CardInstanceId`: passar um
# `match_id` onde se espera uma semente vira erro de mypy, e os dois são str.
RandomSeed = NewType("RandomSeed", str)

T = TypeVar("T")


class EmptyOptionsError(Exception):
    """Sortearam entre nada. Não é caso de borda do jogo: é bug de chamador."""

    def __init__(self, roll: "Roll") -> None:
        super().__init__(
            f"roll {roll.ordinal} of seed {roll.seed!r} has no options to "
            f"choose from: expected a sequence with at least 1 item"
        )
        self.roll = roll


@dataclass(frozen=True, slots=True)
class Roll:
    """Um sorteio identificado: onde, no espaço de aleatoriedade da partida.

    Congelado porque é endereço, não objeto com estado. Cunhado só por
    `Match.mint_roll()`, como `CardInstanceId` é cunhado só por
    `Match.mint_card_instance_id()`.

    >>> Roll(RandomSeed("abc"), 3).ordinal
    3
    """

    seed: RandomSeed
    ordinal: int


class RandomSource(Protocol):
    """A aleatoriedade atrás de uma interface do projeto.

    Duas chamadas com o mesmo `Roll` devolvem o mesmo resultado, em qualquer
    processo: implementações não guardam estado entre chamadas.

    É `Protocol` e não classe base para que um substituto de teste só precise
    dos dois métodos, sem herdar de nada -- a mesma escolha de `CardCatalog`.
    """

    def shuffled(self, items: Sequence[T], roll: Roll) -> list[T]:
        """Permutação de `items`. Lista nova; a original não é tocada.

        >>> source.shuffled(player.deck, match.mint_roll())
        """
        ...

    def choose(self, options: Sequence[T], roll: Roll) -> T:
        """Um dos `options`, ou `EmptyOptionsError` citando o sorteio.

        >>> source.choose(match.players, match.mint_roll()).user_id
        9
        """
        ...


class SeededRandomSource:
    """`RandomSource` sobre `random.Random`, semeado por `(seed, ordinal)`.

    Sem estado próprio: a mesma instância serve qualquer partida e qualquer
    worker, e o ponto de composição pode ter uma só.

    >>> SeededRandomSource().shuffled([1, 2, 3], Roll(RandomSeed("s"), 1))
    [2, 1, 3]
    """

    def shuffled(self, items: Sequence[T], roll: Roll) -> list[T]:
        """Embaralha uma cópia, para que o chamador decida onde ela vai."""
        drawn = list(items)
        self._generator(roll).shuffle(drawn)

        return drawn

    def choose(self, options: Sequence[T], roll: Roll) -> T:
        """Escolhe um, recusando a sequência vazia com o sorteio na mensagem."""
        if not options:
            raise EmptyOptionsError(roll)

        return self._generator(roll).choice(options)

    def _generator(self, roll: Roll) -> random.Random:
        """Um gerador por sorteio, e nunca um compartilhado entre chamadas.

        A chave é texto porque semear com tupla não é aceito nas versões
        atuais, e porque `random.Random(str)` passa pelo SHA-512 do conteúdo --
        determinístico entre processos, ao contrário de `hash()`.
        """
        return random.Random(f"{roll.seed}:{roll.ordinal}")


def new_random_seed() -> RandomSeed:
    """Semente nova, de entropia do sistema. Chamada no ponto de composição.

    `secrets` e não `random`: a semente decide a ordem de dois decks, e um
    valor adivinhável deixaria de ser aleatoriedade para virar informação.

    >>> len(new_random_seed())
    32
    """
    return RandomSeed(secrets.token_hex(16))
