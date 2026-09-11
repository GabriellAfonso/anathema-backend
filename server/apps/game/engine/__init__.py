"""O motor de regras: o que transforma o estado de partida.

`apps.game.match` guarda a partida e responde perguntas sobre ela, e diz de si
mesmo que nada ali é regra. Este pacote é o outro lado: aqui se embaralha, se
compra, se troca carta e se sorteia o dono do token.

Moram aqui o setup da §3, a compra com reset de deck da §9, o ciclo de rodada
das §4, §5 e §8 -- o Upkeep, a Fase de Ação com as três ações que existem, e o
Fim de Rodada --, a pilha de feitiços da §6 com os cinco efeitos do MVP, e a
condição de vitória da §10. O combate da §7 cai no mesmo lugar quando entrar.

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
from .cast_spell import (
    CardIsNotASpellError,
    SpellNeedsTargetError,
    SpellTakesNoTargetError,
    SpellTargetNotOnBattlefieldError,
    WrongSpellTargetSideError,
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
from .player_action import (
    ActionKind,
    CardNotInHandError,
    CastSpellAction,
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
from .spell_effect import SpellEffectNeedsTargetError, apply_spell_effect
from .unit_damage import bury_dead_units, deal_damage_to_unit
from .unit_vitals import (
    BankUnitIsNotAUnitError,
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
from .victory import change_nexus, check_victory

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
    "PassAction",
    "PlayerAction",
    # Recusas de jogada (§5)
    "IllegalActionError",
    "NotYourPriorityError",
    "PhaseForbidsActionError",
    "CardNotInHandError",
    "CardIsNotAUnitError",
    "NotEnoughEnergyError",
    "BankIsFullError",
    "MatchIsOverError",
    # Recusas de lançamento de feitiço (§5B)
    #
    # `cast_spell` **não** entra aqui, pela mesma razão de `run_upkeep` e
    # `end_round`: quem a chama é `round_cycle`.
    "CardIsNotASpellError",
    "SpellTakesNoTargetError",
    "SpellNeedsTargetError",
    "WrongSpellTargetSideError",
    "SpellTargetNotOnBattlefieldError",
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
    # Efeito de feitiço (§5B), o mesmo aplicador que o combate da §7.2 vai usar
    "apply_spell_effect",
    "SpellEffectNeedsTargetError",
    # Vida, dano e morte de unidade
    "unit_max_health",
    "unit_remaining_health",
    "unit_is_dead",
    "unit_has_damage_immunity",
    "BankUnitIsNotAUnitError",
    "deal_damage_to_unit",
    "bury_dead_units",
    # Vitória (§10)
    #
    # As duas são públicas: `change_nexus` é a única porta que escreve Nexus, e
    # `check_victory` é o que a §7.3 vai chamar depois do dano simultâneo, sem
    # passar por ela.
    "change_nexus",
    "check_victory",
    # Constantes da §12 aplicadas por este pacote
    "MAX_ENERGY",
    "MAX_BANK_SIZE",
]
