"""O motor de regras: o que transforma o estado de partida.

`apps.game.match` guarda a partida e responde perguntas sobre ela, e diz de si
mesmo que nada ali é regra. Este pacote é o outro lado: aqui se embaralha, se
compra, se troca carta e se sorteia o dono do token.

Por enquanto só o setup da §3 mora aqui. O Upkeep da §4, a regra geral de
compra da §9 e o combate da §7 caem no mesmo lugar quando entrarem.

>>> from apps.game.engine import MatchEntry, start_match
>>> match = start_match(one, two, catalog=catalog, randomness=source, seed=seed)
>>> match.phase
<MatchPhase.MULLIGAN: 'mulligan'>

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.
"""

from .card_draw import EmptyDeckError, draw_from_deck_top
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
    # Compra
    "draw_from_deck_top",
    "EmptyDeckError",
    # Setup
    "MatchEntry",
    "start_match",
    "finish_setup",
    "InvalidPlayerDeckError",
    # Mulligan
    "record_mulligan",
    "MulliganAlreadyTakenError",
    "CardNotInHandError",
]
