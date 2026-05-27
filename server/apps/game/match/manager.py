from .models import Match


class MatchManager:
    matches = {}        # match_id -> Match
    consumers = {}      # player_id -> consumer

    @classmethod
    def create_match(cls, player1, player2):
        match = Match(player1, player2)
        cls.matches[match.id] = match
        return match

    @classmethod
    def get_match(cls, match_id):
        return cls.matches.get(match_id)

    @classmethod
    def register_consumer(cls, player_id, consumer):
        cls.consumers[player_id] = consumer

    @classmethod
    def get_consumer(cls, player_id):
        return cls.consumers.get(player_id)
