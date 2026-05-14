from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("login", "Вход в систему"),
                    ("logout", "Выход из системы"),
                    ("login_failed", "Неудачная попытка входа"),
                    ("file_upload", "Загрузка файла"),
                    ("file_download", "Скачивание файла"),
                    ("file_delete", "Удаление файла"),
                    ("file_view", "Просмотр файла"),
                    ("user_create", "Создание пользователя"),
                    ("user_update", "Изменение пользователя"),
                    ("permission_grant", "Выдача права доступа"),
                    ("permission_revoke", "Отзыв права доступа"),
                    ("role_change", "Изменение роли"),
                    ("department_assign", "Назначение в отдел"),
                    ("access_denied", "Отказ в доступе"),
                ],
                max_length=30,
                verbose_name="Действие",
            ),
        ),
    ]
