"""O motor de regras: o que transforma o estado de partida.

`apps.game.match` guarda a partida e responde perguntas sobre ela, e diz de si
mesmo que nada ali é regra. Este pacote é o outro lado: aqui se embaralha, se
compra, se troca carta e se sorteia o dono do token.

Moram aqui o setup da §3, a compra com reset de deck da §9, o ciclo de rodada
das §4, §5 e §8 -- o Upkeep, a Fase de Ação com as quatro ações que existem, e o
Fim de Rodada --, o feitiço imediato da §5B com os cinco efeitos do MVP, o
combate da §7 com a janela livre do defensor e o dano simultâneo, e a condição
de vitória da §10.

Uma partida roda do setup da §3 à vitória da §10 sem tocar em websocket. A nota
foi corrigida duas vezes em 2026-09-11: a primeira correção (feitiço que
resolve na hora e não gasta a vez) é a feature 008; a segunda -- energia que acumula, a
declaração como janela, regra própria de SACRIFICIAL FIRE e MAGIC BARRIER, a
desistência -- ainda não está aqui. O relógio da vez (§15) é problema de
transporte, não deste pacote.

>>> from apps.game.engine import MatchEntry, start_match
>>> match = start_match(one, two, catalog=catalog, randomness=source, seed=seed)
>>> match.phase
<MatchPhase.MULLIGAN: 'mulligan'>

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.
"""

from .card_draw import (
    MAX_HAND_SIZE,
    NegativeDrawCountError,
    draw_card,
    draw_cards,
)
from .blocker_pairing import (
    AttackerAlreadyBlockedError,
    BlockerAlreadyBlockingError,
    BlockerNotAssignedError,
    BlockerNotInBankError,
    UnitIsNotAttackingError,
)
from .declare_attack import (
    AttackerNotInBankError,
    AttackTokenAlreadyConsumedError,
    BankHasNoUnitsError,
    DuplicateAttackerError,
    NoAttackersSelectedError,
    NotTheTokenHolderError,
)
from .deck_reset import reset_deck_from_graveyard
from .match_setup import (
    InvalidPlayerDeckError,
    MatchEntry,
    finish_setup,
    start_match,
)
from .mulligan import (
    MulliganAlreadyTakenError,
    record_mulligan,
)
from .play_unit import (
    MAX_BANK_SIZE,
    BankIsFullError,
    CardIsNotAUnitError,
)
from .action_kind import ActionKind
from .combat_action import (
    AssignBlockerAction,
    EndDefenseWindowAction,
    RemoveBlockerAction,
)
from .player_action import (
    CardNotInHandError,
    CastSpellAction,
    DeclareAttackAction,
    IllegalActionError,
    MatchIsOverError,
    NotEnoughEnergyError,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    PlayerAction,
    PlayUnitAction,
    card_in_hand,
    ensure_enough_energy,
)
from .spell_cast_guards import (
    CardIsNotASpellError,
    SpellNeedsTargetError,
    SpellTakesNoTargetError,
    SpellTargetNotOnBattlefieldError,
    WrongSpellTargetSideError,
)
from .spell_effect import SpellEffectNeedsTargetError, apply_spell_effect
from .unit_damage import bury_dead_units, deal_damage_to_unit
from .unit_vitals import (
    BankUnitIsNotAUnitError,
    unit_effective_attack,
    unit_has_damage_immunity,
    unit_is_dead,
    unit_max_health,
    unit_remaining_health,
)
from .round_cycle import (
    CONSECUTIVE_PASSES_TO_EXIT,
    MatchNotAwaitingUpkeepError,
    begin_round_cycle,
    submit_action,
)
from .upkeep import MAX_ENERGY
from .victory import SimultaneousDefeatError, change_nexus, check_victory, forfeit

__all__ = [
    # Compra (§9)
    "draw_card",
    "draw_cards",
    "MAX_HAND_SIZE",
    "NegativeDrawCountError",
    # Reset de deck (§9)
    "reset_deck_from_graveyard",
    # Setup (§3)
    "MatchEntry",
    "start_match",
    "finish_setup",
    "InvalidPlayerDeckError",
    # Mulligan (§3)
    "record_mulligan",
    "MulliganAlreadyTakenError",
    # A forma da ação (§5)
    "ActionKind",
    "PlayUnitAction",
    "CastSpellAction",
    "DeclareAttackAction",
    "PassAction",
    "PlayerAction",
    # A forma das ações que só existem na janela do defensor (§7.2)
    "AssignBlockerAction",
    "RemoveBlockerAction",
    "EndDefenseWindowAction",
    # Recusas de jogada (§5)
    "IllegalActionError",
    "NotYourPriorityError",
    "PhaseForbidsActionError",
    "CardNotInHandError",
    "CardIsNotAUnitError",
    "NotEnoughEnergyError",
    "BankIsFullError",
    "MatchIsOverError",
    # Recusas de lançamento de feitiço, compartilhadas pela §5B e pela §7.2
    #
    # `cast_spell` e `validated_spell_cast` **não** entram aqui, pela mesma
    # razão de `run_upkeep` e `end_round`: quem as chama é `round_cycle`.
    "CardIsNotASpellError",
    "SpellTakesNoTargetError",
    "SpellNeedsTargetError",
    "WrongSpellTargetSideError",
    "SpellTargetNotOnBattlefieldError",
    # Recusas de declaração de ataque (§5C, §7.1)
    #
    # `declare_attack` **não** entra aqui, pela mesma razão de `cast_spell`:
    # quem a chama é `round_cycle`.
    "NotTheTokenHolderError",
    "AttackTokenAlreadyConsumedError",
    "BankHasNoUnitsError",
    "NoAttackersSelectedError",
    "AttackerNotInBankError",
    "DuplicateAttackerError",
    # Recusas de bloqueio (§7.2)
    #
    # `assign_blocker` e `remove_blocker` **não** entram aqui, pela mesma razão:
    # quem as chama é `round_cycle`.
    "BlockerNotInBankError",
    "UnitIsNotAttackingError",
    "BlockerAlreadyBlockingError",
    "AttackerAlreadyBlockedError",
    "BlockerNotAssignedError",
    # Guardas que jogar unidade e lançar feitiço fazem identicamente (§5A, §5B)
    "card_in_hand",
    "ensure_enough_energy",
    # Ciclo de rodada (§4, §5, §8)
    #
    # `run_upkeep` e `end_round` **não** entram aqui: quem os chama é
    # `round_cycle`, e expô-los daria uma porta por onde executar meia rodada --
    # o contrário do que a cascata garante. Os testes deles importam do módulo.
    "begin_round_cycle",
    "submit_action",
    "MatchNotAwaitingUpkeepError",
    "CONSECUTIVE_PASSES_TO_EXIT",
    # Efeito de feitiço: o mesmo aplicador para a §5B e para a §7.2, e é a
    # ausência de um parâmetro de origem que o mantém único
    "apply_spell_effect",
    "SpellEffectNeedsTargetError",
    # Vida, dano e morte de unidade
    "unit_max_health",
    "unit_remaining_health",
    "unit_effective_attack",
    "unit_is_dead",
    "unit_has_damage_immunity",
    "BankUnitIsNotAUnitError",
    "deal_damage_to_unit",
    "bury_dead_units",
    # Vitória e desistência (§10)
    #
    # `change_nexus` altera e apura; `check_victory` só apura; `forfeit` é a
    # outra saída da partida, fora da vez e fora da união de ações.
    "change_nexus",
    "check_victory",
    "forfeit",
    "SimultaneousDefeatError",
    # Constantes da §12 aplicadas por este pacote
    "MAX_ENERGY",
    "MAX_BANK_SIZE",
]
