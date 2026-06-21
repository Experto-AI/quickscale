"""Enforce required organization ownership on CRM-owned models.

Phase F11.10b hard-stops when any NULL-owned Tag, Company, Contact, Stage, or
Deal rows remain.  No auto-backfill, no fresh-install heuristic — all five
models must have organization populated before this migration can apply.
Once the guard passes, the final owner contract is enforced on all five
models: organization is NOT NULL / non-blank and uses on_delete=PROTECT.
"""

import django.db.models.deletion
from django.db import migrations, models


OWNED_MODEL_NAMES = ("Tag", "Company", "Contact", "Stage", "Deal")


def assert_no_null_owned_rows(apps, schema_editor):
    del schema_editor

    null_owned_counts: list[str] = []

    for model_name in OWNED_MODEL_NAMES:
        model = apps.get_model("quickscale_modules_crm", model_name)
        null_owned_count = model._base_manager.filter(organization__isnull=True).count()
        if null_owned_count:
            null_owned_counts.append(f"{model_name}={null_owned_count}")

    if not null_owned_counts:
        return

    raise RuntimeError(
        "Migration 0006 cannot continue while NULL-owned CRM rows remain: "
        + ", ".join(null_owned_counts)
        + ". Backfill organization ownership for these rows before applying "
        "the F11.10b schema flip."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0005_tag_owner_bucket_unique"),
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=assert_no_null_owned_rows,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="tag",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_tags",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="company",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_companies",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="contact",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_contacts",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="stage",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_stages",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="deal",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="crm_deals",
                to="quickscale_modules_orgs.organization",
            ),
        ),
    ]
