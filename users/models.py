"""Кастомная модель пользователя с ролями и отделами."""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class Department(models.Model):
    """
    Отдел организации.
    Используется для группового доступа к категориям файлов.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        return self.users.count()


class UserManager(BaseUserManager):
    """Менеджер для создания пользователей и суперпользователей."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Пользователь системы.

    Роли:
        ADMIN   — полный доступ ко всем файлам и настройкам
        MANAGER — может управлять файлами своей группы
        USER    — доступ только к своим файлам + файлам отдела
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        USER = "user", "Пользователь"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Email")
    full_name = models.CharField(max_length=255, verbose_name="Полное имя")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        verbose_name="Роль",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Отдел",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_staff = models.BooleanField(default=False, verbose_name="Персонал")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    last_login_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP последнего входа"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager(self):
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)


class DepartmentMembership(models.Model):
    """
    Роль пользователя внутри конкретного отдела.

    Отличается от глобальной роли User.role:
      - User.role = admin/manager/user — глобальная роль в системе
      - DepartmentMembership.role = head/member — роль в конкретном отделе

    Один пользователь может быть руководителем HR
    и рядовым сотрудником в проектной группе одновременно.
    """

    class Role(models.TextChoices):
        HEAD   = "head",   "Руководитель отдела"
        MEMBER = "member", "Сотрудник"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Пользователь",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Отдел",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
        verbose_name="Роль в отделе",
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_memberships",
        verbose_name="Назначил",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Назначен")

    class Meta:
        verbose_name = "Членство в отделе"
        verbose_name_plural = "Членства в отделах"
        unique_together = ["user", "department"]
        ordering = ["department", "role"]

    def __str__(self):
        return f"{self.user} — {self.department} ({self.get_role_display()})"

    @property
    def is_head(self):
        return self.role == self.Role.HEAD
