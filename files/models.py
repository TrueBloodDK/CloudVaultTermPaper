"""Модели для папок, файлов и прав доступа."""

import uuid
import os
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from users.rbac import PermissionAction, PermissionEffect


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


class PermissionSubjectMixin(models.Model):
    """Common target fields for user, department and department-role grants."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_permissions",
        verbose_name="Пользователь",
    )
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_permissions",
        verbose_name="Отдел",
    )
    department_role = models.CharField(
        max_length=10,
        choices=[
            ("head", "Руководитель отдела"),
            ("member", "Сотрудник"),
        ],
        blank=True,
        verbose_name="Роль в отделе",
    )
    access = models.CharField(
        max_length=20,
        choices=PermissionAction.choices,
        default=PermissionAction.READ,
        verbose_name="Действие",
    )
    effect = models.CharField(
        max_length=10,
        choices=PermissionEffect.choices,
        default=PermissionEffect.ALLOW,
        verbose_name="Эффект",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_%(class)s_permissions",
        verbose_name="Выдал",
    )
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name="Выдано")

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        has_user = bool(self.user_id)
        has_department = bool(self.department_id)

        if has_user == has_department:
            raise ValidationError(
                "Право должно быть выдано либо пользователю, либо отделу."
            )
        if has_user and self.department_role:
            raise ValidationError(
                "Роль внутри отдела нельзя указывать для пользовательского права."
            )

    @property
    def subject_label(self):
        if self.user_id:
            return str(self.user)
        if self.department_id and self.department_role:
            return f"{self.department} / {self.get_department_role_display()}"
        if self.department_id:
            return str(self.department)
        return "Не задан"

    @property
    def is_allow(self):
        return self.effect == PermissionEffect.ALLOW

    @property
    def is_deny(self):
        return self.effect == PermissionEffect.DENY


class FolderPermission(PermissionSubjectMixin):
    """Явное право на папку для пользователя, отдела или роли внутри отдела."""

    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name="Папка",
    )

    class Meta:
        verbose_name = "Право доступа к папке"
        verbose_name_plural = "Права доступа к папкам"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, department__isnull=True, department_role="")
                    | models.Q(user__isnull=True, department__isnull=False)
                ),
                name="folder_permission_has_one_subject",
            ),
            models.UniqueConstraint(
                fields=["folder", "user", "access"],
                name="unique_folder_user_access",
            ),
            models.UniqueConstraint(
                fields=["folder", "department", "department_role", "access"],
                name="unique_folder_department_role_access",
            ),
        ]

    def __str__(self):
        return f"{self.subject_label} -> {self.folder.full_path} ({self.access}, {self.effect})"


class FilePermission(PermissionSubjectMixin):
    """Явное право на файл для пользователя, отдела или роли внутри отдела."""

    class Access(models.TextChoices):
        READ = PermissionAction.READ, "Чтение"
        DOWNLOAD = PermissionAction.DOWNLOAD, "Скачивание"

    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name="Файл",
    )

    class Meta:
        verbose_name = "Право доступа к файлу"
        verbose_name_plural = "Права доступа к файлам"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, department__isnull=True, department_role="")
                    | models.Q(user__isnull=True, department__isnull=False)
                ),
                name="file_permission_has_one_subject",
            ),
            models.UniqueConstraint(
                fields=["file", "user", "access"],
                name="unique_file_user_access",
            ),
            models.UniqueConstraint(
                fields=["file", "department", "department_role", "access"],
                name="unique_file_department_role_access",
            ),
        ]

    def __str__(self):
        return f"{self.subject_label} -> {self.file.original_name} ({self.access}, {self.effect})"
