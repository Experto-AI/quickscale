"""Migration to alter the CustomUser model Meta options."""
from django.db import migrations


class Migration(migrations.Migration):
    """Change CustomUser verbose_name and verbose_name_plural."""

    dependencies = [
        ('users', '0002_extend_user_profile'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customuser',
            options={'verbose_name': 'User', 'verbose_name_plural': 'Users'},
        ),
    ] 