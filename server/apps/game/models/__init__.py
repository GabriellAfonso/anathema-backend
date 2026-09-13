"""Os modelos do app de partida: por enquanto, só o registro do resultado.

Reexportados aqui porque é `apps.game.models` que o registro de apps do Django
importa -- mesma razão que `apps.players.models` documenta.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`: sem esta lista, nenhum consumidor importa daqui.

Até a feature 012 este era um `models.py` vazio, com o comentário de scaffold do
Django. O app de partida vivia inteiro no Redis; o que mudou é que o **desfecho**
passou a ter uma segunda vida, que sobrevive ao TTL de 6 horas.
"""

from .match_record import MatchRecord

__all__ = ["MatchRecord"]
