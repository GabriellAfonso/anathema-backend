"""Toda recusa que o socket de partida manda, com um código estável.

O cliente Unity casa recusa por texto estável, e a mensagem das exceções do
motor não serve de chave: ela carrega os valores ofensores. O código serve.

A consulta é por **tipo exato**, e não por `isinstance`: `MatchIsOverError` é
subclasse de `PhaseForbidsActionError` e precisa de código próprio (FR-025).
`test_refusal_codes.py` varre toda subclasse de `IllegalActionError` e falha se
alguma ficar sem código ou se dois códigos se repetirem -- é assim que uma
recusa nova do motor não chega ao cliente sem nome.

O contrato inteiro está em `specs/009-match-protocol/contracts/refusal_codes.md`.
"""

from dataclasses import dataclass

from apps.game.engine import (
    AttackerAlreadyBlockedError,
    AttackerNotInBankError,
    AttackTokenAlreadyConsumedError,
    BankHasNoUnitsError,
    BankIsFullError,
    BlockerAlreadyBlockingError,
    BlockerNotAssignedError,
    BlockerNotInBankError,
    CardIsNotASpellError,
    CardIsNotAUnitError,
    CardNotInHandError,
    DuplicateAttackerError,
    MatchIsOverError,
    MulliganAlreadyTakenError,
    NoAttackersSelectedError,
    NotEnoughEnergyError,
    NotTheTokenHolderError,
    NotYourPriorityError,
    PhaseForbidsActionError,
    SpellNeedsTargetError,
    SpellOnlyInDeclarationError,
    SpellTakesNoTargetError,
    SpellTargetNotOnBattlefieldError,
    UnitAlreadyAttackingError,
    UnitIsNotAttackingError,
    WrongSpellTargetSideError,
)

# As recusas do próprio protocolo: forma, armazenamento e falha do servidor.
MALFORMED_MESSAGE = "malformed_message"
UNKNOWN_MESSAGE_TYPE = "unknown_message_type"
MATCH_NOT_FOUND = "match_not_found"
CONCURRENT_MATCH_WRITE = "concurrent_match_write"
INTERNAL_ERROR = "internal_error"

ENGINE_REFUSAL_CODES: dict[type[Exception], str] = {
    NotYourPriorityError: "not_your_priority",
    PhaseForbidsActionError: "phase_forbids_action",
    MatchIsOverError: "match_is_over",
    CardNotInHandError: "card_not_in_hand",
    NotEnoughEnergyError: "not_enough_energy",
    CardIsNotAUnitError: "card_is_not_a_unit",
    BankIsFullError: "bank_is_full",
    CardIsNotASpellError: "card_is_not_a_spell",
    SpellTakesNoTargetError: "spell_takes_no_target",
    SpellNeedsTargetError: "spell_needs_target",
    WrongSpellTargetSideError: "wrong_spell_target_side",
    SpellTargetNotOnBattlefieldError: "spell_target_not_on_battlefield",
    SpellOnlyInDeclarationError: "spell_only_in_declaration",
    NotTheTokenHolderError: "not_the_token_holder",
    AttackTokenAlreadyConsumedError: "attack_token_already_consumed",
    BankHasNoUnitsError: "bank_has_no_units",
    NoAttackersSelectedError: "no_attackers_selected",
    AttackerNotInBankError: "attacker_not_in_bank",
    DuplicateAttackerError: "duplicate_attacker",
    UnitAlreadyAttackingError: "unit_already_attacking",
    UnitIsNotAttackingError: "unit_is_not_attacking",
    BlockerNotInBankError: "blocker_not_in_bank",
    BlockerAlreadyBlockingError: "blocker_already_blocking",
    AttackerAlreadyBlockedError: "attacker_already_blocked",
    BlockerNotAssignedError: "blocker_not_assigned",
    MulliganAlreadyTakenError: "mulligan_already_taken",
}


@dataclass(frozen=True, slots=True)
class Refusal:
    """O que o socket manda a quem teve a mensagem recusada.

    >>> Refusal(code="not_enough_energy", message="user 7 cannot pay ...").code
    'not_enough_energy'
    """

    code: str
    message: str


def refusal_for(error: Exception) -> Refusal | None:
    """A recusa de uma exceção do motor, ou `None` se ela não é recusa de regra.

    `None` não é erro: é a resposta que diz a quem chama que a exceção é outra
    coisa -- falha do servidor, partida expirada -- e pede tratamento próprio.

    >>> refusal_for(NotYourPriorityError(9, 7, "m-1")).code
    'not_your_priority'
    """
    code = ENGINE_REFUSAL_CODES.get(type(error))

    if code is None:
        return None

    return Refusal(code=code, message=str(error))
