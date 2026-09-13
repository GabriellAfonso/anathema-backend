"""Exatamente uma vez: o requisito que carrega a feature.

A mesma partida é observada pelos dois jogadores, em conexões que podem estar em
workers diferentes, e os dois recebem o estado final. Reconectar devolve o estado
final de novo. Nada disso pode produzir um segundo registro nem uma segunda
vitória.

Dois níveis, e os dois importam:

- pelo socket, com o gravador falso -- prova que **quem** dispara é a transição,
  e que a entrega e a reconexão não disparam;
- pelo banco, com `django_db` -- prova que a unicidade de `match_id` é o que faz
  a corrida que sobra perder em vez de duplicar.
"""

import asyncio
from copy import deepcopy

import pytest
from django.contrib.auth.models import User

from apps.game.engine import forfeit
import apps.game.history.recorder as recorder_module
from apps.game.history import (
    DatabaseFinishedMatchRecorder,
    FinishedMatch,
    FinishedSide,
    finished_match,
)
from apps.game.match import Match
from apps.game.models import MatchRecord
from apps.game.tests.fake_finished_match_recorder import FakeFinishedMatchRecorder
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_setup import fake_match_in_action_phase
from apps.game.tests.match_sockets import next_update, open_match_socket, saved
from apps.game.wall_clock import EpochMillis
from apps.players.models.player import PlayerProfile, PlayerStats

PLAYER_ONE = 7
PLAYER_TWO = 9

STARTED_AT = EpochMillis(1_700_000_000_000)
ENDED_AT = EpochMillis(1_700_000_742_000)


# --- Pelo socket: só a transição dispara ------------------------------------


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore()


@pytest.fixture
def recorder() -> FakeFinishedMatchRecorder:
    return FakeFinishedMatchRecorder()


async def _match_in_play(matches: FakeMatchStore) -> Match:
    running = fake_match_in_action_phase(PLAYER_ONE, PLAYER_TWO)
    running.started_at = STARTED_AT

    return await saved(matches, running)


async def test_a_forfeit_over_the_socket_records_once(
    matches: FakeMatchStore, recorder: FakeFinishedMatchRecorder
) -> None:
    """Os dois sockets recebem o estado final; um registro sai."""
    match = await _match_in_play(matches)
    one, _ = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, recorder=recorder
    )
    two, _ = await open_match_socket(
        matches, PLAYER_TWO, match.match_id, recorder=recorder
    )

    await one.send_json_to({"type": "forfeit", "payload": {}})
    await next_update(one)
    await next_update(two)

    assert len(recorder.recorded) == 1
    assert recorder.recorded[0].loser.user_id == PLAYER_ONE
    await one.disconnect()
    await two.disconnect()


async def test_reconnecting_after_the_end_records_nothing(
    matches: FakeMatchStore, recorder: FakeFinishedMatchRecorder
) -> None:
    """Observação nunca registra, quantas vezes for."""
    match = await _match_in_play(matches)
    one, _ = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, recorder=recorder
    )
    await one.send_json_to({"type": "forfeit", "payload": {}})
    await next_update(one)
    await one.disconnect()

    for _ in range(20):
        again, _ = await open_match_socket(
            matches, PLAYER_TWO, match.match_id, recorder=recorder
        )
        await again.disconnect()

    assert len(recorder.recorded) == 1


async def test_a_match_that_never_ends_records_nothing(
    matches: FakeMatchStore, recorder: FakeFinishedMatchRecorder
) -> None:
    """A partida abandonada pelos dois expira do Redis. Não existe derrota por
    abandono, e nada é gravado."""
    match = await _match_in_play(matches)
    one, _ = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, recorder=recorder
    )
    two, _ = await open_match_socket(
        matches, PLAYER_TWO, match.match_id, recorder=recorder
    )

    await one.disconnect()
    await two.disconnect()
    matches.matches.pop(match.match_id)

    assert recorder.recorded == []


async def test_a_failing_recorder_does_not_stop_the_final_state(
    matches: FakeMatchStore, recorder: FakeFinishedMatchRecorder
) -> None:
    """Uma falha de banco é uma linha a menos no histórico, nunca uma recusa."""
    match = await _match_in_play(matches)
    recorder.fails = True
    one, _ = await open_match_socket(
        matches, PLAYER_ONE, match.match_id, recorder=recorder
    )
    two, _ = await open_match_socket(
        matches, PLAYER_TWO, match.match_id, recorder=recorder
    )

    await one.send_json_to({"type": "forfeit", "payload": {}})

    assert await next_update(one) is not None
    assert await next_update(two) is not None
    stored = await matches.get_stored(match.match_id)
    assert stored is not None and stored.match.is_over
    await one.disconnect()
    await two.disconnect()


# --- Pelo banco: a unicidade resolve a corrida ------------------------------


db = pytest.mark.django_db


def _a_player(nickname: str) -> PlayerProfile:
    user = User.objects.create_user(username=nickname, password="x")
    profile = PlayerProfile.objects.create(user=user, nickname=nickname)
    PlayerStats.objects.create(profile=profile)

    return profile


def _finished_twin() -> tuple[Match, Match]:
    """A partida antes e depois da desistência, com perfis de verdade."""
    one, two = _a_player("one").pk, _a_player("two").pk
    match = fake_match_in_action_phase(one, two)
    match.started_at = STARTED_AT
    before = deepcopy(match)
    forfeit(match, one)

    return before, match


@db
async def test_recording_the_same_match_twice_writes_one_row() -> None:
    before, match = _finished_twin()
    finished = finished_match(before, match, ENDED_AT)
    assert finished is not None
    recorder = DatabaseFinishedMatchRecorder()

    assert await recorder.record(finished) is True
    assert await recorder.record(finished) is False

    assert await MatchRecord.objects.filter(match_id=match.match_id).acount() == 1


@db
async def test_the_losing_race_counts_no_second_victory() -> None:
    """Perder a corrida não soma vitória, e não vira exceção."""
    before, match = _finished_twin()
    finished = finished_match(before, match, ENDED_AT)
    assert finished is not None
    recorder = DatabaseFinishedMatchRecorder()

    await recorder.record(finished)
    await recorder.record(finished)

    winner = await PlayerStats.objects.aget(profile_id=finished.winner.user_id)
    assert (winner.wins, winner.matches_played) == (1, 1)


@db
async def test_two_concurrent_recordings_leave_one_row() -> None:
    """Os dois workers chegam ao registro da mesma partida ao mesmo tempo."""
    before, match = _finished_twin()
    finished = finished_match(before, match, ENDED_AT)
    assert finished is not None

    results = await asyncio.gather(
        DatabaseFinishedMatchRecorder().record(finished),
        DatabaseFinishedMatchRecorder().record(finished),
    )

    assert sorted(results) == [False, True]
    assert await MatchRecord.objects.filter(match_id=match.match_id).acount() == 1


def refuse_to_bump_stats(
    side: FinishedSide, finished: FinishedMatch, *, won: bool
) -> None:
    """A segunda escrita da transação, falhando.

    Função nomeada e não `lambda`: é o substituto de uma escrita de banco, e a
    constituição pede nome para isso. Assinatura idêntica à real, senão o teste
    passaria depois de a de verdade mudar.
    """
    raise RuntimeError(f"refusing to bump stats of user {side.user_id}")


@db
async def test_a_failing_statistics_write_leaves_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Atômico: uma falha no meio não deixa vitória contada sem partida registrada."""
    before, match = _finished_twin()
    finished = finished_match(before, match, ENDED_AT)
    assert finished is not None
    monkeypatch.setattr(recorder_module, "_bump_stats", refuse_to_bump_stats)

    with pytest.raises(RuntimeError):
        await DatabaseFinishedMatchRecorder().record(finished)

    assert await MatchRecord.objects.filter(match_id=match.match_id).acount() == 0
    winner = await PlayerStats.objects.aget(profile_id=finished.winner.user_id)
    assert (winner.matches_played, winner.wins) == (0, 0)
