"""O discriminante da união de ações, e o que o envelope de websocket carrega.

Mora sozinho porque os dois lados da união precisam dele: os braços da Fase de
Ação, em `player_action.py`, e os da janela do defensor, em `combat_action.py`.
Deixá-lo num dos dois faria o outro importar de quem importa dele.

"""

from enum import StrEnum


class ActionKind(StrEnum):
    """Discriminante da união, e o que o envelope de websocket vai carregar.

    Conjunto fechado: as quatro ações da Fase de Ação (§5) -- jogar feitiço,
    que vale nas três fases de agir, e declarar ataque, que também manda mais
    atacantes na declaração --, as duas que só existem na declaração (§7.1), as
    três que só existem na defesa (§7.2), e a desistência da §10, que não é
    braço de `PlayerAction` porque vale fora da vez, mas é gesto do jogador e o
    cliente a manda igual.
    """

    PLAY_UNIT = "play_unit"
    CAST_SPELL = "cast_spell"
    PASS = "pass"
    DECLARE_ATTACK = "declare_attack"
    WITHDRAW_ATTACKER = "withdraw_attacker"
    CONFIRM_ATTACK = "confirm_attack"
    ASSIGN_BLOCKER = "assign_blocker"
    REMOVE_BLOCKER = "remove_blocker"
    END_DEFENSE_WINDOW = "end_defense_window"
    FORFEIT = "forfeit"
