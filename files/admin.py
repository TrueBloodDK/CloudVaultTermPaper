from django.contrib import admin
from django.utils.html import format_html
from .models import File, FilePermission, FileCategory


@admin.register(FileCategory)
class FileCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "department_list", "file_count", "created_at"]
    filter_horizontal = ["departments"]   # удобный виджет выбора отделов
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "file_count"]

    def file_count(self, obj):
        return obj.files.filter(status="active").count()
    file_count.short_description = "Файлов"

    def department_list(self, obj):
        depts = obj.departments.all()
        if not depts:
            return format_html('<span style="color:#888">—</span>')
        badges = "".join(
            f'<span style="background:#1a2a3a;color:#4f9eff;padding:1px 7px;'
            f'border-radius:10px;font-size:11px;margin-right:4px">{d.name}</span>'
            for d in depts
        )
        return format_html(badges)
    department_list.short_description = "Отделы"


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = [
        "original_name", "owner", "category",
        "mime_type", "size_kb", "status", "created_at"
    ]
    list_filter = ["status", "mime_type", "category"]
    search_fields = ["original_name", "owner__email"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["-created_at"]
    raw_id_fields = ["owner"]

    fieldsets = (
        ("Файл", {"fields": ("id", "original_name", "encrypted_file", "mime_type")}),
        ("Метаданные", {"fields": ("owner", "category", "description", "size", "checksum")}),
        ("Статус", {"fields": ("status", "created_at", "updated_at")}),
    )


@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ["file", "user", "access", "granted_by", "granted_at"]
    list_filter = ["access"]
    search_fields = ["file__original_name", "user__email"]
    raw_id_fields = ["file", "user", "granted_by"]
