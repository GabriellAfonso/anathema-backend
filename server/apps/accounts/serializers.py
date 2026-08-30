from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator
from rest_framework.serializers import ModelSerializer

from apps.players.services.player_creation import create_player_for_user


class RegisterSerializer(ModelSerializer[User]):

    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(
        ), message="Este e-mail já está sendo utilizado.")]
    )

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password])

    password_confirmation = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirmation')

    def validate_password_confirmation(self, password_confirmation: str) -> str:
        password = self.initial_data.get("password")
        if password and password_confirmation != password:
            raise serializers.ValidationError("Passwords must match.")
        return password_confirmation

    @transaction.atomic
    def create(self, validated_data: dict[str, str]) -> User:
        """Registra o usuário e o jogador na mesma transação.

        O profile nasce aqui, e não num `post_save`, porque esta é a única
        rota de registro: um sinal espalharia a criação por todo `User`
        salvo no projeto (`createsuperuser`, fixtures, admin) e ficaria
        fora da transação que protege o rollback.
        """
        validated_data.pop("password_confirmation", None)
        user = User.objects.create_user(**validated_data)
        create_player_for_user(user, nickname=user.username)
        return user
