"""O motor de regras: o que transforma o estado de partida.

`apps.game.match` guarda a partida e responde perguntas sobre ela, e diz de si
mesmo que nada ali é regra. Este pacote é o outro lado: aqui se embaralha, se
compra, se troca carta e se sorteia o dono do token.

Moram aqui o setup da §3 e a compra com reset de deck da §9. O Upkeep da §4 e o
combate da §7 caem no mesmo lugar quando entrarem.

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
    CardNotInHandError,
    MulliganAlreadyTakenError,
    record_mulligan,
)

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
    "CardNotInHandError",
]
