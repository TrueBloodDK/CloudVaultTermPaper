"""Модели для папок, файлов и прав доступа."""

import uuid
import os
from django.db import models
from django.conf import settings


class Folder(models.Model):
    """
    Папка для организации файлов.
    Поддерживает произвольную вложенность через self-referential FK.
    parent=None означает корневую папку.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Название")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
        verbose_name="Владелец",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская папка",
    )
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="folders",
        verbose_name="Отдел",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменена")

    class Meta:
        verbose_name = "Папка"
        verbose_name_plural = "Папки"
        unique_together = ["name", "parent", "owner"]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        """Список папок от корня до текущей включительно."""
        crumbs = []
        node = self
        while node is not None:
            crumbs.append(node)
            node = node.parent
        return list(reversed(crumbs))

    def get_ancestors_ids(self):
        """UUID всех папок-предков."""
        ids = set()
        node = self.parent
        while node is not None:
            ids.add(node.id)
            node = node.parent
        return ids

    @property
    def full_path(self):
        return " / ".join(f.name for f in self.get_breadcrumbs())


def upload_to(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"uploads/{instance.owner.id}/{uuid.uuid4()}{ext}"


class File(models.Model):
    """Метаданные файла. Сам файл хранится зашифрованным на диске."""

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
    folder = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="files",
        verbose_name="Папка",
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
        ordering = ["original_name"]

    def __str__(self):
        return f"{self.original_name} ({self.owner})"

    @property
    def size_kb(self):
        return round(self.size / 1024, 2)


class FilePermission(models.Model):
    """Явный доступ к файлу для конкретного пользователя."""

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
    access = models.CharField(
        max_length=10, choices=Access.choices, default=Access.READ
    )
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
