"""O motor de regras: o que transforma o estado de partida.

`apps.game.match` guarda a partida e responde perguntas sobre ela, e diz de si
mesmo que nada ali é regra. Este pacote é o outro lado: aqui se embaralha, se
compra, se troca carta e se sorteia o dono do token.

Moram aqui o setup da §3, a compra com reset de deck da §9, e o ciclo de rodada
das §4, §5 e §8 -- o Upkeep, a Fase de Ação com as duas ações que existem, e o
Fim de Rodada. A pilha da §6 e o combate da §7 caem no mesmo lugar quando
entrarem.

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
    NotEnoughEnergyError,
)
from .player_action import (
    ActionKind,
    CardNotInHandError,
    IllegalActionError,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    PlayerAction,
    PlayUnitAction,
)
from .round_cycle import (
    CONSECUTIVE_PASSES_TO_EXIT,
    MatchNotAwaitingUpkeepError,
    begin_round_cycle,
    submit_action,
)
from .upkeep import MAX_ENERGY

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
    # Ciclo de rodada (§4, §5, §8)
    #
    # `run_upkeep` e `end_round` **não** entram aqui: quem os chama é
    # `round_cycle`, e expô-los daria uma porta por onde executar meia rodada --
    # o contrário do que a cascata garante. Os testes deles importam do módulo.
    "begin_round_cycle",
    "submit_action",
    "MatchNotAwaitingUpkeepError",
    "CONSECUTIVE_PASSES_TO_EXIT",
    # Constantes da §12 aplicadas por este pacote
    "MAX_ENERGY",
    "MAX_BANK_SIZE",
]
