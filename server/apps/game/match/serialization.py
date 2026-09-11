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

from .cards_in_play import BankUnit, CardInstanceId, MatchCard
from .combat_state import BlockAssignment, CombatState
from .documents import (
    BankUnitDocument,
    BlockAssignmentDocument,
    CardDocument,
    CombatDocument,
    MatchDocument,
    MatchOutcomeDocument,
    ModifierDocument,
    PlayerDocument,
)
from .match_outcome import MatchOutcome
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
        "next_card_instance_id": match.next_card_instance_id,
        "random_seed": match.random_seed,
        "next_roll_ordinal": match.next_roll_ordinal,
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
        next_card_instance_id=document["next_card_instance_id"],
        random_seed=RandomSeed(document["random_seed"]),
        next_roll_ordinal=document["next_roll_ordinal"],
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

    return {"defeated_user_ids": list(outcome.defeated_user_ids)}


def match_outcome_from_document(
    document: MatchOutcomeDocument | None,
) -> MatchOutcome | None:
    """A volta reembrulha a lista em tupla, e a validação da construção corre
    de novo -- um documento corrompido é recusado na leitura, não usado."""
    if document is None:
        return None

    return MatchOutcome(defeated_user_ids=tuple(document["defeated_user_ids"]))


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
