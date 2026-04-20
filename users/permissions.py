"""Кастомные классы прав доступа (RBAC)."""

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Только администратор."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsManagerOrAdmin(BasePermission):
    """Менеджер или администратор."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_manager


class IsOwnerOrAdmin(BasePermission):
    """Владелец объекта или администратор."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        # Объект должен иметь поле owner
        return getattr(obj, "owner", None) == request.user
