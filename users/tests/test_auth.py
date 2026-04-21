"""Тесты аутентификации: регистрация, вход, выход, роли."""

import pytest
from django.urls import reverse

from users.models import User


@pytest.mark.django_db
class TestRegistration:
    """Тесты регистрации пользователя."""

    def _post_register(self, client, **kwargs):
        defaults = {
            "email": "newuser@test.ru",
            "full_name": "Новый Пользователь",
            "department": "ИТ",
            "password": "strongpass123",
            "password_confirm": "strongpass123",
        }
        defaults.update(kwargs)
        return client.post(reverse("auth:register"), defaults)

    def test_register_success(self, client):
        resp = self._post_register(client)
        assert resp.status_code == 302
        assert User.objects.filter(email="newuser@test.ru").exists()

    def test_register_default_role_is_user(self, client):
        self._post_register(client)
        user = User.objects.get(email="newuser@test.ru")
        assert user.role == User.Role.USER

    def test_register_password_mismatch(self, client):
        resp = self._post_register(client, password_confirm="wrongpass")
        assert resp.status_code == 200
        assert not User.objects.filter(email="newuser@test.ru").exists()

    def test_register_short_password(self, client):
        """Пароль менее 10 символов — ошибка валидации."""
        resp = self._post_register(client, password="short", password_confirm="short")
        assert resp.status_code == 200
        assert not User.objects.filter(email="newuser@test.ru").exists()

    def test_register_duplicate_email(self, client, regular_user):
        resp = self._post_register(client, email=regular_user.email)
        assert resp.status_code == 200
        assert User.objects.filter(email=regular_user.email).count() == 1

    def test_register_logs_in_automatically(self, client):
        resp = self._post_register(client)
        assert resp.status_code == 302
        assert "_auth_user_id" in client.session

    def test_register_creates_audit_record(self, client):
        from audit.models import AuditLog
        self._post_register(client)
        assert AuditLog.objects.filter(action=AuditLog.Action.USER_CREATE).exists()


@pytest.mark.django_db
class TestLogin:
    """Тесты входа в систему."""

    def _post_login(self, client, email="user@test.ru", password="userpass123"):
        return client.post(reverse("auth:login"), {
            "email": email,
            "password": password,
        })

    def test_login_success(self, client, regular_user):
        resp = self._post_login(client)
        assert resp.status_code == 302
        assert "_auth_user_id" in client.session

    def test_login_redirects_to_files(self, client, regular_user):
        resp = self._post_login(client)
        assert resp["Location"] == reverse("files:list")

    def test_login_wrong_password(self, client, regular_user):
        resp = self._post_login(client, password="wrongpassword")
        assert resp.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_login_nonexistent_email(self, client):
        resp = self._post_login(client, email="ghost@test.ru")
        assert resp.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_login_inactive_user(self, client, regular_user):
        regular_user.is_active = False
        regular_user.save()
        resp = self._post_login(client)
        assert "_auth_user_id" not in client.session

    def test_failed_login_creates_audit_record(self, client, regular_user):
        from audit.models import AuditLog
        self._post_login(client, password="wrongpassword")
        assert AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN_FAILED
        ).exists()

    def test_successful_login_creates_audit_record(self, client, regular_user):
        from audit.models import AuditLog
        self._post_login(client)
        assert AuditLog.objects.filter(
            user=regular_user,
            action=AuditLog.Action.LOGIN,
        ).exists()

    def test_successful_login_saves_ip(self, client, regular_user):
        self._post_login(client)
        regular_user.refresh_from_db()
        assert regular_user.last_login_ip is not None

    def test_already_logged_in_redirects(self, auth_client):
        resp = auth_client.get(reverse("auth:login"))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestLogout:
    """Тесты выхода из системы."""

    def test_logout_clears_session(self, auth_client):
        auth_client.post(reverse("auth:logout"))
        assert "_auth_user_id" not in auth_client.session

    def test_logout_creates_audit_record(self, auth_client, regular_user):
        from audit.models import AuditLog
        auth_client.post(reverse("auth:logout"))
        assert AuditLog.objects.filter(
            user=regular_user,
            action=AuditLog.Action.LOGOUT,
        ).exists()

    def test_logout_requires_post(self, auth_client):
        """GET на logout не должен разлогинивать."""
        resp = auth_client.get(reverse("auth:logout"))
        assert resp.status_code == 405


@pytest.mark.django_db
class TestUserModel:
    """Тесты модели пользователя."""

    def test_is_admin_property(self, admin_user):
        assert admin_user.is_admin is True

    def test_is_admin_false_for_regular(self, regular_user):
        assert regular_user.is_admin is False

    def test_is_manager_true_for_admin(self, admin_user):
        assert admin_user.is_manager is True

    def test_is_manager_false_for_user(self, regular_user):
        assert regular_user.is_manager is False

    def test_str_representation(self, regular_user):
        assert "Обычный Пользователь" in str(regular_user)
        assert "user@test.ru" in str(regular_user)

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"

    def test_password_is_hashed(self, regular_user):
        """Пароль не хранится в открытом виде."""
        assert regular_user.password != "userpass123"
        assert regular_user.password.startswith("pbkdf2_")
