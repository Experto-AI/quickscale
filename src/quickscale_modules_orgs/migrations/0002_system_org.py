"""Add is_system field and unique constraint for the System org singleton."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the reserved System organization and its partial unique constraint."""

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="is_system",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_system", True)),
                fields=("is_system",),
                name="unique_system_org",
            ),
        ),
    ]
