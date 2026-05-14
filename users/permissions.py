"""Кастомные классы прав доступа (RBAC)."""

from rest_framework.permissions import BasePermission


class IsSystemAdmin(BasePermission):
    """Только администратор системы."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_system_admin


class IsSecurityAdmin(BasePermission):
    """Только администратор безопасности."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_security_admin


class IsPrivilegedAdmin(BasePermission):
    """Администратор системы или администратор безопасности."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_privileged_admin


class IsAdmin(IsSystemAdmin):
    """Совместимый alias для старых импортов системного администратора."""
    pass


class IsManagerOrAdmin(BasePermission):
    """Устаревший alias: менеджеры будут заменены ролями внутри отделов."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_manager


class IsOwnerOrAdmin(BasePermission):
    """Владелец объекта или администратор."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_system_admin:
            return True
        # Объект должен иметь поле owner
        return getattr(obj, "owner", None) == request.user
