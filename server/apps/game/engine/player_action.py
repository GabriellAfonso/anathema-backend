"""A forma de uma jogada que entra no motor, e o que ela precisa provar antes
de qualquer regra específica.

Este módulo não executa ação nenhuma. Ele define o que uma ação é e responde as
três perguntas que a §5 faz de toda ela, na ordem em que a §5 as faz:

    1. o autor joga esta partida
    2. o autor tem a prioridade
    3. a fase atual permite esta ação

Só depois disso a regra da ação -- a §5A em `play_unit.py`, a §5D em
`round_cycle.py` -- é verificada. Um jogador sem prioridade **e** sem energia
recebe a recusa de prioridade, nunca a de energia.

A união é fechada, como `Card` em `cards/card.py` e `UnitModifier` em
`match/modifiers.py`, e pela mesma razão: um `match` que esqueça um braço é erro
de mypy, não bug em produção. As duas ações que faltam da §5 -- jogar feitiço e
declarar ataque -- entram como braços novos, e nem a guarda comum nem a porta de
`round_cycle` mudam de forma para recebê-las.

Recusar é levantar, e é o oposto do `None` da compra da §9, de propósito: mão
cheia é fluxo normal do jogo e por isso é valor de retorno; jogada ilegal é
entrada inválida e quem chamou precisa tratá-la. Nenhuma regra desta feature
muta antes de todas as suas guardas passarem, então uma recusa deixa a partida
exatamente como estava, sem rollback nenhum a manter completo.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from apps.game.match import CardInstanceId, Match, MatchPhase, PlayerState


class ActionKind(StrEnum):
    """Discriminante da união, e o que o envelope de websocket vai carregar.

    Conjunto fechado. As duas ações que faltam da §5 entram aqui junto com os
    braços delas.
    """

    PLAY_UNIT = "play_unit"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class PlayUnitAction:
    """Jogar uma unidade da mão (§5A).

    `card_instance_id` e não `card_id`: a jogada é sobre **aquela** cópia na
    mão, e o `NewType` da feature 002 faz de trocar um pelo outro um erro de
    mypy.

    >>> PlayUnitAction(actor_user_id=7, card_instance_id=CardInstanceId(3))
    PlayUnitAction(actor_user_id=7, card_instance_id=3)
    """

    # `ClassVar` porque a espécie pertence à mecânica, não à instância: assim
    # nenhum call site consegue construir um PlayUnitAction que se diz `pass`.
    # Mesma disciplina de `ModifierKind` em `match/modifiers.py`.
    action_kind: ClassVar[ActionKind] = ActionKind.PLAY_UNIT
    # As fases em que esta ação é legal. Mora na ação, e não numa cadeia de
    # `if` dentro da guarda, porque a §5 escreve a pergunta como "a fase atual
    # permite **esta** ação". O bloqueio da §7.2 vai declarar `{COMBAT}` sem
    # que `ensure_action_allowed` mude uma linha.
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int
    card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class PassAction:
    """Passar a vez (§5D). Sempre disponível para quem tem a prioridade.

    Sem campo além do autor, e é isso que a união compra: não existe um passe
    com `card_instance_id` a construir nem a validar em tempo de execução.

    >>> PassAction(actor_user_id=7)
    PassAction(actor_user_id=7)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.PASS
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int


# União fechada: um `match` sobre `PlayerAction` que esqueça um braço é erro de
# mypy, não jogada que some em produção.
PlayerAction = PlayUnitAction | PassAction


class IllegalActionError(Exception):
    """Raiz das recusas de jogada.

    Levantar deixa o estado da partida **exatamente** como estava: nenhuma regra
    muta antes de todas as suas guardas passarem, então não há meia ação a
    desfazer.

    Não é a raiz de tudo que o motor recusa. A guarda de participante levanta
    `NotAParticipantError`, que mora em `apps.game.match` e não pode herdar
    daqui sem inverter a dependência entre o pacote de estado e o de regra --
    aquele diz de si mesmo que não conhece regra. Quem quiser pegar toda recusa
    pega as duas.
    """


class NotYourPriorityError(IllegalActionError):
    """Agiu quem não tem a vez. A mensagem diz quem tem.

    >>> raise NotYourPriorityError(9, 7, "m-1")
    NotYourPriorityError: user 9 cannot act in match 'm-1': priority belongs to
    user 7
    """

    def __init__(
        self, actor_user_id: int, priority_user_id: int | None, match_id: str
    ) -> None:
        super().__init__(
            f"user {actor_user_id} cannot act in match {match_id!r}: "
            f"priority belongs to user {priority_user_id}"
        )
        self.actor_user_id = actor_user_id
        self.priority_user_id = priority_user_id


class PhaseForbidsActionError(IllegalActionError):
    """A fase atual não permite esta ação. Cita a fase e as permitidas.

    Cobre a partida ainda em mulligan, e cobriria uma fase automática se alguém
    conseguisse pegá-la no meio -- o que a cascata torna impossível de fora.

    >>> raise PhaseForbidsActionError(
    ...     ActionKind.PASS, MatchPhase.UPKEEP, PassAction.allowed_phases, "m-1"
    ... )
    PhaseForbidsActionError: action 'pass' is not allowed in phase 'upkeep' of
    match 'm-1': expected one of ['action']
    """

    def __init__(
        self,
        action_kind: ActionKind,
        phase: MatchPhase,
        allowed_phases: frozenset[MatchPhase],
        match_id: str,
    ) -> None:
        super().__init__(
            f"action '{action_kind}' is not allowed in phase '{phase}' of match "
            f"{match_id!r}: expected one of {sorted(str(one) for one in allowed_phases)}"
        )
        self.action_kind = action_kind
        self.phase = phase
        self.allowed_phases = allowed_phases


class CardNotInHandError(IllegalActionError):
    """A seleção cita uma carta que não está na mão daquele jogador.

    Cobre também o identificador repetido: a validação consome a mão candidata
    ao casar, então a segunda ocorrência já não está entre as restantes.

    Nasceu em `mulligan.py`, na feature 003, e mora aqui desde a 005: a pergunta
    -- "a carta citada está na mão do autor?" -- é a mesma no mulligan da §3, na
    jogada da §5A e no feitiço da §6 que ainda não existe. Escrevê-la de novo em
    cada uma seria duplicar a regra; importá-la de `mulligan.py` poria a §5A
    dependendo do módulo do setup, que é a direção errada.
    """

    def __init__(
        self, card_instance_id: CardInstanceId, user_id: int, in_hand: list[int]
    ) -> None:
        super().__init__(
            f"card instance {card_instance_id} is not in the hand of user "
            f"{user_id}: expected one of {in_hand}"
        )
        self.card_instance_id = card_instance_id
        self.user_id = user_id


def ensure_action_allowed(match: Match, action: PlayerAction) -> PlayerState:
    """As três guardas da §5, na ordem, antes de qualquer regra específica.

    A ordem é parte do contrato: um autor que falha em duas guardas recebe a
    recusa da primeira delas, sempre.

    Devolve o `PlayerState` do autor, que a guarda 1 já teve de buscar. Assim
    nenhuma regra específica repete a busca, e não sobra um segundo lugar de
    onde `NotAParticipantError` pudesse escapar depois de a partida já ter sido
    alterada.

    >>> ensure_action_allowed(match, PassAction(actor_user_id=7)).user_id
    7
    """
    actor = match.player(action.actor_user_id)

    if match.priority_user_id != action.actor_user_id:
        raise NotYourPriorityError(
            action.actor_user_id, match.priority_user_id, match.match_id
        )

    if match.phase not in action.allowed_phases:
        raise PhaseForbidsActionError(
            action.action_kind, match.phase, action.allowed_phases, match.match_id
        )

    return actor
