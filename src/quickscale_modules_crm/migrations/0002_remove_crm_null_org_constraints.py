"""Remove the dead NULL-organization partial unique constraints.

``TenantModel.organization`` is NOT NULL, so neither null-owner bucket could
ever hold a row.  The organization-scoped constraints on the same fields
remain.
"""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_crm", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="stage",
            name="quickscale_crm_stage_terminal_semantic_null_unique",
        ),
        migrations.RemoveConstraint(
            model_name="tag",
            name="quickscale_crm_tag_name_null_unique",
        ),
    ]
