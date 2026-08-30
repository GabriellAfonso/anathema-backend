from typing import TypedDict

from channels.db import database_sync_to_async

from apps.players.models.player import PlayerProfile


class PlayerData(TypedDict):
    """O que um jogador mostra para os outros. Espelha o `.values()` abaixo.

    `user_id` e não `id`: é o espaço de id da identidade (decisão 0001).
    """

    user_id: int
    nickname: str
    icon: str
    level: int


# channels não publica stubs, então o decorator chega como `Any` e levaria
# a função inteira junto.
@database_sync_to_async  # type: ignore[untyped-decorator]
def get_player_public_data(user_id: int) -> PlayerData | None:
    """Dados públicos do jogador, ou None se o perfil não existe.

    >>> await get_player_public_data(7)
    {'user_id': 7, 'nickname': 'gabriel', 'icon': 'default', 'level': 1}
    """
    return (
        PlayerProfile.objects
        .filter(user_id=user_id)
        .values(
            "user_id",
            "nickname",
            "icon",
            "level",
        )
        .first()
    )
