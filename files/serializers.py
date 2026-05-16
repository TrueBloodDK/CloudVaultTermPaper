"""Сериализаторы для файлов."""

from rest_framework import serializers
from django.conf import settings
from .models import File, FilePermission
from users.models import Department, DepartmentMembership, User
from users.rbac import PermissionEffect


class FileUploadSerializer(serializers.ModelSerializer):
    """Загрузка нового файла."""

    file = serializers.FileField(write_only=True)

    class Meta:
        model = File
        fields = ["file", "description"]

    def validate_file(self, value):
        # Проверяем MIME-тип
        if value.content_type not in settings.ALLOWED_FILE_TYPES:
            raise serializers.ValidationError(
                f"Тип файла '{value.content_type}' не разрешён."
            )
        # Проверяем размер
        if value.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            raise serializers.ValidationError("Файл превышает максимальный размер 50 МБ.")
        return value


class FileListSerializer(serializers.ModelSerializer):
    """Список файлов пользователя."""

    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = File
        fields = [
            "id", "original_name", "mime_type", "size", "size_kb",
            "description", "owner_email", "status", "created_at",
        ]


class FileDetailSerializer(serializers.ModelSerializer):
    """Детальная информация о файле."""

    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            "id", "original_name", "mime_type", "size", "size_kb",
            "checksum", "description", "owner_email",
            "status", "created_at", "updated_at", "permissions",
        ]

    def get_permissions(self, obj):
        perms = obj.permissions.select_related("user", "department").all()
        return [
            {
                "subject": p.subject_label,
                "user": p.user.email if p.user_id else None,
                "department": p.department.name if p.department_id else None,
                "department_role": p.department_role or None,
                "access": p.access,
                "effect": p.effect,
                "granted_at": p.granted_at,
            }
            for p in perms
        ]


class FilePermissionSerializer(serializers.ModelSerializer):
    """Предоставление доступа к файлу пользователю, отделу или роли отдела."""

    class SubjectType:
        USER = "user"
        DEPARTMENT = "department"
        DEPARTMENT_ROLE = "department_role"

        CHOICES = (
            (USER, "Пользователь"),
            (DEPARTMENT, "Отдел"),
            (DEPARTMENT_ROLE, "Роль в отделе"),
        )

    subject_type = serializers.ChoiceField(
        choices=SubjectType.CHOICES,
        default=SubjectType.USER,
        write_only=True,
    )
    user_email = serializers.EmailField(write_only=True, required=False)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        write_only=True,
    )
    department_role = serializers.ChoiceField(
        choices=DepartmentMembership.Role.choices,
        required=False,
        allow_blank=True,
        write_only=True,
    )
    access = serializers.ChoiceField(choices=FilePermission.Access.choices)
    effect = serializers.ChoiceField(
        choices=PermissionEffect.choices,
        default=PermissionEffect.ALLOW,
    )

    class Meta:
        model = FilePermission
        fields = [
            "subject_type",
            "user_email",
            "department",
            "department_role",
            "access",
            "effect",
        ]

    def validate(self, attrs):
        subject_type = attrs.get("subject_type", self.SubjectType.USER)

        if subject_type == self.SubjectType.USER:
            email = attrs.get("user_email")
            if not email:
                raise serializers.ValidationError({
                    "user_email": "Email пользователя обязателен."
                })
            try:
                attrs["target_user"] = User.objects.get(email=email.lower())
            except User.DoesNotExist as exc:
                raise serializers.ValidationError({
                    "user_email": "Пользователь не найден."
                }) from exc
            return attrs

        if subject_type in (self.SubjectType.DEPARTMENT, self.SubjectType.DEPARTMENT_ROLE):
            if not attrs.get("department"):
                raise serializers.ValidationError({
                    "department": "Отдел обязателен."
                })
            if subject_type == self.SubjectType.DEPARTMENT_ROLE and not attrs.get("department_role"):
                raise serializers.ValidationError({
                    "department_role": "Роль в отделе обязательна."
                })
            return attrs

        raise serializers.ValidationError({"subject_type": "Неверный адресат права."})
