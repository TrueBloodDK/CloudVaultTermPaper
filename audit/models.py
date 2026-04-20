"""Модель журнала аудита — фиксирует все действия пользователей."""

import uuid
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """
    Запись журнала аудита.

    Фиксирует: кто, что сделал, с каким объектом, когда и с какого IP.
    Записи только добавляются — изменение и удаление запрещены.
    """

    class Action(models.TextChoices):
        LOGIN = "login", "Вход в систему"
        LOGOUT = "logout", "Выход из системы"
        LOGIN_FAILED = "login_failed", "Неудачная попытка входа"
        FILE_UPLOAD = "file_upload", "Загрузка файла"
        FILE_DOWNLOAD = "file_download", "Скачивание файла"
        FILE_DELETE = "file_delete", "Удаление файла"
        FILE_VIEW = "file_view", "Просмотр файла"
        USER_CREATE = "user_create", "Создание пользователя"
        USER_UPDATE = "user_update", "Изменение пользователя"
        ACCESS_DENIED = "access_denied", "Отказ в доступе"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Пользователь",
    )
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        verbose_name="Действие",
    )
    object_type = models.CharField(
        max_length=50, blank=True, verbose_name="Тип объекта"
    )
    object_id = models.CharField(
        max_length=255, blank=True, verbose_name="ID объекта"
    )
    object_repr = models.CharField(
        max_length=255, blank=True, verbose_name="Представление объекта"
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP-адрес"
    )
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")
    extra = models.JSONField(default=dict, blank=True, verbose_name="Дополнительно")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время", db_index=True)

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал аудита"
        ordering = ["-timestamp"]

    def __str__(self):
        user_str = str(self.user) if self.user else "Аноним"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {user_str} — {self.get_action_display()}"

    def save(self, *args, **kwargs):
        """Запрещаем изменение существующих записей."""
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Записи журнала нельзя изменять")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Запрещаем удаление записей аудита."""
        raise PermissionError("Записи журнала нельзя удалять")
