"""Make is_system non-nullable to enforce the NOT NULL ownership contract.

This completes the System-org singleton invariants (T1.1):
- is_system must not be NULL at the database level.
- The partial unique constraint (0002) already ensures at most one True row.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Make Organization.is_system NOT NULL."""

    dependencies = [
        ("quickscale_modules_orgs", "0002_system_org"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organization",
            name="is_system",
            field=models.BooleanField(default=False),
        ),
    ]
