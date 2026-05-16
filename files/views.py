"""API-представления для работы с файлами (DRF)."""

import io
from django.http import FileResponse
from django.shortcuts import get_object_or_404

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
from .access import (
    can_access_file,
    can_grant_file_permission,
    can_delete_file,
    can_share_file,
    get_accessible_files,
)
from audit.models import AuditLog
from audit.utils import log_action


class FileUploadView(APIView):
    """POST /api/v1/files/upload/ — загрузка и шифрование файла."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = request.FILES["file"]
        raw_data = uploaded.read()

        checksum = compute_checksum(raw_data)
        encrypted_data = encrypt_file(raw_data)
        from django.core.files.base import ContentFile
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
    """GET /api/v1/files/ — список доступных файлов."""

    permission_classes = [IsAuthenticated]
    serializer_class = FileListSerializer

    def get_queryset(self):
        return get_accessible_files(self.request.user)


class FileDetailView(generics.RetrieveAPIView):
    """GET /api/v1/files/<id>/ — метаданные файла."""

    permission_classes = [IsAuthenticated]
    serializer_class = FileDetailSerializer

    def get_object(self):
        file_obj = get_object_or_404(File, pk=self.kwargs["pk"], status=File.Status.ACTIVE)
        if not can_access_file(self.request.user, file_obj, self.request):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к этому файлу")
        log_action(self.request, AuditLog.Action.FILE_VIEW, obj=file_obj)
        return file_obj


class FileDownloadView(APIView):
    """GET /api/v1/files/<id>/download/ — скачивание файла."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not can_access_file(request.user, file_obj, request):
            return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

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
        response["X-Checksum-SHA256"] = file_obj.checksum
        return response


class FileDeleteView(APIView):
    """DELETE /api/v1/files/<id>/delete/ — мягкое удаление файла."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not can_delete_file(request.user, file_obj):
            log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

        file_obj.status = File.Status.DELETED
        file_obj.save(update_fields=["status", "updated_at"])

        log_action(request, AuditLog.Action.FILE_DELETE, obj=file_obj)
        return Response({"detail": "Файл удалён"}, status=status.HTTP_200_OK)


class FileShareView(APIView):
    """POST /api/v1/files/<id>/share/ — предоставление доступа."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not can_share_file(request.user, file_obj):
            return Response(
                {"detail": "Нет прав для передачи доступа к файлу"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FilePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access = serializer.validated_data["access"]
        effect = serializer.validated_data["effect"]

        if not can_grant_file_permission(request.user, file_obj, access):
            return Response(
                {"detail": "Нельзя выдать право выше собственного"},
                status=status.HTTP_403_FORBIDDEN,
            )

        lookup, defaults = _build_file_permission_data(
            file_obj,
            request.user,
            serializer.validated_data,
        )

        perm, created = FilePermission.objects.update_or_create(
            **lookup,
            defaults=defaults,
        )

        extra = {
            "file": str(file_obj.id),
            "file_name": file_obj.original_name,
            "subject": perm.subject_label,
            "access": access,
            "effect": effect,
            "created": created,
        }
        if perm.user_id:
            extra["target_user"] = perm.user.email
        log_action(request, AuditLog.Action.PERMISSION_GRANT, obj=perm, extra=extra)
        action = "создан" if created else "обновлён"
        return Response(
            {
                "detail": f"Доступ {action} для {perm.subject_label}",
                "permission": {
                    "id": perm.id,
                    "subject": perm.subject_label,
                    "access": perm.access,
                    "effect": perm.effect,
                },
            },
            status=status.HTTP_200_OK,
        )


class FilePermissionDeleteView(APIView):
    """DELETE /api/v1/files/permissions/<id>/delete/ — отзыв доступа."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        perm = get_object_or_404(
            FilePermission.objects.select_related("file", "user", "department"),
            pk=pk,
        )

        if not can_share_file(request.user, perm.file):
            return Response(
                {"detail": "Нет прав для отзыва доступа к файлу"},
                status=status.HTTP_403_FORBIDDEN,
            )

        extra = {
            "file": str(perm.file_id),
            "file_name": perm.file.original_name,
            "subject": perm.subject_label,
            "access": perm.access,
            "effect": perm.effect,
        }
        if perm.user_id:
            extra["target_user"] = perm.user.email
        log_action(request, AuditLog.Action.PERMISSION_REVOKE, obj=perm, extra=extra)
        subject = perm.subject_label
        perm.delete()
        return Response(
            {"detail": f"Доступ для {subject} отозван"},
            status=status.HTTP_200_OK,
        )


def _build_file_permission_data(file_obj, granted_by, data):
    subject_type = data["subject_type"]
    access = data["access"]
    defaults = {
        "access": access,
        "effect": data["effect"],
        "granted_by": granted_by,
    }

    if subject_type == FilePermissionSerializer.SubjectType.USER:
        target_user = data["target_user"]
        return (
            {"file": file_obj, "user": target_user, "access": access},
            defaults | {"department": None, "department_role": ""},
        )

    department = data["department"]
    department_role = ""
    if subject_type == FilePermissionSerializer.SubjectType.DEPARTMENT_ROLE:
        department_role = data["department_role"]

    return (
        {
            "file": file_obj,
            "department": department,
            "department_role": department_role,
            "access": access,
        },
        defaults | {"user": None},
    )
