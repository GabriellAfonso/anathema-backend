"""Uma partida completa, do setup da §3 à vitória da §10, sem tocar transporte.

Com o combate fechado, o Fluxo de Partida está implementado de ponta a ponta.
Este arquivo não acrescenta regra nenhuma: ele costura as sete features e
verifica que elas se encontram.

O roteiro é um jogador automático deliberadamente burro — joga todo feitiço que
pode, declara ataque com tudo quando tem o token e confirma **Atacar** logo
depois de gastar os feitiços, joga unidade quando pode, nunca bloqueia, e passa
quando não há mais o que fazer. No combate, o defensor joga feitiço enquanto
pode e depois encerra a janela. É o suficiente para a partida
acabar, e é de propósito que ele não decide nada: o que está sob teste é o
motor, não a estratégia.

O deck não é o de andaime: aquele pega as cartas em ordem de `card_id` e fecha
40 só com unidades, então uma partida com ele nunca joga feitiço. Este tem os
feitiços do MVP menos o SACRIFICIAL FIRE, que a §14 da nota (corrigida em
2026-09-11) restringe à declaração de ataque. O laço de feitiços de uma vez
termina porque todo feitiço do MVP custa pelo menos 2 de energia.

O segundo teste é o que vale mais a longo prazo:
`test_no_automatic_phase_is_ever_observed`. Nenhuma chamada pode devolver a
partida em `UPKEEP` ou `ROUND_END` — é a promessa de
`submit_action` desde a feature 005, agora com o combate dentro dela.
"""

from pathlib import Path

import pytest

from apps.game.cards import (
    CardCatalog,
    CardId,
    Deck,
    Spell,
    TargetKind,
    Unit,
    mvp_catalog,
)
from apps.game.engine import (
    ActionKind,
    CastSpellAction,
    ConfirmAttackAction,
    DeclareAttackAction,
    EndDefenseWindowAction,
    MAX_BANK_SIZE,
    PassAction,
    PlayUnitAction,
    PlayerAction,
    submit_action,
)
from apps.game.match import (
    CardInstanceId,
    Match,
    MatchEndReason,
    MatchPhase,
    PlayerState,
)
from apps.game.randomness import RandomSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_setup import fake_match_in_action_phase

PLAYER_ONE = 7
PLAYER_TWO = 9

# Teto de segurança: uma partida que não termina é bug, e um laço infinito num
# teste não diz qual. Com ataque total todo turno, o Nexus de 20 cai em poucas
# rodadas -- este número é ordens de grandeza acima do necessário.
MAX_ACTIONS = 2000

# Os feitiços do MVP que o jogador automático joga -- todos menos o SACRIFICIAL
# FIRE (1003), que pela §14 só vale na declaração de ataque.
SCRIPTED_SPELLS = (CardId(1001), CardId(1002), CardId(1004), CardId(1005))
DECK_SIZE = 40
COPIES = 3

# Uma jogada e o que ela deixou: fase antes, espécie da ação, fase depois.
Step = tuple[MatchPhase, ActionKind, MatchPhase]

# O motor não pode tocar transporte nem persistência (FR-085, FR-086).
FORBIDDEN_IMPORTS = ("import redis", "from redis", "channels", "django.db")


@pytest.fixture
def catalog() -> CardCatalog:
    return mvp_catalog()


@pytest.fixture
def source() -> RandomSource:
    return ScriptedRandomSource()


def spell_deck(catalog: CardCatalog) -> Deck:
    """Três cópias de cada feitiço do roteiro, e unidades baratas até 40."""
    deck = [card_id for card_id in SCRIPTED_SPELLS for _ in range(COPIES)]
    cheap = [
        card.card_id
        for card in catalog.all_cards()
        if isinstance(card, Unit) and card.energy <= 3
    ]

    for card_id in cheap:
        deck.extend([card_id] * min(COPIES, DECK_SIZE - len(deck)))

    return tuple(deck)


def new_match(catalog: CardCatalog, source: RandomSource) -> Match:
    return fake_match_in_action_phase(
        PLAYER_ONE, PLAYER_TWO, randomness=source, deck=spell_deck(catalog)
    )


def next_action(match: Match, catalog: CardCatalog) -> PlayerAction:
    """Uma jogada legal para quem tem a prioridade. Burra de propósito."""
    assert match.priority_user_id is not None
    actor = match.player(match.priority_user_id)
    spell = _castable_spell(match, actor, catalog)

    if spell is not None:
        return spell

    if match.phase is MatchPhase.DECLARATION:
        return ConfirmAttackAction(actor_user_id=actor.user_id)

    if match.phase is MatchPhase.COMBAT:
        return EndDefenseWindowAction(actor_user_id=actor.user_id)

    return _action_phase_move(match, actor, catalog)


def _action_phase_move(
    match: Match, actor: PlayerState, catalog: CardCatalog
) -> PlayerAction:
    """Sem feitiço a jogar: ataca, senão joga unidade, senão passa."""
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


def _castable_spell(
    match: Match, actor: PlayerState, catalog: CardCatalog
) -> CastSpellAction | None:
    """O primeiro feitiço da mão que cabe na energia e tem alvo, ou `None`."""
    for card in actor.hand:
        template = catalog.card(card.card_id)

        if not isinstance(template, Spell) or template.energy > actor.energy_current:
            continue

        if template.effect.target_kind is TargetKind.NONE:
            return CastSpellAction(actor.user_id, card.card_instance_id)

        target = _target_for(match, actor, template.effect.target_kind)

        if target is not None:
            return CastSpellAction(actor.user_id, card.card_instance_id, target)

    return None


def _target_for(
    match: Match, actor: PlayerState, kind: TargetKind
) -> CardInstanceId | None:
    """A primeira unidade do lado que o efeito pede, ou `None`."""
    side = actor if kind is TargetKind.ALLIED_UNIT else match.opponent_of(actor.user_id)

    return side.bank[0].card.card_instance_id if side.bank else None


def _can_attack(match: Match, actor: PlayerState) -> bool:
    return (
        match.token_holder_user_id == actor.user_id
        and not match.token_consumed
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
) -> list[Step]:
    """Roda a partida até alguém perder, e devolve cada jogada com as fases."""
    steps: list[Step] = []

    for _ in range(MAX_ACTIONS):
        if match.is_over:
            return steps

        before, action = match.phase, next_action(match, catalog)
        submit_action(match, action, catalog=catalog, randomness=source)
        steps.append((before, action.action_kind, match.phase))

    raise AssertionError(
        f"match did not finish in {MAX_ACTIONS} actions: "
        f"round {match.round_number}, nexus "
        f"{[player.nexus for player in match.players]}"
    )


def phases_after(steps: list[Step]) -> list[MatchPhase]:
    """As fases em que cada jogada deixou a partida."""
    return [after for _, _, after in steps]


# --- Do setup à vitória ------------------------------------------------------


def test_a_full_match_runs_from_setup_to_victory(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = new_match(catalog, source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.is_over
    assert match.phase is MatchPhase.FINISHED
    assert match.outcome is not None
    assert match.outcome.reason is MatchEndReason.NEXUS_DEPLETED


def test_the_loser_is_the_one_whose_nexus_reached_zero(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = new_match(catalog, source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.outcome is not None
    assert [player.user_id for player in match.players if player.nexus <= 0] == [
        match.outcome.defeated_user_id
    ]


def test_the_combat_is_reached_at_least_once(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Sem combate a partida não acaba: nenhum dos cinco feitiços do MVP tira
    Nexus do oponente."""
    match = new_match(catalog, source)

    observed = phases_after(play_until_over(match, catalog=catalog, source=source))

    assert MatchPhase.COMBAT in observed


def test_the_match_goes_through_several_rounds(
    catalog: CardCatalog, source: RandomSource
) -> None:
    match = new_match(catalog, source)

    play_until_over(match, catalog=catalog, source=source)

    assert match.round_number > 1


def test_spells_are_cast_in_both_phases(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """Feitiço aceito na Fase de Ação **e** na janela do defensor, na mesma
    partida -- sem isso, o resto do arquivo passaria sem nunca exercitar a
    §5B."""
    match = new_match(catalog, source)

    steps = play_until_over(match, catalog=catalog, source=source)

    cast_in = {before for before, kind, _ in steps if kind is ActionKind.CAST_SPELL}
    assert cast_in >= {MatchPhase.ACTION, MatchPhase.COMBAT}


# --- Nenhuma fase automática observada ---------------------------------------


def test_no_automatic_phase_is_ever_observed(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """A promessa de `submit_action` desde a feature 005, com o combate dentro:
    o chamador vê a Fase de Ação, o Combate e o estado terminal — nunca uma fase
    de passagem."""
    match = new_match(catalog, source)

    observed = phases_after(play_until_over(match, catalog=catalog, source=source))

    assert set(observed) <= {
        MatchPhase.ACTION,
        MatchPhase.DECLARATION,
        MatchPhase.COMBAT,
        MatchPhase.FINISHED,
    }


def test_the_match_never_stalls_in_combat(
    catalog: CardCatalog, source: RandomSource
) -> None:
    """O combate só continua aberto por um feitiço do defensor: este jogador
    nunca bloqueia, então toda outra ação dentro da janela a encerra.

    Até a feature 008 a afirmação era "Combate nunca aparece duas vezes
    seguidas", porque o roteiro não jogava feitiço. Com feitiço que não gasta a
    vez, o defensor pode ficar na janela por algumas jogadas -- e é por isso que
    a pergunta passou a ser **qual** jogada o manteve lá.
    """
    match = new_match(catalog, source)

    steps = play_until_over(match, catalog=catalog, source=source)

    assert all(
        kind is ActionKind.CAST_SPELL
        for before, kind, after in steps
        if before is after and before in (MatchPhase.DECLARATION, MatchPhase.COMBAT)
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
