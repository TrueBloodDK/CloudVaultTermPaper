"""Административный интерфейс для файлов и папок."""

from django.contrib import admin
from .models import File, Folder, FilePermission


class FilePermissionInline(admin.TabularInline):
    model = FilePermission
    extra = 1
    fields = ["user", "access", "granted_by", "granted_at"]
    readonly_fields = ["granted_at"]


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "department", "parent", "created_at"]
    list_filter = ["department"]
    search_fields = ["name", "owner__email"]
    list_select_related = ["owner", "department", "parent"]


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "owner", "folder", "mime_type", "size_kb", "status", "created_at"]
    list_filter = ["status", "mime_type"]
    search_fields = ["original_name", "owner__email"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    list_select_related = ["owner", "folder"]
    inlines = [FilePermissionInline]

    fieldsets = (
        ("Основное", {"fields": ("original_name", "owner", "folder", "description")}),
        ("Технические данные", {
            "fields": ("encrypted_file", "mime_type", "size", "checksum"),
            "classes": ("collapse",),
        }),
        ("Статус", {"fields": ("status", "created_at", "updated_at")}),
    )


@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ["file", "user", "access", "granted_by", "granted_at"]
    list_filter = ["access"]
    search_fields = ["file__original_name", "user__email"]
