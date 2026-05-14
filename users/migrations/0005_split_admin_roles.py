from django.db import migrations, models


def migrate_legacy_roles(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(role="admin").update(role="system_admin")
    User.objects.filter(role="manager").update(role="user")


def restore_legacy_roles(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(role="system_admin").update(role="admin")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_update_rbac_roles"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_roles, restore_legacy_roles),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("system_admin", "Администратор системы"),
                    ("security_admin", "Администратор безопасности"),
                    ("user", "Пользователь"),
                ],
                default="user",
                max_length=20,
                verbose_name="Роль",
            ),
        ),
    ]
