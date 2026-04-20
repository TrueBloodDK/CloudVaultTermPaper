"""Модели для хранения файлов и метаданных."""

import uuid
import os
from django.db import models
from django.conf import settings


def upload_to(instance, filename):
    """Сохраняем файлы в подпапку по UUID пользователя — не по имени."""
    ext = os.path.splitext(filename)[1]
    return f"uploads/{instance.owner.id}/{uuid.uuid4()}{ext}"


class File(models.Model):
    """
    Метаданные файла.
    Сам файл хранится зашифрованным на диске (поле encrypted_file).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        DELETED = "deleted", "Удалён"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="Владелец",
    )
    original_name = models.CharField(max_length=255, verbose_name="Оригинальное имя")
    encrypted_file = models.FileField(upload_to=upload_to, verbose_name="Файл (зашифрован)")
    mime_type = models.CharField(max_length=100, verbose_name="MIME-тип")
    size = models.PositiveBigIntegerField(verbose_name="Размер (байт)")
    checksum = models.CharField(max_length=64, verbose_name="SHA-256 контрольная сумма")
    description = models.TextField(blank=True, verbose_name="Описание")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Загружен")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменён")

    class Meta:
        verbose_name = "Файл"
        verbose_name_plural = "Файлы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_name} ({self.owner})"

    @property
    def size_kb(self):
        return round(self.size / 1024, 2)


class FilePermission(models.Model):
    """
    Права доступа к файлу для конкретного пользователя.
    Позволяет делиться файлами с коллегами.
    """

    class Access(models.TextChoices):
        READ = "read", "Чтение"
        DOWNLOAD = "download", "Скачивание"

    file = models.ForeignKey(
        File, on_delete=models.CASCADE, related_name="permissions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="file_permissions",
    )
    access = models.CharField(max_length=10, choices=Access.choices, default=Access.READ)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="granted_permissions",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Право доступа"
        verbose_name_plural = "Права доступа"
        unique_together = ["file", "user"]

    def __str__(self):
        return f"{self.user} → {self.file.original_name} ({self.access})"
