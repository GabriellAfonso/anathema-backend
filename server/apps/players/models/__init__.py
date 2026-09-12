"""Os modelos do jogador: perfil, estatística, histórico, preferências e deck.

Reexportados aqui porque é `apps.players.models` que o registro de apps do
Django importa. Enquanto este arquivo esteve vazio, os modelos só chegavam ao
registro por `admin.py` os importar -- um modelo novo que ninguém lembrasse de
registrar no admin simplesmente não existiria para o `makemigrations`.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.
"""

from .deck import PlayerDeck
from .player import LoginHistory, PlayerProfile, PlayerStats
from .settings import PlayerSettings

__all__ = [
    "PlayerProfile",
    "PlayerStats",
    "LoginHistory",
    "PlayerSettings",
    "PlayerDeck",
]
