"""Replace Tag.name unique=True with owner-bucket uniqueness.

Phase 11.1d.1 (Tag-first slice): removes the field-level unique=True on
Tag.name and replaces it with two partial UniqueConstraints that together
implement owner-bucket uniqueness:
  - NULL-owned bucket: unique on (name,) where organization IS NULL
  - Org-owned bucket: unique on (name, organization) where organization IS NOT NULL

This preserves legacy NULL-owned duplicate blocking while allowing
same-name tags across different orgs and NULL-owned + org-owned coexistence.
The partial-index approach is portable across SQLite (test) and PostgreSQL
(production).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0004_add_organization_ownership"),
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tag",
            name="name",
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=("name",),
                name="crm_tag_name_unique_null_org",
                condition=models.Q(organization__isnull=True),
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=("name", "organization"),
                name="crm_tag_name_organization_unique",
                condition=models.Q(organization__isnull=False),
            ),
        ),
    ]
