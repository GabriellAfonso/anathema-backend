from urllib.parse import parse_qs

from apps.game.match import Match, build_player_view
from apps.game.match.client import get_match_store
from apps.game.match.store import MatchStore

from .base import BaseConsumer

# Close codes in the private 4000-4999 range, mirroring HTTP: 4001 is the auth
# gate in BaseConsumer, so the match gate continues the 44xx series.
MATCH_ID_MISSING = 4400
NOT_A_PARTICIPANT = 4403
MATCH_NOT_FOUND = 4404


class MatchConsumer(BaseConsumer):
    group_prefix = "match"

    match: Match | None = None

    def __init__(
        self, *args: object, matches: MatchStore | None = None, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire a store with MatchConsumer.as_asgi(matches=...).
        self.matches = matches or get_match_store()

    async def on_connect(self) -> None:
        """Só deixa entrar quem joga a partida pedida."""
        match_id = self.get_match_id()

        if not match_id:
            await self.reject(MATCH_ID_MISSING, "expected ?matchId=<uuid>, got none")
            return

        match = await self.matches.get(match_id)

        if match is None:
            await self.reject(MATCH_NOT_FOUND, f"no live match {match_id!r}")
            return

        if not match.has_player(self.user_id):
            await self.reject(
                NOT_A_PARTICIPANT,
                f"user {self.user_id} does not play match {match_id!r}",
            )
            return

        self.match = match

        await self.channel_layer.group_add(
            self.match_group(match_id),
            self.channel_name,
        )
        await self.send_match_start(match)

    async def on_disconnect(self, code: int) -> None:
        """Sai do grupo da partida.

        `self.match` é None num socket que os gates recusaram: ele foi aceito
        para receber o motivo, então chega aqui sem nunca ter entrado no
        grupo, e o discard não teria o que desfazer.
        """
        if self.match is None:
            return

        await self.channel_layer.group_discard(
            self.match_group(self.match.match_id),
            self.channel_name,
        )

    @classmethod
    def match_group(cls, match_id: str) -> str:
        """Grupo que endereça todos os sockets de uma mesma partida.

        Outro eixo do `user_group` do BaseConsumer: aquele endereça os sockets
        de um usuário, este os dois lados de uma partida. Sem ele a jogada de
        um jogador não teria por onde chegar ao outro.

        >>> MatchConsumer.match_group("m-1")
        'match.match.m-1'
        """
        return f"{cls.group_prefix}.match.{match_id}"

    async def send_match_start(self, match: Match) -> None:
        """Abre o socket com a partida como ela está agora.

        É isto que torna a reconexão possível: reconectar é literalmente
        conectar de novo, e o estado chega no mesmo frame de sempre. Por isso
        não existe mensagem `resync` nem versionamento -- o `MatchStore`
        guarda a partida no Redis por 6h, então ela sobrevive à queda.
        """
        await self.send_event(
            type="match_start",
            payload=build_player_view(match, self.user_id),
        )

    def get_match_id(self) -> str | None:
        query_string: str = self.scope["query_string"].decode()
        match_ids = parse_qs(query_string).get("matchId")

        return match_ids[0] if match_ids else None

    async def reject(self, code: int, reason: str) -> None:
        """Fecha com o motivo legível antes do código.

        O close vem depois do accept de propósito: um close antes do handshake
        chega ao browser como 1006, sem código nem texto.
        """
        await self.send_error("match_denied", reason)
        await self.close(code=code)
