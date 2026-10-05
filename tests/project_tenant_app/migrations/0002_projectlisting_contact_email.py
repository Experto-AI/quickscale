"""Add the personal-data candidate field the W006 control walks."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("project_tenant_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectlisting",
            name="contact_email",
            field=models.EmailField(blank=True, default=""),
        ),
    ]
