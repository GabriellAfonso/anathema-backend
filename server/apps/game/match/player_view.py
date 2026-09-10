"""O recorte do estado que um jogador pode receber.

O servidor é a autoridade. A ordem do deck nunca sai dele, e a mão do oponente
também não.

A ocultação é imposta pelo tipo, não por uma checagem que a revisão precisa
pegar: `OpponentSideView` **não tem** campo de mão, e nenhum dos dois lados
tem campo de conteúdo de deck. Vazar não é um bug de valor -- é erro de mypy,
porque não existe onde escrever.

Produzir a visão é daqui. Empacotar, transmitir e reenviar na reconexão é do
websocket.
"""

from typing import TypedDict

from apps.players.services.player_queries import PlayerData

from .documents import (
    BankUnitDocument,
    CardDocument,
    StackEntryDocument,
)
from .match_state import Match, MatchPhase
from .player_state import PlayerState
from .serialization import (
    to_bank_unit_document,
    to_card_document,
    to_stack_entry_document,
)


class PlayerSideView(TypedDict):
    """O próprio lado: a mão aparece inteira, o deck só como contagem."""

    profile: PlayerData
    nexus: int
    energy_max: int
    energy_current: int
    hand: list[CardDocument]
    bank: list[BankUnitDocument]
    graveyard: list[CardDocument]
    deck_size: int


class OpponentSideView(TypedDict):
    """O outro lado: da mão sai só o tamanho.

    Contagem sim, identidade não -- o cliente precisa saber quantas cartas
    desenhar viradas.
    """

    profile: PlayerData
    nexus: int
    energy_max: int
    energy_current: int
    hand_size: int
    bank: list[BankUnitDocument]
    graveyard: list[CardDocument]
    deck_size: int


class PlayerView(TypedDict):
    """A partida do ponto de vista de um jogador. Derivada, nunca armazenada."""

    match_id: str
    round_number: int
    phase: MatchPhase
    # `None` enquanto a fase é `MULLIGAN`: o sorteio da §3 ainda não aconteceu,
    # e a tela que o cliente desenha nesse momento é a do mulligan, que não
    # precisa de dono de token para existir.
    priority_user_id: int | None
    token_holder_user_id: int | None
    token_consumed: bool
    consecutive_passes: int
    stack: list[StackEntryDocument]
    you: PlayerSideView
    opponent: OpponentSideView


def build_player_view(match: Match, user_id: int) -> PlayerView:
    """A visão daquele jogador, ou recusa citando o `user_id` pedido.

    Recusa em vez de devolver visão parcial: um `user_id` de fora chegando
    aqui significa que o gate de participante não foi consultado antes.

    >>> build_player_view(match, 7)["opponent"]["hand_size"]
    3
    """
    return {
        "match_id": match.match_id,
        "round_number": match.round_number,
        "phase": match.phase,
        "priority_user_id": match.priority_user_id,
        "token_holder_user_id": match.token_holder_user_id,
        "token_consumed": match.token_consumed,
        "consecutive_passes": match.consecutive_passes,
        "stack": [to_stack_entry_document(entry) for entry in match.stack],
        "you": _own_side(match.player(user_id)),
        "opponent": _opponent_side(match.opponent_of(user_id)),
    }


def _own_side(player: PlayerState) -> PlayerSideView:
    """As cartas levam o identificador: é com ele que o cliente mira uma
    cópia específica."""
    return {
        "profile": player.profile,
        "nexus": player.nexus,
        "energy_max": player.energy_max,
        "energy_current": player.energy_current,
        "hand": [to_card_document(card) for card in player.hand],
        "bank": [to_bank_unit_document(unit) for unit in player.bank],
        "graveyard": [to_card_document(card) for card in player.graveyard],
        "deck_size": len(player.deck),
    }


def _opponent_side(opponent: PlayerState) -> OpponentSideView:
    """Mesma forma, menos a mão. O cemitério é informação já revelada."""
    return {
        "profile": opponent.profile,
        "nexus": opponent.nexus,
        "energy_max": opponent.energy_max,
        "energy_current": opponent.energy_current,
        "hand_size": len(opponent.hand),
        "bank": [to_bank_unit_document(unit) for unit in opponent.bank],
        "graveyard": [to_card_document(card) for card in opponent.graveyard],
        "deck_size": len(opponent.deck),
    }
