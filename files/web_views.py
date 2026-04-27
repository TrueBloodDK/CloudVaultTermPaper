"""Веб-представления для файлов и папок."""

import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.db.models import Q
from django.views import View
from django.core.files.base import ContentFile

from files.models import File, FilePermission, FileCategory, Folder
from files.encryption import encrypt_file, decrypt_file, compute_checksum
from files.serializers import FileUploadSerializer
from files.access import can_access_file, get_accessible_files
from users.models import User
from audit.models import AuditLog
from audit.utils import log_action


class FileListView(LoginRequiredMixin, View):
    """
    Главная страница — содержимое текущей папки.

    GET /files/                     — корень (папки и файлы без папки)
    GET /files/?folder=<uuid>       — содержимое конкретной папки
    """
    login_url = "/auth/login/"
    template_name = "files/list.html"

    def get(self, request):
        user = request.user
        folder_id = request.GET.get("folder")
        current_folder = None
        breadcrumbs = []

        if folder_id:
            current_folder = get_object_or_404(
                Folder, pk=folder_id
            )
            # Проверяем доступ к папке
            if not _can_access_folder(user, current_folder):
                messages.error(request, "Нет доступа к этой папке")
                return redirect("files:list")
            breadcrumbs = current_folder.get_breadcrumbs()

        # Подпапки текущего уровня
        if user.is_admin:
            subfolders = Folder.objects.filter(parent=current_folder)
        else:
            subfolders = Folder.objects.filter(
                parent=current_folder,
            ).filter(
                Q(owner=user) |
                Q(department__in=user.department_id and [user.department_id] or [])
            )

        # Файлы текущего уровня
        accessible = get_accessible_files(user)
        files = accessible.filter(folder=current_folder)

        categories = FileCategory.objects.all()
        # Папки для выбора при создании вложенной папки
        user_folders = Folder.objects.filter(
            Q(owner=user) | (Q(department=user.department) if user.department else Q())
        )

        return render(request, self.template_name, {
            "files": files,
            "subfolders": subfolders,
            "current_folder": current_folder,
            "breadcrumbs": breadcrumbs,
            "categories": categories,
            "user_folders": user_folders,
        })


def _can_access_folder(user, folder):
    """Проверяет доступ пользователя к папке."""
    if user.is_admin:
        return True
    if folder.owner == user:
        return True
    if folder.department and user.department == folder.department:
        return True
    return False


# ── Папки ────────────────────────────────────────────────────────────────────

class FolderCreateView(LoginRequiredMixin, View):
    """POST /files/folders/create/ — создать папку."""
    login_url = "/auth/login/"

    def post(self, request):
        name = request.POST.get("name", "").strip()
        parent_id = request.POST.get("parent") or None

        if not name:
            messages.error(request, "Название папки обязательно")
            return _redirect_to_folder(parent_id)

        parent = None
        if parent_id:
            parent = get_object_or_404(Folder, pk=parent_id)
            if not _can_access_folder(request.user, parent):
                messages.error(request, "Нет доступа к родительской папке")
                return redirect("files:list")

        # Проверяем уникальность имени в данной папке
        if Folder.objects.filter(
            name=name, parent=parent, owner=request.user
        ).exists():
            messages.error(request, f"Папка «{name}» уже существует здесь")
            return _redirect_to_folder(parent_id)

        Folder.objects.create(
            name=name,
            owner=request.user,
            parent=parent,
            department=request.user.department,
        )
        messages.success(request, f"Папка «{name}» создана")
        return _redirect_to_folder(parent_id)


class FolderDeleteView(LoginRequiredMixin, View):
    """POST /files/folders/<uuid>/delete/ — удалить папку (каскадно)."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk)

        if not request.user.is_admin and folder.owner != request.user:
            messages.error(request, "Нет прав для удаления этой папки")
            return _redirect_to_folder(str(folder.parent_id) if folder.parent else None)

        parent_id = str(folder.parent_id) if folder.parent else None
        name = folder.name

        # Мягкое удаление всех файлов внутри (рекурсивно)
        _soft_delete_folder_contents(folder)
        folder.delete()

        messages.success(request, f"Папка «{name}» и всё её содержимое удалены")
        return _redirect_to_folder(parent_id)


class FolderRenameView(LoginRequiredMixin, View):
    """POST /files/folders/<uuid>/rename/ — переименовать папку."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk)

        if not request.user.is_admin and folder.owner != request.user:
            messages.error(request, "Нет прав для переименования")
            return _redirect_to_folder(str(folder.parent_id) if folder.parent else None)

        new_name = request.POST.get("name", "").strip()
        if not new_name:
            messages.error(request, "Название не может быть пустым")
            return _redirect_to_folder(str(folder.parent_id) if folder.parent else None)

        folder.name = new_name
        folder.save(update_fields=["name", "updated_at"])
        messages.success(request, f"Папка переименована в «{new_name}»")
        return _redirect_to_folder(str(folder.parent_id) if folder.parent else None)


# ── Файлы ────────────────────────────────────────────────────────────────────

class FileUploadView(LoginRequiredMixin, View):
    """POST /files/upload/ — загрузить и зашифровать файл."""
    login_url = "/auth/login/"

    def post(self, request):
        data = request.POST.copy()
        data["file"] = request.FILES.get("file")
        serializer = FileUploadSerializer(data=data)

        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, str(error))
            folder_id = request.POST.get("folder") or None
            return _redirect_to_folder(folder_id)

        uploaded = request.FILES["file"]
        raw_data = uploaded.read()

        folder_id = request.POST.get("folder") or None
        folder = None
        if folder_id:
            folder = get_object_or_404(Folder, pk=folder_id)

        category_id = request.POST.get("category") or None
        category = None
        if category_id:
            try:
                category = FileCategory.objects.get(pk=category_id)
            except FileCategory.DoesNotExist:
                pass

        file_obj = File.objects.create(
            owner=request.user,
            original_name=uploaded.name,
            encrypted_file=ContentFile(encrypt_file(raw_data), name=uploaded.name),
            mime_type=uploaded.content_type,
            size=uploaded.size,
            checksum=compute_checksum(raw_data),
            description=serializer.validated_data.get("description", ""),
            folder=folder,
            category=category,
        )

        log_action(request, AuditLog.Action.FILE_UPLOAD, obj=file_obj,
                   extra={"size": file_obj.size})
        messages.success(request, f"Файл «{file_obj.original_name}» загружен")
        return _redirect_to_folder(folder_id)


class FileDownloadView(LoginRequiredMixin, View):
    """GET /files/<uuid>/download/ — скачать файл с расшифровкой."""
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
    """POST /files/<uuid>/delete/ — мягкое удаление файла."""
    login_url = "/auth/login/"

    def post(self, request, pk):
        file_obj = get_object_or_404(File, pk=pk, status=File.Status.ACTIVE)

        if not request.user.is_admin and file_obj.owner != request.user:
            log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj)
            messages.error(request, "Нет прав для удаления")
            return redirect("files:list")

        folder_id = str(file_obj.folder_id) if file_obj.folder else None
        name = file_obj.original_name
        file_obj.status = File.Status.DELETED
        file_obj.save(update_fields=["status", "updated_at"])

        log_action(request, AuditLog.Action.FILE_DELETE, obj=file_obj)
        messages.success(request, f"Файл «{name}» удалён")
        return _redirect_to_folder(folder_id)


class FileShareView(LoginRequiredMixin, View):
    """POST /files/<uuid>/share/ — предоставить доступ к файлу."""
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
            file=file_obj, user=target_user,
            defaults={"access": access, "granted_by": request.user},
        )
        messages.success(request, f"Доступ для {target_user.email} предоставлен")
        return redirect("files:list")


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _redirect_to_folder(folder_id):
    """Редирект обратно в папку после действия."""
    if folder_id:
        return redirect(f"/files/?folder={folder_id}")
    return redirect("files:list")


def _soft_delete_folder_contents(folder):
    """
    Рекурсивно помечает все файлы внутри папки как удалённые.
    Вложенные папки удаляются каскадно через БД (on_delete=CASCADE).
    """
    File.objects.filter(folder=folder, status=File.Status.ACTIVE).update(
        status=File.Status.DELETED
    )
    for child in folder.children.all():
        _soft_delete_folder_contents(child)
