from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "full_name", "role", "department", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "department"]
    search_fields = ["email", "full_name"]
    ordering = ["full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("full_name", "department")}),
        ("Роль и права", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Служебная информация", {"fields": ("date_joined", "last_login", "last_login_ip")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "password1", "password2"),
        }),
    )
    readonly_fields = ["date_joined", "last_login", "last_login_ip"]
