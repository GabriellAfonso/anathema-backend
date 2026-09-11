"""A forma das ações que só existem nas janelas do combate: as duas da
declaração (§7.1) e as três da defesa (§7.2).

Separadas dos braços da §5 porque a responsabilidade é outra, e a diferença
está nas duas `ClassVar` de cada uma: a fase é a da janela, e a vez fica com
quem age nela -- menos **Atacar**, que a entrega ao defensor. Tê-las num
arquivo próprio deixa as janelas visíveis em vez de diluídas entre as
dataclasses.

Mandar atacante não mora aqui: é `DeclareAttackAction`, a mesma ação que abre a
declaração na Fase de Ação e acrescenta unidades à zona de ataque dentro dela.

A quarta coisa que o defensor faz na janela é jogar feitiço, e ela não mora
aqui: é `CastSpellAction`, a mesma ação da Fase de Ação, em `player_action.py`.
Até a feature 008 existia um feitiço só da janela, e ele deixou de ter o que o
distinguisse.

Nenhuma delas executa nada. A regra de cada uma mora no módulo dela:
`declare_attack.py`, `blocker_pairing.py` e `combat_cleanup.py`.

A união fechada que as reúne com as da §5 é `PlayerAction`, em
`player_action.py` -- lá porque é lá que moram as guardas comuns que a
consomem.
"""

from dataclasses import dataclass
from typing import ClassVar

from apps.game.match import CardInstanceId, MatchPhase

from .action_kind import ActionKind


@dataclass(frozen=True, slots=True)
class WithdrawAttackerAction:
    """Puxar uma unidade da zona de ataque de volta ao banco (§7.1).

    Puxar a última devolve a partida à Fase de Ação sem consumir nada: o token
    continua disponível, e a vez continua com o atacante.

    >>> WithdrawAttackerAction(actor_user_id=7,
    ...                        attacker_card_instance_id=CardInstanceId(3))
    WithdrawAttackerAction(actor_user_id=7, attacker_card_instance_id=3)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.WITHDRAW_ATTACKER
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.DECLARATION}
    )
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    attacker_card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class ConfirmAttackAction:
    """Atacar (§7.1): encerra a declaração com o que está na zona de ataque.

    Consome o token e abre a janela do defensor. É a única ação das janelas do
    combate que entrega a vez -- ao defensor, que é o oponente de quem ataca.

    Sem campo além do autor: a zona de ataque já está no estado, e nunca vazia
    -- puxar a última unidade já teria saído da declaração.

    >>> ConfirmAttackAction(actor_user_id=7)
    ConfirmAttackAction(actor_user_id=7)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.CONFIRM_ATTACK
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.DECLARATION}
    )
    keeps_priority: ClassVar[bool] = False

    actor_user_id: int


@dataclass(frozen=True, slots=True)
class AssignBlockerAction:
    """Atribuir um bloqueador a um atacante (§7.2).

    Os dois campos nomeiam o papel, e não a posição: trocar um pelo outro numa
    chamada é erro de leitura, não de tipo -- os dois são `CardInstanceId` --, e
    por isso os nomes carregam o papel inteiro.

    >>> AssignBlockerAction(actor_user_id=9,
    ...                     blocker_card_instance_id=CardInstanceId(4),
    ...                     attacker_card_instance_id=CardInstanceId(3))
    AssignBlockerAction(actor_user_id=9, blocker_card_instance_id=4,
                        attacker_card_instance_id=3)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.ASSIGN_BLOCKER
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.COMBAT})
    # A exceção da §7.2: o defensor age quantas vezes quiser sem devolver a vez.
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    blocker_card_instance_id: CardInstanceId
    attacker_card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class RemoveBlockerAction:
    """Tirar um bloqueador já atribuído (§7.2).

    Cita só o bloqueador: o pareamento é 1 para 1, então ele determina o par
    inteiro. Braço próprio e não `AssignBlockerAction` com atacante ausente --
    um `None` ali seria um discriminante escondido dentro de um braço, que é o
    que a união fechada existe para não ter.

    >>> RemoveBlockerAction(actor_user_id=9,
    ...                     blocker_card_instance_id=CardInstanceId(4))
    RemoveBlockerAction(actor_user_id=9, blocker_card_instance_id=4)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.REMOVE_BLOCKER
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.COMBAT})
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    blocker_card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class EndDefenseWindowAction:
    """Encerrar a janela do defensor (§7.2), e com ela o combate.

    Sem campo além do autor, como `PassAction` -- e pela mesma razão: não existe
    um "resolver" com alvo a construir nem a validar.

    Não é um passe. `PassAction` conta para a saída da §5 e é legal só na Fase
    de Ação; esta dispara o dano da §7.3 e é legal só em Combate. Colapsá-las
    faria a contagem de passes atravessar o combate.

    `keeps_priority` é `True` mesmo sendo a última ação da janela: quem devolve
    a vez é a limpeza, que a põe no dono do token -- e deixar a troca comum
    fazer isso acertaria por acidente, porque o dono do token é o oponente do
    defensor. Explícito bate acidental.

    >>> EndDefenseWindowAction(actor_user_id=9)
    EndDefenseWindowAction(actor_user_id=9)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.END_DEFENSE_WINDOW
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.COMBAT})
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
