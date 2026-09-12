"""Partidas vivas no Redis, para todo worker do uvicorn ler a mesma.

O dict de classe que isto substitui vivia em um processo só: com `--workers 4`
a partida criada pelo worker do matchmaking era invisível para o worker onde o
socket de partida do jogador caía, e o gate de participante fecha isso com
4404.

Cada partida é um hash de dois campos: `state`, o documento JSON, e `version`,
quantas vezes a partida já foi escrita. A versão existe para o
compare-and-swap de `mutate` e, desde a feature 009, é também a posição de uma
mudança na sequência da partida que o cliente recebe -- ela cresce 1 a cada
escrita, em qualquer worker. Não é versão de esquema, que continua não
existindo, e por isso ela não mora dentro do documento.

O read-modify-write que este módulo registrava como adiado chegou com o
mulligan simultâneo da §3: duas conexões, possivelmente em workers diferentes,
mutam a mesma partida ao mesmo tempo. `mutate` resolve isso sem trava e sem
relógio -- ou a versão lida ainda é a que está lá, ou a mutação é reaplicada
sobre uma leitura fresca. É a peça que os caminhos de mutação das features de
gameplay reusam.

Desde a feature 010 cada escrita também mantém o **índice de despertar** da §15:
um sorted set com o `match_id` no membro e o próximo instante de relógio da
partida no score. Ele é atualizado dentro do mesmo script Lua que grava o
estado, e não numa chamada depois: um worker que morresse entre as duas deixaria
uma vez que nunca estoura. Quem consome o índice é `wake_queue.py`.

A mesma feature trouxe `renews_expiry`. Toda jogada de cliente renova o TTL de 6
horas; o estouro do relógio **não** renova. É isso que faz uma partida em que
ninguém joga sumir 6 horas depois da última jogada real, em vez de os próprios
estouros a manterem viva para sempre.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

from apps.game.wall_clock import EpochMillis

from .documents import MatchDocument
from .match_clock import clock_wake_at
from .match_state import Match
from .serialization import match_from_document, to_match_document

# Partida abandonada não pode ficar para sempre no Redis. Longo o bastante para
# um jogo lento ou uma reconexão nunca perderem o estado.
MATCH_TTL_SECONDS = 6 * 60 * 60

# Só existem dois escritores possíveis por partida -- os dois jogadores --,
# então a segunda tentativa já é o pior caso realista. A terceira é folga.
MUTATE_ATTEMPTS = 3

# Partida sem prazo nenhum sai do índice de despertar. Texto vazio e não 0
# porque 0 é um instante válido do ponto de vista do Redis, e este argumento
# atravessa o script como string de qualquer jeito.
NO_WAKE = ""

# TTL que manda o script **não** chamar `EXPIRE`. `HSET` numa chave existente
# preserva o tempo de vida que ela já tem, então o estouro do relógio grava sem
# adiar a expiração da partida.
KEEP_EXPIRY = 0

# Grava, renova o TTL e agenda o despertar, sem olhar quem escreveu antes. Para
# a criação, onde ninguém mais escreveu ainda.
#
# KEYS[1] = chave da partida; KEYS[2] = índice de despertar
# ARGV[1] = documento JSON; ARGV[2] = TTL em segundos
# ARGV[3] = match_id; ARGV[4] = instante do despertar, ou '' para tirar do índice
SAVE_SCRIPT = """
redis.call('HSET', KEYS[1], 'state', ARGV[1])
local version = redis.call('HINCRBY', KEYS[1], 'version', 1)
redis.call('EXPIRE', KEYS[1], ARGV[2])
if ARGV[4] == '' then
    redis.call('ZREM', KEYS[2], ARGV[3])
else
    redis.call('ZADD', KEYS[2], ARGV[4], ARGV[3])
end
return version
"""

# Compare-and-swap: grava só se a versão no Redis ainda for a que foi lida.
#
# Uma trava resolveria o mesmo problema, mas trava tem tempo de vida, e tempo
# de vida é uma segunda coisa a acertar -- curto demais e dois donos escrevem,
# longo demais e uma queda de worker congela a partida. Aqui não há relógio:
# ou a versão bate, ou não bate.
#
# Chave inexistente faz `HGET` devolver `false`, que nunca é igual a uma
# string, então a troca é recusada em vez de criar a partida do nada.
#
# Devolve a versão nova, ou 0 na recusa. A primeira escrita já é a versão 1,
# então 0 nunca é uma versão de verdade.
#
# O índice de despertar e o TTL só são tocados quando a troca é aceita: uma
# tentativa recusada não pode reagendar nada.
#
# KEYS[1] = chave da partida; KEYS[2] = índice de despertar
# ARGV[1] = versão esperada; ARGV[2] = documento JSON
# ARGV[3] = TTL em segundos, ou 0 para manter a expiração que a chave já tem
# ARGV[4] = match_id; ARGV[5] = instante do despertar, ou '' para tirar do índice
SWAP_SCRIPT = """
if redis.call('HGET', KEYS[1], 'version') ~= ARGV[1] then
    return 0
end
redis.call('HSET', KEYS[1], 'state', ARGV[2])
local version = redis.call('HINCRBY', KEYS[1], 'version', 1)
if ARGV[3] ~= '0' then
    redis.call('EXPIRE', KEYS[1], ARGV[3])
end
if ARGV[5] == '' then
    redis.call('ZREM', KEYS[2], ARGV[4])
else
    redis.call('ZADD', KEYS[2], ARGV[5], ARGV[4])
end
return version
"""

# A mutação recebe a partida carregada e a altera no lugar. Levantar de dentro
# dela aborta sem gravar nada, que é como uma recusa de mulligan deixa o
# estado intacto.
MatchChange = Callable[[Match], None]


@dataclass(frozen=True, slots=True)
class StoredMatch:
    """A partida e a versão de escrita em que ela foi lida ou gravada.

    >>> (await store.get_stored(match_id)).version
    3
    """

    match: Match
    version: int


class MatchNotFoundError(Exception):
    """Pediram para mutar uma partida que não existe ou já expirou."""

    def __init__(self, match_id: str) -> None:
        super().__init__(
            f"no live match {match_id!r}: expected a match saved within the "
            f"last {MATCH_TTL_SECONDS} seconds"
        )
        self.match_id = match_id


class ConcurrentMatchWriteError(Exception):
    """A partida mudou debaixo de tantas tentativas seguidas que desistimos.

    Com dois escritores possíveis isto não deveria acontecer; se acontecer, o
    que existe é uma mutação em laço, não uma disputa normal.
    """

    def __init__(self, match_id: str, attempts: int) -> None:
        super().__init__(
            f"match {match_id!r} changed under {attempts} consecutive write "
            f"attempts: expected at most {attempts - 1} competing writers"
        )
        self.match_id = match_id
        self.attempts = attempts


class MatchStore:
    """Partidas endereçadas por `match_id`. Cliente Redis injetado.

    Três operações, todas sobre bytes: ler, gravar e mutar. Criar partida é
    regra da §3 e mora em `apps.game.engine.start_match`.

    >>> store = MatchStore(Redis.from_url("redis://localhost:6379/3"))
    >>> await store.save(match)
    >>> (await store.get(match.match_id)).phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    """

    def __init__(self, redis: Redis, key_prefix: str = "match") -> None:
        self._redis = redis
        self._key_prefix = key_prefix
        self._wake_key = wake_index_key(key_prefix)
        self._save = redis.register_script(SAVE_SCRIPT)
        self._swap = redis.register_script(SWAP_SCRIPT)

    async def get(self, match_id: str) -> Match | None:
        """Partida pelo id, ou None se nunca existiu ou já expirou."""
        state = await self._redis.hget(self._key(match_id), "state")

        if state is None:
            return None

        return _match_from_state(state)

    async def get_stored(self, match_id: str) -> StoredMatch | None:
        """Partida e versão numa leitura só, ou None se não existe mais.

        É o que o socket de partida manda ao conectar: a versão deixa o cliente
        comparar o estado inicial com atualizações que já estavam em trânsito.
        """
        version, state = await self._redis.hmget(
            self._key(match_id), ["version", "state"]
        )

        if state is None or version is None:
            return None

        return StoredMatch(match=_match_from_state(state), version=int(version))

    async def save(self, match: Match) -> int:
        """Grava o estado, renova o TTL e agenda o despertar, sem olhar quem
        escreveu antes, e devolve a versão nova.

        Para a criação. Mutação de partida viva usa `mutate`, que não
        sobrescreve escrita alheia.
        """
        version = await self._save(
            keys=[self._key(match.match_id), self._wake_key],
            args=[
                _dump(match),
                MATCH_TTL_SECONDS,
                match.match_id,
                _wake_score(match),
            ],
        )

        return int(version)

    async def mutate(
        self, match_id: str, change: MatchChange, *, renews_expiry: bool = True
    ) -> StoredMatch:
        """Lê, aplica `change`, e grava só se ninguém escreveu no meio.

        Devolve a partida gravada e a versão que a gravação criou.

        Versão divergente significa que outro worker escreveu: relê e aplica
        `change` de novo, sobre o estado fresco. Reaplicar é seguro porque o
        ordinal do sorteio vem da partida recarregada, então a tentativa que
        vence nunca reusa um fluxo de aleatoriedade já gasto.

        `renews_expiry=False` grava sem adiar a expiração da partida: é o que o
        estouro do relógio usa, para que uma partida em que ninguém joga suma 6
        horas depois da última jogada **real** (§15, feature 010).

        >>> await store.mutate(
        ...     match_id,
        ...     lambda match: record_mulligan(match, 7, cards, randomness=src),
        ... )
        """
        for _ in range(MUTATE_ATTEMPTS):
            version, match = await self._read_versioned(match_id)
            change(match)
            written = await self._swap_state(
                match_id, version, match, renews_expiry=renews_expiry
            )

            if written:
                return StoredMatch(match=match, version=written)

        raise ConcurrentMatchWriteError(match_id, MUTATE_ATTEMPTS)

    async def _read_versioned(self, match_id: str) -> tuple[bytes | str, Match]:
        """Estado e versão numa leitura só: lê-los separado abriria uma janela
        entre os dois em que a versão deixaria de descrever aquele estado."""
        version, state = await self._redis.hmget(
            self._key(match_id), ["version", "state"]
        )

        if state is None or version is None:
            raise MatchNotFoundError(match_id)

        return version, _match_from_state(state)

    async def _swap_state(
        self,
        match_id: str,
        version: bytes | str,
        match: Match,
        *,
        renews_expiry: bool = True,
    ) -> int:
        """A versão nova, ou 0 se outra escrita chegou antes."""
        swapped = await self._swap(
            keys=[self._key(match_id), self._wake_key],
            args=[
                version,
                _dump(match),
                MATCH_TTL_SECONDS if renews_expiry else KEEP_EXPIRY,
                match_id,
                _wake_score(match),
            ],
        )

        return int(swapped)

    def _key(self, match_id: str) -> str:
        return f"{self._key_prefix}:{match_id}"


def wake_index_key(key_prefix: str) -> str:
    """A chave do índice de despertar daquele prefixo.

    Função e não constante porque os testes criam o store com um prefixo
    próprio, e o índice tem de acompanhar -- senão um teste varreria os
    despertares de outro.

    >>> wake_index_key("match")
    'match:wake'
    """
    return f"{key_prefix}:wake"


def _dump(match: Match) -> str:
    return json.dumps(to_match_document(match))


def _wake_score(match: Match) -> EpochMillis | str:
    """O score do índice, ou `NO_WAKE` para tirar a partida dele.

    Derivado do estado que está sendo gravado, e por isso sempre de acordo com
    ele: o índice não é uma segunda fonte a manter em sincronia.
    """
    wake_at = clock_wake_at(match.clock)

    return NO_WAKE if wake_at is None else wake_at


def _match_from_state(state: bytes | str) -> Match:
    """A fronteira JSON é o único ponto onde o formato não é verificável: o que
    sai do Redis é `Any` até alguém afirmar o contrário."""
    return match_from_document(cast(MatchDocument, json.loads(state)))
