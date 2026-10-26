"""Add a debit reference and its per-organization uniqueness constraint."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_billing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="credittransaction",
            name="reference",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="credittransaction",
            constraint=models.UniqueConstraint(
                condition=~models.Q(reference=""),
                fields=("organization", "reference", "transaction_type"),
                name="quickscale_billing_credittransaction_reference_unique",
            ),
        ),
    ]
