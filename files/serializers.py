"""Сериализаторы для файлов."""

from rest_framework import serializers
from django.conf import settings
from .models import File, FilePermission


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
        perms = obj.permissions.select_related("user").all()
        return [
            {"user": p.user.email, "access": p.access, "granted_at": p.granted_at}
            for p in perms
        ]


class FilePermissionSerializer(serializers.ModelSerializer):
    """Предоставление доступа к файлу другому пользователю."""

    user_email = serializers.EmailField(write_only=True)

    class Meta:
        model = FilePermission
        fields = ["user_email", "access"]
