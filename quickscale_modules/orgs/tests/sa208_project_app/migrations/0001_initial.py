"""Initial schema and FORCE-RLS policy for the SA208 project fixture."""

from __future__ import annotations

from typing import Any

import django.db.models.deletion
import django.db.models.manager
from django.db import migrations, models

from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls

PROVIDER_RECORD_TABLE = "sa208_project_app_projectproviderrecord"
PROVIDER_RECORD_RLS_POLICY = "sa208_provider_record_org_isolation"
_PROVIDER_RECORD_RLS_TARGETS = ((PROVIDER_RECORD_TABLE, PROVIDER_RECORD_RLS_POLICY),)


def _forward_rls(apps: Any, schema_editor: Any) -> None:
    """Install the fixture's migration-owned FORCE-RLS policy."""
    del apps
    revert_force_rls(schema_editor, _PROVIDER_RECORD_RLS_TARGETS)
    apply_force_rls(schema_editor, _PROVIDER_RECORD_RLS_TARGETS)


def _reverse_rls(apps: Any, schema_editor: Any) -> None:
    """Remove the fixture's FORCE-RLS policy when reversing the migration."""
    del apps
    revert_force_rls(schema_editor, _PROVIDER_RECORD_RLS_TARGETS)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("quickscale_orgs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectProviderRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("mls_id", models.CharField(blank=True, default="", max_length=64)),
                (
                    "local_ref_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="quickscale_orgs.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project provider record",
                "verbose_name_plural": "Project provider records",
                "base_manager_name": "all_objects",
            },
            managers=[
                ("objects", django.db.models.manager.Manager()),
                ("all_objects", django.db.models.manager.Manager()),
            ],
        ),
        migrations.RunPython(
            code=_forward_rls,
            reverse_code=_reverse_rls,
            hints={"target_db": "default"},
        ),
    ]
