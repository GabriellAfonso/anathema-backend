from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator
from rest_framework.serializers import ModelSerializer


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

    def create(self, validated_data: dict[str, str]) -> User:
        validated_data.pop("password_confirmation", None)
        return User.objects.create_user(**validated_data)
