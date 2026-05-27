from uuid import uuid4


class Match:
    def __init__(self, player1, player2):
        self.id = str(uuid4())
        self.players = [player1, player2]
        self.turn = player1["id"]
        self.board_state = {}
        self.hands = {player1["id"]: [], player2["id"]: []}

    def play_card(self, player_id, card_id):
        # lógica simples de exemplo
        self.board_state.setdefault(player_id, []).append(card_id)
        self.turn = self.players[0]["id"] if self.turn == self.players[1]["id"] else self.players[1]["id"]

    def get_state_for_player(self, player_id):
        return {
            "your_hand": self.hands[player_id],
            "board": self.board_state,
            "turn": self.turn,
        }
