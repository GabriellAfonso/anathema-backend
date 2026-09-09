"""As cartas do catálogo: o que elas são, não o que fazem em partida.

Uma carta aqui é um molde imutável. A unidade que ganha buff no banco é uma
instância dela, criada pela camada de partida — o catálogo nunca muda.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from .effects import SpellEffect

# `user_id` e `card_id` são os dois inteiros e viajam nos mesmos payloads de
# websocket. `NewType` custa nada em tempo de execução e transforma a troca de
# um pelo outro em erro de mypy.
CardId = NewType("CardId", int)


class CardType(StrEnum):
    """O tipo é campo próprio, nunca um detalhe codificado dentro do `card_id`."""

    UNIT = "unit"
    SPELL = "spell"


# Faixas de alocação: unidade embaixo, feitiço em cima. Serve para ler uma lista
# de deck crua e reconhecer o que é o quê. NÃO é como se descobre o tipo de uma
# carta — isso é `card_type`, e comparar `card_id` com 1000 para decidir tipo é
# proibido.
UNIT_ID_MIN = 1
UNIT_ID_MAX = 1000
SPELL_ID_MIN = 1001


@dataclass(frozen=True, slots=True)
class Unit:
    """Carta permanente: fica no banco até morrer.

    `health` e não `defense`: "defesa" colide com bloqueio, que é outra
    mecânica. E não `nexus`, que é a vida do jogador e mora na partida.

    >>> Unit(CardId(1), "JOHN COPPER", 5, 7, 5, "john_card").health
    5
    """

    card_id: CardId
    name: str
    energy: int
    attack: int
    health: int
    image: str

    @property
    def card_type(self) -> CardType:
        """Sempre `UNIT`.

        Propriedade e não campo com default: campo aceitaria
        `Unit(card_type=CardType.SPELL)`, estado que não pode existir.
        """
        return CardType.UNIT


@dataclass(frozen=True, slots=True)
class Spell:
    """Carta de efeito único: resolve e vai para o cemitério.

    `description` é para o cliente mostrar ao jogador. O motor lê `effect`.

    >>> Spell(CardId(1004), "LIFE POTION", 4, "Você recupera 5 de Nexus.",
    ...       RestoreNexus(amount=5), "life_potion").effect.amount
    5
    """

    card_id: CardId
    name: str
    energy: int
    description: str
    effect: SpellEffect
    image: str

    @property
    def card_type(self) -> CardType:
        """Sempre `SPELL`. Mesma razão de `Unit.card_type`."""
        return CardType.SPELL


# União fechada: um `match` sobre `Card` que esqueça um braço é erro de mypy.
Card = Unit | Spell
