"""
Централизованная логика проверки доступа к файлам и папкам.

Уровни проверки:
  1. Администратор системы       → полный доступ к файловой структуре
  2. Владелец файла/папки        → полный доступ к своим объектам
  3. Явный FilePermission        → доступ к конкретному файлу
  4. Руководитель отдела (head)  → все файлы отдела, удаление, расшаривание
  5. Рядовой сотрудник (member)  → просмотр, скачивание, загрузка;
                                   удаление только своих файлов
"""

from audit.models import AuditLog
from audit.utils import log_action
from users.rbac import PermissionAction, PermissionEffect


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


def get_user_membership_pairs(user):
    """Список пар (department_id, role) для проверки role-specific прав."""
    return list(
        user.memberships.values_list("department_id", "role")
    )


def get_action_scope(action):
    """
    Действия, которые покрывают запрошенную операцию.
    Например, manage покрывает любое управление папкой.
    """
    scopes = {
        PermissionAction.VIEW: [
            PermissionAction.VIEW,
            PermissionAction.READ,
            PermissionAction.MANAGE,
        ],
        PermissionAction.READ: [PermissionAction.READ, PermissionAction.MANAGE],
        PermissionAction.DOWNLOAD: [
            PermissionAction.DOWNLOAD,
            PermissionAction.READ,
            PermissionAction.MANAGE,
        ],
        PermissionAction.UPLOAD: [PermissionAction.UPLOAD, PermissionAction.MANAGE],
        PermissionAction.CREATE: [PermissionAction.CREATE, PermissionAction.MANAGE],
        PermissionAction.UPDATE: [PermissionAction.UPDATE, PermissionAction.MANAGE],
        PermissionAction.DELETE: [PermissionAction.DELETE, PermissionAction.MANAGE],
        PermissionAction.SHARE: [PermissionAction.SHARE, PermissionAction.MANAGE],
        PermissionAction.AUDIT: [PermissionAction.AUDIT, PermissionAction.MANAGE],
        PermissionAction.MANAGE: [PermissionAction.MANAGE],
    }
    return scopes.get(action, [action])


def permission_applies_to_user(permission, user):
    """Проверяет, относится ли объект разрешения к пользователю."""
    if permission.user_id:
        return permission.user_id == user.id
    if not permission.department_id:
        return False

    membership = get_membership(user, permission.department)
    if membership is None:
        return False
    if permission.department_role:
        return membership.role == permission.department_role
    return True


def permission_q_for_user(user, effect, actions, prefix="permissions"):
    """Q-условие для разрешений папки/файла, подходящих пользователю."""
    from django.db.models import Q

    user_dept_ids = list(get_user_departments(user).values_list("id", flat=True))
    conditions = Q(**{
        f"{prefix}__user": user,
        f"{prefix}__effect": effect,
        f"{prefix}__access__in": actions,
    })

    if user_dept_ids:
        conditions |= Q(**{
            f"{prefix}__department_id__in": user_dept_ids,
            f"{prefix}__department_role": "",
            f"{prefix}__effect": effect,
            f"{prefix}__access__in": actions,
        })

    role_conditions = Q()
    for department_id, role in get_user_membership_pairs(user):
        role_conditions |= Q(**{
            f"{prefix}__department_id": department_id,
            f"{prefix}__department_role": role,
            f"{prefix}__effect": effect,
            f"{prefix}__access__in": actions,
        })
    return conditions | role_conditions


def has_direct_permission(permission_manager, user, action):
    """
    Проверяет прямые права на конкретный объект.
    Deny сильнее allow, но системный админ и владелец обрабатываются выше.
    """
    actions = get_action_scope(action)
    applicable = [
        p for p in permission_manager.select_related("user", "department").filter(
            access__in=actions
        )
        if permission_applies_to_user(p, user)
    ]
    if any(p.effect == PermissionEffect.DENY for p in applicable):
        return False
    if any(p.effect == PermissionEffect.ALLOW for p in applicable):
        return True
    return None


# ── Проверки доступа ──────────────────────────────────────────────────────────

def can_access_folder(user, folder, action=PermissionAction.VIEW):
    """Может ли пользователь выполнить действие над папкой."""
    if user.is_system_admin or folder.owner == user:
        return True

    direct = has_direct_permission(folder.permissions, user, action)
    if direct is not None:
        return direct

    if folder.department_id:
        if action in (
            PermissionAction.VIEW,
            PermissionAction.READ,
            PermissionAction.UPLOAD,
            PermissionAction.CREATE,
        ):
            return is_dept_member(user, folder.department)
        if action in (
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.SHARE,
            PermissionAction.MANAGE,
            PermissionAction.AUDIT,
        ):
            return is_dept_head(user, folder.department)
    return False

def can_access_file(user, file_obj, request=None):
    """Может ли пользователь просматривать/скачивать файл."""
    if user.is_system_admin or file_obj.owner == user:
        return True

    direct = has_direct_permission(file_obj.permissions, user, PermissionAction.DOWNLOAD)
    if direct is not None:
        return direct

    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_member(user, file_obj.folder.department):
            return True
    if request is not None:
        log_action(request, AuditLog.Action.ACCESS_DENIED, obj=file_obj,
                   extra={"reason": "no_permission"})
    return False


def can_delete_file(user, file_obj):
    """Системный админ и руководитель отдела — любой файл. Рядовой — только свои."""
    if user.is_system_admin or file_obj.owner == user:
        return True
    if file_obj.folder and file_obj.folder.department_id:
        if is_dept_head(user, file_obj.folder.department):
            return True
    return False


def can_share_file(user, file_obj):
    """Расшаривать могут только системный админ и руководитель отдела."""
    if user.is_system_admin:
        return True
    if file_obj.folder and file_obj.folder.department_id:
        return is_dept_head(user, file_obj.folder.department)
    return file_obj.owner == user


def can_upload_to_folder(user, folder):
    """Загружать в папку могут системный админ, владелец и любой член отдела."""
    return can_access_folder(user, folder, PermissionAction.UPLOAD)


def can_manage_folder(user, folder):
    """Управлять папкой могут системный админ, владелец и руководитель."""
    return can_access_folder(user, folder, PermissionAction.MANAGE)


# ── QuerySet-ы ────────────────────────────────────────────────────────────────

def get_accessible_files(user):
    """QuerySet всех файлов доступных пользователю."""
    from files.models import File
    from django.db.models import Q

    if user.is_system_admin:
        return File.objects.filter(
            status=File.Status.ACTIVE
        ).select_related("owner", "folder")

    user_dept_ids = get_user_departments(user).values_list("id", flat=True)

    file_actions = get_action_scope(PermissionAction.DOWNLOAD)

    conditions = Q(owner=user)
    conditions |= permission_q_for_user(
        user,
        PermissionEffect.ALLOW,
        file_actions,
    )
    if user_dept_ids:
        conditions |= Q(
            folder__department_id__in=user_dept_ids,
            status=File.Status.ACTIVE,
        )

    deny_conditions = permission_q_for_user(
        user,
        PermissionEffect.DENY,
        file_actions,
    )

    return File.objects.filter(
        conditions, status=File.Status.ACTIVE,
    ).exclude(
        ~Q(owner=user),
        deny_conditions,
    ).select_related("owner", "folder").distinct()


def get_accessible_folders(user, parent=None):
    """QuerySet папок доступных пользователю на данном уровне."""
    from files.models import Folder
    from django.db.models import Q

    if user.is_system_admin:
        return Folder.objects.filter(parent=parent).select_related("owner", "department")

    user_dept_ids = get_user_departments(user).values_list("id", flat=True)
    folder_actions = get_action_scope(PermissionAction.VIEW)
    conditions = Q(owner=user) | Q(department_id__in=user_dept_ids)
    conditions |= permission_q_for_user(
        user,
        PermissionEffect.ALLOW,
        folder_actions,
    )

    deny_conditions = permission_q_for_user(
        user,
        PermissionEffect.DENY,
        folder_actions,
    )

    return Folder.objects.filter(
        conditions, parent=parent
    ).exclude(
        ~Q(owner=user),
        deny_conditions,
    ).select_related("owner", "department").distinct()
