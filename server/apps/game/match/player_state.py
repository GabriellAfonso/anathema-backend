"""Um lado do tabuleiro: as quatro zonas de carta de um jogador, o Nexus e as
duas energias.

Os tetos de mão (10) e de banco (6) da §12 **não** são validados aqui.
Aplicá-los é regra — o de mão acontece na compra (§9), o de banco ao jogar
unidade (§5A) — e regra não é deste pacote.
"""

from dataclasses import dataclass, field

from apps.players.services.player_queries import PlayerData

from .cards_in_play import BankUnit, MatchCard
from .chosen_deck import ChosenDeck

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
    # O deck da entrada na fila, congelado -- lista **e** nome. Não é `deck`
    # acima: aquele é a pilha de compra, e ela esvazia. Este é o que o jogador
    # escolheu, e existe para o registro do resultado (feature 012) guardar com
    # que deck cada um jogou mesmo depois de o deck ser editado ou apagado.
    #
    # `None` só em documento gravado antes da feature 012 e ainda dentro do TTL
    # de 6 horas. Partida criada por este código sempre tem.
    chosen_deck: ChosenDeck | None = None
    hand: list[MatchCard] = field(default_factory=list)
    bank: list[BankUnit] = field(default_factory=list)
    graveyard: list[MatchCard] = field(default_factory=list)
    # Começa em 0 e sobe no primeiro Upkeep, então a rodada 1 tem 1 de energia
    # (§4). Uma energia só: ela acumula de rodada em rodada até o teto, e a
    # máxima que existia até a correção da nota de 2026-09-11 deixou de ter o
    # que guardar.
    energy_current: int = 0
    # O mulligan da §3 é uma vez por jogador por partida. Este booleano é a
    # única marca dele: "de quem o setup ainda espera" é derivado daqui pelo
    # `Match`, e não guardado numa segunda lista que pudesse divergir.
    mulligan_taken: bool = False

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
