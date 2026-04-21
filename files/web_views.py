"""Веб-представления для работы с файлами (Django Templates)."""

import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.db.models import Q
from django.views import View
from django.core.files.base import ContentFile

from files.models import File, FilePermission
from files.encryption import encrypt_file, decrypt_file, compute_checksum
from files.serializers import FileUploadSerializer
from users.models import User
from audit.models import AuditLog
from audit.utils import log_action


class FileListView(LoginRequiredMixin, View):
    login_url = "/auth/login/"
    template_name = "files/list.html"

    def get(self, request):
        user = request.user
        if user.is_admin:
            files = File.objects.filter(
                status=File.Status.ACTIVE
            ).select_related("owner")
        else:
            files = File.objects.filter(
                Q(owner=user) | Q(permissions__user=user),
                status=File.Status.ACTIVE,
            ).select_related("owner").distinct()

        return render(request, self.template_name, {"files": files})


class FileUploadView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request):
        data = request.POST.copy()
        data["file"] = request.FILES.get("file")
        serializer = FileUploadSerializer(data=data)
        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, str(error))
            return redirect("files:list")

        uploaded = request.FILES["file"]
        raw_data = uploaded.read()

        checksum = compute_checksum(raw_data)
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
                   extra={"size": file_obj.size})
        messages.success(request, f"Файл «{file_obj.original_name}» зашифрован и загружен")
        return redirect("files:list")


class FileDownloadView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def get(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)
        user = request.user

        # Проверяем права доступа
        if not user.is_admin and file_obj.owner != user:
            has_perm = file_obj.permissions.filter(user=user).exists()
            if not has_perm:
                log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
                messages.error(request, "Нет доступа к этому файлу")
                return redirect("files:list")

        encrypted_data = file_obj.encrypted_file.read()
        raw_data = decrypt_file(encrypted_data)

        log_action(request, AuditLog.Action.FILE_DOWNLOAD, obj=file_obj)

        response = FileResponse(
            io.BytesIO(raw_data),
            content_type=file_obj.mime_type,
            as_attachment=True,
            filename=file_obj.original_name,
        )
        response["X-Checksum-SHA256"] = file_obj.checksum
        return response


class FileDeleteView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not request.user.is_admin and file_obj.owner != request.user:
            log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            messages.error(request, "Нет прав для удаления этого файла")
            return redirect("files:list")

        name = file_obj.original_name
        file_obj.status = File.Status.DELETED
        file_obj.save(update_fields=["status", "updated_at"])

        log_action(request, AuditLog.Action.FILE_DELETE, obj=file_obj)
        messages.success(request, f"Файл «{name}» удалён")
        return redirect("files:list")


class FileShareView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not request.user.is_admin and file_obj.owner != request.user:
            messages.error(request, "Только владелец может управлять доступом")
            return redirect("files:list")

        target_email = request.POST.get("user_email", "").strip().lower()
        access = request.POST.get("access", FilePermission.Access.READ)

        try:
            target_user = User.objects.get(email=target_email)
        except User.DoesNotExist:
            messages.error(request, f"Пользователь «{target_email}» не найден")
            return redirect("files:list")

        if target_user == request.user:
            messages.error(request, "Нельзя предоставить доступ самому себе")
            return redirect("files:list")

        FilePermission.objects.update_or_create(
            file=file_obj,
            user=target_user,
            defaults={"access": access, "granted_by": request.user},
        )

        messages.success(
            request,
            f"Доступ для {target_user.email} предоставлен: {access}"
        )
        return redirect("files:list")
