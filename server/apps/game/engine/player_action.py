"""A forma de uma jogada que entra no motor, e o que ela precisa provar antes
de qualquer regra específica.

Este módulo não executa ação nenhuma. Ele define o que uma ação é e responde as
três perguntas que a §5 faz de toda ela, na ordem em que a §5 as faz:

    1. o autor joga esta partida
    2. o autor tem a prioridade
    3. a fase atual permite esta ação -- e uma partida terminada (§10) não
       permite nenhuma

Só depois disso a regra da ação -- a §5A em `play_unit.py`, a §5D em
`round_cycle.py` -- é verificada. Um jogador sem prioridade **e** sem energia
recebe a recusa de prioridade, nunca a de energia.

A união é fechada, como `Card` em `cards/card.py` e `UnitModifier` em
`match/modifiers.py`, e pela mesma razão: um `match` que esqueça um braço é erro
de mypy, não bug em produção. Jogar feitiço entrou como braço novo na feature
006, e as ações do combate na 007, sem que a guarda comum nem a porta de
`round_cycle` mudassem de forma -- que é exatamente o que a feature 005 escreveu
prevendo. Na 008 a união perdeu um braço, quando o feitiço da janela do defensor
deixou de ser uma ação separada.

**Ficar com a vez mora na ação, e é isso que impede a exceção de vazar.** Quem
joga unidade, passa ou confirma o ataque entrega a vez; quem joga feitiço (§5B,
em qualquer fase) ou age numa janela do combate (§7.1, §7.2) fica com ela.
`keeps_priority` é a propriedade da ação que diz qual das duas vale, e
`round_cycle._pass_priority` só a lê -- ela não conhece nenhuma das duas
exceções, e cada braço declara a sua resposta por si.

Os quatro braços da §5 ficam aqui, junto das guardas comuns que os consomem; os
três exclusivos da §7.2 ficam em `combat_action.py`, e o discriminante que os
dois lados precisam, em `action_kind.py`. A união fechada é montada aqui porque é
aqui que `ensure_action_allowed` a recebe.

Recusar é levantar, e é o oposto do `None` da compra da §9, de propósito: mão
cheia é fluxo normal do jogo e por isso é valor de retorno; jogada ilegal é
entrada inválida e quem chamou precisa tratá-la. Nenhuma regra desta feature
muta antes de todas as suas guardas passarem, então uma recusa deixa a partida
exatamente como estava, sem rollback nenhum a manter completo.
"""

from dataclasses import dataclass
from typing import ClassVar

from apps.game.match import (
    CardInstanceId,
    Match,
    MatchCard,
    MatchOutcome,
    MatchPhase,
    PlayerState,
)

from .action_kind import ActionKind
from .combat_action import (
    AssignBlockerAction,
    ConfirmAttackAction,
    EndDefenseWindowAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
)


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
    # Se a ação devolve a vez. Mora na ação pela mesma razão que
    # `allowed_phases` mora: a §5 escreve que a vez passa depois de jogar
    # unidade ou passar, e as exceções são jogar feitiço, que não gasta a vez
    # (§5B), e as janelas do combate, em que atacante e defensor agem quantas
    # vezes quiserem (§7.1, §7.2).
    #
    # Escrever as exceções aqui, e não numa condição dentro de
    # `round_cycle._pass_priority`, é o que as impede de vazar: quem lê aquela
    # função não precisa saber de nenhuma, e cada ação declara a sua resposta
    # por si.
    #
    # Sem default, como `allowed_phases`: um braço novo que esqueça de
    # responder é erro de mypy, e a resposta errada por omissão seria
    # justamente a que vaza.
    keeps_priority: ClassVar[bool] = False

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
    keeps_priority: ClassVar[bool] = False

    actor_user_id: int


@dataclass(frozen=True, slots=True)
class CastSpellAction:
    """Jogar um feitiço da mão (§5B), na Fase de Ação ou na janela do defensor.

    `target_card_instance_id` é anulável porque a ausência de alvo é estado
    **legítimo** de dois dos cinco feitiços do MVP, e não campo que alguém
    esqueceu de preencher. `None` é "não mira nada" -- e não existe outro
    significado, porque o feitiço resolve na hora e o alvo não tem como sumir
    entre o lançamento e o efeito.

    `{ACTION, COMBAT}` e `keeps_priority = True`: o Fluxo de Partida, corrigido
    em 2026-09-11, faz o feitiço resolver na hora e não gastar a vez em qualquer
    fase em que o jogador tem a prioridade. Até a feature 008 existiam duas
    ações -- esta, que esperava dois passes para resolver e devolvia a vez, e
    uma da §7.2 que resolvia na hora e ficava com ela. Sem a espera, as duas
    faziam a mesma coisa com os mesmos campos, e ficou uma.

    >>> CastSpellAction(actor_user_id=7, card_instance_id=CardInstanceId(3),
    ...                 target_card_instance_id=CardInstanceId(11))
    CastSpellAction(actor_user_id=7, card_instance_id=3,
                    target_card_instance_id=11)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.CAST_SPELL
    # As três fases em que alguém tem a vez para agir: a Fase de Ação, a
    # declaração do atacante (§7.1) e a defesa (§7.2).
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.ACTION, MatchPhase.DECLARATION, MatchPhase.COMBAT}
    )
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None


@dataclass(frozen=True, slots=True)
class DeclareAttackAction:
    """Declarar ataque (§5C) e mandar mais atacantes na declaração (§7.1).

    Na Fase de Ação abre a declaração com as unidades escolhidas na zona de
    ataque; dentro dela, acrescenta unidades à zona. Nada é consumido: quem
    consome o token é `ConfirmAttackAction`, e a vez fica com o atacante
    enquanto ele monta a zona.

    `attacker_card_instance_ids` é uma tupla e não uma lista: a ação é
    `frozen=True`, e uma lista dentro dela seria um campo imutável apontando
    para um conteúdo mutável. A ordem é a da declaração, e é preservada -- o
    dano da §7.3 é simultâneo e não a usa.

    Nunca vazia: declarar ataque sem escolher unidade é jogada mal formada, e
    `declare_attack` a recusa. O tipo não consegue dizer isso, e a recusa cita o
    que o tipo não diz.

    >>> DeclareAttackAction(actor_user_id=7,
    ...                     attacker_card_instance_ids=(CardInstanceId(3),))
    DeclareAttackAction(actor_user_id=7, attacker_card_instance_ids=(3,))
    """

    action_kind: ClassVar[ActionKind] = ActionKind.DECLARE_ATTACK
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.ACTION, MatchPhase.DECLARATION}
    )
    # `True` desde a correção da nota de 2026-09-11: declarar abre uma janela
    # do atacante, e quem entrega a vez ao defensor é **Atacar**.
    keeps_priority: ClassVar[bool] = True

    actor_user_id: int
    attacker_card_instance_ids: tuple[CardInstanceId, ...]


# União fechada: um `match` sobre `PlayerAction` que esqueça um braço é erro de
# mypy, não jogada que some em produção.
PlayerAction = (
    PlayUnitAction
    | PassAction
    | CastSpellAction
    | DeclareAttackAction
    | WithdrawAttackerAction
    | ConfirmAttackAction
    | AssignBlockerAction
    | RemoveBlockerAction
    | EndDefenseWindowAction
)


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


class MatchIsOverError(PhaseForbidsActionError):
    """A partida acabou (§10). Nenhuma ação é aceita, de nenhum jogador.

    Subclasse e não irmã de `PhaseForbidsActionError`: a afirmação é
    literalmente verdadeira -- a fase proíbe a ação --, e quem já escrevia
    `except PhaseForbidsActionError` continua pegando o caso.

    Levantada de **dentro** da terceira guarda, e não numa guarda nova antes
    delas: a ordem participante -> prioridade -> fase é contrato da feature 005
    e não muda. A consequência aceita é que um `user_id` que não joga a partida
    recebe `NotAParticipantError` mesmo depois de ela acabar, porque a guarda 1
    é sobre identidade.

    >>> raise MatchIsOverError(ActionKind.PASS, outcome, "m-1")
    MatchIsOverError: action 'pass' is not allowed in match 'm-1': the match is
    over, defeated user_id 7
    """

    def __init__(
        self, action_kind: ActionKind, outcome: MatchOutcome | None, match_id: str
    ) -> None:
        # Pula o `__init__` de `PhaseForbidsActionError`: a mensagem dele cita
        # as fases permitidas, e "esperava uma de ['action']" é resposta ruim
        # para uma partida que acabou.
        IllegalActionError.__init__(
            self,
            f"action '{action_kind}' is not allowed in match {match_id!r}: "
            f"the match is over, defeated user_id "
            f"{outcome.defeated_user_id if outcome else None}",
        )
        self.action_kind = action_kind
        self.outcome = outcome
        self.match_id = match_id


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


class NotEnoughEnergyError(IllegalActionError):
    """Custo maior que a energia atual. Cita os dois números.

    Nasceu em `play_unit.py`, na feature 005, e mora aqui desde a 006: a
    pergunta -- "a energia do autor cobre o custo da carta?" -- é a mesma na
    §5A e na §5B, e escrevê-la de novo em cada uma seria duplicar a regra.

    >>> raise NotEnoughEnergyError(7, CardInstanceId(3), 3, 1)
    NotEnoughEnergyError: user 7 cannot pay card instance 3: costs 3 energy, has 1
    """

    def __init__(
        self, user_id: int, card_instance_id: CardInstanceId, cost: int, available: int
    ) -> None:
        super().__init__(
            f"user {user_id} cannot pay card instance {card_instance_id}: "
            f"costs {cost} energy, has {available}"
        )
        self.user_id = user_id
        self.card_instance_id = card_instance_id
        self.cost = cost
        self.available = available


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

    if match.phase is MatchPhase.FINISHED:
        raise MatchIsOverError(action.action_kind, match.outcome, match.match_id)

    if match.phase not in action.allowed_phases:
        raise PhaseForbidsActionError(
            action.action_kind, match.phase, action.allowed_phases, match.match_id
        )

    return actor


def card_in_hand(actor: PlayerState, card_instance_id: CardInstanceId) -> MatchCard:
    """A carta citada, na mão **do autor**, ou `CardNotInHandError`.

    A mão consultada é sempre a de quem age, então citar a carta do oponente cai
    aqui, na mesma recusa de uma carta que não existe -- que é o que ela é, do
    ponto de vista de quem está jogando.

    Compartilhada pela §5A e pela §5B, pelo mesmo argumento que trouxe
    `CardNotInHandError` de `mulligan.py` para cá.

    >>> card_in_hand(actor, CardInstanceId(3)).card_id
    1001
    """
    for card in actor.hand:
        if card.card_instance_id == card_instance_id:
            return card

    raise CardNotInHandError(
        card_instance_id,
        actor.user_id,
        [held.card_instance_id for held in actor.hand],
    )


def ensure_enough_energy(actor: PlayerState, card: MatchCard, cost: int) -> None:
    """`energia >= custo`. Igual passa, e deixa a energia em 0.

    Recebe o custo como `int` e não a carta do catálogo: é o único campo lido, e
    `Unit` e `Spell` não têm base comum -- pedir uma delas obrigaria a inventar
    um `Protocol` para dois tipos que já são uma união fechada.

    >>> ensure_enough_energy(actor, card, 5)
    """
    if actor.energy_current >= cost:
        return

    raise NotEnoughEnergyError(
        actor.user_id, card.card_instance_id, cost, actor.energy_current
    )
