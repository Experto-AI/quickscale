"""Seed initial forms migration."""

from django.db import migrations
from django.core.management import call_command


def seed_forms(apps, schema_editor):
    try:
        call_command("forms_seed_presets")
    except Exception:
        # In testing or unexpected environments where command doesn't exist, fail gracefully
        pass


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_forms", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_forms, reverse_code=reverse_seed),
    ]
