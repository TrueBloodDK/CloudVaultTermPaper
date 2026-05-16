"""Веб-представления для файлов и папок."""

import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.views import View
from django.core.files.base import ContentFile

from files.models import File, FilePermission, Folder
from files.encryption import encrypt_file, decrypt_file, compute_checksum
from files.serializers import FileUploadSerializer
from files.access import (
    can_access_file, can_access_folder, can_delete_file,
    can_grant_file_permission, can_share_file,
    can_upload_to_folder, can_manage_folder,
    get_accessible_files, get_accessible_folders,
)
from users.models import Department, DepartmentMembership, User
from users.rbac import PermissionEffect
from audit.models import AuditLog
from audit.utils import log_action


class FileListView(LoginRequiredMixin, View):
    login_url = "/auth/login/"
    template_name = "files/list.html"

    def get(self, request):
        folder_id = request.GET.get("folder")
        current_folder = None
        breadcrumbs = []

        if folder_id:
            current_folder = get_object_or_404(Folder, pk=folder_id)
            if not can_access_folder(request.user, current_folder):
                messages.error(request, "Нет доступа к этой папке")
                return redirect("files:list")
            breadcrumbs = current_folder.get_breadcrumbs()

        subfolders = get_accessible_folders(request.user, parent=current_folder)
        files = list(
            get_accessible_files(request.user)
            .filter(folder=current_folder)
            .prefetch_related("permissions__user", "permissions__department")
        )
        for file_obj in files:
            file_obj.can_manage_permissions = can_share_file(request.user, file_obj)
            file_obj.can_delete = can_delete_file(request.user, file_obj)

        return render(request, self.template_name, {
            "files": files,
            "subfolders": subfolders,
            "current_folder": current_folder,
            "breadcrumbs": breadcrumbs,
            "can_upload": _can_upload_here(request.user, current_folder),
            "departments": Department.objects.all(),
            "users": User.objects.filter(is_active=True).order_by("full_name"),
            "permission_actions": FilePermission.Access.choices,
            "permission_effects": PermissionEffect.choices,
            "department_roles": DepartmentMembership.Role.choices,
        })


def _can_upload_here(user, folder):
    if user.is_system_admin or folder is None:
        return True
    return can_upload_to_folder(user, folder)


# ── Папки ────────────────────────────────────────────────────────────────────

class FolderCreateView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request):
        name = request.POST.get("name", "").strip()
        parent_id = request.POST.get("parent") or None
        parent = None

        if parent_id:
            parent = get_object_or_404(Folder, pk=parent_id)
            if not can_upload_to_folder(request.user, parent):
                messages.error(request, "Нет прав для создания папки здесь")
                return _back(parent_id)

        if not name:
            messages.error(request, "Название папки обязательно")
            return _back(parent_id)

        if Folder.objects.filter(name=name, parent=parent, owner=request.user).exists():
            messages.error(request, f"Папка «{name}» уже существует здесь")
            return _back(parent_id)

        Folder.objects.create(
            name=name,
            owner=request.user,
            parent=parent,
            department=parent.department if parent else request.user.department,
        )
        messages.success(request, f"Папка «{name}» создана")
        return _back(parent_id)


class FolderDeleteView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk)

        if not can_manage_folder(request.user, folder):
            messages.error(request, "Нет прав для удаления этой папки")
            return _back(str(folder.parent_id) if folder.parent else None)

        parent_id = str(folder.parent_id) if folder.parent else None
        name = folder.name
        _soft_delete_folder_contents(folder)
        folder.delete()
        messages.success(request, f"Папка «{name}» удалена")
        return _back(parent_id)


class FolderRenameView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk)

        if not can_manage_folder(request.user, folder):
            messages.error(request, "Нет прав для переименования")
            return _back(str(folder.parent_id) if folder.parent else None)

        new_name = request.POST.get("name", "").strip()
        if not new_name:
            messages.error(request, "Название не может быть пустым")
            return _back(str(folder.parent_id) if folder.parent else None)

        folder.name = new_name
        folder.save(update_fields=["name", "updated_at"])
        messages.success(request, f"Папка переименована в «{new_name}»")
        return _back(str(folder.parent_id) if folder.parent else None)


# ── Файлы ────────────────────────────────────────────────────────────────────

class FileUploadView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request):
        folder_id = request.POST.get("folder") or None
        folder = None

        if folder_id:
            folder = get_object_or_404(Folder, pk=folder_id)
            if not can_upload_to_folder(request.user, folder):
                messages.error(request, "Нет прав для загрузки в эту папку")
                return _back(folder_id)

        data = request.POST.copy()
        data["file"] = request.FILES.get("file")
        serializer = FileUploadSerializer(data=data)

        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, str(error))
            return _back(folder_id)

        uploaded = request.FILES["file"]
        raw_data = uploaded.read()

        file_obj = File.objects.create(
            owner=request.user,
            original_name=uploaded.name,
            encrypted_file=ContentFile(encrypt_file(raw_data), name=uploaded.name),
            mime_type=uploaded.content_type,
            size=uploaded.size,
            checksum=compute_checksum(raw_data),
            description=serializer.validated_data.get("description", ""),
            folder=folder,
        )

        log_action(request, AuditLog.Action.FILE_UPLOAD, obj=file_obj,
                   extra={"size": file_obj.size})
        messages.success(request, f"Файл «{file_obj.original_name}» загружен")
        return _back(folder_id)


class FileDownloadView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def get(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not can_access_file(request.user, file_obj, request):
            messages.error(request, "Нет доступа к этому файлу")
            return redirect("files:list")

        raw_data = decrypt_file(file_obj.encrypted_file.read())
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

        if not can_delete_file(request.user, file_obj):
            log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            messages.error(request, "Нет прав для удаления этого файла")
            return redirect("files:list")

        folder_id = str(file_obj.folder_id) if file_obj.folder else None
        name = file_obj.original_name
        file_obj.status = File.Status.DELETED
        file_obj.save(update_fields=["status", "updated_at"])

        log_action(request, AuditLog.Action.FILE_DELETE, obj=file_obj)
        messages.success(request, f"Файл «{name}» удалён")
        return _back(folder_id)


class FileShareView(LoginRequiredMixin, View):
    login_url = "/auth/login/"

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not can_share_file(request.user, file_obj):
            messages.error(request, "Только руководитель отдела или администратор может расшаривать файлы")
            return redirect("files:list")

        subject_type = request.POST.get("subject_type", "user")
        access = request.POST.get("access", FilePermission.Access.READ)
        effect = request.POST.get("effect", PermissionEffect.ALLOW)

        if access not in [choice[0] for choice in FilePermission.Access.choices]:
            messages.error(request, "Неверный уровень доступа")
            return redirect("files:list")

        if effect not in [choice[0] for choice in PermissionEffect.choices]:
            messages.error(request, "Неверное правило доступа")
            return redirect("files:list")

        if not can_grant_file_permission(request.user, file_obj, access):
            messages.error(request, "Нельзя выдать право выше собственного")
            return redirect("files:list")

        subject, lookup, defaults = _build_file_permission_lookup(
            request,
            file_obj,
            subject_type,
            access,
            effect,
        )
        if subject is None:
            return _back(str(file_obj.folder_id) if file_obj.folder else None)

        permission, created = FilePermission.objects.update_or_create(
            **lookup,
            defaults=defaults,
        )
        log_action(request, AuditLog.Action.PERMISSION_GRANT, obj=permission, extra={
            "file": str(file_obj.id),
            "file_name": file_obj.original_name,
            "subject": permission.subject_label,
            "access": access,
            "effect": effect,
            "created": created,
        })
        messages.success(request, f"Доступ для {subject} сохранён")
        return _back(str(file_obj.folder_id) if file_obj.folder else None)


class FilePermissionDeleteView(LoginRequiredMixin, View):
    """POST /files/permissions/<id>/delete/ — отозвать право на файл."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        permission = get_object_or_404(
            FilePermission.objects.select_related("file", "user", "department"),
            pk=pk,
        )
        file_obj = permission.file
        folder_id = str(file_obj.folder_id) if file_obj.folder else None

        if not can_share_file(request.user, file_obj):
            messages.error(request, "Нет прав для отзыва доступа")
            return _back(folder_id)

        subject = permission.subject_label
        access = permission.access
        effect = permission.effect
        log_action(request, AuditLog.Action.PERMISSION_REVOKE, obj=permission, extra={
            "file": str(file_obj.id),
            "file_name": file_obj.original_name,
            "subject": subject,
            "access": access,
            "effect": effect,
        })
        permission.delete()
        messages.success(request, f"Доступ для {subject} отозван")
        return _back(folder_id)


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _back(folder_id):
    if folder_id:
        return redirect(f"/files/?folder={folder_id}")
    return redirect("files:list")


def _soft_delete_folder_contents(folder):
    File.objects.filter(folder=folder, status=File.Status.ACTIVE).update(
        status=File.Status.DELETED
    )
    for child in folder.children.all():
        _soft_delete_folder_contents(child)


def _build_file_permission_lookup(request, file_obj, subject_type, access, effect):
    defaults = {
        "access": access,
        "effect": effect,
        "granted_by": request.user,
    }

    if subject_type == "user":
        target_email = request.POST.get("user_email", "").strip().lower()
        try:
            target_user = User.objects.get(email=target_email)
        except User.DoesNotExist:
            messages.error(request, f"Пользователь «{target_email}» не найден")
            return None, None, None

        if target_user == request.user:
            messages.error(request, "Нельзя предоставить доступ самому себе")
            return None, None, None

        return (
            target_user,
            {"file": file_obj, "user": target_user, "access": access},
            defaults | {"department": None, "department_role": ""},
        )

    if subject_type in ("department", "department_role"):
        dept_id = request.POST.get("department")
        if not dept_id:
            messages.error(request, "Выберите отдел")
            return None, None, None

        department = get_object_or_404(Department, pk=dept_id)
        department_role = ""
        if subject_type == "department_role":
            department_role = request.POST.get(
                "department_role",
                DepartmentMembership.Role.MEMBER,
            )
            if department_role not in [choice[0] for choice in DepartmentMembership.Role.choices]:
                messages.error(request, "Неверная роль в отделе")
                return None, None, None

        return (
            department,
            {
                "file": file_obj,
                "department": department,
                "department_role": department_role,
                "access": access,
            },
            defaults | {"user": None},
        )

    messages.error(request, "Неверный адресат права")
    return None, None, None


class FolderChangeDeptView(LoginRequiredMixin, View):
    """POST /files/folders/<uuid>/dept/ — сменить отдел папки (только system_admin)."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        if not request.user.is_system_admin:
            messages.error(request, "Только администратор системы может менять отдел папки")
            return redirect("files:list")

        folder = get_object_or_404(Folder, pk=pk)
        dept_id = request.POST.get("department") or None

        from users.models import Department
        dept = None
        if dept_id:
            dept = get_object_or_404(Department, pk=dept_id)

        old_dept = str(folder.department) if folder.department else "—"
        folder.department = dept
        folder.save(update_fields=["department", "updated_at"])

        new_dept = str(dept) if dept else "—"
        messages.success(
            request,
            f"Отдел папки «{folder.name}» изменён: {old_dept} → {new_dept}"
        )
        parent_id = str(folder.parent_id) if folder.parent else None
        return _back(parent_id)
