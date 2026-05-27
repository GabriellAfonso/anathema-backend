from channels.db import database_sync_to_async
from apps.players.models.player import PlayerProfile


@database_sync_to_async
def get_player_public_data(user_id):
    return (
        PlayerProfile.objects
        .filter(user_id=user_id)
        .values(
            "id",
            "nickname",
            "icon",
            "level",
        )
        .first()
    )
