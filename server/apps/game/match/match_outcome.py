"""Como a partida acabou: quem perdeu, e por quê (Fluxo de Partida §10).

Estado, e não evento. A §10 descreve o fim como situação -- "esse jogador
perde" --, e situação que precisa sobreviver ao Redis e ser lida por qualquer
worker do uvicorn não cabe numa exceção que um processo levantou e o outro
nunca viu.

Nada aqui decide **quando** a partida acaba nem quem perdeu: isso é regra, e
regra é do motor. Aqui o resultado só é representado.
"""

from dataclasses import dataclass
from enum import StrEnum


class MatchEndReason(StrEnum):
    """Por que a partida acabou. Conjunto fechado: as duas saídas da §10.

    Existe para o cliente distinguir "o Nexus dele chegou a zero" de "ele
    desistiu" sem inferir do Nexus -- quem desiste com 20 de Nexus perdeu
    igual.
    """

    NEXUS_DEPLETED = "nexus_depleted"
    FORFEIT = "forfeit"


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Quem perdeu, e por quê.

    Um derrotado só: **não existe empate** (Fluxo de Partida, corrigido em
    2026-09-11). Até a correção o campo era uma tupla de um ou dois `user_id`,
    e o de dois era o empate; sem empate, a tupla só abria espaço para um estado
    que não existe.

    **Não existe campo de vencedor**: ele é o outro jogador de `match.players`,
    e gravá-lo seria a segunda fonte que `PlayerState.user_id` e
    `Match.awaiting_mulligan_user_ids` já recusam pela mesma razão -- uma segunda
    fonte não dá erro quando diverge, dá estado errado que passa despercebido.

    >>> MatchOutcome(defeated_user_id=7, reason=MatchEndReason.FORFEIT).reason
    <MatchEndReason.FORFEIT: 'forfeit'>
    """

    defeated_user_id: int
    reason: MatchEndReason
