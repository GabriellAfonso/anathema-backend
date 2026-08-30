"""Dados públicos de jogador para os testes, sem passar pelo banco.

`PlayerData` é um TypedDict fechado: montar o dicionário na mão em cada teste
espalharia as mesmas quatro chaves por todo lado.
"""

from apps.players.services.player_queries import PlayerData


def fake_player_data(user_id: int, nickname: str = "player") -> PlayerData:
    """>>> fake_player_data(7, "one")
    {'user_id': 7, 'nickname': 'one', 'icon': 'default', 'level': 1}
    """
    return {
        "user_id": user_id,
        "nickname": nickname,
        "icon": "default",
        "level": 1,
    }
