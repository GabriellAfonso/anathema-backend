"""Uma partida viva entre dois jogadores, endereçada por `match_id`.

Construída pelo MatchStore, nunca direto de um consumer: o estado precisa
chegar ao Redis para os outros workers do uvicorn enxergarem a partida.

Este módulo guarda o estado e responde perguntas sobre ele. Nada aqui decide
se uma jogada é legal, aplica dano, troca prioridade ou avança fase — isso é
regra, e regra é do motor.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from apps.players.services.player_queries import PlayerData

from .cards_in_play import BankUnit, CardInstanceId
from .player_state import PlayerState
from .spell_stack import StackEntry


class MatchPhase(StrEnum):
    """As cinco fases da §2 do Fluxo de Partida. Conjunto fechado.

    `COMBAT` existe desde já, mas o estado que o combate precisa — o
    pareamento de bloqueadores da §7.2 — entra na feature de combate.
    """

    UPKEEP = "upkeep"
    ACTION = "action"
    STACK_RESOLUTION = "stack_resolution"
    COMBAT = "combat"
    ROUND_END = "round_end"


class NotAParticipantError(Exception):
    """Pediram o estado de um `user_id` que não joga esta partida.

    É erro de programação, não fluxo normal: o gate de `MatchConsumer` já
    deveria ter fechado o socket. Quem quer só perguntar usa `has_player`.
    """

    def __init__(self, user_id: int | None, match_id: str) -> None:
        super().__init__(
            f"user {user_id} does not play match {match_id!r}: "
            f"expected the user_id of one of its two players"
        )
        self.user_id = user_id
        self.match_id = match_id


@dataclass(slots=True)
class Match:
    """A partida inteira: os dois jogadores e tudo que a §2 lista.

    >>> match = Match.start({"user_id": 7, ...}, {"user_id": 9, ...})
    >>> match.priority_user_id
    7
    """

    match_id: str
    # Tupla de dois, não lista: a aridade fica no tipo, e o mypy recusa uma
    # partida com um ou três jogadores. Nenhuma estrutura daqui é indexada por
    # `user_id` -- chave de objeto JSON é sempre string, e o modelo anterior
    # só sobrevivia porque convertia de volta na leitura. Sem chave, não sobra
    # o que converter.
    players: tuple[PlayerState, PlayerState]
    token_holder_user_id: int
    priority_user_id: int
    round_number: int = 1
    token_consumed: bool = False
    phase: MatchPhase = MatchPhase.UPKEEP
    # Fim da lista é o topo: `append` empilha, e a resolução é LIFO (§6).
    stack: list[StackEntry] = field(default_factory=list)
    consecutive_passes: int = 0
    # Contador de identidade de carta. Campo do estado, e não do processo,
    # porque a partida é lida por qualquer worker do uvicorn: um contador de
    # processo daria números repetidos entre workers.
    next_card_instance_id: int = 1

    @classmethod
    def start(cls, player1: PlayerData, player2: PlayerData) -> "Match":
        """Partida nova, válida e ainda não jogável.

        Embaralhar, comprar 4, mulligan e sortear o token são o setup da §3 e
        entram com a feature de setup. Até lá as quatro zonas nascem vazias.

        >>> Match.start(one, two).phase
        <MatchPhase.UPKEEP: 'upkeep'>
        """
        return cls(
            match_id=str(uuid4()),
            players=(PlayerState(profile=player1), PlayerState(profile=player2)),
            # Valor de espera, não regra: quem sorteia o dono do token é a §3.
            token_holder_user_id=player1["user_id"],
            priority_user_id=player1["user_id"],
        )

    def has_player(self, user_id: int | None) -> bool:
        """A partida é o dono da regra de quem pode falar com ela.

        Aceita `None` e devolve `False`: um socket sem usuário autenticado
        nunca passa no gate, e nunca levanta.

        >>> match.has_player(7)
        True
        """
        return any(player.user_id == user_id for player in self.players)

    def player(self, user_id: int) -> PlayerState:
        """O estado do jogador, ou recusa citando o `user_id` pedido.

        >>> match.player(7).nexus
        20
        """
        for player in self.players:
            if player.user_id == user_id:
                return player

        raise NotAParticipantError(user_id, self.match_id)

    def opponent_of(self, user_id: int) -> PlayerState:
        """O outro jogador, ou recusa citando o `user_id` pedido.

        >>> match.opponent_of(7).user_id
        9
        """
        first, second = self.players

        if first.user_id == user_id:
            return second

        if second.user_id == user_id:
            return first

        raise NotAParticipantError(user_id, self.match_id)

    def bank_unit(self, card_instance_id: CardInstanceId) -> BankUnit | None:
        """A unidade em campo com aquele identificador, ou `None`.

        É a revalidação de alvo da §6, e `None` **não é erro**: é a resposta
        que autoriza o fizzle. Quem pergunta não precisa saber de qual jogador
        o alvo é, nem envolver a chamada em `try`.

        Diverge de `player()`, que levanta, porque as perguntas são
        diferentes: pedir um jogador que não joga é bug; perguntar por um alvo
        que sumiu é o caso normal.

        >>> match.bank_unit(CardInstanceId(3)) is None
        True
        """
        for player in self.players:
            found = _unit_in_bank(player.bank, card_instance_id)

            if found is not None:
                return found

        return None

    def mint_card_instance_id(self) -> CardInstanceId:
        """Cunha o próximo identificador de carta desta partida.

        Único ponto do código que produz um `CardInstanceId`. **Não** é
        chamado ao mover carta de zona: o identificador nasce com a carta e
        acompanha ela, e o reset de deck da §9 devolve as mesmas cartas com os
        mesmos números.

        >>> match.mint_card_instance_id()
        1
        """
        minted = self.next_card_instance_id
        self.next_card_instance_id += 1

        return CardInstanceId(minted)


def _unit_in_bank(
    bank: Sequence[BankUnit], card_instance_id: CardInstanceId
) -> BankUnit | None:
    """Busca num banco só. Extraída para manter `bank_unit` em dois níveis."""
    for unit in bank:
        if unit.card.card_instance_id == card_instance_id:
            return unit

    return None
