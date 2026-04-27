"""Модели для папок, файлов, категорий и прав доступа."""

import uuid
import os
from django.db import models
from django.conf import settings


class FileCategory(models.Model):
    """Категория файлов с групповым доступом по отделам."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    departments = models.ManyToManyField(
        "users.Department",
        blank=True,
        related_name="file_categories",
        verbose_name="Разрешённые отделы",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        verbose_name = "Категория файлов"
        verbose_name_plural = "Категории файлов"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def department_list(self):
        return ", ".join(self.departments.values_list("name", flat=True)) or "—"


class Folder(models.Model):
    """
    Папка для организации файлов.

    Поддерживает произвольную вложенность через self-referential FK.
    parent=None означает корневую папку пользователя.

    Пример дерева:
        HR документы/          (parent=None)
        ├── Кадры 2024/        (parent=HR документы)
        │   ├── Январь/        (parent=Кадры 2024)
        │   └── Февраль/       (parent=Кадры 2024)
        └── Договоры/          (parent=HR документы)
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
        verbose_name="Отдел (для групповых папок)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменена")

    class Meta:
        verbose_name = "Папка"
        verbose_name_plural = "Папки"
        # Уникальность: одно имя в одной папке у одного владельца
        unique_together = ["name", "parent", "owner"]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        """
        Возвращает список папок от корня до текущей (включительно).
        Используется для хлебных крошек в интерфейсе.

        Пример: [HR документы, Кадры 2024, Январь]
        """
        crumbs = []
        node = self
        while node is not None:
            crumbs.append(node)
            node = node.parent
        return list(reversed(crumbs))

    def get_ancestors_ids(self):
        """Возвращает set UUID всех папок-предков. Нужен для проверки доступа."""
        ids = set()
        node = self.parent
        while node is not None:
            ids.add(node.id)
            node = node.parent
        return ids

    @property
    def full_path(self):
        """Полный путь папки в виде строки: HR / Кадры 2024 / Январь"""
        return " / ".join(f.name for f in self.get_breadcrumbs())


def upload_to(instance, filename):
    """Сохраняем файлы в подпапку по UUID владельца."""
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
    category = models.ForeignKey(
        FileCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="files",
        verbose_name="Категория",
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
