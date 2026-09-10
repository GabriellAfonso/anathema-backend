"""A partida como ela viaja: o que a serialização grava e lê no Redis.

Chave de objeto JSON é sempre string. O modelo anterior guardava as mãos e o
tabuleiro em dicionários indexados por `user_id` e precisava converter as
chaves de volta para inteiro na leitura -- conserto que alguém tinha de
lembrar em toda estrutura nova, e cujo esquecimento não dá erro, dá busca que
não acha nada.

Aqui não existe chave por `user_id` em nível nenhum: os jogadores são uma
lista, e o `user_id` mora dentro de `profile`, como valor. Não sobra o que
converter.

Os campos de enum são `StrEnum`, que já é `str`: `json.dumps` os escreve como
texto e a volta compara igual.
"""

from typing import Literal, TypedDict

from apps.game.cards import EffectDuration
from apps.players.services.player_queries import PlayerData

from .match_state import MatchPhase
from .modifiers import ModifierKind


class CardDocument(TypedDict):
    """Uma carta em partida. Nome, custo, ataque e vida ficam no catálogo."""

    card_instance_id: int
    card_id: int


class AttackModifierDocument(TypedDict):
    modifier_kind: Literal[ModifierKind.ATTACK]
    amount: int
    duration: EffectDuration


class HealthModifierDocument(TypedDict):
    modifier_kind: Literal[ModifierKind.HEALTH]
    amount: int
    duration: EffectDuration


class DamageImmunityDocument(TypedDict):
    """Sem `amount`: a mecânica é tudo ou nada, e o documento espelha isso."""

    modifier_kind: Literal[ModifierKind.DAMAGE_IMMUNITY]
    duration: EffectDuration


# União etiquetada por `modifier_kind`: o mypy estreita para o braço certo num
# `match` sobre esse campo, então ler `amount` de uma imunidade é erro de tipo.
ModifierDocument = (
    AttackModifierDocument | HealthModifierDocument | DamageImmunityDocument
)


class BankUnitDocument(TypedDict):
    """Dano acumulado, nunca vida atual -- vida efetiva é derivada."""

    card: CardDocument
    damage_taken: int
    modifiers: list[ModifierDocument]


class StackEntryDocument(TypedDict):
    """O alvo é o identificador, nunca uma referência. `None` é ausência de
    alvo, não alvo que sumiu."""

    card: CardDocument
    caster_user_id: int
    target_card_instance_id: int | None


class PlayerDocument(TypedDict):
    profile: PlayerData
    nexus: int
    deck: list[CardDocument]
    hand: list[CardDocument]
    bank: list[BankUnitDocument]
    graveyard: list[CardDocument]
    energy_max: int
    energy_current: int


class MatchDocument(TypedDict):
    """A partida inteira. `players` é lista de dois, na ordem do par."""

    match_id: str
    players: list[PlayerDocument]
    round_number: int
    token_holder_user_id: int
    token_consumed: bool
    priority_user_id: int
    phase: MatchPhase
    stack: list[StackEntryDocument]
    consecutive_passes: int
    next_card_instance_id: int
