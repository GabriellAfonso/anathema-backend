from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.players.models.player import PlayerProfile
from apps.players.serializers import PlayerSerializer


class PlayerMeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Perfil do usuário autenticado, ou 404 se ele não é jogador.

        Contas criadas fora do registro (`createsuperuser`, fixtures) não
        passam por `create_player_for_user` e não têm profile. Isso é 404,
        não 500: o recurso não existe para esse usuário.
        """
        profile = PlayerProfile.objects.filter(user=request.user).first()
        if profile is None:
            raise NotFound(
                f"user_id={request.user.pk} não tem PlayerProfile. "
                "Só contas criadas pelo registro são jogadores."
            )

        return Response(PlayerSerializer(profile).data)
