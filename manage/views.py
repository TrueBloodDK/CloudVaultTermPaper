"""Веб-представления панели управления (только для администраторов)."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.views import View

from users.models import User, Department, DepartmentMembership
from users.rbac import PermissionAction, PermissionEffect
from audit.models import AuditLog
from audit.utils import log_action


class AdminRequiredMixin(LoginRequiredMixin):
    login_url = "/auth/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_system_admin:
            messages.error(request, "Доступ только для администратора системы")
            return redirect("files:list")
        return super().dispatch(request, *args, **kwargs)


# ── Пользователи ──────────────────────────────────────────────────────────────

class UserListView(AdminRequiredMixin, View):
    def get(self, request):
        users = User.objects.prefetch_related(
            "memberships__department"
        ).order_by("full_name")
        departments = Department.objects.all()
        return render(request, "manage/users.html", {
            "users": users,
            "departments": departments,
            "role_choices": User.Role.choices,
        })


class UserUpdateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if user == request.user:
            messages.error(request, "Нельзя изменить собственный аккаунт через панель")
            return redirect("manage:users")

        role = request.POST.get("role", user.role)
        is_active = request.POST.get("is_active") == "1"

        if role not in [r[0] for r in User.Role.choices]:
            messages.error(request, "Неверная роль")
            return redirect("manage:users")

        user.role = role
        user.is_active = is_active
        user.save(update_fields=["role", "is_active"])

        log_action(request, AuditLog.Action.ROLE_CHANGE, obj=user, extra={
            "role": role,
            "is_active": is_active,
        })
        messages.success(request, f"Пользователь {user.full_name} обновлён")
        return redirect("manage:users")


# ── Членство в отделах ────────────────────────────────────────────────────────

class MembershipCreateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        dept_id = request.POST.get("department")
        role = request.POST.get("membership_role", DepartmentMembership.Role.MEMBER)

        if not dept_id:
            messages.error(request, "Выберите отдел")
            return redirect("manage:users")

        dept = get_object_or_404(Department, pk=dept_id)
        membership, created = DepartmentMembership.objects.update_or_create(
            user=user, department=dept,
            defaults={"role": role, "assigned_by": request.user},
        )

        log_action(request, AuditLog.Action.DEPARTMENT_ASSIGN, obj=membership, extra={
            "target_user": user.email,
            "department": dept.name,
            "department_role": role,
            "created": created,
        })
        action = "добавлен в" if created else "обновлён в"
        messages.success(
            request,
            f"{user.full_name} {action} отдел «{dept.name}» "
            f"как {membership.get_role_display()}"
        )
        return redirect("manage:users")


class MembershipDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        membership = get_object_or_404(DepartmentMembership, pk=pk)
        user_name = membership.user.full_name
        dept_name = membership.department.name
        log_action(request, AuditLog.Action.DEPARTMENT_ASSIGN, obj=membership, extra={
            "target_user": membership.user.email,
            "department": dept_name,
            "revoked": True,
        })
        membership.delete()
        messages.success(request, f"{user_name} удалён из отдела «{dept_name}»")
        return redirect("manage:users")


# ── Отделы ────────────────────────────────────────────────────────────────────

class DepartmentListView(AdminRequiredMixin, View):
    def get(self, request):
        departments = Department.objects.prefetch_related(
            "memberships__user"
        ).order_by("name")
        return render(request, "manage/departments.html", {
            "departments": departments,
        })


class DepartmentCreateView(AdminRequiredMixin, View):
    def post(self, request):
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Название обязательно")
            return redirect("manage:departments")
        if Department.objects.filter(name=name).exists():
            messages.error(request, f"Отдел «{name}» уже существует")
            return redirect("manage:departments")

        Department.objects.create(name=name, description=description)
        messages.success(request, f"Отдел «{name}» создан")
        return redirect("manage:departments")


class DepartmentUpdateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Название обязательно")
            return redirect("manage:departments")
        if Department.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, f"Отдел «{name}» уже существует")
            return redirect("manage:departments")

        dept.name = name
        dept.description = description
        dept.save(update_fields=["name", "description"])
        messages.success(request, f"Отдел «{name}» обновлён")
        return redirect("manage:departments")


class DepartmentDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        name = dept.name
        dept.delete()
        messages.success(request, f"Отдел «{name}» удалён")
        return redirect("manage:departments")


# ── Папки ─────────────────────────────────────────────────────────────────────

class FolderListView(AdminRequiredMixin, View):
    """GET /manage/folders/ — все папки системы с фильтрацией."""

    def get(self, request):
        from files.models import Folder
        from django.db.models import Q

        qs = Folder.objects.select_related(
            "owner", "department", "parent"
        ).prefetch_related(
            "files",
            "permissions__user",
            "permissions__department",
        ).order_by("name")

        # Поиск
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(owner__email__icontains=q)
            )

        # Фильтр по отделу
        dept = request.GET.get("dept", "").strip()
        if dept == "none":
            qs = qs.filter(department__isnull=True)
        elif dept:
            qs = qs.filter(department_id=dept)

        return render(request, "manage/folders.html", {
            "folders": qs,
            "departments": Department.objects.all(),
            "users": User.objects.filter(is_active=True).order_by("full_name"),
            "permission_actions": PermissionAction.choices,
            "permission_effects": PermissionEffect.choices,
            "department_roles": DepartmentMembership.Role.choices,
        })


class FolderPermissionCreateView(AdminRequiredMixin, View):
    """POST /manage/folders/<uuid>/permissions/ — выдать право на папку."""

    def post(self, request, pk):
        from files.models import Folder, FolderPermission

        folder = get_object_or_404(Folder, pk=pk)
        subject_type = request.POST.get("subject_type", "").strip()
        action = request.POST.get("access", PermissionAction.VIEW)
        effect = request.POST.get("effect", PermissionEffect.ALLOW)

        if action not in PermissionAction.values:
            messages.error(request, "Неверное действие доступа")
            return redirect("manage:folders")
        if effect not in PermissionEffect.values:
            messages.error(request, "Неверный эффект правила")
            return redirect("manage:folders")

        defaults = {
            "effect": effect,
            "granted_by": request.user,
        }

        try:
            lookup = _build_folder_permission_lookup(request, folder, subject_type, action)
            permission, created = FolderPermission.objects.update_or_create(
                **lookup,
                defaults=defaults,
            )
            permission.full_clean()
            permission.save()
        except (User.DoesNotExist, Department.DoesNotExist, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect("manage:folders")

        state = "создано" if created else "обновлено"
        log_action(request, AuditLog.Action.PERMISSION_GRANT, obj=permission, extra={
            "folder": str(folder.id),
            "folder_name": folder.full_path,
            "subject": permission.subject_label,
            "access": permission.access,
            "effect": permission.effect,
            "created": created,
        })
        messages.success(
            request,
            f"Право «{permission.get_access_display()}» для {permission.subject_label} {state}"
        )
        return redirect("manage:folders")


class FolderPermissionDeleteView(AdminRequiredMixin, View):
    """POST /manage/folder-permissions/<id>/delete/ — отозвать право."""

    def post(self, request, pk):
        from files.models import FolderPermission

        permission = get_object_or_404(FolderPermission, pk=pk)
        label = permission.subject_label
        action = permission.get_access_display()
        log_action(request, AuditLog.Action.PERMISSION_REVOKE, obj=permission, extra={
            "folder": str(permission.folder_id),
            "folder_name": permission.folder.full_path,
            "subject": label,
            "access": permission.access,
            "effect": permission.effect,
        })
        permission.delete()
        messages.success(request, f"Право «{action}» для {label} отозвано")
        return redirect("manage:folders")


def _build_folder_permission_lookup(request, folder, subject_type, action):
    if subject_type == "user":
        email = request.POST.get("user_email", "").strip().lower()
        if not email:
            raise ValueError("Укажите email пользователя")
        return {
            "folder": folder,
            "user": User.objects.get(email=email),
            "department": None,
            "department_role": "",
            "access": action,
        }

    if subject_type in ("department", "department_role"):
        dept_id = request.POST.get("department") or None
        if not dept_id:
            raise ValueError("Выберите отдел")
        lookup = {
            "folder": folder,
            "user": None,
            "department": Department.objects.get(pk=dept_id),
            "access": action,
        }
        if subject_type == "department_role":
            role = request.POST.get("department_role", "")
            if role not in DepartmentMembership.Role.values:
                raise ValueError("Выберите роль внутри отдела")
            lookup["department_role"] = role
        else:
            lookup["department_role"] = ""
        return lookup

    raise ValueError("Выберите адресата права")
