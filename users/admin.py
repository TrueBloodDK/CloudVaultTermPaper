from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "user_count", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]
    readonly_fields = ["created_at", "user_count"]

    def user_count(self, obj):
        count = obj.users.count()
        return format_html(
            '<span style="font-weight:600">{}</span> сотр.', count
        )
    user_count.short_description = "Сотрудников"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email", "full_name", "role_badge", "department",
        "is_active", "date_joined"
    ]
    list_filter = ["role", "is_active", "department"]
    search_fields = ["email", "full_name"]
    ordering = ["full_name"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("full_name",)}),
        ("Организация", {"fields": ("role", "department")}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Служебная информация", {
            "fields": ("date_joined", "last_login", "last_login_ip"),
            "classes": ("collapse",),
        }),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "department", "password1", "password2"),
        }),
    )
    readonly_fields = ["date_joined", "last_login", "last_login_ip"]

    def role_badge(self, obj):
        colors = {
            "admin":   ("#f55f5f", "#2d0a0a"),
            "manager": ("#f5c842", "#2d2500"),
            "user":    ("#4f9eff", "#051a33"),
        }
        bg, fg = colors.get(obj.role, ("#888", "#fff"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600">{}</span>',
            bg, fg, obj.get_role_display()
        )
    role_badge.short_description = "Роль"
