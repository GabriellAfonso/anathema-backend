"""O discriminante da união de ações, e o que o envelope de websocket carrega.

Mora sozinho porque os dois lados da união precisam dele: os braços da Fase de
Ação, em `player_action.py`, e os da janela do defensor, em `combat_action.py`.
Deixá-lo num dos dois faria o outro importar de quem importa dele.

"""

from enum import StrEnum


class ActionKind(StrEnum):
    """Discriminante da união, e o que o envelope de websocket vai carregar.

    Conjunto fechado, e **completo**: quatro ações da Fase de Ação (§5) e
    quatro da janela do defensor (§7.2). O Fluxo de Partida não tem uma nona em
    lugar nenhum, e por isso esta lista não cresce mais.
    """

    PLAY_UNIT = "play_unit"
    CAST_SPELL = "cast_spell"
    PASS = "pass"
    DECLARE_ATTACK = "declare_attack"
    ASSIGN_BLOCKER = "assign_blocker"
    REMOVE_BLOCKER = "remove_blocker"
    CAST_COMBAT_SPELL = "cast_combat_spell"
    END_DEFENSE_WINDOW = "end_defense_window"
