"""
Централизованная логика проверки доступа к файлам и папкам.

Пять уровней проверки (по порядку):

  1. Глобальный admin                → полный доступ ко всему
  2. Явный FilePermission            → доступ к конкретному файлу
  3. Руководитель отдела (head)      → полный доступ к файлам своего отдела,
                                       может удалять и расшаривать
  4. Рядовой сотрудник (member)      → просмотр, скачивание, загрузка новых,
                                       удаление только своих файлов
  5. Всё остальное                   → доступ запрещён
"""

from django.db.models import Q
from audit.models import AuditLog
from audit.utils import log_action


# ── Вспомогательные функции ───────────────────────────────────────────────────

def get_membership(user, department):
    """
    Возвращает DepartmentMembership или None.
    Кешируем в атрибуте объекта чтобы не делать лишних запросов.
    """
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
    """Является ли пользователь руководителем данного отдела."""
    m = get_membership(user, department)
    return m is not None and m.is_head


def is_dept_member(user, department):
    """Является ли пользователь членом данного отдела (любая роль)."""
    m = get_membership(user, department)
    return m is not None


def get_user_departments(user):
    """Возвращает QuerySet всех отделов пользователя."""
    from users.models import Department
    return Department.objects.filter(memberships__user=user)


# ── Проверка доступа к файлу ──────────────────────────────────────────────────

def can_access_file(user, file_obj, request=None):
    """
    Может ли пользователь просматривать/скачивать файл.
    """
    # 1. Глобальный admin
    if user.is_admin:
        return True

    # 2. Владелец файла
    if file_obj.owner == user:
        return True

    # 3. Явное разрешение (FilePermission)
    if file_obj.permissions.filter(user=user).exists():
        return True

    # 4. Доступ через категорию отдела (старый механизм — оставляем)
    if file_obj.category_id and user.department_id:
        if file_obj.category.departments.filter(id=user.department_id).exists():
            return True

    # 5. Членство в отделе папки файла
    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_member(user, file_obj.folder.department):
            return True

    if request is not None:
        log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj,
                   extra={"reason": "no_permission"})
    return False


def can_delete_file(user, file_obj):
    """
    Может ли пользователь удалить файл.

    - admin → всегда да
    - руководитель отдела → да для любого файла отдела
    - рядовой сотрудник → только свои файлы
    """
    if user.is_admin:
        return True
    if file_obj.owner == user:
        return True
    # Руководитель отдела папки
    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_head(user, file_obj.folder.department):
            return True
    return False


def can_share_file(user, file_obj):
    """
    Может ли пользователь расшаривать файл другим отделам.

    - admin → всегда да
    - руководитель отдела → да для файлов своего отдела
    - рядовой сотрудник → нет
    """
    if user.is_admin:
        return True
    if file_obj.owner == user:
        # Владелец-руководитель может расшаривать
        if file_obj.folder and file_obj.folder.department_id:
            return is_dept_head(user, file_obj.folder.department)
        # Файл без папки — только владелец-руководитель своего отдела
        if user.department_id:
            return is_dept_head(user, user.department)
    return False


def can_upload_to_folder(user, folder):
    """
    Может ли пользователь загружать файлы в папку.

    - admin → всегда да
    - руководитель или рядовой сотрудник отдела → да
    - владелец папки → да
    """
    if user.is_admin:
        return True
    if folder.owner == user:
        return True
    if folder.department_id:
        return is_dept_member(user, folder.department)
    return False


def can_manage_folder(user, folder):
    """
    Может ли пользователь создавать/удалять/переименовывать папку.

    - admin → всегда да
    - руководитель отдела → да для папок своего отдела
    - владелец папки → да для своих личных папок
    """
    if user.is_admin:
        return True
    if folder.owner == user:
        return True
    if folder.department_id:
        return is_dept_head(user, folder.department)
    return False


# ── QuerySet доступных файлов ─────────────────────────────────────────────────

def get_accessible_files(user):
    """
    Возвращает QuerySet всех файлов доступных пользователю.
    Учитывает все уровни RBAC.
    """
    from files.models import File

    if user.is_admin:
        return File.objects.filter(
            status=File.Status.ACTIVE
        ).select_related("owner", "category", "folder")

    # Собираем условия через Q
    conditions = Q(owner=user)

    # Явные разрешения
    conditions |= Q(permissions__user=user)

    # Доступ через категорию и отдел пользователя (старый механизм)
    if user.department_id:
        conditions |= Q(
            category__departments=user.department,
            status=File.Status.ACTIVE,
        )

    # Доступ через членство в отделе папки
    user_dept_ids = get_user_departments(user).values_list("id", flat=True)
    if user_dept_ids:
        conditions |= Q(
            folder__department_id__in=user_dept_ids,
            status=File.Status.ACTIVE,
        )

    return File.objects.filter(
        conditions,
        status=File.Status.ACTIVE,
    ).select_related("owner", "category", "folder").distinct()


def get_accessible_folders(user, parent=None):
    """
    Возвращает QuerySet папок доступных пользователю на данном уровне.
    """
    from files.models import Folder

    if user.is_admin:
        return Folder.objects.filter(parent=parent).select_related("owner", "department")

    user_dept_ids = get_user_departments(user).values_list("id", flat=True)

    conditions = Q(owner=user) | Q(department_id__in=user_dept_ids)

    return Folder.objects.filter(
        conditions, parent=parent
    ).select_related("owner", "department").distinct()
