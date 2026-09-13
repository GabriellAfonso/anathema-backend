"""O socket da fila: entrar dizendo o deck, parear, e abrir a partida.

Conectar **não** entra na fila. O cliente manda `join_queue` com o `deck_id`, e
é ali que o deck é conferido e validado. Uma mensagem em vez do `connect` dá as
duas coisas de que a feature 011 precisa: o deck viajando na entrada, e a
recusa sem fechar o socket -- o cliente corrige e tenta de novo, sem reconectar.

**Toda recusa acontece antes de chamar a fila.** Recusar no pareamento faria o
oponente perder o tempo de fila dele por um problema que não é dele, e o par já
teria sido consumido.

O contrato está em
`specs/011-deck-catalog-api/contracts/matchmaking_messages.md`.
"""

import json
import logging
from typing import cast

from apps.game.cards import CardCatalog, DeckProblem, deck_problems, get_card_catalog
from apps.game.engine import InvalidPlayerDeckError, MatchEntry, start_match
from apps.game.match import Match
from apps.game.match.client import get_match_store
from apps.game.match.store import MatchStore
from apps.game.matchmaking.client import get_matchmaking_queue
from apps.game.matchmaking.queue import MatchmakingQueue, QueueEntry
from apps.game.protocol import (
    DECK_NOT_FOUND,
    DECK_NOT_SPECIFIED,
    INVALID_DECK,
    opening_match_clock,
)
from apps.game.randomness import (
    RandomSource,
    SeededRandomSource,
    new_random_seed,
)
from apps.game.wall_clock import SystemWallClock, WallClock
from apps.players.services.deck_problem_payload import deck_problems_payload
from apps.players.services.deck_queries import (
    DatabasePlayerDeckSource,
    PlayerDeckSource,
)
from apps.players.services.player_queries import PlayerData, get_player_public_data

from .base import BaseConsumer, ClientEventMessage

logger = logging.getLogger(__name__)


def deck_id_in(payload: object) -> int | None:
    """O `deck_id` da mensagem, ou `None` se ele não veio como inteiro.

    `bool` é subclasse de `int` em Python, e `{"deck_id": true}` não é um
    identificador -- por isso a exclusão explícita.

    >>> deck_id_in({"deck_id": 4})
    4
    """
    if not isinstance(payload, dict):
        return None

    deck_id = payload.get("deck_id")

    if isinstance(deck_id, bool) or not isinstance(deck_id, int):
        return None

    return deck_id


class MatchmakingConsumer(BaseConsumer):
    group_prefix = "matchmaking"

    def __init__(
        self,
        *args: object,
        queue: MatchmakingQueue | None = None,
        matches: MatchStore | None = None,
        decks: PlayerDeckSource | None = None,
        catalog: CardCatalog | None = None,
        randomness: RandomSource | None = None,
        clock: WallClock | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire all six with MatchmakingConsumer.as_asgi(queue=..., matches=...,
        # decks=..., catalog=..., randomness=..., clock=...).
        self.queue = queue or get_matchmaking_queue()
        self.matches = matches or get_match_store()
        self.decks = decks or DatabasePlayerDeckSource()
        self.catalog = catalog or get_card_catalog()
        # `SeededRandomSource` não guarda estado entre chamadas -- a semente e
        # o ordinal vêm da partida --, então uma instância por consumer não
        # custa nada e não compartilha nada.
        self.randomness = randomness or SeededRandomSource()
        self.clock = clock or SystemWallClock()

    async def on_connect(self) -> None:
        """Socket aberto, e fora da fila.

        Até a feature 011 conectar entrava na fila sozinho. Não dá mais: a
        entrada exige dizer o deck, e o cliente diz pelo `join_queue`.
        """

    async def on_disconnect(self, code: int) -> None:
        await self.queue.leave(self.user_id)

    async def handle_join_queue(self, payload: object) -> None:
        """Entra na fila com o deck informado, ou recusa antes de entrar.

        As três perguntas vêm nesta ordem, e todas antes da fila: o campo veio?
        o deck é deste jogador? ele passa nas três regras?

        >>> await consumer.handle_join_queue({"deck_id": 4})
        """
        deck_id = deck_id_in(payload)

        if deck_id is None:
            await self.refuse_join(
                DECK_NOT_SPECIFIED,
                f"payload is {payload!r}: expected {{'deck_id': <int>}}",
            )
            return

        await self.join_with_deck(deck_id)

    async def join_with_deck(self, deck_id: int) -> None:
        """Busca o deck **do autor**, valida, e só então ocupa lugar na fila."""
        deck = await self.decks.deck_for(user_id=self.user_id, deck_id=deck_id)

        if deck is None:
            await self.refuse_join(
                DECK_NOT_FOUND,
                f"deck_id {deck_id} is not a deck of user {self.user_id}",
                deck_id=deck_id,
            )
            return

        problems = deck_problems(deck.card_ids, self.catalog)

        if problems:
            await self.refuse_invalid_deck(deck_id, problems)
            return

        await self.enter_queue(QueueEntry(user_id=self.user_id, deck=deck))

    async def enter_queue(self, entry: QueueEntry) -> None:
        """Ocupa lugar na fila; abre a partida se essa entrada fechou um par.

        A lista que entra aqui é a que a partida vai usar: o pareamento não
        relê o deck, então editá-lo ou apagá-lo daqui em diante não muda nada.
        """
        pair = await self.queue.join(entry)

        if not pair:
            return

        await self.open_match_for(pair)

    async def open_match_for(self, pair: tuple[QueueEntry, QueueEntry]) -> None:
        """Resolve os perfis dos dois pareados e abre a partida."""
        first = await self.match_entry_for(pair[0])
        second = await self.match_entry_for(pair[1])

        if first is None or second is None:
            await self.send_error(
                "matchmaking_failed",
                f"no profile for one of the paired users "
                f"{(pair[0].user_id, pair[1].user_id)}",
            )
            return

        await self.open_match(first, second)

    async def match_entry_for(self, entry: QueueEntry) -> MatchEntry | None:
        """Perfil e deck juntos, ou `None` se o jogador não tem perfil.

        O deck vem da entrada na fila, e **não** de nova consulta: é aqui que
        se vê que o pareamento não relê nada.
        """
        profile = await self.profile_for(entry.user_id)

        if profile is None:
            return None

        return MatchEntry(profile=profile, deck=entry.deck)

    async def profile_for(self, user_id: int) -> PlayerData | None:
        """Os dados públicos do jogador, para o `match_found`.

        Método próprio para ser a única linha deste consumer que toca o banco
        no pareamento -- os testes de socket a substituem e continuam fora do
        banco, como o `conftest.py` de `apps/game/tests` exige.

        O `cast` existe porque `database_sync_to_async` chega sem stubs e
        devolve `Any`; a função embrulhada é tipada.
        """
        return cast(PlayerData | None, await get_player_public_data(user_id))

    async def open_match(self, first: MatchEntry, second: MatchEntry) -> None:
        """Roda o setup da §3 até a espera do mulligan, grava e avisa os dois.

        Deck recusado não deixa partida nascer, então o aviso de falha sai
        antes de qualquer gravação: não existe partida meio-criada no Redis.
        """
        try:
            match = self.start_match_for(first, second)
        except InvalidPlayerDeckError as refused:
            await self.send_error("matchmaking_failed", str(refused))
            return

        # O prazo do mulligan conta da criação, e não da conexão de cada um: o
        # relógio da §15 não pode depender de socket aberto, e é agora que o
        # `match_found` sai para os dois.
        #
        # `started_at` é escrito aqui, na mesma linha, e não dentro de
        # `start_match`: o motor não lê tempo (§15), e `test_engine_reads_no_time`
        # reprova quem tentar. É daqui que sai a duração no registro do
        # resultado (feature 012).
        created_at = self.clock.now_ms()
        match.started_at = created_at
        match.clock = opening_match_clock(created_at)

        await self.matches.save(match)

        await self.announce_match(match, first.profile, second.profile)
        await self.announce_match(match, second.profile, first.profile)

    def start_match_for(self, first: MatchEntry, second: MatchEntry) -> Match:
        """Executa o setup com os dois decks de verdade. Síncrono: não toca I/O.

        Até a feature 011 havia aqui um `deck_for` que dava o mesmo deck a todo
        jogador. Ele saiu; o setup não mudou em nada.
        """
        return start_match(
            first,
            second,
            catalog=self.catalog,
            randomness=self.randomness,
            seed=new_random_seed(),
        )

    async def refuse_join(self, code: str, message: str, **details: object) -> None:
        """Recusa a entrada na fila sem fechar o socket, e registra o motivo.

        O jogador não ocupou lugar nenhum: as três guardas rodam antes da fila.
        """
        logger.info(
            json.dumps(
                {
                    "event": "join_queue_refused",
                    "user_id": self.user_id,
                    "code": code,
                    **details,
                }
            )
        )

        await self.send_refusal(code, message, **details)

    async def refuse_invalid_deck(
        self, deck_id: int, problems: tuple[DeckProblem, ...]
    ) -> None:
        """Recusa nomeando **cada** problema, todos de uma vez.

        A tradução é a mesma do HTTP, para que a recusa saia igual nos dois
        transportes.
        """
        await self.refuse_join(
            INVALID_DECK,
            "; ".join(problem.message for problem in problems),
            deck_id=deck_id,
            deck_problems=deck_problems_payload(problems),
        )

    async def announce_match(
        self, match: Match, player: PlayerData, opponent: PlayerData
    ) -> None:
        """Avisa um jogador do pareamento, do ponto de vista dele."""
        message: ClientEventMessage = {
            "type": "client_event",
            "event": "match_found",
            "payload": {
                "self": player,
                "opponent": opponent,
                "match_id": match.match_id,
            },
        }

        await self.channel_layer.group_send(self.user_group(player["user_id"]), message)
