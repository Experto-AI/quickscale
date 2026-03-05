from django.contrib.auth.models import UserManager
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_auth", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", UserManager()),
            ],
        ),
    ]
