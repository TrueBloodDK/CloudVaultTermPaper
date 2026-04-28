"""
Централизованная логика проверки доступа к файлам и папкам.

Уровни проверки:
  1. Глобальный admin            → полный доступ ко всему
  2. Владелец файла/папки        → полный доступ к своим объектам
  3. Явный FilePermission        → доступ к конкретному файлу
  4. Руководитель отдела (head)  → все файлы отдела, удаление, расшаривание
  5. Рядовой сотрудник (member)  → просмотр, скачивание, загрузка;
                                   удаление только своих файлов
"""

from audit.models import AuditLog
from audit.utils import log_action


def get_membership(user, department):
    """Возвращает DepartmentMembership или None. Кешируется на объекте."""
    from users.models import DepartmentMembership
    cache_key = f"_membership_{department.pk}"
    if not hasattr(user, cache_key):
        try:
            m = DepartmentMembership.objects.get(user=user, department=department)
        except DepartmentMembership.DoesNotExist:
            m = None
        setattr(user, cache_key, m)
    return getattr(user, cache_key)


def is_dept_head(user, department):
    m = get_membership(user, department)
    return m is not None and m.is_head


def is_dept_member(user, department):
    m = get_membership(user, department)
    return m is not None


def get_user_departments(user):
    """QuerySet всех отделов пользователя."""
    from users.models import Department
    return Department.objects.filter(memberships__user=user)


# ── Проверки доступа ──────────────────────────────────────────────────────────

def can_access_file(user, file_obj, request=None):
    """Может ли пользователь просматривать/скачивать файл."""
    if user.is_admin or file_obj.owner == user:
        return True
    if file_obj.permissions.filter(user=user).exists():
        return True
    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_member(user, file_obj.folder.department):
            return True
    if request is not None:
        log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj,
                   extra={"reason": "no_permission"})
    return False


def can_delete_file(user, file_obj):
    """admin и руководитель отдела — любой файл. Рядовой — только свои."""
    if user.is_admin or file_obj.owner == user:
        return True
    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_head(user, file_obj.folder.department):
            return True
    return False


def can_share_file(user, file_obj):
    """Расшаривать могут только admin и руководитель отдела."""
    if user.is_admin:
        return True
    if file_obj.folder and file_obj.folder.department_id:
        return is_dept_head(user, file_obj.folder.department)
    return file_obj.owner == user


def can_upload_to_folder(user, folder):
    """Загружать в папку могут admin, владелец и любой член отдела."""
    if user.is_admin or folder.owner == user:
        return True
    if folder.department_id:
        return is_dept_member(user, folder.department)
    return False


def can_manage_folder(user, folder):
    """Управлять папкой (удалять, переименовывать) могут admin, владелец и руководитель."""
    if user.is_admin or folder.owner == user:
        return True
    if folder.department_id:
        return is_dept_head(user, folder.department)
    return False


# ── QuerySet-ы ────────────────────────────────────────────────────────────────

def get_accessible_files(user):
    """QuerySet всех файлов доступных пользователю."""
    from files.models import File
    from django.db.models import Q

    if user.is_admin:
        return File.objects.filter(
            status=File.Status.ACTIVE
        ).select_related("owner", "folder")

    user_dept_ids = get_user_departments(user).values_list("id", flat=True)

    conditions = Q(owner=user)
    conditions |= Q(permissions__user=user)
    if user_dept_ids:
        conditions |= Q(
            folder__department_id__in=user_dept_ids,
            status=File.Status.ACTIVE,
        )

    return File.objects.filter(
        conditions, status=File.Status.ACTIVE,
    ).select_related("owner", "folder").distinct()


def get_accessible_folders(user, parent=None):
    """QuerySet папок доступных пользователю на данном уровне."""
    from files.models import Folder
    from django.db.models import Q

    if user.is_admin:
        return Folder.objects.filter(parent=parent).select_related("owner", "department")

    user_dept_ids = get_user_departments(user).values_list("id", flat=True)
    conditions = Q(owner=user) | Q(department_id__in=user_dept_ids)

    return Folder.objects.filter(
        conditions, parent=parent
    ).select_related("owner", "department").distinct()
