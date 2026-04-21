"""Тесты журнала аудита: модель, middleware, утилиты."""

import pytest
from django.urls import reverse

from audit.models import AuditLog
from audit.utils import log_action, get_client_ip


@pytest.mark.django_db
class TestAuditLogModel:
    """Тесты модели AuditLog."""

    def test_create_log_entry(self, regular_user):
        log = AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.FILE_UPLOAD,
            object_type="File",
            object_id="some-uuid",
            object_repr="report.pdf",
            ip_address="127.0.0.1",
        )
        assert log.pk is not None
        assert log.timestamp is not None

    def test_str_representation(self, regular_user):
        log = AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.LOGIN,
        )
        result = str(log)
        assert "Обычный Пользователь" in result
        assert "Вход в систему" in result

    def test_anonymous_log_entry(self):
        """Запись без пользователя (анонимный запрос)."""
        log = AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED,
            extra={"email": "hacker@evil.com"},
        )
        assert log.user is None
        assert "Аноним" in str(log)

    def test_cannot_modify_existing_record(self, regular_user):
        """Изменение существующей записи запрещено."""
        log = AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.LOGIN,
        )
        log.action = AuditLog.Action.FILE_DELETE
        with pytest.raises(PermissionError):
            log.save()

    def test_cannot_delete_record(self, regular_user):
        """Удаление записи журнала запрещено."""
        log = AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.LOGIN,
        )
        with pytest.raises(PermissionError):
            log.delete()

    def test_records_ordered_by_timestamp_desc(self, regular_user):
        AuditLog.objects.create(user=regular_user, action=AuditLog.Action.LOGIN)
        AuditLog.objects.create(user=regular_user, action=AuditLog.Action.FILE_UPLOAD)
        AuditLog.objects.create(user=regular_user, action=AuditLog.Action.LOGOUT)

        logs = list(AuditLog.objects.all())
        for i in range(len(logs) - 1):
            assert logs[i].timestamp >= logs[i + 1].timestamp

    def test_extra_field_stores_json(self, regular_user):
        extra = {"size": 1024, "mime": "application/pdf", "tags": ["important"]}
        log = AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.FILE_UPLOAD,
            extra=extra,
        )
        log.refresh_from_db()
        assert log.extra["size"] == 1024
        assert log.extra["tags"] == ["important"]


@pytest.mark.django_db
class TestAuditMiddleware:
    """Тесты middleware автоматической записи 403."""

    def test_403_creates_access_denied_record(self, client, sample_file):
        """Запрос к чужому файлу → ACCESS_DENIED в журнале."""
        url = reverse("files:download", args=[sample_file.id])
        # client без авторизации → редирект на логин, не 403
        # Логинимся как посторонний пользователь
        from django.contrib.auth import get_user_model
        User = get_user_model()
        outsider = User.objects.create_user(
            email="outsider@test.ru",
            full_name="Посторонний",
            password="outsiderpass1",
        )
        client.force_login(outsider)
        client.get(url)

        assert AuditLog.objects.filter(
            action=AuditLog.Action.ACCESS_DENIED
        ).exists()


@pytest.mark.django_db
class TestGetClientIp:
    """Тесты извлечения IP-адреса клиента."""

    def test_ip_from_remote_addr(self, rf):
        request = rf.get("/", REMOTE_ADDR="192.168.1.1")
        assert get_client_ip(request) == "192.168.1.1"

    def test_ip_from_x_forwarded_for(self, rf):
        """X-Forwarded-For приоритетнее REMOTE_ADDR."""
        request = rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1",
            REMOTE_ADDR="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.5"


@pytest.mark.django_db
class TestAuditView:
    """Тесты страницы журнала аудита."""

    def test_audit_page_requires_login(self, client):
        resp = client.get(reverse("audit:list"))
        assert resp.status_code == 302

    def test_regular_user_redirected_from_audit(self, auth_client):
        resp = auth_client.get(reverse("audit:list"))
        assert resp.status_code == 302

    def test_admin_can_view_audit(self, admin_client, admin_user):
        AuditLog.objects.create(user=admin_user, action=AuditLog.Action.LOGIN)
        resp = admin_client.get(reverse("audit:list"))
        assert resp.status_code == 200

    def test_audit_shows_log_entries(self, admin_client, regular_user):
        AuditLog.objects.create(
            user=regular_user,
            action=AuditLog.Action.FILE_UPLOAD,
            object_repr="secret.pdf",
        )
        resp = admin_client.get(reverse("audit:list"))
        assert "secret.pdf" in resp.content.decode()

    def test_audit_filter_by_action(self, admin_client, regular_user):
        AuditLog.objects.create(user=regular_user, action=AuditLog.Action.LOGIN)
        AuditLog.objects.create(user=regular_user, action=AuditLog.Action.FILE_DELETE)

        resp = admin_client.get(reverse("audit:list") + "?action=login")
        assert resp.status_code == 200

        # Фильтр по action=login → только 1 запись в таблице
        logs_in_context = resp.context["logs"]
        assert logs_in_context.count() == 1
        assert logs_in_context.first().action == AuditLog.Action.LOGIN
