from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.players.serializers import PlayerSerializer


class PlayerMeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        player = request.user.profile
        serializer = PlayerSerializer(player)
        return Response(serializer.data)
