"""A ação C da §5 e a declaração da §7.1: montar a zona de ataque e atacar.

Fluxo de Partida, corrigido em 2026-09-11: declarar ataque abre uma janela do
atacante. Nela ele manda unidades para a zona de ataque, puxa de volta, e joga
feitiço; nada é consumido até **Atacar**. Puxou todas de volta, a partida volta
à Fase de Ação como se ele não tivesse declarado -- o token disponível, a vez
com ele, e a contagem de passes onde estava.

A zona de ataque é `CombatState.attacker_card_instance_ids`. A unidade mandada
não sai do banco do dono -- é o mesmo desenho da feature 007, e é o que faz "os
sobreviventes voltam pro banco" da §7.4 valer sem código.

Mandar atacante faz seis perguntas, nesta ordem, e a ordem é parte da regra:

    1. o autor é o dono do token de ataque
    2. o token ainda não foi consumido nesta rodada
    3. o banco do autor tem alguma unidade
    4. a seleção tem ao menos uma unidade
    5. cada unidade citada está no banco do autor, uma vez só
    6. nenhuma unidade citada já está na zona de ataque

Eram seis até a feature 008: a terceira exigia que nenhum feitiço estivesse
esperando para resolver, e com o feitiço resolvendo na hora nunca há.

As gerais e baratas vêm antes; a que cita uma unidade específica vem por
último. É a mesma disciplina de `cast_spell.py`, em que a carta precisa ser
resolvida antes de se poder citar o custo dela na recusa de energia.

A 3 vem antes da 4 de propósito. São fatos diferentes -- banco vazio é "não há
o que atacar", seleção vazia é "há, e você não escolheu nada" --, e colapsá-las
esconderia qual dos dois clientes está quebrado.

As cinco acontecem **antes** da primeira atribuição, como em `play_unit.py`. É a
ordem que garante que uma recusa deixa o estado idêntico, e não um rollback que
alguém teria de manter completo.

Nenhuma carta se move e nenhuma energia é gasta: declarar ataque não é jogar
carta. Na declaração o que muda é só o par `(combat, phase)`; em **Atacar**, o
token e a contagem de passes.
"""

from apps.game.match import (
    CardInstanceId,
    CombatState,
    Match,
    MatchPhase,
    PlayerState,
)

from .blocker_pairing import UnitIsNotAttackingError
from .combat_action import WithdrawAttackerAction
from .player_action import DeclareAttackAction, IllegalActionError


class NotTheTokenHolderError(IllegalActionError):
    """Declarou ataque quem não tem o token. A mensagem diz quem tem.

    Distinta de `NotYourPriorityError`: ter a vez e ter o token são coisas
    diferentes, e o defensor de uma rodada tem a vez o tempo todo sem nunca
    poder atacar nela.

    >>> raise NotTheTokenHolderError(9, 7, "m-1")
    NotTheTokenHolderError: user 9 cannot declare an attack in match 'm-1': the
    attack token belongs to user 7
    """

    def __init__(
        self, actor_user_id: int, token_holder_user_id: int | None, match_id: str
    ) -> None:
        super().__init__(
            f"user {actor_user_id} cannot declare an attack in match "
            f"{match_id!r}: the attack token belongs to user "
            f"{token_holder_user_id}"
        )
        self.actor_user_id = actor_user_id
        self.token_holder_user_id = token_holder_user_id


class AttackTokenAlreadyConsumedError(IllegalActionError):
    """Um ataque por rodada (§12). O token volta no Upkeep seguinte, já com o
    dono trocado.

    >>> raise AttackTokenAlreadyConsumedError(7, 3, "m-1")
    AttackTokenAlreadyConsumedError: user 7 already attacked in round 3 of match
    'm-1': the attack token comes back in the next upkeep
    """

    def __init__(self, user_id: int, round_number: int, match_id: str) -> None:
        super().__init__(
            f"user {user_id} already attacked in round {round_number} of match "
            f"{match_id!r}: the attack token comes back in the next upkeep"
        )
        self.user_id = user_id
        self.round_number = round_number


class BankHasNoUnitsError(IllegalActionError):
    """Não há o que atacar. Distinta de `NoAttackersSelectedError`, que é "há, e
    você não escolheu nada".

    >>> raise BankHasNoUnitsError(7)
    BankHasNoUnitsError: bank of user 7 is empty: expected at least 1 unit to
    declare an attack
    """

    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"bank of user {user_id} is empty: expected at least 1 unit to "
            f"declare an attack"
        )
        self.user_id = user_id


class NoAttackersSelectedError(IllegalActionError):
    """Seleção vazia com banco cheio. Jogada mal formada, não combate vazio.

    >>> raise NoAttackersSelectedError(7, 3)
    NoAttackersSelectedError: user 7 selected no attackers: expected at least 1
    of the 3 units in the bank
    """

    def __init__(self, user_id: int, bank_size: int) -> None:
        super().__init__(
            f"user {user_id} selected no attackers: expected at least 1 of the "
            f"{bank_size} units in the bank"
        )
        self.user_id = user_id
        self.bank_size = bank_size


class AttackerNotInBankError(IllegalActionError):
    """A seleção cita uma unidade que não está no banco do autor.

    Cobre três erros de cliente numa recusa só, e é o que ela é do ponto de
    vista de quem joga: a unidade do oponente, a carta que ainda está na mão e a
    unidade que já morreu -- nenhuma delas está no banco dele.

    >>> raise AttackerNotInBankError(CardInstanceId(11), 7, [3, 5, 8])
    AttackerNotInBankError: card instance 11 is not in the bank of user 7:
    expected one of [3, 5, 8]
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


class DuplicateAttackerError(IllegalActionError):
    """A mesma unidade citada duas vezes.

    Recusa e não deduplicação silenciosa: uma unidade atacando duas vezes é o
    que o cliente pediu, e ignorar o pedido esconderia a tela quebrada. Pela
    mesma razão que `SpellTakesNoTargetError` recusa em vez de ignorar o alvo.

    >>> raise DuplicateAttackerError(CardInstanceId(5))
    DuplicateAttackerError: card instance 5 is selected twice as an attacker:
    expected each unit at most once
    """

    def __init__(self, card_instance_id: CardInstanceId) -> None:
        super().__init__(
            f"card instance {card_instance_id} is selected twice as an "
            f"attacker: expected each unit at most once"
        )
        self.card_instance_id = card_instance_id


class UnitAlreadyAttackingError(IllegalActionError):
    """Mandaram para a zona de ataque uma unidade que já está lá (§7.1).

    Distinta de `DuplicateAttackerError`, que é a mesma unidade duas vezes na
    mesma seleção: esta é a tela que ofereceu de novo uma unidade já mandada.

    >>> raise UnitAlreadyAttackingError(CardInstanceId(3), "m-1")
    UnitAlreadyAttackingError: card instance 3 is already in the attack zone of
    match 'm-1': expected a unit still in the bank
    """

    def __init__(self, card_instance_id: CardInstanceId, match_id: str) -> None:
        super().__init__(
            f"card instance {card_instance_id} is already in the attack zone of "
            f"match {match_id!r}: expected a unit still in the bank"
        )
        self.card_instance_id = card_instance_id


def declare_attack(
    match: Match, actor: PlayerState, action: DeclareAttackAction
) -> None:
    """A §5C e o "mandar atacante" da §7.1: as unidades vão para a zona.

    Na Fase de Ação abre a declaração; dentro dela, acrescenta à zona. Não
    consome o token, não mexe na contagem de passes, e não troca a vez --
    `keeps_priority` é `True`.

    Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit` e
    `cast_spell`. Não recebe `catalog`: nenhuma guarda daqui lê molde de carta.

    >>> declare_attack(match, actor, action)
    >>> match.phase
    <MatchPhase.DECLARATION: 'declaration'>
    """
    _ensure_actor_holds_the_token(match, actor)
    _ensure_token_is_unconsumed(match, actor)
    _ensure_bank_has_units(actor)
    _ensure_selection_is_not_empty(actor, action)
    _ensure_every_attacker_is_in_the_bank(actor, action)
    _ensure_none_is_already_attacking(match, action)

    _send_to_the_attack_zone(match, action)


def withdraw_attacker(match: Match, action: WithdrawAttackerAction) -> None:
    """Puxa uma unidade da zona de ataque de volta ao banco (§7.1).

    Puxar a última devolve a partida à Fase de Ação sem consumir nada.

    >>> withdraw_attacker(match, action)
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """
    combat = match.ongoing_combat()
    attacker = action.attacker_card_instance_id

    if not combat.is_attacking(attacker):
        raise UnitIsNotAttackingError(
            attacker, list(combat.attacker_card_instance_ids), match.match_id
        )

    combat.attacker_card_instance_ids.remove(attacker)

    if not combat.attacker_card_instance_ids:
        _close_the_declaration(match)


def confirm_attack(match: Match) -> None:
    """**Atacar** (§7.1): consome o token e abre a janela do defensor.

    Zera a contagem de passes -- a §5 conta passes **consecutivos**, e um ataque
    quebra a sequência. É essa zeragem que deixa `_exit_action_phase` inerte
    durante a defesa sem que ela precise saber da §7.

    A vez **não** é trocada aqui: `ConfirmAttackAction.keeps_priority` é
    `False`, e `submit_action` a entrega ao oponente do autor -- o defensor.

    >>> confirm_attack(match)
    >>> match.phase
    <MatchPhase.COMBAT: 'combat'>
    """
    match.ongoing_combat()

    match.token_consumed = True
    match.consecutive_passes = 0
    match.phase = MatchPhase.COMBAT


def _ensure_actor_holds_the_token(match: Match, actor: PlayerState) -> None:
    """Guarda 1: só o dono do token declara ataque."""
    if match.token_holder_user_id == actor.user_id:
        return

    raise NotTheTokenHolderError(
        actor.user_id, match.token_holder_user_id, match.match_id
    )


def _ensure_token_is_unconsumed(match: Match, actor: PlayerState) -> None:
    """Guarda 2: um ataque por rodada (§12)."""
    if not match.token_consumed:
        return

    raise AttackTokenAlreadyConsumedError(
        actor.user_id, match.round_number, match.match_id
    )


def _ensure_bank_has_units(actor: PlayerState) -> None:
    """Guarda 3: há o que atacar."""
    if actor.bank:
        return

    raise BankHasNoUnitsError(actor.user_id)


def _ensure_selection_is_not_empty(
    actor: PlayerState, action: DeclareAttackAction
) -> None:
    """Guarda 4: e alguma coisa foi escolhida."""
    if action.attacker_card_instance_ids:
        return

    raise NoAttackersSelectedError(actor.user_id, len(actor.bank))


def _ensure_every_attacker_is_in_the_bank(
    actor: PlayerState, action: DeclareAttackAction
) -> None:
    """Guarda 5: cada unidade citada está no banco do autor, uma vez só.

    A ausência é verificada antes da repetição: citar uma unidade que não
    existe é erro mais básico que citá-la duas vezes, e uma seleção com os dois
    problemas recebe a recusa da unidade ausente.
    """
    # Anotada como `list[int]` e não inferida: `list` é invariante, e uma
    # `list[CardInstanceId]` não entra onde a recusa pede `list[int]`.
    in_bank: list[int] = [unit.card.card_instance_id for unit in actor.bank]
    seen: set[CardInstanceId] = set()

    for card_instance_id in action.attacker_card_instance_ids:
        if card_instance_id not in in_bank:
            raise AttackerNotInBankError(card_instance_id, actor.user_id, in_bank)

        if card_instance_id in seen:
            raise DuplicateAttackerError(card_instance_id)

        seen.add(card_instance_id)


def _ensure_none_is_already_attacking(
    match: Match, action: DeclareAttackAction
) -> None:
    """Guarda 6: nenhuma unidade citada já está na zona de ataque.

    Só tem o que perguntar dentro da declaração; na Fase de Ação não existe
    zona ainda.
    """
    if match.combat is None:
        return

    for card_instance_id in action.attacker_card_instance_ids:
        if match.combat.is_attacking(card_instance_id):
            raise UnitAlreadyAttackingError(card_instance_id, match.match_id)


def _send_to_the_attack_zone(match: Match, action: DeclareAttackAction) -> None:
    """Abre a declaração, ou acrescenta à zona que já existe.

    Um dos dois pontos deste módulo que escrevem o par `(combat, phase)`; o
    outro é `_close_the_declaration`, e a saída da defesa é
    `combat_cleanup._leave_combat`. É o argumento de `victory._finish_match`,
    aplicado a uma transição que tem ida e volta.
    """
    chosen = list(action.attacker_card_instance_ids)

    if match.combat is not None:
        match.combat.attacker_card_instance_ids.extend(chosen)
        return

    match.combat = CombatState(attacker_card_instance_ids=chosen)
    match.phase = MatchPhase.DECLARATION


def _close_the_declaration(match: Match) -> None:
    """Todos puxados de volta: a Fase de Ação, como se não tivesse declarado.

    Não toca token, vez nem passes -- nada disso mudou ao declarar.
    """
    match.combat = None
    match.phase = MatchPhase.ACTION
