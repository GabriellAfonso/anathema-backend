"""A ação C da §5: declarar ataque, e com ela a entrada do combate da §7.1.

Seis perguntas, nesta ordem, e a ordem é parte da regra:

    1. o autor é o dono do token de ataque
    2. o token ainda não foi consumido nesta rodada
    3. a pilha está vazia
    4. o banco do autor tem alguma unidade
    5. a seleção tem ao menos uma unidade
    6. cada unidade citada está no banco do autor, uma vez só

As gerais e baratas vêm antes; a que cita uma unidade específica vem por
último. É a mesma disciplina de `cast_spell.py`, em que a carta precisa ser
resolvida antes de se poder citar o custo dela na recusa de energia.

A 4 vem antes da 5 de propósito. São fatos diferentes -- banco vazio é "não há
o que atacar", seleção vazia é "há, e você não escolheu nada" --, e colapsá-las
esconderia qual dos dois clientes está quebrado.

As seis acontecem **antes** da primeira atribuição, como em `play_unit.py`. É a
ordem que garante que uma recusa deixa o estado idêntico, e não um rollback que
alguém teria de manter completo.

Nenhuma carta se move e nenhuma energia é gasta: declarar ataque não é jogar
carta. O que muda é o token, a contagem de passes e o par `(combat, phase)`.
"""

from apps.game.match import (
    CardInstanceId,
    CombatState,
    Match,
    MatchPhase,
    PlayerState,
)

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


class StackIsNotEmptyError(IllegalActionError):
    """A §5C exige pilha vazia. O combate não usa a pilha, e deixar feitiço
    pendente entrando nele daria um efeito resolvendo depois do dano.

    >>> raise StackIsNotEmptyError(2, "m-1")
    StackIsNotEmptyError: match 'm-1' has 2 pending spells: expected an empty
    stack to declare an attack
    """

    def __init__(self, stack_size: int, match_id: str) -> None:
        super().__init__(
            f"match {match_id!r} has {stack_size} pending spells: expected an "
            f"empty stack to declare an attack"
        )
        self.stack_size = stack_size
        self.match_id = match_id


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


def declare_attack(
    match: Match, actor: PlayerState, action: DeclareAttackAction
) -> None:
    """A §5C: consome o token, registra os atacantes e entra em Combate.

    Recebe o `actor` que `ensure_action_allowed` já buscou, como `play_unit` e
    `cast_spell`. Não recebe `catalog`: nenhuma guarda daqui lê molde de carta.

    Zera a contagem de passes, como toda jogada -- a §5 conta passes
    **consecutivos**. É essa zeragem que deixa `_exit_action_phase` inerte
    durante o combate inteiro, sem que ela precise saber da §7.

    A prioridade **não** é trocada aqui. Quem troca é `submit_action`, e
    `keeps_priority = False` a manda para o oponente do autor -- o defensor.

    >>> declare_attack(match, actor, action)
    >>> match.phase
    <MatchPhase.COMBAT: 'combat'>
    """
    _ensure_actor_holds_the_token(match, actor)
    _ensure_token_is_unconsumed(match, actor)
    _ensure_stack_is_empty(match)
    _ensure_bank_has_units(actor)
    _ensure_selection_is_not_empty(actor, action)
    _ensure_every_attacker_is_in_the_bank(actor, action)

    match.token_consumed = True
    match.consecutive_passes = 0
    _enter_combat(match, action)


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


def _ensure_stack_is_empty(match: Match) -> None:
    """Guarda 3: o combate não usa a pilha, e não entra com ela cheia."""
    if not match.stack:
        return

    raise StackIsNotEmptyError(len(match.stack), match.match_id)


def _ensure_bank_has_units(actor: PlayerState) -> None:
    """Guarda 4: há o que atacar."""
    if actor.bank:
        return

    raise BankHasNoUnitsError(actor.user_id)


def _ensure_selection_is_not_empty(
    actor: PlayerState, action: DeclareAttackAction
) -> None:
    """Guarda 5: e alguma coisa foi escolhida."""
    if action.attacker_card_instance_ids:
        return

    raise NoAttackersSelectedError(actor.user_id, len(actor.bank))


def _ensure_every_attacker_is_in_the_bank(
    actor: PlayerState, action: DeclareAttackAction
) -> None:
    """Guarda 6: cada unidade citada está no banco do autor, uma vez só.

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


def _enter_combat(match: Match, action: DeclareAttackAction) -> None:
    """Único ponto deste módulo que escreve o par `(combat, phase)`.

    A invariante `phase is COMBAT` ⟹ `combat is not None` vale porque existe um
    lugar só onde ela pode ser quebrada de cada lado -- este na entrada, e
    `combat_cleanup._leave_combat` na saída. É o argumento de
    `victory._finish_match`, aplicado a uma transição que tem ida e volta.
    """
    match.combat = CombatState(
        attacker_card_instance_ids=list(action.attacker_card_instance_ids)
    )
    match.phase = MatchPhase.COMBAT
