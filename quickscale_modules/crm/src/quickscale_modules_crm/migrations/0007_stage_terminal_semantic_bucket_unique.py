"""Replace Stage.terminal_semantic unique=True with owner-bucket uniqueness.

Phase F11-deferred: removes the field-level unique=True on
Stage.terminal_semantic and replaces it with two partial UniqueConstraints
that together implement per-org owner-bucket uniqueness:
  - NULL-owned bucket: unique on (terminal_semantic,) where organization IS NULL
  - Org-owned bucket: unique on (terminal_semantic, organization) where
    organization IS NOT NULL

Post-0006, all Stage rows have organization set (NOT NULL, PROTECT), so the
NULL-owned bucket is a complete safety net rather than an active path. The
partial-index approach is portable across SQLite (test) and PostgreSQL
(production).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0006_enforce_required_organization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stage",
            name="terminal_semantic",
            field=models.CharField(
                blank=True,
                choices=[("won", "Won"), ("lost", "Lost")],
                editable=False,
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                fields=("terminal_semantic",),
                name="crm_stage_terminal_semantic_unique_null_org",
                condition=models.Q(organization__isnull=True),
            ),
        ),
        migrations.AddConstraint(
            model_name="stage",
            constraint=models.UniqueConstraint(
                fields=("terminal_semantic", "organization"),
                name="crm_stage_terminal_semantic_organization_unique",
                condition=models.Q(organization__isnull=False),
            ),
        ),
    ]
