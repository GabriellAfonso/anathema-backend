from apps.game.cards import CardCatalog, Deck, mvp_catalog, starter_deck
from apps.game.engine import InvalidPlayerDeckError, MatchEntry, start_match
from apps.game.match import Match
from apps.game.match.client import get_match_store
from apps.game.match.store import MatchStore
from apps.game.matchmaking.client import get_matchmaking_queue
from apps.game.matchmaking.queue import MatchmakingQueue
from apps.game.randomness import (
    RandomSource,
    SeededRandomSource,
    new_random_seed,
)
from apps.players.services.player_queries import PlayerData, get_player_public_data

from .base import BaseConsumer, ClientEventMessage


class MatchmakingConsumer(BaseConsumer):
    group_prefix = "matchmaking"

    def __init__(
        self,
        *args: object,
        queue: MatchmakingQueue | None = None,
        matches: MatchStore | None = None,
        catalog: CardCatalog | None = None,
        randomness: RandomSource | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire all four with MatchmakingConsumer.as_asgi(queue=..., matches=...,
        # catalog=..., randomness=...).
        self.queue = queue or get_matchmaking_queue()
        self.matches = matches or get_match_store()
        self.catalog = catalog or mvp_catalog()
        # `SeededRandomSource` não guarda estado entre chamadas -- a semente e
        # o ordinal vêm da partida --, então uma instância por consumer não
        # custa nada e não compartilha nada.
        self.randomness = randomness or SeededRandomSource()

    async def on_connect(self) -> None:
        await self.join_queue()

    async def on_disconnect(self, code: int) -> None:
        await self.queue.leave(self.user_id)

    async def join_queue(self) -> None:
        """Entra na fila; cria a partida se esse join fechou um par."""
        pair = await self.queue.join(self.user_id)

        if not pair:
            return

        player1 = await get_player_public_data(pair[0])
        player2 = await get_player_public_data(pair[1])

        if player1 is None or player2 is None:
            await self.send_error(
                "matchmaking_failed",
                f"no profile for one of the paired users {pair}",
            )
            return

        await self.open_match(player1, player2)

    async def open_match(self, player1: PlayerData, player2: PlayerData) -> None:
        """Roda o setup da §3 até a espera do mulligan, grava e avisa os dois.

        Deck recusado não deixa partida nascer, então o aviso de falha sai
        antes de qualquer gravação: não existe partida meio-criada no Redis.
        """
        try:
            match = self.start_match_for(player1, player2)
        except InvalidPlayerDeckError as refused:
            await self.send_error("matchmaking_failed", str(refused))
            return

        await self.matches.save(match)

        await self.announce_match(match, player1, player2)
        await self.announce_match(match, player2, player1)

    def start_match_for(self, player1: PlayerData, player2: PlayerData) -> Match:
        """Monta os dois lados e executa o setup. Síncrono: não toca I/O."""
        return start_match(
            MatchEntry(profile=player1, deck=self.deck_for(player1)),
            MatchEntry(profile=player2, deck=self.deck_for(player2)),
            catalog=self.catalog,
            randomness=self.randomness,
            seed=new_random_seed(),
        )

    def deck_for(self, player: PlayerData) -> Deck:
        """Andaime: todo jogador chega com o mesmo deck derivado do catálogo.

        Guardar deck de jogador em banco é outra feature; quando ela entrar, é
        esta função que some, e nada do setup muda.
        """
        return starter_deck(self.catalog)

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
