"""Seed initial forms migration."""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import migrations


def seed_forms(apps, schema_editor):
    try:
        call_command("forms_seed_presets")
    except (CommandError, SystemExit):
        # Tolerate missing or no-op preset command in test/minimal environments
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
