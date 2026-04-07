"""Align form retention defaults with the settings-backed runtime default."""

import quickscale_modules_forms.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_forms", "0002_seed_forms"),
    ]

    operations = [
        migrations.AlterField(
            model_name="form",
            name="data_retention_days",
            field=models.PositiveIntegerField(
                default=quickscale_modules_forms.models.get_default_form_data_retention_days,
                help_text="Submissions older than this many days are eligible for anonymization.",
            ),
        ),
    ]
