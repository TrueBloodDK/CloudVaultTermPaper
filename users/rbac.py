"""RBAC constants shared by access checks, serializers and UI."""

from django.db import models


class PermissionAction(models.TextChoices):
    """Actions that can be granted on protected resources."""

    VIEW = "view", "Просмотр в списке"
    READ = "read", "Чтение"
    DOWNLOAD = "download", "Скачивание"
    UPLOAD = "upload", "Загрузка"
    CREATE = "create", "Создание"
    UPDATE = "update", "Изменение"
    DELETE = "delete", "Удаление"
    SHARE = "share", "Передача доступа"
    MANAGE = "manage", "Управление"
    AUDIT = "audit", "Просмотр аудита"


class ResourceType(models.TextChoices):
    """Resource kinds that participate in RBAC checks."""

    FILE = "file", "Файл"
    FOLDER = "folder", "Папка"


class PermissionEffect(models.TextChoices):
    """Whether a rule grants or blocks an action."""

    ALLOW = "allow", "Разрешить"
    DENY = "deny", "Запретить"
