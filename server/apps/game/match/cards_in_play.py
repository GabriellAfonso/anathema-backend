"""Cartas que pertencem a uma partida: cópias concretas de um molde do
catálogo, cada uma endereçável sozinha.

Uma carta do catálogo é um molde imutável compartilhado por todas as partidas
do servidor. Duas cópias de KRONOS no banco são coisas diferentes, e um feitiço
mirado numa delas não pode acertar a outra — por isso toda carta em partida
carrega identidade própria.

O molde nunca é alterado. Dano, buff e cura recaem sobre a instância.
"""

from dataclasses import dataclass, field
from typing import NewType

from apps.game.cards import CardId

from .modifiers import UnitModifier

# Três inteiros viajam nos mesmos payloads de websocket: `user_id`, `card_id` e
# este. `NewType` custa nada em tempo de execução e transforma a troca de um
# pelo outro em erro de mypy.
#
# É opaco de propósito: não codifica `card_id`, nem dono, nem zona, nem ordinal
# de cópia. Quem quer saber a carta lê `card_id`; quem quer saber o dono vê em
# qual jogador ela está. Derivar qualquer um desses fatos do valor ou da faixa
# é proibido, pelo mesmo motivo que `card.py` proíbe para as faixas de
# `card_id`.
CardInstanceId = NewType("CardInstanceId", int)


@dataclass(slots=True)
class MatchCard:
    """Uma carta que pertence a uma partida. Vive no deck, na mão, no
    cemitério e dentro de uma entrada da pilha.

    Dois campos e mais nada: nome, custo, ataque e vida ficam no catálogo, e
    carta fora do banco não carrega dano nem buff — um `MatchCard` nem tem
    onde guardá-los.

    >>> MatchCard(CardInstanceId(3), CardId(15)).card_id
    15
    """

    card_instance_id: CardInstanceId
    card_id: CardId


@dataclass(slots=True)
class BankUnit:
    """Uma unidade em campo. Existe só enquanto está no banco.

    Contém o `MatchCard` em vez de repetir seus dois campos: assim mover a
    unidade preserva a identidade por construção, e o dano e os modificadores
    ficam para trás sem que ninguém precise lembrar de zerá-los.

    >>> unit = BankUnit(card=MatchCard(CardInstanceId(3), CardId(15)))
    >>> unit.card.card_instance_id
    3

    Mão para banco, e banco para cemitério:

    >>> bank.append(BankUnit(card=hand.pop(index)))
    >>> graveyard.append(dead_unit.card)
    """

    card: MatchCard
    # Dano acumulado, não vida atual. Vida efetiva é o molde mais os
    # modificadores de vida, menos isto — e fazer essa conta é do motor.
    # Guardar vida absoluta obrigaria a desfazer na mão a expiração de um buff
    # de vida temporário, e o resultado passaria a depender da ordem dos
    # eventos.
    damage_taken: int = 0
    # Entra pronta e sem buff: não existe doença de invocação (Fluxo de Partida
    # §5A).
    modifiers: list[UnitModifier] = field(default_factory=list)
