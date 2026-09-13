"""A partida usa o deck que foi validado, não o deck de agora.

O par fecha depois da entrada, possivelmente em outro worker. Se o deck fosse
relido no pareamento, uma edição entre o `join_queue` e o par produziria uma
partida diferente da que foi validada -- ou nenhuma, se o deck tivesse sido
apagado. É a razão de `QueueEntry` carregar a lista.

O teste edita e apaga o deck **na fonte** entre as duas entradas, que é
exatamente o que o jogador faria pelo HTTP naquele intervalo.
"""

from collections.abc import Mapping
from typing import cast

import pytest
from channels.layers import get_channel_layer
from django.contrib.auth.base_user import AbstractBaseUser

from apps.game.cards import CardId, Deck, get_card_catalog, starter_deck
from apps.game.consumers.matchmaking import MatchmakingConsumer
from apps.game.match.store import MatchStore
from apps.game.matchmaking.queue import MatchmakingQueue
from apps.players.services.player_queries import PlayerData
from apps.game.tests.fake_match_store import FakeMatchStore
from apps.game.tests.fake_matchmaking_queue import FakeMatchmakingQueue
from apps.game.tests.fake_chosen_deck import fake_chosen_deck
from apps.game.tests.fake_player_deck_source import FakePlayerDeckSource
from apps.game.tests.fake_player_data import fake_player_data
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_users import FakePlayerUser
from apps.game.tests.fake_wall_clock import FakeWallClock

PLAYER_ONE = 7
PLAYER_TWO = 9
DECK_ID = 1


class SilentConsumer(MatchmakingConsumer):
    """Não manda nada, e não vai ao banco pelo perfil.

    Só o perfil é substituído. O caminho do deck -- da entrada na fila até o
    `MatchEntry` -- fica o de produção, que é justamente o que está sob teste:
    um `match_entry_for` de mentira faria este arquivo passar mesmo se o deck
    da entrada fosse descartado.
    """

    async def send_event(
        self, *, type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        return None

    async def profile_for(self, user_id: int) -> PlayerData:
        return fake_player_data(user_id, f"player-{user_id}")


@pytest.fixture
def deck() -> Deck:
    return starter_deck(get_card_catalog())


@pytest.fixture
def decks(deck: Deck) -> FakePlayerDeckSource:
    return FakePlayerDeckSource(
        {
            (PLAYER_ONE, DECK_ID): fake_chosen_deck(deck),
            (PLAYER_TWO, DECK_ID): fake_chosen_deck(deck),
        }
    )


@pytest.fixture
def queue() -> FakeMatchmakingQueue:
    return FakeMatchmakingQueue()


@pytest.fixture
def matches() -> FakeMatchStore:
    return FakeMatchStore(FakeWallClock())


def consumer(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
    user_id: int,
) -> SilentConsumer:
    built = SilentConsumer(
        queue=cast(MatchmakingQueue, queue),
        matches=cast(MatchStore, matches),
        decks=decks,
        catalog=get_card_catalog(),
        randomness=ScriptedRandomSource(),
        clock=FakeWallClock(),
    )
    built.user = cast(AbstractBaseUser, FakePlayerUser(user_id))
    built.channel_layer = get_channel_layer()

    return built


def decks_in_play(matches: FakeMatchStore) -> dict[int, list[int]]:
    """Que cartas cada jogador levou para a partida gravada.

    Soma mão, deck restante e cemitério: o setup da §3 compra 4 antes de o
    documento existir, e é o total que precisa bater com a lista validada.
    """
    saved = list(matches.matches.values())
    assert len(saved) == 1, f"esperava uma partida gravada, achei {len(saved)}"

    match = saved[0].match

    return {
        player.user_id: sorted(
            [card.card_id for card in player.hand]
            + [card.card_id for card in player.deck]
            + [card.card_id for card in player.graveyard]
        )
        for player in match.players
    }


async def join(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
    user_id: int,
) -> None:
    await consumer(queue, matches, decks, user_id).handle_join_queue(
        {"deck_id": DECK_ID}
    )


async def test_the_match_uses_the_list_validated_on_the_way_in(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
    deck: Deck,
) -> None:
    """O jogador troca todas as cartas depois de entrar, e antes do par."""
    await join(queue, matches, decks, PLAYER_ONE)

    replacement = fake_chosen_deck(tuple(CardId(1) for _ in deck))
    decks.give(user_id=PLAYER_ONE, deck_id=DECK_ID, deck=replacement)
    await join(queue, matches, decks, PLAYER_TWO)

    assert decks_in_play(matches)[PLAYER_ONE] == sorted(deck)


async def test_deleting_the_deck_before_the_pair_still_makes_the_match(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
    deck: Deck,
) -> None:
    """Apagar o deck com que se está na fila não impede o par."""
    await join(queue, matches, decks, PLAYER_ONE)

    decks.take(user_id=PLAYER_ONE, deck_id=DECK_ID)
    await join(queue, matches, decks, PLAYER_TWO)

    assert decks_in_play(matches)[PLAYER_ONE] == sorted(deck)


async def test_the_deck_is_read_once_per_join_and_never_again(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
) -> None:
    """Uma leitura por entrada, nenhuma no pareamento.

    É a asserção que quebra se alguém reintroduzir uma consulta ao banco no
    momento do par -- a janela que a `QueueEntry` existe para fechar.
    """
    await join(queue, matches, decks, PLAYER_ONE)
    await join(queue, matches, decks, PLAYER_TWO)

    assert decks.asked == [(PLAYER_ONE, DECK_ID), (PLAYER_TWO, DECK_ID)]


async def test_each_player_keeps_their_own_list(
    queue: FakeMatchmakingQueue,
    matches: FakeMatchStore,
    decks: FakePlayerDeckSource,
    deck: Deck,
) -> None:
    """Os dois decks não se trocam de dono no caminho da fila até o setup."""
    reversed_deck = fake_chosen_deck(tuple(reversed(deck)))
    decks.give(user_id=PLAYER_TWO, deck_id=DECK_ID, deck=reversed_deck)

    await join(queue, matches, decks, PLAYER_ONE)
    await join(queue, matches, decks, PLAYER_TWO)

    in_play = decks_in_play(matches)

    assert in_play[PLAYER_ONE] == sorted(deck)
    assert in_play[PLAYER_TWO] == sorted(reversed_deck.card_ids)
