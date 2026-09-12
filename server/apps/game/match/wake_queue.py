"""A fila de despertar das partidas: quais precisam de olhada, e quando.

Um sorted set no Redis, com o `match_id` no membro e o próximo instante de
relógio da partida no score (§15). Quem mantém o score é o `MatchStore`, dentro
do mesmo script Lua que grava o estado -- não existe partida gravada sem o
despertar dela. Aqui ficam as três operações de quem consome o índice.

O lease **não** protege estado: quem protege é o compare-and-swap de `mutate`.
Ele só evita que os quatro workers do uvicorn façam o mesmo trabalho ao mesmo
tempo, e por isso pode vencer sem consequência nenhuma -- um worker que morre
depois de reivindicar atrasa aquele evento em, no máximo, o lease, e o próximo
worker o pega. É a diferença entre isto e uma trava: aqui vencer cedo demais
custa trabalho repetido, não estado errado.

`release` só reagenda se o score ainda é o do lease: uma jogada que chegou no
meio já reescreveu o índice pelo estado novo, e essa gravação vale mais que o
que este worker leu.
"""

from dataclasses import dataclass

from redis.asyncio import Redis

from apps.game.wall_clock import EpochMillis

from .store import NO_WAKE, wake_index_key

# Reivindica os vencidos empurrando o score de cada um para o fim do lease, numa
# execução só: dois workers na mesma volta não pegam o mesmo membro.
#
# `ZADD ... XX` porque o membro tem de existir: se outro worker o removeu entre
# a leitura e o empurrão, não é para recriá-lo.
#
# KEYS[1] = índice; ARGV[1] = agora; ARGV[2] = fim do lease; ARGV[3] = limite
CLAIM_SCRIPT = """
local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[3])
for _, member in ipairs(due) do
    redis.call('ZADD', KEYS[1], 'XX', ARGV[2], member)
end
return due
"""

# Devolve o membro ao índice, mas só se ninguém mexeu nele desde o claim.
#
# A comparação é numérica: o Redis devolve o score como texto formatado, e
# comparar strings faria `1700000000000` diferir de si mesmo por formatação.
#
# KEYS[1] = índice; ARGV[1] = match_id; ARGV[2] = fim do lease reivindicado
# ARGV[3] = despertar novo, ou '' para tirar do índice
RELEASE_SCRIPT = """
local score = redis.call('ZSCORE', KEYS[1], ARGV[1])
if not score or tonumber(score) ~= tonumber(ARGV[2]) then
    return 0
end
if ARGV[3] == '' then
    redis.call('ZREM', KEYS[1], ARGV[1])
else
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[1])
end
return 1
"""


@dataclass(frozen=True, slots=True)
class ClaimedWake:
    """Um despertar reivindicado por este worker, e até quando.

    `lease_until_ms` não é prazo de trabalho: é o score que ficou no índice, e é
    com ele que `release` prova que ninguém reagendou no meio.

    >>> claimed.match_id
    'm-1'
    """

    match_id: str
    lease_until_ms: EpochMillis


class MatchWakeQueue:
    """O índice de despertar, endereçado pelo mesmo prefixo do `MatchStore`.

    Cliente Redis injetado, como no store.

    >>> queue = MatchWakeQueue(Redis.from_url("redis://localhost:6379/3"))
    >>> await queue.claim_due(now, lease_ms=5000, limit=50)
    [ClaimedWake(match_id='m-1', lease_until_ms=1700000005000)]
    """

    def __init__(self, redis: Redis, key_prefix: str = "match") -> None:
        self._redis = redis
        self._key = wake_index_key(key_prefix)
        self._claim = redis.register_script(CLAIM_SCRIPT)
        self._release = redis.register_script(RELEASE_SCRIPT)

    async def claim_due(
        self, now: EpochMillis, *, lease_ms: int, limit: int
    ) -> list[ClaimedWake]:
        """As partidas cujo despertar já venceu, reivindicadas por este worker."""
        lease_until = EpochMillis(now + lease_ms)
        claimed = await self._claim(keys=[self._key], args=[now, lease_until, limit])

        return [
            ClaimedWake(match_id=_text(member), lease_until_ms=lease_until)
            for member in claimed
        ]

    async def release(self, claimed: ClaimedWake, wake_at: EpochMillis | None) -> None:
        """Reagenda o que este worker reivindicou e não rendeu gravação.

        `None` tira a partida do índice. Se uma gravação mudou o score no meio,
        esta chamada não faz nada -- o estado novo já agendou o que vale.
        """
        await self._release(
            keys=[self._key],
            args=[
                claimed.match_id,
                claimed.lease_until_ms,
                NO_WAKE if wake_at is None else wake_at,
            ],
        )

    async def forget(self, match_id: str) -> None:
        """Tira do índice a partida que não existe mais no armazenamento."""
        await self._redis.zrem(self._key, match_id)


def _text(member: bytes | str) -> str:
    """O membro como texto: o cliente Redis devolve bytes por default."""
    return member.decode() if isinstance(member, bytes) else member
