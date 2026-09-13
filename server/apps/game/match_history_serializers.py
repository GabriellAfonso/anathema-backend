"""A linha do histórico, do ponto de vista de quem está pedindo.

A mesma linha do banco vira "venci" para um jogador e "perdi" para o outro, e é
por isso que `won` é derivado do requisitante em vez de gravado: um campo
gravado teria de ser dois, um por lado.

O que **não** sai daqui: o deck da partida e o Nexus final dos dois. Ficam no
registro para a análise de balanceamento depois; expô-los ao cliente é decisão de
outra feature -- e o deck do oponente está na mesma linha, o que torna a omissão
uma escolha, não um esquecimento.
"""

from typing import TypedDict

from rest_framework import serializers

from apps.game.models import MatchRecord
from apps.players.models.player import PlayerProfile

# O `source` explícito existe porque o campo do modelo se chama `winner`/`loser`
# e a resposta fala de "oponente" -- quem pergunta não se vê como um dos dois
# lados de uma linha, se vê como jogador.
OPPONENT_FIELDS = ("user_id", "nickname", "icon", "level")


class OpponentPayload(TypedDict):
    """Os mesmos campos públicos que `PlayerData` já expõe em partida."""

    user_id: int
    nickname: str
    icon: str
    level: int


class MatchHistorySerializer(serializers.ModelSerializer[MatchRecord]):
    """Uma partida do histórico. Precisa do `user_id` do requisitante no contexto.

    >>> MatchHistorySerializer(record, context={"user_id": 7}).data["won"]
    True
    """

    won = serializers.SerializerMethodField()
    opponent = serializers.SerializerMethodField()

    class Meta:
        model = MatchRecord
        fields = (
            "match_id",
            "won",
            "end_reason",
            "opponent",
            "duration_seconds",
            "final_round",
            "ended_at",
        )

    def get_won(self, record: MatchRecord) -> bool:
        """Venceu quem pediu? Derivado, porque a linha serve aos dois lados."""
        return record.winner_id == self._asking_user_id()

    def get_opponent(self, record: MatchRecord) -> OpponentPayload | None:
        """O outro jogador, ou `None` se o perfil dele foi apagado.

        `None` não quebra a linha: o desfecho continua legível, porque quem não
        é `loser` é `winner`. É o que `on_delete=SET_NULL` existe para permitir.
        """
        other = record.loser if self.get_won(record) else record.winner

        return None if other is None else _opponent_payload(other)

    def _asking_user_id(self) -> int:
        """Quem pediu. Recusa nomeada em vez de `KeyError` de dicionário.

        A view sempre põe; a recusa é para quem instanciar o serializer sem
        contexto e receberia "perdi" em toda linha, silenciosamente.
        """
        user_id = self.context.get("user_id")

        if not isinstance(user_id, int):
            raise RuntimeError(
                f"context user_id is {user_id!r}: expected the int user_id of "
                f"the player asking for their own history"
            )

        return user_id


def _opponent_payload(profile: PlayerProfile) -> OpponentPayload:
    """`user_id` e não `id`: o espaço de identidade é nomeado (decisão 0001)."""
    return {
        "user_id": profile.pk,
        "nickname": profile.nickname,
        "icon": profile.icon,
        "level": profile.level,
    }
