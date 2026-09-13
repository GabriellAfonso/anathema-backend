"""Gravar o resultado: a porta que o caminho de partida vê, e o ORM atrás dela.

A porta existe por uma regra registrada em `apps/game/tests/conftest.py`:
**nenhum teste de websocket toca o banco**. Uma escrita de ORM alcançável do
consumer quebraria isso na suíte inteira, não só no teste que a exercita. Mesma
forma de `PlayerDeckSource`, e pela mesma razão.

O retorno é `bool`, e não `None`: `False` é "outro worker já registrou esta
partida", que é resultado normal e não falha. Perder a corrida não vira exceção
e não chega ao cliente.

Registro e estatísticas vão na **mesma** transação. Uma falha no meio deixaria
vitória contada sem partida registrada -- o pior dos dois estados, porque ninguém
consegue apurar depois qual das duas ficou para trás.
"""

import datetime
from typing import Protocol, cast

from channels.db import database_sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import F

from apps.game.models import MatchRecord
from apps.game.wall_clock import EpochMillis
from apps.players.models.player import PlayerStats

from .finished_match import FinishedMatch, FinishedSide

MILLIS_PER_SECOND = 1000


class FinishedMatchRecorder(Protocol):
    """Grava o resultado de uma partida terminada. Uma vez, e só uma.

    `Protocol` e não classe base para que o substituto de teste só precise do
    método, sem herdar de nada -- mesma escolha de `PlayerDeckSource`,
    `CardCatalog` e `WallClock`.
    """

    async def record(self, finished: FinishedMatch) -> bool:
        """`True` se esta chamada gravou; `False` se a partida já estava lá."""
        ...


class DatabaseFinishedMatchRecorder:
    """A implementação de verdade: uma linha e dois contadores, numa transação.

    >>> await DatabaseFinishedMatchRecorder().record(finished)
    True
    >>> await DatabaseFinishedMatchRecorder().record(finished)   # de novo
    False
    """

    async def record(self, finished: FinishedMatch) -> bool:
        """O `cast` existe porque `database_sync_to_async` chega sem stubs e
        devolve `Any`; a função embrulhada é tipada logo abaixo."""
        return cast(bool, await _write_record(finished))


# channels não publica stubs, então o decorator chega como `Any` e levaria a
# função inteira junto.
@database_sync_to_async  # type: ignore[untyped-decorator]
@transaction.atomic
def _write_record(finished: FinishedMatch) -> bool:
    """A linha e os dois contadores, tudo ou nada.

    A ordem importa: sem registro não há estatística. É o `INSERT` que decide
    quem venceu a corrida, e só quem venceu soma vitória.
    """
    if not _insert_record(finished):
        return False

    _bump_stats(finished.winner, finished, won=True)
    _bump_stats(finished.loser, finished, won=False)

    return True


def _insert_record(finished: FinishedMatch) -> bool:
    """Insere a linha, ou devolve `False` se outro worker chegou primeiro.

    O `atomic` aninhado é um savepoint, e é obrigatório: um `IntegrityError`
    levantado direto dentro da transação externa a marca para rollback, e o
    `update()` de estatística seguinte levantaria `TransactionManagementError`.
    Com o savepoint, só a tentativa de inserção é desfeita.
    """
    try:
        with transaction.atomic():
            MatchRecord.objects.create(**_record_fields(finished))
    except IntegrityError:
        return False

    return True


def _record_fields(finished: FinishedMatch) -> dict[str, object]:
    """Os campos da linha, do valor já derivado do estado.

    `winner_id` e `loser_id` e não `winner=` / `loser=`: são o `user_id`, que é
    também o `profile_id` (decisão 0001), e atribuí-los direto evita uma ida ao
    banco para carregar dois perfis que ninguém vai ler.
    """
    return {
        "match_id": finished.match_id,
        "winner_id": finished.winner.user_id,
        "loser_id": finished.loser.user_id,
        "end_reason": finished.reason,
        "started_at": _as_datetime(finished.started_at),
        "ended_at": _as_datetime(finished.ended_at),
        "duration_seconds": finished.duration_seconds,
        "final_round": finished.final_round,
        "winner_final_nexus": finished.winner.final_nexus,
        "loser_final_nexus": finished.loser.final_nexus,
        "winner_deck_name": finished.winner.deck_name,
        "loser_deck_name": finished.loser.deck_name,
        "winner_deck_card_ids": [int(c) for c in finished.winner.deck_card_ids],
        "loser_deck_card_ids": [int(c) for c in finished.loser.deck_card_ids],
    }


def _bump_stats(side: FinishedSide, finished: FinishedMatch, *, won: bool) -> None:
    """Soma a partida aos contadores daquele jogador.

    `F()` e não `obj.wins += 1; obj.save()`: o incremento acontece no banco,
    numa instrução só. Duas partidas do mesmo jogador terminando ao mesmo tempo
    em workers diferentes somam as duas; ler em Python e escrever de volta faria
    a segunda apagar a primeira.

    `filter().update()` e não `get()`: um perfil sem `PlayerStats` -- conta
    criada fora do registro, por `createsuperuser` ou fixture -- afeta 0 linhas
    e segue. Derrubar aqui desfaria o registro de uma partida que de fato
    aconteceu, por causa de um contador que nunca existiu.
    """
    PlayerStats.objects.filter(profile_id=side.user_id).update(
        matches_played=F("matches_played") + 1,
        wins=F("wins") + (1 if won else 0),
        losses=F("losses") + (0 if won else 1),
        play_time=F("play_time") + finished.duration_seconds,
    )


def _as_datetime(moment: EpochMillis) -> datetime.datetime:
    """De milissegundos da época para o `DateTimeField`, sempre em UTC.

    `USE_TZ` está ligado, então o Django espera instante consciente de fuso.
    O fuso de exibição é problema do cliente.

    >>> _as_datetime(EpochMillis(1700000000000)).tzinfo
    datetime.timezone.utc
    """
    return datetime.datetime.fromtimestamp(moment / MILLIS_PER_SECOND, tz=datetime.UTC)


DATABASE_RECORDER_MATCHES_THE_PROTOCOL: FinishedMatchRecorder = (
    DatabaseFinishedMatchRecorder()
)
