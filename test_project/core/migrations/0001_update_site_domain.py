"""Custom site domain migration to avoid duplication errors.

This migration uses update_or_create instead of create to prevent
unique constraint violations when the site with ID=1 already exists.
"""
from django.db import migrations


def update_site_forward(apps, schema_editor):
    """Update the default site or create it if it doesn't exist."""
    Site = apps.get_model('sites', 'Site')
    # Use update_or_create to handle cases where the site already exists
    Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': 'example.com',
            'name': 'example.com'
        }
    )


def update_site_backward(apps, schema_editor):
    """Backward migration - no action needed."""
    pass


class Migration(migrations.Migration):
    """Migration to update site domain safely."""

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_site_forward, update_site_backward),
    ] 