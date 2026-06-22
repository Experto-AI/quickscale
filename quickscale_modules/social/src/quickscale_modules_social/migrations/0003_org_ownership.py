"""Add organization FK and remove global normalized_url uniqueness.

Phase F11.13a: tenant isolation for the social module.

- Adds nullable ``organization`` FK to both ``SocialLink`` and ``SocialEmbed``.
- Removes the global ``unique=True`` constraint on ``normalized_url`` since
  multiple organizations may link to the same social URL.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Add org ownership fields and relax normalized_url uniqueness."""

    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        ("quickscale_modules_social", "0002_socialembed_resolution_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="sociallink",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="quickscale_modules_orgs.organization",
                related_name="%(app_label)s_%(class)s_set",
            ),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="quickscale_modules_orgs.organization",
                related_name="%(app_label)s_%(class)s_set",
            ),
        ),
        migrations.AlterField(
            model_name="sociallink",
            name="normalized_url",
            field=models.URLField(
                blank=True,
                editable=False,
                max_length=500,
            ),
        ),
        migrations.AlterField(
            model_name="socialembed",
            name="normalized_url",
            field=models.URLField(
                blank=True,
                editable=False,
                max_length=500,
            ),
        ),
    ]
