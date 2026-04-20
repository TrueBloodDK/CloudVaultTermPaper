"""Представления для работы с файлами."""

import io
from django.http import FileResponse
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import File, FilePermission
from .serializers import (
    FileUploadSerializer,
    FileListSerializer,
    FileDetailSerializer,
    FilePermissionSerializer,
)
from .encryption import encrypt_file, decrypt_file, compute_checksum
from users.models import User
from users.permissions import IsOwnerOrAdmin, IsAdmin
from audit.models import AuditLog
from audit.utils import log_action


class FileUploadView(APIView):
    """POST /api/v1/files/ — загрузка и шифрование файла."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = request.FILES["file"]
        raw_data = uploaded.read()

        # Считаем контрольную сумму до шифрования
        checksum = compute_checksum(raw_data)

        # Шифруем содержимое
        encrypted_data = encrypt_file(raw_data)
        encrypted_file = ContentFile(encrypted_data, name=uploaded.name)

        file_obj = File.objects.create(
            owner=request.user,
            original_name=uploaded.name,
            encrypted_file=encrypted_file,
            mime_type=uploaded.content_type,
            size=uploaded.size,
            checksum=checksum,
            description=serializer.validated_data.get("description", ""),
        )

        log_action(request, AuditLog.Action.FILE_UPLOAD, obj=file_obj,
                   extra={"size": file_obj.size, "mime": file_obj.mime_type})

        return Response(
            FileDetailSerializer(file_obj).data,
            status=status.HTTP_201_CREATED,
        )


class FileListView(generics.ListAPIView):
    """GET /api/v1/files/ — список файлов текущего пользователя."""

    permission_classes = [IsAuthenticated]
    serializer_class = FileListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            # Администратор видит все активные файлы
            return File.objects.filter(status=File.Status.ACTIVE).select_related("owner")

        # Обычный пользователь видит свои файлы + файлы с предоставленным доступом
        return File.objects.filter(
            Q(owner=user) | Q(permissions__user=user),
            status=File.Status.ACTIVE,
        ).select_related("owner").distinct()


class FileDetailView(generics.RetrieveAPIView):
    """GET /api/v1/files/<id>/ — метаданные файла."""

    permission_classes = [IsAuthenticated]
    serializer_class = FileDetailSerializer

    def get_object(self):
        file_obj = get_object_or_404(File, pk=self.kwargs["pk"], status=File.Status.ACTIVE)
        self._check_access(file_obj)
        log_action(self.request, AuditLog.Action.FILE_VIEW, obj=file_obj)
        return file_obj

    def _check_access(self, file_obj):
        user = self.request.user
        if user.is_admin or file_obj.owner == user:
            return
        has_perm = file_obj.permissions.filter(user=user).exists()
        if not has_perm:
            log_action(self.request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к этому файлу")


class FileDownloadView(APIView):
    """GET /api/v1/files/<id>/download/ — скачивание (расшифровка) файла."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        # Проверяем права: владелец, admin или явный доступ
        user = request.user
        if not user.is_admin and file_obj.owner != user:
            has_perm = file_obj.permissions.filter(
                user=user,
                access__in=[FilePermission.Access.READ, FilePermission.Access.DOWNLOAD],
            ).exists()
            if not has_perm:
                log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
                return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

        # Читаем и расшифровываем
        encrypted_data = file_obj.encrypted_file.read()
        raw_data = decrypt_file(encrypted_data)

        log_action(request, AuditLog.Action.FILE_DOWNLOAD, obj=file_obj,
                   extra={"size": file_obj.size})

        response = FileResponse(
            io.BytesIO(raw_data),
            content_type=file_obj.mime_type,
            as_attachment=True,
            filename=file_obj.original_name,
        )
        # Заголовок с контрольной суммой — клиент может проверить целостность
        response["X-Checksum-SHA256"] = file_obj.checksum
        return response


class FileDeleteView(APIView):
    """DELETE /api/v1/files/<id>/ — мягкое удаление файла."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not request.user.is_admin and file_obj.owner != request.user:
            log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

        file_obj.status = File.Status.DELETED
        file_obj.save(update_fields=["status", "updated_at"])

        log_action(request, AuditLog.Action.FILE_DELETE, obj=file_obj)

        return Response({"detail": "Файл удалён"}, status=status.HTTP_200_OK)


class FileShareView(APIView):
    """POST /api/v1/files/<id>/share/ — предоставление доступа к файлу."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not request.user.is_admin and file_obj.owner != request.user:
            return Response({"detail": "Только владелец может делиться файлом"},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = FilePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user = get_object_or_404(User, email=serializer.validated_data["user_email"])

        perm, created = FilePermission.objects.update_or_create(
            file=file_obj,
            user=target_user,
            defaults={
                "access": serializer.validated_data["access"],
                "granted_by": request.user,
            },
        )

        action = "создан" if created else "обновлён"
        return Response(
            {"detail": f"Доступ {action} для {target_user.email}"},
            status=status.HTTP_200_OK,
        )
