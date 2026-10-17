"""Management command to seed built-in form presets"""

from typing import Any

from django.core.management.base import BaseCommand

from quickscale_modules_forms.management.commands._presets import seed_form_presets


class Command(BaseCommand):
    """Seeds ready-to-use form presets: contact, newsletter, feedback, support"""

    help = "Seed built-in form presets (contact, newsletter, feedback, support)"

    def handle(self, *args: Any, **options: Any) -> None:
        for slug, created in seed_form_presets():
            if created:
                self.stdout.write(f"  Created: {slug}")
            else:
                self.stdout.write(f"  Already exists: {slug}")

        self.stdout.write(self.style.SUCCESS("Form presets seeded successfully."))
