"""Como a partida acabou: quem chegou a Nexus zero (Fluxo de Partida §10).

Estado, e não evento. A §10 descreve o fim como situação -- "esse jogador
perde" --, e situação que precisa sobreviver ao Redis e ser lida por qualquer
worker do uvicorn não cabe numa exceção que um processo levantou e o outro
nunca viu.

Nada aqui decide **quando** a partida acaba nem quem perdeu: isso é regra, e
regra é do motor. Aqui o resultado só é representado.
"""

from dataclasses import dataclass

# A partida tem exatamente dois jogadores (§2), então um resultado nomeia um
# derrotado -- e o outro venceu -- ou os dois, e foi empate.
MIN_DEFEATED = 1
MAX_DEFEATED = 2


class InvalidMatchOutcomeError(Exception):
    """Construíram um resultado que não é resultado de partida nenhuma.

    Vazio, três ou repetido. É erro de programação, não fluxo: quem constrói
    isto já decidiu que a partida acabou.

    >>> raise InvalidMatchOutcomeError(())
    InvalidMatchOutcomeError: defeated_user_ids is (): expected one or two
    distinct user_ids
    """

    def __init__(self, defeated_user_ids: tuple[int, ...]) -> None:
        super().__init__(
            f"defeated_user_ids is {defeated_user_ids}: "
            f"expected one or two distinct user_ids"
        )
        self.defeated_user_ids = defeated_user_ids


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Quem perdeu, e nada mais.

    Um `user_id` é derrota do outro jogador; dois é empate. **Não existe campo
    de vencedor**: ele é `match.players` menos isto, e gravá-lo seria a segunda
    fonte que `PlayerState.user_id` e `Match.awaiting_mulligan_user_ids` já
    recusam pela mesma razão -- uma segunda fonte não dá erro quando diverge,
    dá estado errado que passa despercebido.

    Valida na construção, alto e cedo, como `FrozenCardCatalog`: depois disso
    não existe resultado inválido a checar em tempo de partida.

    >>> MatchOutcome(defeated_user_ids=(7,)).is_draw
    False
    """

    defeated_user_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        _reject_impossible_arity(self.defeated_user_ids)

    @property
    def is_draw(self) -> bool:
        """Os dois Nexus chegaram a zero no mesmo cálculo (§10).

        Derivada e nunca gravada: um booleano ao lado da lista poderia
        discordar dela.

        >>> MatchOutcome(defeated_user_ids=(7, 9)).is_draw
        True
        """
        return len(self.defeated_user_ids) == MAX_DEFEATED


def _reject_impossible_arity(defeated_user_ids: tuple[int, ...]) -> None:
    """Um ou dois `user_id`, sem repetição. Qualquer outra coisa recusa.

    O mesmo jogador não perde duas vezes, e uma partida sem derrotado não
    acabou.
    """
    distinct = set(defeated_user_ids)

    if len(distinct) != len(defeated_user_ids):
        raise InvalidMatchOutcomeError(defeated_user_ids)

    if not MIN_DEFEATED <= len(distinct) <= MAX_DEFEATED:
        raise InvalidMatchOutcomeError(defeated_user_ids)
