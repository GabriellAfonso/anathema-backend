import json
import logging
from copy import deepcopy
from typing import TypedDict
from urllib.parse import parse_qs

from apps.game.cards import CardCatalog, mvp_catalog
from apps.game.match import Match
from apps.game.match.client import get_match_store
from apps.game.match.store import (
    ConcurrentMatchWriteError,
    MatchNotFoundError,
    MatchStore,
    StoredMatch,
)
from apps.game.protocol import (
    ClientCommand,
    MalformedMessageError,
    MatchUpdatePayload,
    apply_command,
    match_start_payload,
    match_update_payload,
    parse_client_message,
    refusal_codes,
    refusal_for,
)
from apps.game.randomness import RandomSource, SeededRandomSource

from .base import BaseConsumer

# Close codes in the private 4000-4999 range, mirroring HTTP: 4001 is the auth
# gate in BaseConsumer, so the match gate continues the 44xx series.
MATCH_ID_MISSING = 4400
NOT_A_PARTICIPANT = 4403
MATCH_NOT_FOUND = 4404

logger = logging.getLogger(__name__)


class MatchUpdateMessage(TypedDict):
    """Mensagem de channel layer que leva o frame **já montado** para um jogador.

    Vai ao grupo de usuário dele, nunca ao grupo da partida: o payload contém a
    mão do destinatário. `match_id` deixa o socket de outra partida do mesmo
    usuário ignorá-la.
    """

    type: str
    match_id: str
    payload: MatchUpdatePayload


class RecordedChange:
    """A mutação do comando, e a partida de antes da tentativa que valeu.

    `MatchStore.mutate` pode reaplicar a mudança sobre uma leitura fresca quando
    outro worker escreveu no meio. Cada tentativa sobrescreve `before`, então o
    que sobra quando `mutate` devolve é o antes da tentativa gravada -- e é dele
    que a descrição do que aconteceu precisa (FR-037).
    """

    def __init__(
        self, command: ClientCommand, catalog: CardCatalog, randomness: RandomSource
    ) -> None:
        self.command = command
        self.catalog = catalog
        self.randomness = randomness
        self.before: Match | None = None

    def recorded_before(self) -> Match:
        """A partida de antes da tentativa gravada.

        Recusa nomeada em vez de `assert` -- que some com `-O` -- para o caso
        impossível de `mutate` devolver sem ter chamado a mudança.
        """
        if self.before is None:
            raise RuntimeError(
                f"no state recorded for {self.command!r}: expected mutate to run the change"
            )

        return self.before

    def __call__(self, match: Match) -> None:
        self.before = deepcopy(match)
        apply_command(
            match, self.command, catalog=self.catalog, randomness=self.randomness
        )


class MatchConsumer(BaseConsumer):
    group_prefix = "match"

    match_id: str | None = None

    def __init__(
        self,
        *args: object,
        matches: MatchStore | None = None,
        catalog: CardCatalog | None = None,
        randomness: RandomSource | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Channels passes as_asgi(**initkwargs) through to __init__, so tests
        # wire all three with MatchConsumer.as_asgi(matches=..., catalog=...,
        # randomness=...).
        self.matches = matches or get_match_store()
        self.catalog = catalog or mvp_catalog()
        self.randomness = randomness or SeededRandomSource()

    async def on_connect(self) -> None:
        """Só deixa entrar quem joga a partida pedida."""
        match_id = self.get_match_id()

        if not match_id:
            await self.reject(MATCH_ID_MISSING, "expected ?matchId=<uuid>, got none")
            return

        stored = await self.matches.get_stored(match_id)

        if stored is None:
            await self.reject(MATCH_NOT_FOUND, f"no live match {match_id!r}")
            return

        if not stored.match.has_player(self.user_id):
            await self.reject(
                NOT_A_PARTICIPANT,
                f"user {self.user_id} does not play match {match_id!r}",
            )
            return

        await self.join_match(stored)

    async def join_match(self, stored: StoredMatch) -> None:
        """Entra no grupo da partida e abre o socket com o estado atual.

        Guarda só o `match_id`. A partida em si é lida de novo a cada jogada:
        um estado guardado pela conexão envelheceria assim que o outro jogador
        agisse, e avaliar jogada contra ele perderia escrita (FR-007).
        """
        self.match_id = stored.match.match_id

        await self.channel_layer.group_add(
            self.match_group(self.match_id),
            self.channel_name,
        )
        await self.send_match_start(stored)

    async def on_disconnect(self, code: int) -> None:
        """Sai do grupo da partida.

        `self.match_id` é None num socket que os gates recusaram: ele foi aceito
        para receber o motivo, então chega aqui sem nunca ter entrado no
        grupo, e o discard não teria o que desfazer.
        """
        if self.match_id is None:
            return

        await self.channel_layer.group_discard(
            self.match_group(self.match_id),
            self.channel_name,
        )

    @classmethod
    def match_group(cls, match_id: str) -> str:
        """Grupo que endereça todos os sockets de uma mesma partida.

        Outro eixo do `user_group` do BaseConsumer: aquele endereça os sockets
        de um usuário, este os dois lados de uma partida. **Não** recebe frame
        com visão: a visão de um jogador contém a mão dele, e o grupo da partida
        entregaria essa mão ao outro. Atualização vai ao grupo de usuário.

        >>> MatchConsumer.match_group("m-1")
        'match.match.m-1'
        """
        return f"{cls.group_prefix}.match.{match_id}"

    async def send_match_start(self, stored: StoredMatch) -> None:
        """Abre o socket com a partida como ela está agora, e a versão dela.

        É isto que torna a reconexão possível: reconectar é literalmente
        conectar de novo, e o estado chega no mesmo frame de sempre. A versão
        deixa o cliente descartar uma atualização em trânsito que seja mais
        velha que este estado. O `MatchStore` guarda a partida no Redis por 6h,
        então ela sobrevive à queda.
        """
        await self.send_event(
            type="match_start",
            payload=match_start_payload(stored.match, stored.version, self.user_id),
        )

    async def receive_json(self, content: dict[str, object], **kwargs: object) -> None:
        """Uma mensagem do cliente: forma, motor, gravação e distribuição.

        Não passa pelo roteamento `handle_<type>` do BaseConsumer: a forma de
        cada tipo é do `protocol`, que conhece o conjunto inteiro e recusa o
        que não reconhece.
        """
        if self.match_id is None:
            return

        try:
            command = parse_client_message(content, author_user_id=self.user_id)
        except MalformedMessageError as refused:
            await self.send_refusal(refused.code, str(refused))
            return

        await self.play(self.match_id, command, content)

    async def play(
        self, match_id: str, command: ClientCommand, content: dict[str, object]
    ) -> None:
        """Aplica o comando dentro do compare-and-swap e distribui o resultado.

        Toda falha vira recusa só para este socket, e nenhuma fecha a conexão.
        """
        change = RecordedChange(command, self.catalog, self.randomness)

        try:
            stored = await self.matches.mutate(match_id, change)
        except Exception as failure:
            await self.refuse_failure(failure, match_id, content)
            return

        await self.broadcast_update(change.recorded_before(), stored, command)

    async def refuse_failure(
        self, failure: Exception, match_id: str, content: dict[str, object]
    ) -> None:
        """Traduz a falha de uma jogada na recusa que o cliente recebe.

        Recusa de regra leva o código do catálogo; partida expirada e disputa
        sem convergência têm código próprio; qualquer outra coisa é
        `internal_error`, com mensagem genérica e o detalhe só no log.
        """
        refusal = refusal_for(failure)

        if refusal is not None:
            await self.send_refusal(refusal.code, refusal.message)
            return

        if isinstance(failure, MatchNotFoundError):
            await self.send_refusal(refusal_codes.MATCH_NOT_FOUND, str(failure))
            return

        self.log_failure(failure, match_id, content)

        if isinstance(failure, ConcurrentMatchWriteError):
            await self.send_refusal(refusal_codes.CONCURRENT_MATCH_WRITE, str(failure))
            return

        await self.send_refusal(
            refusal_codes.INTERNAL_ERROR, "the server failed to process the message"
        )

    def log_failure(
        self, failure: Exception, match_id: str, content: dict[str, object]
    ) -> None:
        """Falha do servidor, em JSON estruturado, com o traceback."""
        logger.error(
            json.dumps(
                {
                    "event": "match_message_failed",
                    "match_id": match_id,
                    "user_id": self.user_id,
                    "message_type": str(content.get("type")),
                    "error": type(failure).__name__,
                }
            ),
            exc_info=failure,
        )

    async def broadcast_update(
        self, before: Match, stored: StoredMatch, command: ClientCommand
    ) -> None:
        """Um frame por jogador, montado para ele, ao grupo de usuário dele.

        Nunca ao grupo da partida: o frame de um contém a mão dele. Todo socket
        do jogador naquela partida recebe, inclusive o que mandou -- a
        atualização é a confirmação da jogada.
        """
        for player in stored.match.players:
            message: MatchUpdateMessage = {
                "type": "match.update",
                "match_id": stored.match.match_id,
                "payload": match_update_payload(
                    before, stored.match, stored.version, command, player.user_id
                ),
            }
            await self.channel_layer.group_send(
                self.user_group(player.user_id), message
            )

    async def match_update(self, message: MatchUpdateMessage) -> None:
        """Channel-layer handler: encaminha a atualização desta partida.

        O grupo de usuário é de todos os sockets de partida do usuário; um
        socket velho de outra partida ignora a mensagem.
        """
        if message["match_id"] != self.match_id:
            return

        await self.send_event(type="match_update", payload=message["payload"])

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
