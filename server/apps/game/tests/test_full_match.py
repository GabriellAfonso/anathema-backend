"""Uma partida completa, do setup da §3 à vitória da §10, sem tocar transporte.

Com o combate fechado, o Fluxo de Partida está implementado de ponta a ponta.
Este arquivo não acrescenta regra nenhuma: ele costura as sete features e
verifica que elas se encontram.

O roteiro é um jogador automático deliberadamente burro — joga unidade quando
pode, ataca com tudo quando tem o token, nunca bloqueia, e passa quando não há
mais o que fazer. É o suficiente para a partida acabar, e é de propósito que ele
não decide nada: o que está sob teste é o motor, não a estratégia.

O segundo teste é o que vale mais a longo prazo:
`test_no_automatic_phase_is_ever_observed`. Nenhuma chamada pode devolver a
partida em `UPKEEP`, `STACK_RESOLUTION` ou `ROUND_END` — é a promessa de
`submit_action` desde a feature 005, agora com o combate dentro dela.
"""

from pathlib import Path

import pytest

from apps.game.cards import CardCatalog, Unit, mvp_catalog
from apps.game.engine import (
    DeclareAttackAction,
    EndDefenseWindowAction,
    MAX_BANK_SIZE,
    PassAction,
    PlayUnitAction,
    PlayerAction,
    submit_action,
)
from apps.game.match import CardInstanceId, Match, MatchPhase, PlayerState
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase

PLAYER_ONE = 7
PLAYER_TWO = 9

# Teto de segurança: uma partida que não termina é bug, e um laço infinito num
# teste não diz qual. Com ataque total todo turno, o Nexus de 20 cai em poucas
# rodadas -- este número é ordens de grandeza acima do necessário.
MAX_ACTIONS = 2000

# O motor não pode tocar transporte nem persistência (FR-085, FR-086).
FORBIDDEN_IMPORTS = ("import redis", "from redis", "channels", "django.db")


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def next_action(match: Match, catalog: CardCatalog) -> PlayerAction:
    """Uma jogada legal para quem tem a prioridade. Burra de propósito."""
    assert match.priority_user_id is not None
    actor = match.player(match.priority_user_id)

    if match.phase is MatchPhase.COMBAT:
        return EndDefenseWindowAction(actor_user_id=actor.user_id)

    if _can_attack(match, actor):
        return DeclareAttackAction(
            actor_user_id=actor.user_id,
            attacker_card_instance_ids=tuple(
                unit.card.card_instance_id for unit in actor.bank
            ),
        )

    playable = _playable_unit(actor, catalog)

    if playable is not None:
        return PlayUnitAction(actor_user_id=actor.user_id, card_instance_id=playable)

    return PassAction(actor_user_id=actor.user_id)


def _can_attack(match: Match, actor: PlayerState) -> bool:
    return (
        match.token_holder_user_id == actor.user_id
        and not match.token_consumed
        and not match.stack
        and bool(actor.bank)
    )


def _playable_unit(actor: PlayerState, catalog: CardCatalog) -> CardInstanceId | None:
    """A primeira unidade da mão que cabe na energia e no banco, ou `None`."""
    if len(actor.bank) >= MAX_BANK_SIZE:
        return None

    for card in actor.hand:
        template = catalog.card(card.card_id)

        if isinstance(template, Unit) and template.energy <= actor.energy_current:
            return card.card_instance_id

    return None


def play_until_over(
    match: Match, *, catalog: CardCatalog, source: RandomSource
) -> list[MatchPhase]:
    """Roda a partida até alguém perder, e devolve as fases observadas."""
    observed: list[MatchPhase] = []

    for _ in range(MAX_ACTIONS):
        if match.is_over:
            return observed

        submit_action(
            match, next_action(match, catalog), catalog=catalog, randomness=source
        )
        observed.append(match.phase)

    raise AssertionError(
        f"match did not finish in {MAX_ACTIONS} actions: "
        f"round {match.round_number}, nexus "
        f"{[player.nexus for player in match.players]}"
    )


# --- Do setup à vitória ------------------------------------------------------


def test_a_full_match_runs_from_setup_to_victory(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.is_over
    assert match.phase is MatchPhase.FINISHED
    assert match.outcome is not None
    assert len(match.outcome.defeated_user_ids) >= 1


def test_the_loser_is_the_one_whose_nexus_reached_zero(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.outcome is not None
    assert set(match.outcome.defeated_user_ids) == {
        player.user_id for player in match.players if player.nexus <= 0
    }


def test_the_combat_is_reached_at_least_once(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem combate a partida não acaba: nenhum dos cinco feitiços do MVP tira
    Nexus do oponente."""
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    observed = play_until_over(match, catalog=catalog, source=source)

    assert MatchPhase.COMBAT in observed


def test_the_match_goes_through_several_rounds(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.round_number > 1


# --- Nenhuma fase automática observada ---------------------------------------


def test_no_automatic_phase_is_ever_observed(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A promessa de `submit_action` desde a feature 005, com o combate dentro:
    o chamador vê a Fase de Ação, o Combate e o estado terminal — nunca uma fase
    de passagem."""
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    observed = play_until_over(match, catalog=catalog, source=source)

    assert set(observed) <= {
        MatchPhase.ACTION,
        MatchPhase.COMBAT,
        MatchPhase.FINISHED,
    }


def test_the_match_never_stalls_in_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Combate nunca aparece duas vezes seguidas: este jogador nunca bloqueia,
    então a ação seguinte sempre o encerra."""
    match = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO, randomness=source)

    observed = play_until_over(match, catalog=catalog, source=source)

    assert not any(
        first is MatchPhase.COMBAT and second is MatchPhase.COMBAT
        for first, second in zip(observed, observed[1:])
    )


# --- O motor não toca transporte ---------------------------------------------


def test_the_engine_imports_no_transport_and_no_persistence() -> None:
    """FR-085 e FR-086 verificados no código, e não em `sys.modules`: o Django
    já está importado pelo pytest, e a pergunta é sobre **este** pacote.

    O escopo é o `engine/`, e não o `match/`: `match/store.py` e
    `match/client.py` são justamente o embrulho do Redis que a feature 003
    entregou, e é o **chamador** que grava por eles. O motor recebe a partida e
    devolve a partida.
    """
    offenders = [
        (path.name, line)
        for path in _engine_sources()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
        and any(forbidden in line for forbidden in FORBIDDEN_IMPORTS)
    ]

    assert offenders == []


def test_the_engine_never_reaches_for_the_store() -> None:
    """Nem por dentro do próprio `apps.game`: gravar é do chamador."""
    offenders = [
        (path.name, line)
        for path in _engine_sources()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
        and ("match.store" in line or "consumers" in line)
    ]

    assert offenders == []


def _engine_sources() -> list[Path]:
    root = Path(__file__).resolve().parent.parent

    return sorted((root / "engine").glob("*.py"))
