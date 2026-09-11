"""Toda recusa do motor tem um código estável, e nenhum código se repete.

O cliente Unity casa pelo código. Uma recusa nova do motor sem código chegaria
ao cliente como `internal_error`, e dois códigos iguais para recusas diferentes
fariam o cliente responder à coisa errada (FR-025).
"""

from apps.game.engine import (
    IllegalActionError,
    MatchIsOverError,
    MulliganAlreadyTakenError,
    NotYourPriorityError,
    PassAction,
    PhaseForbidsActionError,
    ActionKind,
)
from apps.game.match import MatchPhase
from apps.game.protocol import (
    CONCURRENT_MATCH_WRITE,
    INTERNAL_ERROR,
    MALFORMED_MESSAGE,
    MATCH_NOT_FOUND,
    UNKNOWN_MESSAGE_TYPE,
    refusal_for,
)
from apps.game.protocol.refusal_codes import ENGINE_REFUSAL_CODES


def _every_subclass(root: type[Exception]) -> list[type[Exception]]:
    found: list[type[Exception]] = []

    for child in root.__subclasses__():
        found.append(child)
        found.extend(_every_subclass(child))

    return found


def test_every_engine_refusal_has_a_code() -> None:
    missing = [
        refusal.__name__
        for refusal in _every_subclass(IllegalActionError)
        if refusal not in ENGINE_REFUSAL_CODES
    ]

    assert missing == []


def test_the_mulligan_refusal_has_a_code() -> None:
    assert ENGINE_REFUSAL_CODES[MulliganAlreadyTakenError] == "mulligan_already_taken"


def test_no_two_refusals_share_a_code() -> None:
    codes = [
        *ENGINE_REFUSAL_CODES.values(),
        MALFORMED_MESSAGE,
        UNKNOWN_MESSAGE_TYPE,
        MATCH_NOT_FOUND,
        CONCURRENT_MATCH_WRITE,
        INTERNAL_ERROR,
    ]

    assert len(codes) == len(set(codes))


def test_a_subclass_refusal_gets_its_own_code_not_its_parent() -> None:
    """Consulta por tipo exato: partida terminada não é "fase proibida"."""
    over = refusal_for(MatchIsOverError(ActionKind.PASS, None, "m-1"))
    forbidden = refusal_for(
        PhaseForbidsActionError(
            ActionKind.PASS, MatchPhase.UPKEEP, PassAction.allowed_phases, "m-1"
        )
    )

    assert over is not None and forbidden is not None
    assert (over.code, forbidden.code) == ("match_is_over", "phase_forbids_action")


def test_the_refusal_carries_the_readable_message() -> None:
    refusal = refusal_for(NotYourPriorityError(9, 7, "m-1"))

    assert refusal is not None
    assert refusal.code == "not_your_priority"
    assert "priority belongs to user 7" in refusal.message


def test_an_exception_that_is_not_a_rule_refusal_has_no_code() -> None:
    assert refusal_for(ValueError("boom")) is None


def test_codes_are_stable_text_without_values() -> None:
    """Minúsculas e sublinhado: nada de valor da jogada dentro do código."""
    assert all(
        code.replace("_", "").isalpha() and code.islower()
        for code in ENGINE_REFUSAL_CODES.values()
    )
