from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_departmentmembership"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("system_admin", "Администратор системы"),
                    ("security_admin", "Администратор безопасности"),
                    ("user", "Пользователь"),
                    ("admin", "Администратор (устар.)"),
                    ("manager", "Менеджер (устар.)"),
                ],
                default="user",
                max_length=20,
                verbose_name="Роль",
            ),
        ),
    ]
