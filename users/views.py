"""Представления для аутентификации и управления пользователями."""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserRegisterSerializer,
    UserProfileSerializer,
    UserListSerializer,
)
from .permissions import IsAdmin


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ — регистрация нового пользователя."""

    permission_classes = [AllowAny]
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": "Аккаунт создан", "email": user.email},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — инвалидация refresh-токена."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()  # Добавляем в чёрный список
            return Response({"detail": "Выход выполнен"}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"detail": "Неверный токен"}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/auth/me/ — профиль текущего пользователя."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """GET /api/v1/auth/users/ — список всех пользователей (только admin)."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserListSerializer
    queryset = User.objects.all()
