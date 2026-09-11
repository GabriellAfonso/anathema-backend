"""O bloqueio da §7.2: pôr uma unidade do defensor na frente de um atacante, e
tirá-la de lá.

Duas funções num módulo só porque elas são os dois lados da **mesma**
invariante: o pareamento 1 para 1 estrito da §12, em que cada bloqueador cobre
no máximo um atacante e cada atacante recebe no máximo um bloqueador. Separá-las
poria a invariante em dois arquivos.

Nenhuma das duas gasta energia, move carta, causa dano ou altera Nexus. O que
elas escrevem é `CombatState.blocks`, e mais nada.

Nenhuma das duas pergunta se o autor é o defensor, e não existe guarda para
isso: durante o Combate a prioridade é do defensor, e `ensure_action_allowed` já
recusou o atacante antes de chegar aqui -- citando de quem é a vez, que é o que
a §7.1 quer dizer com "é espectador".
"""

from apps.game.match import (
    BlockAssignment,
    CardInstanceId,
    CombatState,
    Match,
    PlayerState,
)

from .combat_action import AssignBlockerAction, RemoveBlockerAction
from .player_action import IllegalActionError


class BlockerNotInBankError(IllegalActionError):
    """Bloquear com uma unidade que não está no banco do defensor.

    Cobre a unidade do atacante, a carta ainda na mão e a que já morreu --
    nenhuma delas está no banco dele, que é o que importa.

    >>> raise BlockerNotInBankError(CardInstanceId(11), 9, [4, 6])
    BlockerNotInBankError: card instance 11 is not in the bank of user 9:
    expected one of [4, 6]
    """

    def __init__(
        self, card_instance_id: CardInstanceId, user_id: int, in_bank: list[int]
    ) -> None:
        super().__init__(
            f"card instance {card_instance_id} is not in the bank of user "
            f"{user_id}: expected one of {in_bank}"
        )
        self.card_instance_id = card_instance_id
        self.user_id = user_id


class UnitIsNotAttackingError(IllegalActionError):
    """O bloqueador foi apontado para uma unidade que não está atacando.

    Cobre a unidade do próprio defensor, a do atacante que ficou fora da
    declaração, e o atacante que morreu por feitiço dentro da janela -- esta
    última porque a guarda pergunta as duas coisas: declarado **e** ainda em
    campo.

    >>> raise UnitIsNotAttackingError(CardInstanceId(8), [3, 5], "m-1")
    UnitIsNotAttackingError: card instance 8 is not attacking in match 'm-1':
    expected one of [3, 5]
    """

    def __init__(
        self, card_instance_id: CardInstanceId, attacking: list[int], match_id: str
    ) -> None:
        super().__init__(
            f"card instance {card_instance_id} is not attacking in match "
            f"{match_id!r}: expected one of {attacking}"
        )
        self.card_instance_id = card_instance_id
        self.attacking = attacking


class BlockerAlreadyBlockingError(IllegalActionError):
    """Uma unidade cobrindo dois atacantes. O pareamento é 1 para 1 (§12).

    >>> raise BlockerAlreadyBlockingError(CardInstanceId(4), CardInstanceId(3))
    BlockerAlreadyBlockingError: card instance 4 already blocks card instance 3:
    expected an unassigned blocker
    """

    def __init__(
        self,
        blocker_card_instance_id: CardInstanceId,
        attacker_card_instance_id: CardInstanceId,
    ) -> None:
        super().__init__(
            f"card instance {blocker_card_instance_id} already blocks card "
            f"instance {attacker_card_instance_id}: expected an unassigned "
            f"blocker"
        )
        self.blocker_card_instance_id = blocker_card_instance_id
        self.attacker_card_instance_id = attacker_card_instance_id


class AttackerAlreadyBlockedError(IllegalActionError):
    """Dois bloqueadores num atacante. O outro lado do 1 para 1.

    Trocar de bloqueador exige remover antes -- e é para isso que a §7.2 dá a
    remoção.

    >>> raise AttackerAlreadyBlockedError(CardInstanceId(3), CardInstanceId(4))
    AttackerAlreadyBlockedError: card instance 3 is already blocked by card
    instance 4: expected an unblocked attacker
    """

    def __init__(
        self,
        attacker_card_instance_id: CardInstanceId,
        blocker_card_instance_id: CardInstanceId,
    ) -> None:
        super().__init__(
            f"card instance {attacker_card_instance_id} is already blocked by "
            f"card instance {blocker_card_instance_id}: expected an unblocked "
            f"attacker"
        )
        self.attacker_card_instance_id = attacker_card_instance_id
        self.blocker_card_instance_id = blocker_card_instance_id


class BlockerNotAssignedError(IllegalActionError):
    """Remover um bloqueador que não foi atribuído.

    Recusa e não no-op silencioso: remover o que não existe é tela
    desatualizada, e um no-op a esconderia.

    >>> raise BlockerNotAssignedError(CardInstanceId(6), [4], "m-1")
    BlockerNotAssignedError: card instance 6 is not blocking anything in match
    'm-1': expected one of [4]
    """

    def __init__(
        self, card_instance_id: CardInstanceId, assigned: list[int], match_id: str
    ) -> None:
        super().__init__(
            f"card instance {card_instance_id} is not blocking anything in "
            f"match {match_id!r}: expected one of {assigned}"
        )
        self.card_instance_id = card_instance_id
        self.assigned = assigned


def assign_blocker(
    match: Match, actor: PlayerState, action: AssignBlockerAction
) -> None:
    """A §7.2: uma unidade do banco do defensor na frente de um atacante.

    Quatro guardas, nesta ordem. As duas primeiras perguntam se as unidades
    citadas existem onde deveriam; as duas últimas, se o pareamento 1 para 1
    aguenta mais este par. Citar unidade inexistente é erro mais básico que
    violar a regra de aridade, e por isso vem antes.

    A prioridade **não** é trocada: `keeps_priority` é `True`, e é isso que
    deixa o defensor bloquear de novo em seguida.

    >>> assign_blocker(match, defender, action)
    >>> match.ongoing_combat().blocker_of(attacker)
    4
    """
    combat = match.ongoing_combat()
    blocker = action.blocker_card_instance_id
    attacker = action.attacker_card_instance_id

    _ensure_blocker_is_in_the_bank(actor, blocker)
    _ensure_target_is_attacking(match, combat, attacker)
    _ensure_blocker_is_free(combat, blocker)
    _ensure_attacker_is_unblocked(combat, attacker)

    combat.blocks.append(
        BlockAssignment(
            blocker_card_instance_id=blocker, attacker_card_instance_id=attacker
        )
    )


def remove_blocker(match: Match, action: RemoveBlockerAction) -> None:
    """A §7.2: desfaz um pareamento, liberando as duas unidades.

    Não recebe `actor`: a única pergunta que ela faz é sobre o pareamento, e o
    banco do defensor não entra nela -- um bloqueador atribuído já provou que
    está lá quando foi atribuído.

    Lista nova em vez de `remove()`: `BlockAssignment` é dataclass com `__eq__`
    gerado, e remover por valor levaria qualquer par igual. É a mesma razão que
    `unit_damage._bury_dead_in_bank` escreve para comparar por identificador.

    >>> remove_blocker(match, action)
    >>> match.ongoing_combat().attacker_blocked_by(blocker) is None
    True
    """
    combat = match.ongoing_combat()
    blocker = action.blocker_card_instance_id

    _ensure_blocker_is_assigned(match, combat, blocker)

    combat.blocks = [
        block for block in combat.blocks if block.blocker_card_instance_id != blocker
    ]


def _ensure_blocker_is_in_the_bank(
    actor: PlayerState, blocker_card_instance_id: CardInstanceId
) -> None:
    """Guarda 1: bloqueia quem está no banco de quem bloqueia."""
    # `list[int]` anotada e não inferida: `list` é invariante, e uma
    # `list[CardInstanceId]` não entra onde a recusa pede `list[int]`.
    in_bank: list[int] = [unit.card.card_instance_id for unit in actor.bank]

    if blocker_card_instance_id in in_bank:
        return

    raise BlockerNotInBankError(blocker_card_instance_id, actor.user_id, in_bank)


def _ensure_target_is_attacking(
    match: Match, combat: CombatState, attacker_card_instance_id: CardInstanceId
) -> None:
    """Guarda 2: o alvo do bloqueio foi declarado **e** ainda está em campo.

    As duas perguntas juntas, e não só a primeira: um atacante morto por feitiço
    dentro da janela continua na lista da declaração, e pôr um bloqueador na
    frente dele não é jogada que faça sentido. A revalidação do dano é outra
    coisa, e acontece na §7.3.
    """
    attacking: list[int] = list(combat.attacker_card_instance_ids)

    if combat.is_attacking(attacker_card_instance_id) and match.bank_unit(
        attacker_card_instance_id
    ):
        return

    raise UnitIsNotAttackingError(attacker_card_instance_id, attacking, match.match_id)


def _ensure_blocker_is_free(
    combat: CombatState, blocker_card_instance_id: CardInstanceId
) -> None:
    """Guarda 3: o bloqueador ainda não cobre ninguém."""
    covered = combat.attacker_blocked_by(blocker_card_instance_id)

    if covered is None:
        return

    raise BlockerAlreadyBlockingError(blocker_card_instance_id, covered)


def _ensure_attacker_is_unblocked(
    combat: CombatState, attacker_card_instance_id: CardInstanceId
) -> None:
    """Guarda 4: o atacante ainda não tem quem o cubra."""
    blocker = combat.blocker_of(attacker_card_instance_id)

    if blocker is None:
        return

    raise AttackerAlreadyBlockedError(attacker_card_instance_id, blocker)


def _ensure_blocker_is_assigned(
    match: Match, combat: CombatState, blocker_card_instance_id: CardInstanceId
) -> None:
    """Guarda única da remoção: há o que remover."""
    if combat.attacker_blocked_by(blocker_card_instance_id) is not None:
        return

    assigned: list[int] = [block.blocker_card_instance_id for block in combat.blocks]

    raise BlockerNotAssignedError(blocker_card_instance_id, assigned, match.match_id)
