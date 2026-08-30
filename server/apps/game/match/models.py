from typing import TypedDict
from uuid import uuid4

from apps.players.services.player_queries import PlayerData

# Uma carta é identificada por string; o baralho ainda não existe.
CardId = str


class MatchState(TypedDict):
    """A partida como ela viaja: o que `as_dict` grava e `from_dict` lê.

    As mãos e o tabuleiro são chaveados por string, não por `user_id`, porque
    é assim que sobrevivem ao JSON -- chave de objeto JSON é sempre string.
    """

    match_id: str
    players: list[PlayerData]
    turn: int
    board_state: dict[str, list[CardId]]
    hands: dict[str, list[CardId]]


class PlayerView(TypedDict):
    """A partida do ponto de vista de um jogador: mão dele, tabuleiro de todos."""

    your_hand: list[CardId]
    board: dict[int, list[CardId]]
    turn: int


class Match:
    """Uma partida viva entre dois jogadores, endereçada por `match_id`.

    Construída pelo MatchStore, nunca direto de um consumer: o estado precisa
    chegar ao Redis para os outros workers enxergarem a partida.

    >>> match = Match.start({"user_id": 7}, {"user_id": 9})
    >>> match.turn
    7
    """

    def __init__(
        self,
        match_id: str,
        players: list[PlayerData],
        turn: int,
        board_state: dict[int, list[CardId]],
        hands: dict[int, list[CardId]],
    ) -> None:
        self.match_id = match_id
        self.players = players
        self.turn = turn
        self.board_state = board_state
        self.hands = hands

    @classmethod
    def start(cls, player1: PlayerData, player2: PlayerData) -> "Match":
        """Partida nova, mão vazia dos dois lados; player1 começa."""
        return cls(
            match_id=str(uuid4()),
            players=[player1, player2],
            turn=player1["user_id"],
            board_state={},
            hands={player1["user_id"]: [], player2["user_id"]: []},
        )

    @classmethod
    def from_dict(cls, state: MatchState) -> "Match":
        """Reconstrói o que `as_dict` gravou.

        Traz as chaves de volta para int: toda busca aqui dentro é por
        `User.id`, e `hands["7"]` erraria silenciosamente.
        """
        return cls(
            match_id=state["match_id"],
            players=state["players"],
            turn=state["turn"],
            board_state={int(k): v for k, v in state["board_state"].items()},
            hands={int(k): v for k, v in state["hands"].items()},
        )

    def as_dict(self) -> MatchState:
        return {
            "match_id": self.match_id,
            "players": self.players,
            "turn": self.turn,
            "board_state": {str(k): v for k, v in self.board_state.items()},
            "hands": {str(k): v for k, v in self.hands.items()},
        }

    def has_player(self, user_id: int | None) -> bool:
        """A partida é o dono da regra de quem pode falar com ela.

        >>> match.has_player(7)
        True
        """
        return any(player["user_id"] == user_id for player in self.players)

    def play_card(self, player_id: int, card_id: CardId) -> None:
        # lógica simples de exemplo
        self.board_state.setdefault(player_id, []).append(card_id)
        self.turn = self.players[0]["user_id"] if self.turn == self.players[1]["user_id"] else self.players[1]["user_id"]

    def get_state_for_player(self, player_id: int) -> PlayerView:
        return {
            "your_hand": self.hands[player_id],
            "board": self.board_state,
            "turn": self.turn,
        }
