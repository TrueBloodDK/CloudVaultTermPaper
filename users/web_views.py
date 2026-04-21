"""Веб-представления для аутентификации (Django Templates)."""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.views import View

from users.models import User
from users.serializers import UserRegisterSerializer
from audit.models import AuditLog
from audit.utils import log_action, get_client_ip


class LoginView(View):
    template_name = "auth/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("files:list")
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None

        if user and user.check_password(password) and user.is_active:
            login(request, user)

            # Сохраняем IP последнего входа
            user.last_login_ip = get_client_ip(request)
            user.save(update_fields=["last_login_ip"])

            log_action(request, AuditLog.Action.LOGIN, obj=user)
            return redirect("files:list")
        else:
            # Фиксируем неудачную попытку
            log_action(
                request,
                AuditLog.Action.LOGIN_FAILED,
                extra={"email": email},
            )
            return render(request, self.template_name, {
                "error": "Неверный email или пароль",
                "email": email,
            })


class LogoutView(View):
    def post(self, request):
        log_action(request, AuditLog.Action.LOGOUT)
        logout(request)
        messages.success(request, "Вы вышли из системы")
        return redirect("auth:login")


class RegisterView(View):
    template_name = "auth/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("files:list")
        return render(request, self.template_name)

    def post(self, request):
        data = {
            "email": request.POST.get("email", "").strip().lower(),
            "full_name": request.POST.get("full_name", "").strip(),
            "department": request.POST.get("department", "").strip(),
            "password": request.POST.get("password", ""),
            "password_confirm": request.POST.get("password_confirm", ""),
        }

        serializer = UserRegisterSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            log_action(request, AuditLog.Action.USER_CREATE, obj=user)
            messages.success(request, f"Аккаунт создан. Добро пожаловать, {user.full_name}!")
            login(request, user)
            return redirect("files:list")
        else:
            return render(request, self.template_name, {
                "errors": serializer.errors,
                "form_data": data,
            })
