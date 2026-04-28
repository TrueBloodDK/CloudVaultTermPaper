"""Веб-представления панели управления (только для администраторов)."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from users.models import User, Department, DepartmentMembership


class AdminRequiredMixin(LoginRequiredMixin):
    login_url = "/auth/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            messages.error(request, "Доступ только для администраторов")
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
