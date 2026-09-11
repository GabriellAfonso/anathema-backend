"""O estado de uma partida viva e a serialização que o leva ao Redis.

Nada aqui é regra de jogo: não se decide se uma jogada é legal, não se aplica
dano, não se troca prioridade nem se avança fase. O estado é dado; quem o
transforma é o motor.

>>> from apps.game.match import Match
>>> match.has_player(7)
True

Quem monta uma partida é `apps.game.engine.start_match`, que executa a §3.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.
"""

from .cards_in_play import BankUnit, CardInstanceId, MatchCard
from .combat_state import BlockAssignment, CombatState
from .documents import (
    BankUnitDocument,
    BlockAssignmentDocument,
    CardDocument,
    CombatDocument,
    MatchDocument,
    MatchOutcomeDocument,
    ModifierDocument,
    PlayerDocument,
)
from .match_outcome import InvalidMatchOutcomeError, MatchOutcome
from .match_state import (
    Match,
    MatchIsNotInCombatError,
    MatchPhase,
    NotAParticipantError,
)
from .modifiers import (
    AttackModifier,
    DamageImmunity,
    HealthModifier,
    ModifierKind,
    UnitModifier,
)
from .player_state import STARTING_NEXUS, PlayerState
from .player_view import (
    OpponentSideView,
    PlayerSideView,
    PlayerView,
    build_player_view,
)
from .serialization import (
    combat_from_document,
    match_from_document,
    match_outcome_from_document,
    to_combat_document,
    to_match_document,
    to_match_outcome_document,
)

__all__ = [
    # Cartas em partida
    "CardInstanceId",
    "MatchCard",
    "BankUnit",
    # Modificadores
    "ModifierKind",
    "AttackModifier",
    "HealthModifier",
    "DamageImmunity",
    "UnitModifier",
    # Combate (§7)
    "BlockAssignment",
    "CombatState",
    # Estado
    "MatchPhase",
    "PlayerState",
    "Match",
    "NotAParticipantError",
    "MatchIsNotInCombatError",
    "STARTING_NEXUS",
    # Desfecho da partida (§10)
    "MatchOutcome",
    "InvalidMatchOutcomeError",
    # Forma gravada
    "CardDocument",
    "ModifierDocument",
    "BankUnitDocument",
    "BlockAssignmentDocument",
    "CombatDocument",
    "PlayerDocument",
    "MatchOutcomeDocument",
    "MatchDocument",
    "to_match_document",
    "match_from_document",
    "to_match_outcome_document",
    "match_outcome_from_document",
    "to_combat_document",
    "combat_from_document",
    # Visão do jogador
    "PlayerSideView",
    "OpponentSideView",
    "PlayerView",
    "build_player_view",
]
