"""Um lado do tabuleiro: as quatro zonas de carta de um jogador, o Nexus e as
duas energias.

Os tetos de mão (10) e de banco (6) da §12 **não** são validados aqui.
Aplicá-los é regra — o de mão acontece na compra (§9), o de banco ao jogar
unidade (§5A) — e regra não é deste pacote.
"""

from dataclasses import dataclass, field

from apps.players.services.player_queries import PlayerData

from .cards_in_play import BankUnit, MatchCard

# Fluxo de Partida §12.
STARTING_NEXUS = 20


@dataclass(slots=True)
class PlayerState:
    """O estado de jogo de um jogador, mais os dados públicos dele.

    >>> state = PlayerState(profile=fake_player_data(7))
    >>> state.user_id
    7
    >>> state.nexus
    20
    """

    profile: PlayerData
    nexus: int = STARTING_NEXUS
    # Topo do deck é o começo da lista: comprar é tirar de `deck[0]`.
    deck: list[MatchCard] = field(default_factory=list)
    hand: list[MatchCard] = field(default_factory=list)
    bank: list[BankUnit] = field(default_factory=list)
    graveyard: list[MatchCard] = field(default_factory=list)
    # Começa em 0 e sobe no primeiro Upkeep, então a rodada 1 tem 1 de energia
    # (§4).
    energy_max: int = 0
    energy_current: int = 0

    @property
    def user_id(self) -> int:
        """A identidade do jogador, que já vive dentro de `profile`.

        Propriedade e não campo próprio: duplicar o `user_id` criaria duas
        fontes que podem divergir. Isto dá o nome curto ao caminho quente sem
        o risco.

        >>> state.user_id
        7
        """
        return self.profile["user_id"]
