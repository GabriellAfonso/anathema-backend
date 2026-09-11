"""O que aconteceu numa mudança aceita, recortado para quem vai ler.

A descrição sai da **diferença** entre a partida antes e depois da mutação
gravada, e não de um registro dentro do motor: o motor não muda para caber no
transporte (FR-042), e a diferença já responde tudo que o cliente precisa --
qual foi a jogada, e o que ela causou.

A lista tem ordem fixa: primeiro a jogada, depois as consequências -- dano em
unidade, unidade morta, Nexus alterado, rodada nova, compras, fim da partida.
Uma cascata inteira (dois passes, fim de rodada, Upkeep) vira uma lista só.

**O recorte por destinatário acontece aqui, e só aqui.** A compra do próprio
jogador traz as cartas; a do oponente, só a contagem. O mulligan traz só a
contagem para os dois. Toda carta citada por inteiro está no banco ou no
cemitério no momento do evento, e portanto já é pública.
"""

from typing import Literal, TypedDict, assert_never

from apps.game.engine import (
    AssignBlockerAction,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    PassAction,
    PlayUnitAction,
    RemoveBlockerAction,
    WithdrawAttackerAction,
)
from apps.game.match import (
    CardDocument,
    CardInstanceId,
    Match,
    MatchEndReason,
    MatchPhase,
    PlayerState,
)
from apps.game.match.serialization import to_card_document

from .commands import ClientCommand, ForfeitCommand, MulliganCommand


class MulliganTakenEvent(TypedDict):
    kind: Literal["mulligan_taken"]
    user_id: int
    swapped_count: int


class UnitPlayedEvent(TypedDict):
    kind: Literal["unit_played"]
    user_id: int
    card: CardDocument


class SpellCastEvent(TypedDict):
    kind: Literal["spell_cast"]
    user_id: int
    card: CardDocument
    target_card_instance_id: int | None


class PassedEvent(TypedDict):
    kind: Literal["passed"]
    user_id: int


class AttackersSentEvent(TypedDict):
    kind: Literal["attackers_sent"]
    user_id: int
    attacker_card_instance_ids: list[int]


class AttackerWithdrawnEvent(TypedDict):
    kind: Literal["attacker_withdrawn"]
    user_id: int
    attacker_card_instance_id: int


class AttackConfirmedEvent(TypedDict):
    kind: Literal["attack_confirmed"]
    user_id: int


class BlockerAssignedEvent(TypedDict):
    kind: Literal["blocker_assigned"]
    user_id: int
    blocker_card_instance_id: int
    attacker_card_instance_id: int


class BlockerRemovedEvent(TypedDict):
    kind: Literal["blocker_removed"]
    user_id: int
    blocker_card_instance_id: int


class DefenseEndedEvent(TypedDict):
    kind: Literal["defense_ended"]
    user_id: int


class ForfeitedEvent(TypedDict):
    kind: Literal["forfeited"]
    user_id: int


class UnitDamagedEvent(TypedDict):
    kind: Literal["unit_damaged"]
    card_instance_id: int
    amount: int


class UnitDiedEvent(TypedDict):
    kind: Literal["unit_died"]
    user_id: int
    card: CardDocument


class NexusChangedEvent(TypedDict):
    kind: Literal["nexus_changed"]
    user_id: int
    amount: int


class RoundStartedEvent(TypedDict):
    kind: Literal["round_started"]
    round_number: int
    token_holder_user_id: int | None


class CardsDrawnEvent(TypedDict):
    """`cards` vazia para o oponente: a compra dele revela só que ele comprou."""

    kind: Literal["cards_drawn"]
    user_id: int
    count: int
    cards: list[CardDocument]


class MatchFinishedEvent(TypedDict):
    kind: Literal["match_finished"]
    defeated_user_id: int
    reason: MatchEndReason


PlayEvent = (
    MulliganTakenEvent
    | UnitPlayedEvent
    | SpellCastEvent
    | PassedEvent
    | AttackersSentEvent
    | AttackerWithdrawnEvent
    | AttackConfirmedEvent
    | BlockerAssignedEvent
    | BlockerRemovedEvent
    | DefenseEndedEvent
    | ForfeitedEvent
)
MatchEvent = (
    PlayEvent
    | UnitDamagedEvent
    | UnitDiedEvent
    | NexusChangedEvent
    | RoundStartedEvent
    | CardsDrawnEvent
    | MatchFinishedEvent
)
CombatCommand = (
    DeclareAttackAction
    | WithdrawAttackerAction
    | ConfirmAttackAction
    | AssignBlockerAction
    | RemoveBlockerAction
    | EndDefenseWindowAction
)


def describe_change(
    before: Match, after: Match, command: ClientCommand, *, recipient_user_id: int
) -> list[MatchEvent]:
    """A jogada e o que ela causou, na ordem fixa, recortados para o
    destinatário.

    >>> describe_change(before, after, PassAction(9), recipient_user_id=7)[0]
    {'kind': 'passed', 'user_id': 9}
    """
    return [
        _play_event(before, command),
        *_units_damaged(before, after),
        *_units_died(before, after),
        *_nexus_changes(before, after),
        *_round_started(before, after),
        *_cards_drawn(before, after, recipient_user_id),
        *_match_finished(before, after),
    ]


def _play_event(before: Match, command: ClientCommand) -> PlayEvent:
    """A jogada. Carta jogada é lida do estado de antes, onde ainda estava na
    mão do autor."""
    match command:
        case MulliganCommand():
            return _mulligan_taken(command)
        case ForfeitCommand():
            return {"kind": "forfeited", "user_id": command.user_id}
        case PlayUnitAction():
            return _unit_played(before, command)
        case CastSpellAction():
            return _spell_cast(before, command)
        case PassAction():
            return {"kind": "passed", "user_id": command.actor_user_id}
        case _:
            return _combat_event(command)


def _combat_event(command: CombatCommand) -> PlayEvent:
    """As jogadas das duas janelas do combate (§7.1, §7.2)."""
    author = command.actor_user_id

    match command:
        case DeclareAttackAction():
            return _attackers_sent(command)
        case WithdrawAttackerAction():
            return _attacker_withdrawn(command)
        case ConfirmAttackAction():
            return {"kind": "attack_confirmed", "user_id": author}
        case AssignBlockerAction():
            return _blocker_assigned(command)
        case RemoveBlockerAction():
            return _blocker_removed(command)
        case EndDefenseWindowAction():
            return {"kind": "defense_ended", "user_id": author}
        case _:
            assert_never(command)


def _mulligan_taken(command: MulliganCommand) -> MulliganTakenEvent:
    """Só a contagem, para os dois: quais cartas foram trocadas é segredo."""
    return {
        "kind": "mulligan_taken",
        "user_id": command.user_id,
        "swapped_count": len(command.card_instance_ids),
    }


def _unit_played(before: Match, command: PlayUnitAction) -> UnitPlayedEvent:
    return {
        "kind": "unit_played",
        "user_id": command.actor_user_id,
        "card": _hand_card(before, command.actor_user_id, command.card_instance_id),
    }


def _spell_cast(before: Match, command: CastSpellAction) -> SpellCastEvent:
    return {
        "kind": "spell_cast",
        "user_id": command.actor_user_id,
        "card": _hand_card(before, command.actor_user_id, command.card_instance_id),
        "target_card_instance_id": command.target_card_instance_id,
    }


def _attackers_sent(command: DeclareAttackAction) -> AttackersSentEvent:
    # Anotada como `list[int]`: `list` é invariante, e a lista de
    # `CardInstanceId` não entraria no campo do evento.
    attackers: list[int] = list(command.attacker_card_instance_ids)

    return {
        "kind": "attackers_sent",
        "user_id": command.actor_user_id,
        "attacker_card_instance_ids": attackers,
    }


def _attacker_withdrawn(command: WithdrawAttackerAction) -> AttackerWithdrawnEvent:
    return {
        "kind": "attacker_withdrawn",
        "user_id": command.actor_user_id,
        "attacker_card_instance_id": command.attacker_card_instance_id,
    }


def _blocker_assigned(command: AssignBlockerAction) -> BlockerAssignedEvent:
    return {
        "kind": "blocker_assigned",
        "user_id": command.actor_user_id,
        "blocker_card_instance_id": command.blocker_card_instance_id,
        "attacker_card_instance_id": command.attacker_card_instance_id,
    }


def _blocker_removed(command: RemoveBlockerAction) -> BlockerRemovedEvent:
    return {
        "kind": "blocker_removed",
        "user_id": command.actor_user_id,
        "blocker_card_instance_id": command.blocker_card_instance_id,
    }


def _hand_card(
    match: Match, user_id: int, card_instance_id: CardInstanceId
) -> CardDocument:
    """A carta que a jogada aceita tirou da mão. Aceita, ela estava lá."""
    for card in match.player(user_id).hand:
        if card.card_instance_id == card_instance_id:
            return to_card_document(card)

    raise LookupError(
        f"card instance {card_instance_id} is not in the hand of user {user_id} "
        f"before the change: expected the card an accepted play used"
    )


def _units_damaged(before: Match, after: Match) -> list[UnitDamagedEvent]:
    """Unidade que está em campo antes e depois, com mais dano acumulado."""
    events: list[UnitDamagedEvent] = []

    for unit in (unit for player in after.players for unit in player.bank):
        previous = before.bank_unit(unit.card.card_instance_id)

        if previous is not None and unit.damage_taken > previous.damage_taken:
            amount = unit.damage_taken - previous.damage_taken
            events.append(
                {
                    "kind": "unit_damaged",
                    "card_instance_id": unit.card.card_instance_id,
                    "amount": amount,
                }
            )

    return events


def _units_died(before: Match, after: Match) -> list[UnitDiedEvent]:
    """Unidade em campo antes, e no cemitério do dono depois."""
    events: list[UnitDiedEvent] = []

    for owner_before, owner_after in zip(before.players, after.players):
        buried = {card.card_instance_id for card in owner_after.graveyard}

        for unit in owner_before.bank:
            if unit.card.card_instance_id in buried:
                events.append(
                    {
                        "kind": "unit_died",
                        "user_id": owner_before.user_id,
                        "card": to_card_document(unit.card),
                    }
                )

    return events


def _nexus_changes(before: Match, after: Match) -> list[NexusChangedEvent]:
    return [
        {
            "kind": "nexus_changed",
            "user_id": now.user_id,
            "amount": now.nexus - then.nexus,
        }
        for then, now in zip(before.players, after.players)
        if now.nexus != then.nexus
    ]


def _round_started(before: Match, after: Match) -> list[RoundStartedEvent]:
    """Rodada nova, ou a Rodada 1 que o fim do setup abriu."""
    opened_first_round = (
        before.phase is MatchPhase.MULLIGAN and after.phase is MatchPhase.ACTION
    )

    if after.round_number == before.round_number and not opened_first_round:
        return []

    return [
        {
            "kind": "round_started",
            "round_number": after.round_number,
            "token_holder_user_id": after.token_holder_user_id,
        }
    ]


def _cards_drawn(
    before: Match, after: Match, recipient_user_id: int
) -> list[CardsDrawnEvent]:
    """Cartas que estão na mão depois e não estavam antes."""
    events: list[CardsDrawnEvent] = []

    for then, now in zip(before.players, after.players):
        drawn = _new_in_hand(then, now)

        if drawn:
            shown = drawn if now.user_id == recipient_user_id else []
            events.append(
                {
                    "kind": "cards_drawn",
                    "user_id": now.user_id,
                    "count": len(drawn),
                    "cards": shown,
                }
            )

    return events


def _new_in_hand(then: PlayerState, now: PlayerState) -> list[CardDocument]:
    held = {card.card_instance_id for card in then.hand}

    return [
        to_card_document(card) for card in now.hand if card.card_instance_id not in held
    ]


def _match_finished(before: Match, after: Match) -> list[MatchFinishedEvent]:
    if before.outcome is not None or after.outcome is None:
        return []

    outcome = after.outcome
    return [
        {
            "kind": "match_finished",
            "defeated_user_id": outcome.defeated_user_id,
            "reason": outcome.reason,
        }
    ]
