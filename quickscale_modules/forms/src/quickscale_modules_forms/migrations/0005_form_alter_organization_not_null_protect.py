"""Make Form.organization NOT NULL with PROTECT.

T1.7: adopt the shared NOT NULL/PROTECT ownership contract (D3/D5).
Existing rows from 0002_seed_forms are assigned to the System org.
"""

from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def assign_system_org(apps: Any, schema_editor: Any) -> None:
    """Assign any existing forms without an org to the System org.

    Creates the System org row if it does not yet exist (fresh install).
    Depends on orgs 0003 so that ``is_system`` is available on the
    historical Organization model.
    """
    Form = apps.get_model("quickscale_modules_forms", "Form")
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")

    try:
        system_org = Organization.objects.get(is_system=True, slug="__system__")
    except Organization.DoesNotExist:
        system_org = Organization.objects.create(
            name="System",
            slug="__system__",
            is_system=True,
            is_personal=False,
        )
    Form.objects.filter(organization__isnull=True).update(organization=system_org)


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_forms", "0004_form_organization_alter_form_slug_and_more"),
        ("quickscale_modules_orgs", "0003_alter_organization_is_system"),
    ]

    operations = [
        migrations.RunPython(assign_system_org, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="form",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="forms",
                to="quickscale_modules_orgs.organization",
            ),
        ),
    ]
