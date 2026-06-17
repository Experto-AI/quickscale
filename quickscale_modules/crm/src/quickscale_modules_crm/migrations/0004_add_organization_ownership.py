"""Add nullable organization ownership to CRM-owned models.

Phase 2 of F11.1d: adds a nullable FK to Organization on Tag, Company,
Contact, Stage, and Deal.  ContactNote and DealNote remain parent-derived.
All fields are additive-only with no data mutation.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_crm", "0003_stage_terminal_semantic_unique"),
        ("quickscale_modules_orgs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_tags",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_companies",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_contacts",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="stage",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_stages",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="deal",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_deals",
                to="quickscale_modules_orgs.organization",
            ),
        ),
    ]
