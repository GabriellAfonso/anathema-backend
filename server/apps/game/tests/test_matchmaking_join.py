"""Entrar na fila exige dizer o deck, e ele é conferido antes da fila.

A propriedade que mais importa aqui não é a recusa em si: é **quando** ela
acontece. Um jogador recusado nunca pode ter ocupado lugar na fila, senão o
oponente seguinte perde o tempo de fila dele por um problema que não é dele, e
o par já teria sido consumido.

Sem banco e sem Redis: o deck chega por `FakePlayerDeckSource` e a fila é
`FakeMatchmakingQueue`. Quem prova a fila de verdade é
`test_matchmaking_queue.py`, contra Redis; quem prova a consulta de verdade é
`apps/players/tests/test_deck_queries.py`, com `django_db`.
"""

from collections.abc import Mapping
from typing import cast

import pytest
from channels.layers import get_channel_layer
from django.contrib.auth.base_user import AbstractBaseUser

from apps.game.cards import CardId, Deck, get_card_catalog, starter_deck
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.match.store import MatchStore
from apps.game.matchmaking.queue import MatchmakingQueue, QueueEntry
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_chosen_deck import fake_chosen_deck
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.fake_wall_clock import FakeWallClock

PLAYER_ONE = 7
PLAYER_TWO = 9
THEIR_DECK_ID = 1
NOBODYS_DECK_ID = 999


class RecordingConsumer(MatchmakingConsumer):
    """Guarda o que o socket mandaria, em vez de mandar.

    Subclasse nomeada e não `monkeypatch`: é o mesmo movimento de
    `InterleavedMatchStore`, e deixa a asserção olhar para um atributo em vez
    de para um mock.
    """

    # Preenchido pela fábrica abaixo: sobrescrever `__init__` só para isto
    # obrigaria a repetir a assinatura inteira do consumer.
    sent: list[dict[str, object]]

    async def send_event(
        self, *, type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        self.sent.append({"type": type, "payload": dict(payload or {})})

    @property
    def last(self) -> dict[str, object]:
        assert self.sent, "o socket não mandou nada"

        return self.sent[-1]

    @property
    def last_payload(self) -> dict[str, object]:
        payload = self.last["payload"]
        assert isinstance(payload, dict)

        return payload


@pytest.fixture
def deck() -> Deck:
    return starter_deck(get_card_catalog())


@pytest.fixture
def decks(deck: Deck) -> FakePlayerDeckSource:
    return FakePlayerDeckSource({(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(deck)})


@pytest.fixture
def queue() -> FakeMatchmakingQueue:
    return FakeMatchmakingQueue()


def consumer(
    queue: FakeMatchmakingQueue,
    decks: FakePlayerDeckSource,
    user_id: int = PLAYER_ONE,
) -> RecordingConsumer:
    """O consumer com as dependências do teste, sem passar pelo socket."""
    clock = FakeWallClock()
    built = RecordingConsumer(
        queue=cast(MatchmakingQueue, queue),
        matches=cast(MatchStore, FakeMatchStore(clock)),
        decks=decks,
        catalog=get_card_catalog(),
        randomness=ScriptedRandomSource(),
        clock=clock,
    )
    built.sent = []
    built.user = cast(AbstractBaseUser, FakePlayerUser(user_id))
    built.channel_layer = get_channel_layer()

    return built


# --- Conectar não entra mais na fila ----------------------------------------


async def test_connecting_no_longer_joins_the_queue(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    """A quebra deliberada de protocolo da feature 011."""
    await consumer(queue, decks).on_connect()

    assert await queue.size() == 0


# --- As quatro recusas ------------------------------------------------------


async def test_joining_without_a_deck_is_refused(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    socket = consumer(queue, decks)

    await socket.handle_join_queue({})

    assert socket.last["type"] == "message_refused"
    assert socket.last_payload["code"] == "deck_not_specified"


async def test_a_deck_id_that_is_not_an_integer_is_refused(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": "quatro"})

    assert socket.last_payload["code"] == "deck_not_specified"


async def test_a_deck_that_exists_for_nobody_is_refused(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": NOBODYS_DECK_ID})

    assert socket.last_payload["code"] == "deck_not_found"


async def test_someone_elses_deck_gets_the_very_same_refusal(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource, deck: Deck
) -> None:
    """Nada na recusa confirma que o deck de outro jogador existe.

    A comparação é entre **dois mundos** com o mesmo pedido: num deles o deck
    1 existe e é de outro jogador, no outro ele não existe para ninguém. Mesmo
    autor, mesmo `deck_id`, e a resposta tem de ser idêntica byte a byte --
    comparar dois `deck_id` diferentes provaria menos, porque a recusa ecoa o
    identificador pedido.
    """
    with_someone_elses = consumer(queue, decks, user_id=PLAYER_TWO)
    with_nothing = consumer(queue, FakePlayerDeckSource(), user_id=PLAYER_TWO)

    await with_someone_elses.handle_join_queue({"deck_id": THEIR_DECK_ID})
    await with_nothing.handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert with_someone_elses.last_payload["code"] == "deck_not_found"
    assert with_someone_elses.last_payload == with_nothing.last_payload


async def test_a_deck_that_stopped_being_valid_is_refused_naming_the_problem(
    queue: FakeMatchmakingQueue, deck: Deck
) -> None:
    """Um deck salvo ontem pode citar uma carta que saiu do catálogo hoje."""
    gone = CardId(9999)
    decks = FakePlayerDeckSource(
        {(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(tuple(deck[:-1]) + (gone,))}
    )
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert socket.last_payload["code"] == "invalid_deck"
    assert f"card_id {gone} is not in the catalog" in str(socket.last_payload["error"])


async def test_a_fourth_copy_is_named_with_its_count(
    queue: FakeMatchmakingQueue, deck: Deck
) -> None:
    """A recusa nomeia a carta e a contagem, não um "deck inválido" genérico."""
    over_the_limit = tuple(deck[:-1]) + (deck[0],)
    decks = FakePlayerDeckSource(
        {(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(over_the_limit)}
    )
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": THEIR_DECK_ID})

    problems = socket.last_payload["deck_problems"]
    assert isinstance(problems, list)
    assert problems[0]["kind"] == "too_many_copies"
    assert problems[0]["card_id"] == int(deck[0])
    assert problems[0]["count"] == 4
    assert problems[0]["limit"] == 3


async def test_every_problem_comes_out_at_once(
    queue: FakeMatchmakingQueue, deck: Deck
) -> None:
    broken = tuple(deck[:37]) + (deck[0], CardId(9999))
    decks = FakePlayerDeckSource(
        {(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(broken)}
    )
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": THEIR_DECK_ID})

    problems = socket.last_payload["deck_problems"]
    assert isinstance(problems, list)
    assert {problem["kind"] for problem in problems} == {
        "wrong_deck_size",
        "too_many_copies",
        "unknown_card",
    }


# --- A ordem: recusa antes da fila ------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [{}, {"deck_id": "quatro"}, {"deck_id": NOBODYS_DECK_ID}],
)
async def test_a_refused_player_never_takes_a_place_in_the_queue(
    queue: FakeMatchmakingQueue,
    decks: FakePlayerDeckSource,
    payload: dict[str, object],
) -> None:
    """Nenhuma recusa acontece depois da chamada à fila."""
    await consumer(queue, decks).handle_join_queue(payload)

    assert await queue.size() == 0


async def test_an_invalid_deck_never_takes_a_place_in_the_queue(
    queue: FakeMatchmakingQueue, deck: Deck
) -> None:
    decks = FakePlayerDeckSource(
        {(PLAYER_ONE, THEIR_DECK_ID): fake_chosen_deck(tuple(deck[:12]))}
    )

    await consumer(queue, decks).handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert await queue.size() == 0


async def test_the_refusal_does_not_close_the_socket(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    """O cliente corrige e tenta de novo, sem reconectar."""
    socket = consumer(queue, decks)

    await socket.handle_join_queue({"deck_id": NOBODYS_DECK_ID})
    await socket.handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert await queue.size() == 1


# --- A entrada aceita -------------------------------------------------------


async def test_a_valid_deck_takes_a_place_in_the_queue(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource, deck: Deck
) -> None:
    await consumer(queue, decks).handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert await queue.size() == 1
    assert queue.waiting[0] == QueueEntry(
        user_id=PLAYER_ONE, deck=fake_chosen_deck(deck)
    )


async def test_the_deck_is_asked_for_by_its_owner(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    """O consumer pergunta por `(autor, deck_id)`, nunca por `deck_id` solto --
    é isso que faz deck alheio e deck inexistente saírem pelo mesmo caminho."""
    await consumer(queue, decks).handle_join_queue({"deck_id": THEIR_DECK_ID})

    assert decks.asked == [(PLAYER_ONE, THEIR_DECK_ID)]


async def test_leaving_takes_the_entry_out(
    queue: FakeMatchmakingQueue, decks: FakePlayerDeckSource
) -> None:
    socket = consumer(queue, decks)
    await socket.handle_join_queue({"deck_id": THEIR_DECK_ID})

    await socket.on_disconnect(1000)

    assert await queue.size() == 0
