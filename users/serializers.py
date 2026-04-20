"""Сериализаторы для аутентификации и работы с пользователями."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Расширяем стандартный JWT-токен:
    добавляем в payload роль и имя пользователя.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        token["email"] = user.email
        return token


class UserRegisterSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя."""

    password = serializers.CharField(write_only=True, min_length=10)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "full_name", "department", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """Профиль текущего пользователя (только чтение чувствительных полей)."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "department", "date_joined", "last_login_ip"]
        read_only_fields = ["id", "email", "role", "date_joined", "last_login_ip"]


class UserListSerializer(serializers.ModelSerializer):
    """Список пользователей (для администраторов)."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "department", "is_active", "date_joined"]
