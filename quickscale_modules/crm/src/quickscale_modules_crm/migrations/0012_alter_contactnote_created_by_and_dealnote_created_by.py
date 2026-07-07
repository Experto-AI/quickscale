"""SA35: Change ContactNote.created_by and DealNote.created_by on_delete to SET_NULL

Account deletion no longer cascade-destroys CRM notes written by the
deleted user.  Both fields gain null=True, blank=True — the display code
already tolerates None for created_by.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "quickscale_modules_crm",
            "0011_alter_company_options_alter_contact_options_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="contactnote",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="dealnote",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
