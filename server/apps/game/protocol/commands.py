"""O que o cliente pode pedir, e a porta do motor por onde cada pedido entra.

Três famílias. As nove ações de `PlayerAction` passam pela porta única de
`submit_action`, com as guardas de prioridade e de fase do motor. O mulligan
passa por `record_mulligan`, e é aqui que o fim do setup acontece sozinho: se o
segundo mulligan fechou o setup, `begin_round_cycle` roda **na mesma chamada**,
e portanto na mesma mutação gravada (FR-009). A desistência passa por `forfeit`,
que vale fora da vez.

Nada aqui lê socket nem Redis. `apply_command` altera a partida no lugar, como
as portas do motor, e quem grava é o chamador, dentro de `MatchStore.mutate`.
"""

from dataclasses import dataclass
from typing import assert_never

from apps.game.cards import CardCatalog
from apps.game.engine import (
    AssignBlockerAction,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    PassAction,
    PlayerAction,
    PlayUnitAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
    begin_round_cycle,
    forfeit,
    record_mulligan,
    submit_action,
)
from apps.game.match import CardInstanceId, Match, MatchPhase
from apps.game.randomness import RandomSource


@dataclass(frozen=True, slots=True)
class MulliganCommand:
    """A escolha de mulligan de um jogador: as cartas da mão a trocar.

    >>> MulliganCommand(user_id=7, card_instance_ids=(CardInstanceId(3),))
    MulliganCommand(user_id=7, card_instance_ids=(3,))
    """

    user_id: int
    card_instance_ids: tuple[CardInstanceId, ...]


@dataclass(frozen=True, slots=True)
class ForfeitCommand:
    """A desistência da §10.

    >>> ForfeitCommand(user_id=7)
    ForfeitCommand(user_id=7)
    """

    user_id: int


# União fechada: `apply_command` e `describe_change` despacham com `match` e
# `assert_never`, e um braço novo sem tratamento é erro de mypy.
ClientCommand = PlayerAction | MulliganCommand | ForfeitCommand


def command_author(command: ClientCommand) -> int:
    """Quem pediu. As ações chamam o autor de `actor_user_id`, os outros dois
    de `user_id`, e esta é a única função que precisa saber disso.

    >>> command_author(ForfeitCommand(user_id=7))
    7
    """
    if isinstance(command, (MulliganCommand, ForfeitCommand)):
        return command.user_id

    return command.actor_user_id


def apply_command(
    match: Match,
    command: ClientCommand,
    *,
    catalog: CardCatalog,
    randomness: RandomSource,
) -> None:
    """Leva o comando à porta do motor. Recusa do motor atravessa sem mudança.

    >>> apply_command(match, PassAction(actor_user_id=7),
    ...               catalog=catalog, randomness=source)
    """
    match command:
        case MulliganCommand():
            _take_mulligan(match, command, randomness)
        case ForfeitCommand():
            forfeit(match, command.user_id)
        case (
            PlayUnitAction()
            | CastSpellAction()
            | PassAction()
            | DeclareAttackAction()
            | WithdrawAttackerAction()
            | ConfirmAttackAction()
            | AssignBlockerAction()
            | RemoveBlockerAction()
            | EndDefenseWindowAction()
        ):
            submit_action(match, command, catalog=catalog, randomness=randomness)
        case _:
            assert_never(command)


def _take_mulligan(
    match: Match, command: MulliganCommand, randomness: RandomSource
) -> None:
    """O mulligan e, se ele fechou o setup, o Upkeep da Rodada 1.

    O setup do motor para em `UPKEEP` sem executá-lo -- posicionar não é
    executar. Sem o empurrão aqui, a partida ficaria esperando uma terceira
    mensagem que nenhum cliente sabe que precisa mandar.
    """
    record_mulligan(
        match, command.user_id, command.card_instance_ids, randomness=randomness
    )

    if match.phase is MatchPhase.UPKEEP:
        begin_round_cycle(match, randomness=randomness)
