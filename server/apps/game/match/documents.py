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

from .match_outcome import MatchEndReason
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


class TurnDeadlineDocument(TypedDict):
    """A vez e os dois instantes dela (§15), em milissegundos da época."""

    turn_number: int
    holder_user_id: int
    round_number: int
    warns_at_ms: int
    expires_at_ms: int
    warning_sent: bool


class MatchClockDocument(TypedDict):
    """Os prazos da partida. `turn` e `mulligan_expires_at_ms` nunca valem ao
    mesmo tempo, e os dois `None` é partida sem prazo -- antes de o mulligan ser
    armado, e depois do fim.

    Obrigatório e anulável campo a campo, e não ausente: `total=False` tornaria
    **todo** o documento opcional, que é o argumento que `outcome` já usou.
    """

    turn: TurnDeadlineDocument | None
    mulligan_expires_at_ms: int | None


class MatchOutcomeDocument(TypedDict):
    """Quem perdeu, e por quê (§10). O motivo atravessa como string, e a volta
    reembrulha no enum -- como `phase` já faz."""

    defeated_user_id: int
    reason: MatchEndReason


class BlockAssignmentDocument(TypedDict):
    """Um par do bloqueio da §7.2.

    Par, e não uma entrada de objeto `{"4": 3}`: chave de JSON é sempre string,
    e um objeto indexado por identificador de carta precisaria da conversão de
    volta que o cabeçalho deste módulo existe para não ter.
    """

    blocker_card_instance_id: int
    attacker_card_instance_id: int


class CombatDocument(TypedDict):
    """O combate em curso. `blocks` vazia é combate sem bloqueador nenhum; sem
    combate é `MatchDocument["combat"] is None`, que é outro fato."""

    attacker_card_instance_ids: list[int]
    blocks: list[BlockAssignmentDocument]


class ChosenDeckDocument(TypedDict):
    """O deck da entrada na fila: a lista, e o nome que ele tinha lá.

    Cópia congelada, e não `deck_id`: ver o cabeçalho de `chosen_deck.py`.
    """

    name: str
    card_ids: list[int]


class OptionalPlayerFields(TypedDict, total=False):
    """O que um `PlayerDocument` gravado antes da feature 012 não tem.

    `total=False` numa base separada, e não no documento inteiro: tornar **todo**
    o `PlayerDocument` opcional é o que `MatchClockDocument` já recusa logo
    acima, e pela mesma razão. Assim só estes campos podem faltar, e
    `document.get(...)` vale `T | None` sob mypy strict, sem `cast`.

    Some quando não sobrar nenhuma partida viva daquela época -- 6 horas depois
    da implantação, pelo TTL de `store.py`.
    """

    chosen_deck: ChosenDeckDocument | None


class PlayerDocument(OptionalPlayerFields):
    profile: PlayerData
    nexus: int
    deck: list[CardDocument]
    hand: list[CardDocument]
    bank: list[BankUnitDocument]
    graveyard: list[CardDocument]
    energy_current: int
    mulligan_taken: bool


class OptionalMatchFields(TypedDict, total=False):
    """O que um `MatchDocument` gravado antes da feature 012 não tem.

    Mesma forma e mesma razão de `OptionalPlayerFields`.
    """

    started_at: int | None


class MatchDocument(OptionalMatchFields):
    """A partida inteira. `players` é lista de dois, na ordem do par.

    Não tem número de versão de esquema, e continua não tendo. A `version` que
    o Redis guarda ao lado deste documento é versão de **escrita**, do
    compare-and-swap de `store.py`, e por isso não mora aqui.
    """

    match_id: str
    players: list[PlayerDocument]
    round_number: int
    # `None` enquanto a partida está na espera do mulligan: o sorteio da §3 é
    # o que os preenche, os dois juntos.
    token_holder_user_id: int | None
    token_consumed: bool
    priority_user_id: int | None
    phase: MatchPhase
    # `None` enquanto a partida corre, como `token_holder_user_id` é `None`
    # antes do sorteio da §3. Anda junto de `phase == "finished"`.
    outcome: MatchOutcomeDocument | None
    # `None` fora da §7. Obrigatória e anulável, e não ausente: `total=False`
    # tornaria **todo** o documento opcional, que é o argumento que `outcome`
    # já usou.
    combat: CombatDocument | None
    consecutive_passes: int
    # Os prazos da §15. Estado de transporte, gravado junto do resto para
    # atravessar os workers numa escrita só.
    clock: MatchClockDocument
    next_card_instance_id: int
    # `RandomSeed` é `str` em tempo de execução; a volta reembrulha, como
    # `CardId` e `CardInstanceId` já fazem.
    random_seed: str
    next_roll_ordinal: int
