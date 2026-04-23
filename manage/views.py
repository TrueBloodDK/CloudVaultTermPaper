"""Веб-представления панели управления (только для администраторов)."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from users.models import User, Department
from files.models import FileCategory


class AdminRequiredMixin(LoginRequiredMixin):
    """Миксин — доступ только для администраторов."""
    login_url = "/auth/login/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            messages.error(request, "Доступ только для администраторов")
            return redirect("files:list")
        return super().dispatch(request, *args, **kwargs)


# ── Пользователи ─────────────────────────────────────────────────────────────

class UserListView(AdminRequiredMixin, View):
    """GET /manage/users/ — список всех пользователей."""

    def get(self, request):
        users = User.objects.select_related("department").order_by("full_name")
        departments = Department.objects.all()
        return render(request, "manage/users.html", {
            "users": users,
            "departments": departments,
        })


class UserUpdateView(AdminRequiredMixin, View):
    """POST /manage/users/<id>/ — изменить роль, отдел, статус пользователя."""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Защита: нельзя изменить самого себя через эту форму
        if user == request.user:
            messages.error(request, "Нельзя изменить собственный аккаунт через панель управления")
            return redirect("manage:users")

        role = request.POST.get("role", user.role)
        dept_id = request.POST.get("department") or None
        is_active = request.POST.get("is_active") == "1"

        if role not in [r[0] for r in User.Role.choices]:
            messages.error(request, "Неверная роль")
            return redirect("manage:users")

        user.role = role
        user.is_active = is_active
        user.department_id = dept_id
        user.save(update_fields=["role", "is_active", "department_id"])

        messages.success(request, f"Пользователь {user.full_name} обновлён")
        return redirect("manage:users")


# ── Отделы ────────────────────────────────────────────────────────────────────

class DepartmentListView(AdminRequiredMixin, View):
    """GET /manage/departments/ — список отделов."""

    def get(self, request):
        departments = Department.objects.prefetch_related(
            "users", "file_categories"
        ).order_by("name")
        return render(request, "manage/departments.html", {
            "departments": departments,
        })


class DepartmentCreateView(AdminRequiredMixin, View):
    """POST /manage/departments/create/ — создать отдел."""

    def post(self, request):
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Название отдела обязательно")
            return redirect("manage:departments")

        if Department.objects.filter(name=name).exists():
            messages.error(request, f"Отдел «{name}» уже существует")
            return redirect("manage:departments")

        Department.objects.create(name=name, description=description)
        messages.success(request, f"Отдел «{name}» создан")
        return redirect("manage:departments")


class DepartmentUpdateView(AdminRequiredMixin, View):
    """POST /manage/departments/<id>/ — изменить отдел."""

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
    """POST /manage/departments/<id>/delete/ — удалить отдел."""

    def post(self, request, pk):
        dept = get_object_or_404(Department, pk=pk)
        name = dept.name
        # Пользователи останутся, department_id станет NULL (SET_NULL)
        dept.delete()
        messages.success(request, f"Отдел «{name}» удалён")
        return redirect("manage:departments")


# ── Категории файлов ──────────────────────────────────────────────────────────

class CategoryListView(AdminRequiredMixin, View):
    """GET /manage/categories/ — список категорий."""

    def get(self, request):
        from django.db.models import Count, Q
        categories = FileCategory.objects.prefetch_related(
            "departments"
        ).annotate(
            active_files_count=Count(
                "files", filter=Q(files__status="active")
            )
        ).order_by("name")
        departments = Department.objects.all()
        return render(request, "manage/categories.html", {
            "categories": categories,
            "departments": departments,
        })


class CategoryCreateView(AdminRequiredMixin, View):
    """POST /manage/categories/create/ — создать категорию."""

    def post(self, request):
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        dept_ids = request.POST.getlist("departments")

        if not name:
            messages.error(request, "Название категории обязательно")
            return redirect("manage:categories")

        if FileCategory.objects.filter(name=name).exists():
            messages.error(request, f"Категория «{name}» уже существует")
            return redirect("manage:categories")

        cat = FileCategory.objects.create(name=name, description=description)
        if dept_ids:
            cat.departments.set(Department.objects.filter(id__in=dept_ids))

        messages.success(request, f"Категория «{name}» создана")
        return redirect("manage:categories")


class CategoryUpdateView(AdminRequiredMixin, View):
    """POST /manage/categories/<id>/ — изменить категорию."""

    def post(self, request, pk):
        cat = get_object_or_404(FileCategory, pk=pk)
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        dept_ids = request.POST.getlist("departments")

        if not name:
            messages.error(request, "Название обязательно")
            return redirect("manage:categories")

        if FileCategory.objects.filter(name=name).exclude(pk=pk).exists():
            messages.error(request, f"Категория «{name}» уже существует")
            return redirect("manage:categories")

        cat.name = name
        cat.description = description
        cat.save(update_fields=["name", "description"])
        cat.departments.set(Department.objects.filter(id__in=dept_ids))

        messages.success(request, f"Категория «{name}» обновлена")
        return redirect("manage:categories")


class CategoryDeleteView(AdminRequiredMixin, View):
    """POST /manage/categories/<id>/delete/ — удалить категорию."""

    def post(self, request, pk):
        cat = get_object_or_404(FileCategory, pk=pk)
        name = cat.name
        # Файлы останутся, category_id станет NULL (SET_NULL)
        cat.delete()
        messages.success(request, f"Категория «{name}» удалена")
        return redirect("manage:categories")
