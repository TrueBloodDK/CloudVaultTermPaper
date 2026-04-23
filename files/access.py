"""
Централизованная логика проверки доступа к файлам.

Три уровня (проверяются по порядку):
  1. Владелец файла или администратор → всегда есть доступ
  2. Явная запись FilePermission для пользователя → есть доступ
  3. Отдел пользователя входит в разрешённые для категории файла → есть доступ
"""

from audit.models import AuditLog
from audit.utils import log_action


def can_access_file(user, file_obj, request=None):
    """
    Проверяет есть ли у пользователя доступ к файлу.

    Args:
        user:     объект пользователя
        file_obj: объект File
        request:  HTTP-запрос (для записи в аудит, необязательно)

    Returns:
        True если доступ разрешён, False если запрещён
    """
    # 1. Владелец или администратор
    if user.is_admin or file_obj.owner == user:
        return True

    # 2. Явное персональное разрешение
    if file_obj.permissions.filter(user=user).exists():
        return True

    # 3. Доступ через категорию и отдел
    if file_obj.category_id and user.department_id:
        if file_obj.category.departments.filter(id=user.department_id).exists():
            return True

    # Доступ запрещён — пишем в аудит если есть запрос
    if request is not None:
        log_action(
            request,
            AuditLog.Action.ACCESS_DENIED,
            obj=file_obj,
            extra={"reason": "no_permission"},
        )

    return False


def get_accessible_files(user):
    """
    Возвращает QuerySet всех файлов доступных пользователю.
    """
    from files.models import File
    from django.db.models import Q

    if user.is_admin:
        return File.objects.filter(
            status=File.Status.ACTIVE
        ).select_related("owner", "category")

    conditions = Q(owner=user)
    conditions |= Q(permissions__user=user)

    if user.department_id:
        conditions |= Q(
            category__departments=user.department,
            status=File.Status.ACTIVE,
        )

    return File.objects.filter(
        conditions,
        status=File.Status.ACTIVE,
    ).select_related("owner", "category").distinct()
