"""Ida e volta entre o estado vivo e a forma gravada.

Único módulo que conhece o formato do Redis. Os tipos de domínio não mencionam
JSON em lugar nenhum, e o `match` que decide qual modificador reconstruir mora
aqui, não dentro de `BankUnit`.

Garantia: para qualquer estado válido,
`match_from_document(json.loads(json.dumps(to_match_document(match))))` é
igual ao original -- identificadores, contador, ordem do deck,
dano acumulado, modificadores e o pareamento de bloqueadores da §7.2 inclusive.
"""

from apps.game.cards import CardId, EffectDuration
from apps.game.randomness import RandomSeed
from apps.game.wall_clock import EpochMillis

from .cards_in_play import BankUnit, CardInstanceId, MatchCard
from .chosen_deck import ChosenDeck
from .combat_state import BlockAssignment, CombatState
from .documents import (
    BankUnitDocument,
    BlockAssignmentDocument,
    CardDocument,
    ChosenDeckDocument,
    CombatDocument,
    MatchClockDocument,
    MatchDocument,
    MatchOutcomeDocument,
    ModifierDocument,
    PlayerDocument,
    TurnDeadlineDocument,
)
from .match_clock import MatchClock, TurnDeadline
from .match_outcome import MatchEndReason, MatchOutcome
from .match_state import Match, MatchPhase
from .modifiers import (
    AttackModifier,
    DamageImmunity,
    HealthModifier,
    ModifierKind,
    UnitModifier,
)
from .player_state import PlayerState


def to_match_document(match: Match) -> MatchDocument:
    """A partida inteira, pronta para `json.dumps`.

    >>> to_match_document(match)["next_card_instance_id"]
    81
    """
    return {
        "match_id": match.match_id,
        "players": [to_player_document(player) for player in match.players],
        "round_number": match.round_number,
        "token_holder_user_id": match.token_holder_user_id,
        "token_consumed": match.token_consumed,
        "priority_user_id": match.priority_user_id,
        "phase": match.phase,
        "outcome": to_match_outcome_document(match.outcome),
        "combat": to_combat_document(match.combat),
        "consecutive_passes": match.consecutive_passes,
        "clock": to_match_clock_document(match.clock),
        "next_card_instance_id": match.next_card_instance_id,
        "random_seed": match.random_seed,
        "next_roll_ordinal": match.next_roll_ordinal,
        "started_at": match.started_at,
    }


def match_from_document(document: MatchDocument) -> Match:
    """Reconstrói o que `to_match_document` gravou.

    >>> match_from_document(document).phase
    <MatchPhase.ACTION: 'action'>
    """
    first, second = document["players"]

    return Match(
        match_id=document["match_id"],
        players=(player_from_document(first), player_from_document(second)),
        token_holder_user_id=document["token_holder_user_id"],
        priority_user_id=document["priority_user_id"],
        round_number=document["round_number"],
        token_consumed=document["token_consumed"],
        phase=MatchPhase(document["phase"]),
        outcome=match_outcome_from_document(document["outcome"]),
        combat=combat_from_document(document["combat"]),
        consecutive_passes=document["consecutive_passes"],
        clock=match_clock_from_document(document["clock"]),
        next_card_instance_id=document["next_card_instance_id"],
        random_seed=RandomSeed(document["random_seed"]),
        next_roll_ordinal=document["next_roll_ordinal"],
        started_at=epoch_millis_or_none(document.get("started_at")),
    )


def to_player_document(player: PlayerState) -> PlayerDocument:
    """Um lado do tabuleiro. `user_id` viaja dentro de `profile`, como valor."""
    return {
        "profile": player.profile,
        "nexus": player.nexus,
        "deck": [to_card_document(card) for card in player.deck],
        "hand": [to_card_document(card) for card in player.hand],
        "bank": [to_bank_unit_document(unit) for unit in player.bank],
        "graveyard": [to_card_document(card) for card in player.graveyard],
        "energy_current": player.energy_current,
        "mulligan_taken": player.mulligan_taken,
        "chosen_deck": to_chosen_deck_document(player.chosen_deck),
    }


def player_from_document(document: PlayerDocument) -> PlayerState:
    return PlayerState(
        profile=document["profile"],
        nexus=document["nexus"],
        deck=[card_from_document(card) for card in document["deck"]],
        hand=[card_from_document(card) for card in document["hand"]],
        bank=[bank_unit_from_document(unit) for unit in document["bank"]],
        graveyard=[card_from_document(card) for card in document["graveyard"]],
        energy_current=document["energy_current"],
        mulligan_taken=document["mulligan_taken"],
        chosen_deck=chosen_deck_from_document(document.get("chosen_deck")),
    )


def epoch_millis_or_none(value: int | None) -> EpochMillis | None:
    """Reembrulha um instante que pode não estar lá.

    Ausente e `None` são o mesmo fato aqui: documento gravado antes da feature
    012 não tem o campo, e partida que o tem nunca o tem vazio.

    >>> epoch_millis_or_none(1700000000000)
    1700000000000
    """
    return None if value is None else EpochMillis(value)


def to_chosen_deck_document(
    chosen: ChosenDeck | None,
) -> ChosenDeckDocument | None:
    """`None` atravessa como `None`, como `to_match_outcome_document` já faz."""
    if chosen is None:
        return None

    return {"name": chosen.name, "card_ids": list(chosen.card_ids)}


def chosen_deck_from_document(
    document: ChosenDeckDocument | None,
) -> ChosenDeck | None:
    """A volta reembrulha os inteiros em `CardId`, como `card_from_document`."""
    if document is None:
        return None

    return ChosenDeck(
        name=document["name"],
        card_ids=tuple(CardId(card_id) for card_id in document["card_ids"]),
    )


def to_card_document(card: MatchCard) -> CardDocument:
    """>>> to_card_document(card)
    {'card_instance_id': 3, 'card_id': 15}
    """
    return {"card_instance_id": card.card_instance_id, "card_id": card.card_id}


def card_from_document(document: CardDocument) -> MatchCard:
    return MatchCard(
        card_instance_id=CardInstanceId(document["card_instance_id"]),
        card_id=CardId(document["card_id"]),
    )


def to_bank_unit_document(unit: BankUnit) -> BankUnitDocument:
    return {
        "card": to_card_document(unit.card),
        "damage_taken": unit.damage_taken,
        "modifiers": [to_modifier_document(m) for m in unit.modifiers],
    }


def bank_unit_from_document(document: BankUnitDocument) -> BankUnit:
    return BankUnit(
        card=card_from_document(document["card"]),
        damage_taken=document["damage_taken"],
        modifiers=[modifier_from_document(m) for m in document["modifiers"]],
    )


def to_match_outcome_document(
    outcome: MatchOutcome | None,
) -> MatchOutcomeDocument | None:
    """`None` atravessa como `None`: partida em andamento não tem desfecho."""
    if outcome is None:
        return None

    return {"defeated_user_id": outcome.defeated_user_id, "reason": outcome.reason}


def match_outcome_from_document(
    document: MatchOutcomeDocument | None,
) -> MatchOutcome | None:
    """A volta reembrulha o motivo no enum: um motivo desconhecido é recusado
    na leitura, não usado."""
    if document is None:
        return None

    return MatchOutcome(
        defeated_user_id=document["defeated_user_id"],
        reason=MatchEndReason(document["reason"]),
    )


def to_combat_document(combat: CombatState | None) -> CombatDocument | None:
    """`None` atravessa como `None`: partida fora da §7 não tem combate.

    Mesma forma de `to_match_outcome_document`, e pela mesma razão.
    """
    if combat is None:
        return None

    return {
        "attacker_card_instance_ids": list(combat.attacker_card_instance_ids),
        "blocks": [to_block_assignment_document(block) for block in combat.blocks],
    }


def combat_from_document(document: CombatDocument | None) -> CombatState | None:
    """A volta reembrulha os inteiros em `CardInstanceId`, como
    `card_from_document` já faz."""
    if document is None:
        return None

    return CombatState(
        attacker_card_instance_ids=[
            CardInstanceId(one) for one in document["attacker_card_instance_ids"]
        ],
        blocks=[block_assignment_from_document(one) for one in document["blocks"]],
    )


def to_block_assignment_document(block: BlockAssignment) -> BlockAssignmentDocument:
    return {
        "blocker_card_instance_id": block.blocker_card_instance_id,
        "attacker_card_instance_id": block.attacker_card_instance_id,
    }


def block_assignment_from_document(
    document: BlockAssignmentDocument,
) -> BlockAssignment:
    return BlockAssignment(
        blocker_card_instance_id=CardInstanceId(document["blocker_card_instance_id"]),
        attacker_card_instance_id=CardInstanceId(document["attacker_card_instance_id"]),
    )


def to_match_clock_document(clock: MatchClock) -> MatchClockDocument:
    """Os prazos da §15. Instante é `int` nos dois lados; a volta reembrulha em
    `EpochMillis`, como `CardId` e `RandomSeed` já fazem."""
    return {
        "turn": to_turn_deadline_document(clock.turn),
        "mulligan_expires_at_ms": clock.mulligan_expires_at_ms,
    }


def match_clock_from_document(document: MatchClockDocument) -> MatchClock:
    mulligan = document["mulligan_expires_at_ms"]

    return MatchClock(
        turn=turn_deadline_from_document(document["turn"]),
        mulligan_expires_at_ms=None if mulligan is None else EpochMillis(mulligan),
    )


def to_turn_deadline_document(
    turn: TurnDeadline | None,
) -> TurnDeadlineDocument | None:
    """`None` atravessa como `None`: partida no mulligan ou terminada não tem
    vez. Mesma forma de `to_combat_document`, e pela mesma razão."""
    if turn is None:
        return None

    return {
        "turn_number": turn.turn_number,
        "holder_user_id": turn.holder_user_id,
        "round_number": turn.round_number,
        "warns_at_ms": turn.warns_at_ms,
        "expires_at_ms": turn.expires_at_ms,
        "warning_sent": turn.warning_sent,
    }


def turn_deadline_from_document(
    document: TurnDeadlineDocument | None,
) -> TurnDeadline | None:
    if document is None:
        return None

    return TurnDeadline(
        turn_number=document["turn_number"],
        holder_user_id=document["holder_user_id"],
        round_number=document["round_number"],
        warns_at_ms=EpochMillis(document["warns_at_ms"]),
        expires_at_ms=EpochMillis(document["expires_at_ms"]),
        warning_sent=document["warning_sent"],
    )


def to_modifier_document(modifier: UnitModifier) -> ModifierDocument:
    """O discriminante é o que permite a volta: `{"amount": 2}` sozinho serve
    tanto para ataque quanto para vida.

    Exaustivo sobre a união: um modificador novo sem braço é erro de mypy.
    """
    match modifier:
        case AttackModifier(amount=amount, duration=duration):
            return {
                "modifier_kind": ModifierKind.ATTACK,
                "amount": amount,
                "duration": duration,
            }
        case HealthModifier(amount=amount, duration=duration):
            return {
                "modifier_kind": ModifierKind.HEALTH,
                "amount": amount,
                "duration": duration,
            }
        case DamageImmunity(duration=duration):
            return {
                "modifier_kind": ModifierKind.DAMAGE_IMMUNITY,
                "duration": duration,
            }


def modifier_from_document(document: ModifierDocument) -> UnitModifier:
    """Exaustivo por construção: um `ModifierKind` novo sem braço aqui é erro
    de mypy, não bug em produção."""
    duration = EffectDuration(document["duration"])

    match document["modifier_kind"]:
        case ModifierKind.ATTACK:
            return AttackModifier(amount=document["amount"], duration=duration)
        case ModifierKind.HEALTH:
            return HealthModifier(amount=document["amount"], duration=duration)
        case ModifierKind.DAMAGE_IMMUNITY:
            return DamageImmunity(duration=duration)
